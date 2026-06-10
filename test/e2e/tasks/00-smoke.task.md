---
id: 00-smoke
timeoutMs: 600000
---
This is a pipeline smoke test. It must NOT use any external API, network data, or installed
skill — it only proves the container → Claude Code → html2pdf → PDF wiring works.

Create a single self-contained HTML file (for example `report.html` in the current working
directory) for a document titled **"E2E Smoke Test Report"**. It should contain:

- An `<h1>` with that title.
- One short paragraph stating this is an automated pipeline check.
- A small three-row table with two columns, "Check" and "Status", listing:
  "Container" → "ok", "Claude Code" → "ok", "PDF render" → "ok".

Use only inline HTML and CSS — no external scripts, fonts, images, or network requests.
Keep it to a single page.
