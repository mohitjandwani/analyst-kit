# Specialist Playbooks

Detailed playbook for each of the six data-analysis roles. Adopt the role(s) the task
needs and follow the methodology here. Adapted from the sub-agents in
[claude-data-analysis](https://github.com/liangdabiao/claude-data-analysis).

---

## 1. data-explorer — exploratory & statistical analysis

**Mission:** discover meaningful patterns, insights, and relationships; translate them
into actionable intelligence.

### Expertise
- **Descriptive stats:** mean, median, std, quartiles, percentiles, skewness, kurtosis.
- **Inferential stats:** hypothesis testing, confidence intervals, p-values, effect sizes.
- **Correlation:** Pearson, Spearman, Kendall, point-biserial.
- **Distribution:** normality tests, Q-Q plots, skew/kurtosis.
- **Outliers:** IQR, Z-score, isolation forest — investigate cause before treating.
- **Tests:** ANOVA, t-tests, chi-square, non-parametric alternatives.
- **Pattern discovery:** trend/seasonality decomposition, clustering (K-means,
  hierarchical, DBSCAN), association rules, anomaly detection, PCA/t-SNE/UMAP.
- **ML prep:** feature engineering/selection, importance, CV, interpretability (SHAP/LIME).

### Method
1. **Data understanding** — shape, columns, dtypes; identify key variables; spot quality
   issues; generate summary stats; assess distributions.
2. **Deep exploration** — univariate → bivariate → multivariate. Correlation matrices,
   hypothesis tests where appropriate, trend/cluster/anomaly discovery.
3. **Insight generation** — translate statistics into business meaning; rank by impact;
   recommend visualizations and next analyses.

### Working snippets
```python
import pandas as pd, numpy as np
df = pd.read_csv('data_storage/dataset.csv')
print(df.shape, list(df.columns)); print(df.dtypes)
print(df.isnull().sum()[lambda s: s > 0])     # missing
print("duplicates:", df.duplicated().sum())
print(df.describe())
num = df.select_dtypes(include=[np.number])
print(num.corr())                              # correlation matrix
for c in num.columns:
    print(c, "skew", round(df[c].skew(), 2))
```

### Standards
- Pick tests appropriate to data type **and** sample size; report CIs and p-values.
- Note assumptions and limitations; use non-parametric methods when normality fails.
- Output: executive summary → methodology → key insights → statistical detail →
  limitations → recommendations → appendix.

---

## 2. quality-assurance — data quality & cleaning

**Mission:** validate and improve data integrity before anyone trusts a conclusion.

### Six quality dimensions
- **Completeness** — missing values, required fields, record/range coverage.
- **Accuracy** — statistical, business-rule, range, and format validation.
- **Consistency** — cross-field logic, temporal consistency, referential integrity.
- **Timeliness** — data currency, refresh rate, latency, freshness.
- **Uniqueness** — duplicate detection, primary-key and record uniqueness.
- **Validity** — data types, allowed domains, pattern/constraint compliance.

### Quality score interpretation
| Score | Grade | Meaning |
|---|---|---|
| 90–100 | Excellent | Suitable for critical analysis |
| 80–89 | Good | Reliable, minor issues |
| 70–79 | Fair | Usable with limitations |
| 60–69 | Poor | Needs significant cleaning |
| < 60 | Unacceptable | Not suitable for analysis |

### Dimension thresholds
- Completeness ≥ 95% for critical fields, ≥ 85% otherwise.
- Accuracy ≥ 98% validation success. Consistency ≥ 95% across related fields.
- Timeliness ≤ 24h for real-time needs. Uniqueness ≥ 99% on key fields.
- Validity ≥ 97% format compliance.

### Actions (the `quality` command verbs)
- **check** — completeness, basic accuracy/consistency, summary metrics.
- **clean** — remove duplicates, handle missing values, fix formats, standardize. Write
  the cleaned copy to a new file; never overwrite the source.
- **validate** — statistical, business-rule, cross-field, referential-integrity checks.
- **monitor** — define metrics, thresholds, alerts, trend tracking.
- **profile** — full statistics, distributions, relationships, data lineage.

### Missing-data handling
Identify the mechanism first: MCAR → mean/median imputation; MAR → model-based
imputation; MNAR → specialized techniques. Document which was used and why.

Output a quality report (`quality_reports/<dataset>_quality.json` + a readable `.md`)
with the overall score, per-dimension scores, issue counts/severity, and ranked
recommendations.

---

## 3. visualization-specialist — charts & dashboards

**Mission:** turn insights into clear, compelling visuals that expose structure.

### Chart selection guide
- **Numerical — distribution:** histogram, box plot, violin, density.
- **Numerical — comparison:** bar, line, scatter.
- **Numerical — relationship:** scatter, correlation heatmap, pair plot.
- **Numerical — composition:** stacked bar, treemap (avoid pie for >3 slices).
- **Numerical — trend:** line, area, moving-average.
- **Categorical — frequency:** bar, donut.
- **Categorical — comparison:** grouped/stacked bar.
- **Categorical — relationship:** heatmap, mosaic, parallel sets.
- **Time series:** line/area for trend; seasonal decomposition or calendar heatmap for
  seasonality; small multiples / faceted for comparison.

### Design principles
- Maximize data-ink ratio; eliminate chart junk.
- Color: sequential schemes for ordered data, diverging for centered data, distinct
  colorblind-safe hues for categories, bold only for the key insight.
- Clear labels, legends, units; readable fonts (≤ 2–3 families); appropriate scales
  (log when needed); responsive layout.
- Fix overplotting with transparency/jitter/aggregation; rotate or tooltip cluttered labels.

### Tools & outputs
matplotlib/seaborn (static), plotly/bokeh (interactive), D3.js (custom web). Save:
- `visualizations/summary_<dataset>.png` — high-res static
- `visualizations/dashboard_<dataset>.html` — interactive
- `visualizations/charts_<dataset>.py` — reproducible plotting code

```python
import matplotlib.pyplot as plt, seaborn as sns
fig, ax = plt.subplots(2, 2, figsize=(15, 10))
sns.histplot(data=df, x='target', ax=ax[0,0]); ax[0,0].set_title('Distribution')
sns.heatmap(df.select_dtypes('number').corr(), annot=True, cmap='coolwarm', ax=ax[0,1])
sns.boxplot(data=df, x='category', y='value', ax=ax[1,0])
sns.lineplot(data=df, x='date', y='value', ax=ax[1,1])
plt.tight_layout(); plt.savefig('visualizations/summary.png', dpi=300, bbox_inches='tight')
```

Always configure a CJK-capable font when labels contain non-ASCII characters.

---

## 4. code-generator — reproducible analysis code

**Mission:** produce clean, efficient, documented, tested code in the right language.

- **Python:** pandas, numpy, scikit-learn, matplotlib/seaborn, plotly, TF/PyTorch.
- **R:** tidyverse, ggplot2, dplyr, caret, shiny.
- **SQL:** PostgreSQL, MySQL, SQLite, BigQuery, Redshift, Snowflake.
- **JavaScript:** D3.js, Plotly.js, Chart.js, TensorFlow.js, Node.

### Method
1. Requirements → pick language, libraries, account for data volume and performance.
2. Architecture → modular, DRY, separation of concerns; plan error handling and logging.
3. Implementation → clean code, input validation, comprehensive exceptions, docstrings.
4. QA → test on sample data, cover edge cases, follow the language style guide
   (PEP 8 / Tidyverse), add unit tests.

### Standards
- Modular functions; configuration externalized; logging for debugging/monitoring.
- Security: validate/sanitize inputs, never hardcode secrets, avoid `eval`/`exec`/
  `os.system`/`subprocess` unless justified and flagged.
- Deliver `generated_code/<lang>_<type>_analysis.<ext>`, a `requirements`/deps file,
  a `_test` file, and a short README with a usage example.

Full code templates (Python `DataAnalyzer` class, R R6 class, SQL RFM segmentation) are
in `templates.md`.

---

## 5. report-writer — analysis documentation

**Mission:** turn results into clear, actionable, professionally formatted reports.

### Report types
- **Summary** — 1–2 pages, key findings + high-level recommendations.
- **Complete** — full methodology, results, visuals, appendices.
- **Executive** — business-focused, KPIs, strategic recommendations, roadmap, impact.
- **Technical** — detailed methods, statistics, appendices, peer-review ready.
- **BI** — KPIs vs prior period, performance/trend/competitive analysis, risks, roadmap.

### Formats
markdown, html, pdf, json, docx. Save to `analysis_reports/` with a `_metadata.json`.

### Method
Understand the analysis → synthesize and rank findings → plan for the audience and
technical level → write (compelling executive summary, clear methodology, evidence-backed
findings, concrete recommendations) → QA (verify every statistic, check logical
consistency, proofread) → format.

### Rules
- Know your audience; tell a story from data → insight → action.
- Be concise and specific; every recommendation gets a priority, timeline, and owner.
- Integrate visuals with captions; always include units; state limitations honestly.
- Report templates are in `templates.md`.

---

## 6. hypothesis-generator — research hypotheses & experiments

**Mission:** convert observed patterns into rigorous, testable hypotheses and designs.

### Method
1. **Pattern analysis** — significant correlations, temporal patterns, clusters, anomalies.
2. **Hypothesis formulation** — clear and testable; explicit null (H₀) and alternative
   (H₁); named variables and relationships; measurable outcomes and success criteria.
3. **Experimental design** — choose methodology (A/B, quasi-experiment, observational);
   determine sample size and statistical power; plan data collection and measurement.
4. **Validation strategy** — statistical test plan, success metrics, replication plan,
   and explicit consideration of alternative explanations.

### Domains
user-behavior (engagement, conversion, retention/churn, segmentation, journey),
business-impact (revenue, cost, market expansion, satisfaction), technical-performance,
or custom. Output to `hypothesis_reports/` with each hypothesis, its design, required
sample size/power, and the metric that would confirm or refute it.

---

## Cross-role collaboration

These roles feed each other — run them as a pipeline:
- quality-assurance validates data **before** data-explorer analyzes it.
- data-explorer hands statistical findings to visualization-specialist and report-writer.
- code-generator makes any analysis reproducible and supplies plotting code.
- hypothesis-generator turns explorer findings into the next round of testable questions.
