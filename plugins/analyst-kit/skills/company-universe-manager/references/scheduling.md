# Scheduling the daily monitor + report

The daily run has two parts: a cheap, deterministic **monitor** (Python, fetches
dates and diffs — no LLM) and an LLM **report** step (news synthesis + PDF).

## Primary: harness cron (in-session)

The agent registers a recurring job with `CronCreate`:

```
CronCreate({
  cron: "13 7 * * *",          // 07:13 local — avoid round :00 marks
  durable: true,                // survive Claude restarts
  recurring: true,
  prompt: "Run the company-universe-manager daily routine: monitor key dates, gather news, build and render the daily report, then summarize what changed."
})
```

On fire, the agent runs the pipeline (see SKILL.md): `monitor_dates.py` →
`fetch_news.py` → `build_report.py` → hand the contract to
`reporting/scripts/render.ts` → summarize `changes/<today>.json` → mirror to the
remote backend if `config.backend == "remote"`.

### Caveats (important — tell the user)

- **Session-bound.** Harness cron only fires while a Claude REPL is **open and
  idle**. It will **not** run overnight with Claude closed.
- **7-day expiry.** Recurring jobs auto-expire after 7 days (they fire one last
  time, then delete). Re-arm weekly, or use launchd below for indefinite runs.
- Manage jobs with `CronList` / `CronDelete`.

## Unattended upgrade: macOS launchd (optional)

For a daily run that fires even when no Claude session is open, schedule a
headless invocation with `launchd`. Create
`~/Library/LaunchAgents/com.company-universe.daily.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.company-universe.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string><string>-lc</string>
    <string>claude -p "Run the company-universe-manager daily routine"</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>13</integer></dict>
  <key>StandardOutPath</key><string>/tmp/company-universe-daily.log</string>
  <key>StandardErrorPath</key><string>/tmp/company-universe-daily.err</string>
</dict></plist>
```

Load it: `launchctl load ~/Library/LaunchAgents/com.company-universe.daily.plist`.

Caveats: the machine must be awake at the scheduled time; each run consumes
credits (a full headless Claude turn); the deterministic monitor alone can be run
without the LLM by invoking the Python scripts directly if you only want
change-detection without the narrative report.
