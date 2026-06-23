# Code & Report Templates

Production-ready starting points for the code-generator and report-writer roles. Adapt to
the dataset; keep the structure (error handling, logging, docstrings, saved artifacts).
Adapted from [claude-data-analysis](https://github.com/liangdabiao/claude-data-analysis).

---

## Python — `DataAnalyzer` class

A robust, documented analysis harness: config dataclass, logging, typed load with
per-format handling, validation, dispatchable analysis, and result saving.

```python
"""High-quality Python template for data analysis."""
import json, logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Union
import pandas as pd, numpy as np

@dataclass
class AnalysisConfig:
    input_path: str
    output_path: str
    analysis_type: str            # descriptive | correlation | regression
    parameters: Dict[str, Union[str, int, float]]

class DataAnalyzer:
    def __init__(self, config: AnalysisConfig):
        self.config = config
        self.logger = self._setup_logger()
        self.data = None
        self.results = {}

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger(__name__); logger.setLevel(logging.INFO)
        if not logger.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            logger.addHandler(h)
        return logger

    def load_data(self) -> pd.DataFrame:
        p = Path(self.config.input_path)
        if not p.exists():
            raise FileNotFoundError(f"Data file not found: {p}")
        suf = p.suffix.lower()
        if suf == '.csv':            self.data = pd.read_csv(p)
        elif suf in ('.xlsx', '.xls'): self.data = pd.read_excel(p)
        elif suf == '.json':         self.data = pd.read_json(p)
        else: raise ValueError(f"Unsupported file format: {suf}")
        self.logger.info(f"Loaded data: {self.data.shape}")
        return self.data

    def validate_data(self) -> bool:
        if self.data is None:
            self.logger.error("No data loaded"); return False
        miss = self.data.isnull().sum()
        if miss.any(): self.logger.warning(f"Missing values: {miss[miss > 0].to_dict()}")
        return True

    def run_analysis(self) -> Dict:
        if not self.validate_data():
            raise ValueError("Data validation failed")
        t = self.config.analysis_type.lower()
        if t == 'descriptive': self.results = self._descriptive()
        else: raise ValueError(f"Unsupported analysis type: {t}")
        self.logger.info(f"Analysis completed: {t}")
        return self.results

    def _descriptive(self) -> Dict:
        num = self.data.select_dtypes(include=[np.number]).columns
        return {
            'summary_statistics': self.data[num].describe(),
            'correlation_matrix': self.data[num].corr(),
            'missing_values': self.data.isnull().sum(),
            'data_types': self.data.dtypes,
        }

    def save_results(self) -> None:
        out = Path(self.config.output_path); out.mkdir(parents=True, exist_ok=True)
        as_json = {k: (v.to_dict() if isinstance(v, pd.DataFrame) else v)
                   for k, v in self.results.items()}
        (out / 'analysis_results.json').write_text(json.dumps(as_json, indent=2, default=str))
        for k, v in self.results.items():
            if isinstance(v, pd.DataFrame): v.to_csv(out / f'{k}.csv')
        self.logger.info(f"Results saved to: {out}")

if __name__ == "__main__":
    cfg = AnalysisConfig('data_storage/sample.csv', 'analysis_reports/', 'descriptive', {})
    a = DataAnalyzer(cfg); a.load_data(); a.run_analysis(); a.save_results()
```

---

## R — R6 analysis class

```r
library(tidyverse); library(jsonlite)

AnalysisConfig <- R6::R6Class("AnalysisConfig", public = list(
  input_path = NULL, output_path = NULL, analysis_type = NULL, parameters = NULL,
  initialize = function(input_path, output_path, analysis_type, parameters = list()) {
    self$input_path <- input_path; self$output_path <- output_path
    self$analysis_type <- analysis_type; self$parameters <- parameters
  }))

DataAnalyzer <- R6::R6Class("DataAnalyzer",
  private = list(.data = NULL, .results = list(),
    log = function(msg, level = "INFO")
      cat(sprintf("[%s] %s: %s\n", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), level, msg))),
  public = list(config = NULL,
    initialize = function(config) self$config <- config,
    load_data = function() {
      if (!file.exists(self$config$input_path)) stop("Data file not found")
      ext <- tolower(tools::file_ext(self$config$input_path))
      private$.data <- switch(ext,
        csv  = readr::read_csv(self$config$input_path, show_col_types = FALSE),
        json = as.data.frame(fromJSON(self$config$input_path)),
        stop(paste("Unsupported format:", ext)))
      private$log(paste("Loaded:", paste(dim(private$.data), collapse = "x")))
      invisible(private$.data)
    },
    run_analysis = function() {
      num <- private$.data %>% select(where(is.numeric))
      private$.results <- list(
        summary = summary(num),
        correlation = cor(num, use = "complete.obs"),
        missing = colSums(is.na(private$.data)))
      private$log(paste("Analysis completed:", self$config$analysis_type))
      private$.results
    },
    save_results = function() {
      dir.create(self$config$output_path, recursive = TRUE, showWarnings = FALSE)
      write_json(private$.results, file.path(self$config$output_path, "analysis_results.json"))
      private$log(paste("Saved to:", self$config$output_path))
    }))
```

---

## SQL — RFM customer segmentation

CTE-based, commented, with NTILE scoring, segment labels, summary table, indexes, and
views. Adapt table/column names.

```sql
-- Customer segmentation via RFM (Recency, Frequency, Monetary)
WITH customer_summary AS (
    SELECT c.customer_id, c.customer_name, c.signup_date,
           COUNT(DISTINCT o.order_id) AS total_orders,
           COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_revenue,
           COALESCE(AVG(oi.quantity * oi.unit_price), 0) AS avg_order_value,
           COALESCE(MAX(o.order_date), CURRENT_DATE) AS last_order_date
    FROM customers c
    LEFT JOIN orders o ON c.customer_id = o.customer_id
    LEFT JOIN order_items oi ON o.order_id = oi.order_id
    GROUP BY c.customer_id, c.customer_name, c.signup_date
),
rfm AS (
    SELECT *, DATEDIFF(CURRENT_DATE, last_order_date) AS recency_days,
           total_orders AS frequency, total_revenue AS monetary
    FROM customer_summary WHERE last_order_date IS NOT NULL
),
scored AS (
    SELECT *,
           NTILE(5) OVER (ORDER BY recency_days DESC) AS recency_score,
           NTILE(5) OVER (ORDER BY frequency ASC)     AS frequency_score,
           NTILE(5) OVER (ORDER BY monetary ASC)      AS monetary_score
    FROM rfm
)
SELECT customer_id, customer_name, total_revenue,
       CONCAT(recency_score, frequency_score, monetary_score) AS rfm_code,
       CASE
         WHEN recency_score >= 4 AND frequency_score >= 4 AND monetary_score >= 4 THEN 'Champions'
         WHEN recency_score >= 3 AND frequency_score >= 3 AND monetary_score >= 3 THEN 'Loyal'
         WHEN recency_score >= 4 AND frequency_score <= 2 THEN 'New'
         WHEN recency_score <= 2 AND frequency_score >= 4 THEN 'At Risk'
         WHEN recency_score <= 2 AND frequency_score <= 2 THEN 'Lost'
         ELSE 'Other'
       END AS rfm_segment
FROM scored
ORDER BY (recency_score + frequency_score + monetary_score) DESC;
```

---

## Report templates

### Executive summary
```markdown
# Executive Summary: <Dataset> Analysis

## Key Findings
- **Primary insight:** <key statistical finding>
- **Business impact:** <quantified implication>
- **Performance metrics:** <KPIs>

## Recommendations
1. **Immediate action:** <action — timeline — owner>
2. **Strategic initiative:** <longer-term recommendation>
3. **Investment priority:** <resource allocation>

## Next Steps
- Phase 1 (0–30 days): <immediate actions>
- Phase 2 (30–90 days): <medium-term initiatives>
- Phase 3 (90+ days): <strategic actions>
```

### Technical report
```markdown
# Technical Analysis Report: <Dataset>

## Abstract
<objectives, methods, key findings in a paragraph>

## 1. Introduction — background, objectives, methodology overview
## 2. Data Description — sources, structure, quality
## 3. Methodology — data preparation, statistical methods, techniques
## 4. Results — descriptive stats, inferential stats, key findings
## 5. Discussion — interpretation, limitations, implications
## 6. Conclusions — summary, recommendations, future research
## 7. References
## 8. Appendices — technical detail, data dictionary, code listings
```

### Business intelligence report
```markdown
# Business Intelligence Report: <Subject>

## Executive Summary
## Key Performance Indicators
- **KPI 1:** <value> (<change> vs prior period)
- **KPI 2:** <value> (<change> vs prior period)

## Performance Analysis — revenue / customer / operational / market metrics
## Trend Analysis — short-term, long-term, seasonal
## Competitive Landscape — position, advantages, opportunities
## Recommendations — strategic initiatives, tactical actions, investment priorities
## Risk Assessment — key risks, mitigation, contingencies
## Implementation Roadmap — phases 1/2/3
## Success Metrics — measurement framework, milestones, monitoring plan
```
