# PharmaSignal — Drug Safety Early Warning System

> **Analytics Engineering Portfolio Project**  
> Stack: SQL · DuckDB · Power BI  
> Domain: Pharmaceutical Safety Monitoring

---

## Business Question

> *"Which drugs in our portfolio are showing early signs of unexpected adverse events — before they become a regulatory or patient safety crisis?"*

Pharmacovigilance teams at drug sponsors continuously monitor post-market safety data. A signal is not a confirmed problem — it is a statistically unusual pattern that warrants investigation. Detecting signals early means faster regulatory response and better patient outcomes. Missing them means FDA enforcement actions, label changes under pressure, and patient harm.

This project turns adverse event report data into a ranked weekly watchlist, so a medical safety officer can prioritize their attention with confidence.

---

## Project Structure

```
pharmasignal/
├── README.md
├── genai_usage.md                      ← How AI tools were used in this project
├── data/
│   ├── drugs.csv                       ← Portfolio reference: 12 drugs
│   ├── adverse_events.csv              ← ~28k simulated AE reports
│   └── sales_volume.csv               ← Monthly units sold per drug
├── sql/
│   ├── 01_create_tables.sql           ← Raw layer: load CSVs into DuckDB
│   ├── 02_staging.sql                 ← Staging layer: clean & standardize
│   ├── 03_risk_scores.sql             ← Analytics layer: score each drug
│   └── 04_outputs.sql                 ← Export CSVs for Power BI
├── outputs/
│   ├── risk_watchlist.csv             ← One row per drug, scored & ranked
│   ├── ae_breakdown.csv               ← Reaction-level detail (last 4 quarters)
│   └── quarterly_trend.csv            ← Drug × quarter trend data
└── powerbi/
    └── pharmasignal_theme.json        ← Color theme for Power BI
```

---

## How to Run

**Requirements:** Python 3.9+, DuckDB (`pip install duckdb`)

```bash
# 1. Generate source data
python generate_data.py

# 2. Run the full SQL pipeline
python run_pipeline.py

# 3. Open Power BI → load files from outputs/
```

All SQL logic runs locally in DuckDB — no cloud account needed. The same SQL is 100% compatible with PostgreSQL and Snowflake with minor dialect adjustments (noted in the SQL files).

---

## Data Sources

### Public base
Drug metadata structure follows the [ClinicalTrials.gov](https://clinicaltrials.gov) and [FDA FAERS](https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers) schemas. No real patient data is used.

### Synthetic extension (fully documented)

| File | What's real | What's simulated | Why |
|---|---|---|---|
| `drugs.csv` | Therapeutic area structure, class benchmarks | Drug names, launch dates | Fictional drugs needed for portfolio framing |
| `adverse_events.csv` | FAERS report schema, outcome codes, reporter types | All event records (~28k rows) | Real FAERS data requires matching real drug names |
| `sales_volume.csv` | Realistic volume ranges by therapeutic area | All values | Needed to normalize reporting rates |

Three drugs (Veraximab, Celvaxin, Norafentix) are seeded with elevated risk patterns to demonstrate signal detection. This is documented transparently in `generate_data.py`.

---

## The SQL Data Model

Three raw tables → two staging views → three output tables.

```
raw_drugs              raw_adverse_events      raw_sales_volume
     │                        │                       │
     └──────────┬─────────────┘                       │
                ▼                                      │
          stg_drugs          stg_adverse_events   stg_quarterly_sales
                │                    │                  │
                └──────────┬─────────┴──────────────────┘
                           ▼
                  03_risk_scores.sql
                  (CTE chain — scored per drug)
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
    risk_watchlist.csv  ae_breakdown  quarterly_trend
    (Power BI Page 1)  (Page 2)       (Page 3)
```

---

## The Risk Signal Score

Each drug receives a composite score (0–100) computed entirely in SQL — no Python, no external tools.

### Four components

| Component | Weight | What it measures | Why it matters |
|---|---|---|---|
| Reporting Rate Index | 30% | AE reports per 1,000 units sold vs portfolio average | Without this, widely prescribed drugs always look riskier |
| Severity Ratio | 35% | % serious outcomes vs therapeutic class benchmark | Oncology and CNS have different baselines — class context is everything |
| Novelty Index | 20% | % of reactions not seen in the drug's first 6 months post-launch | Novel reactions = real-world risk diverging from trial findings |
| Velocity Flag | 15% | Quarter-over-quarter growth in report volume | A report spike often leads formal signal detection by 1–2 quarters |

### Thresholds

| Score | Flag | Action |
|---|---|---|
| ≥ 65 | Investigate | Immediate pharmacovigilance review |
| 40–64 | Monitor | Enhanced surveillance, re-evaluate next quarter |
| < 40 | Clear | Routine monitoring continues |

### Q1 2024 Results

| Drug | Area | Score | Flag |
|---|---|---|---|
| Veraximab | Oncology | 72.7 | **Investigate** |
| Celvaxin | Cardiology | 64.5 | Monitor |
| Norafentix | CNS | 59.1 | Monitor |
| Durosamab | Cardiology | 45.3 | Monitor |
| Daxolimab | Oncology | 33.9 | Clear |
| Loretinib | Oncology | 32.1 | Clear |
| Eptifenex | Cardiology | 30.4 | Clear |
| Relixanib | Autoimmune | 28.4 | Clear |

---

## Power BI Dashboard

Three pages, each answering one business question.

**Page 1 — Watchlist:** *Which drugs need attention this quarter?*
Load `risk_watchlist.csv`. Build a table visual with conditional formatting on `signal_flag`. Add a bar chart of `composite_score` sorted descending with a reference line at 65.

**Page 2 — AE Detail:** *What is happening with this drug?*
Load `ae_breakdown.csv`. Filter by `drug_id` using a slicer. Bar chart of `reaction` by `report_count`, colored by `is_novel_reaction`. Donut of `severity_bucket`.

**Page 3 — Trend:** *Is this drug getting better or worse over time?*
Load `quarterly_trend.csv`. Line chart of `total_reports` and `serious_pct` by `quarter`, one line per drug.

---

## What This Project Demonstrates

- SQL as the analytical layer, not just a data fetch tool
- Clean separation of concerns: raw → staging → analytics → output
- Normalization thinking: why raw counts mislead and how to fix them
- Benchmark-relative scoring: different drug classes have different risk baselines
- Transparent synthetic data: documented assumptions, reproducible results
- End-to-end deliverable: from CSVs to a decision-ready dashboard

---

## Limitations & Real-World Extensions

| What this project does | What a production system would add |
|---|---|
| Composite score (simplified) | Disproportionality ratios (PRR, ROR) over full FAERS population |
| Reaction types as strings | MedDRA hierarchy — grouping reactions by System Organ Class |
| Quarterly batch output | Automated weekly refresh triggered by new FAERS quarterly release |
| Power BI import mode | DirectQuery on Snowflake — live data, no CSV exports |
| Manual threshold (65) | Statistical threshold based on historical signal confirmation rates |

---

*All drug names are fictional. Adverse event data is simulated for demonstration purposes.*
