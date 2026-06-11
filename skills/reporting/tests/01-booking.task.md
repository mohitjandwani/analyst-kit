---
id: 01-booking
timeoutMs: 600000
---

Compare bookings vs revenue % growth YoY for Roblox (RBLX), quarterly, for the last
3 years. The final deliverable is a branded PDF written to `output/01-booking.pdf`,
produced by the reporting skill.

The storyline is **pre-decided** — upstream skills gather the data and build the
chart contract; the reporting skill only decides layout (report mode, portrait) and
renders:

1. **Page — "Do bookings lead revenue?"** A chart of bookings vs revenue YoY growth
   by quarter (charting skill, `yoy` pipeline). The page's `story` states the answer
   in one sentence; `stats` chips carry the latest quarter's YoY for both series.
2. **Page — "The underlying numbers."** A table of every quarter's bookings, revenue,
   and YoY values (`table-commentary`), with commentary calling out the quarters
   where the two series diverged, and the filing/exhibit each number came from in
   `source`.

Plus a cover page, and the auto-appended References page listing every filing and
data source — each data page cites into it via `sources`. Every data page must have
a `story`.
