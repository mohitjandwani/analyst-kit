# data-analysis skill

End-to-end data analysis for any structured dataset (CSV, JSON, Excel, SQL): profile and
clean data, run exploratory and statistical analysis, build visualizations, generate
reproducible code (Python / R / SQL / JS), write reports, and form testable hypotheses.

Adapted from the multi-agent project
[liangdabiao/claude-data-analysis](https://github.com/liangdabiao/claude-data-analysis).
Its six specialist sub-agents and slash commands are collapsed here into a single skill
with **specialist roles** and a **pipeline**. (The source project's hooks were dropped —
hooks don't run from a skill; they require a project-level `.claude/settings.json`.)

## Files
- `SKILL.md` — entry point: principle, roles, pipeline, request routing, layout, rules.
- `references/specialists.md` — full playbook per role (explorer, QA, viz, code, report,
  hypothesis), chart-selection guide, quality dimensions and thresholds.
- `references/templates.md` — Python/R/SQL code templates and report templates.

## Usage
Triggered automatically when the user asks to analyze, visualize, profile, clean, model,
or report on a dataset. Follow the pipeline in `SKILL.md`: Setup → Quality → Explore →
Visualize → Generate code → Report → Hypothesize, adopting the roles the task needs.

Default conventions: datasets in `data_storage/`; outputs in `visualizations/`,
`generated_code/`, `analysis_reports/`, `quality_reports/`, `hypothesis_reports/`.
