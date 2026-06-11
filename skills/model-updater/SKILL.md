---
name: model-updater
type: capability
description: >
  (Placeholder — not yet implemented; excluded from the registry and plugins via
  EXCLUDED_SKILLS.) Update a maintained financial model — a Google Sheet or a model
  file on disk — with newly reported actuals: normalize the new period using the
  analyst-playbook's sector rules, diff against the model's assumptions, patch the
  affected cells/series, and append a changelog entry. Triggers: "update the model
  for X", "refresh the financial model with Q3 actuals", "push the new quarter into
  the sheet".
---

# Model updater — placeholder

Not implemented yet. Intended design: one **update contract** (load → normalize →
diff → patch → changelog) with two adapters behind it — a file adapter (model file +
rendered artifact on disk) first, then a Google Sheets adapter (service-account auth
via env).

Until this ships, the analyst-playbook's deliverable triage applies: when an
engagement is a model update, write the normalized series and assumptions to
clearly-named files and state in the output that the model-update step was delivered
as files.
