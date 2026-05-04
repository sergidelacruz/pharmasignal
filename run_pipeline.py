"""
PharmaSignal — Pipeline Runner
Run this after generate_data.py to execute the full SQL pipeline
and produce the three output CSVs ready for Power BI.

Usage: python run_pipeline.py
"""

import duckdb, os, sys

DB_PATH   = "pharmasignal.db"
DATA_DIR  = "data"
OUT_DIR   = "outputs"

os.makedirs(OUT_DIR, exist_ok=True)

print("PharmaSignal Pipeline")
print("=" * 40)

con = duckdb.connect(DB_PATH)

# ── 01 Raw tables ───────────────────────────────────────────
print("\n[1/4] Loading raw tables...")
for stmt in [
    "CREATE OR REPLACE TABLE raw_drugs (drug_id VARCHAR, drug_name VARCHAR, therapeutic_area VARCHAR, indication VARCHAR, launch_date DATE, class_avg_serious_rate DOUBLE)",
    "CREATE OR REPLACE TABLE raw_adverse_events (report_id INTEGER, drug_id VARCHAR, drug_name VARCHAR, therapeutic_area VARCHAR, event_date DATE, quarter VARCHAR, months_on_market INTEGER, reaction VARCHAR, is_novel_reaction INTEGER, outcome VARCHAR, is_serious INTEGER, reporter_type VARCHAR, country VARCHAR, age_group VARCHAR, sex VARCHAR)",
    "CREATE OR REPLACE TABLE raw_sales_volume (drug_id VARCHAR, year_month VARCHAR, units_sold INTEGER)",
    f"COPY raw_drugs FROM '{DATA_DIR}/drugs.csv' (HEADER TRUE)",
    f"COPY raw_adverse_events FROM '{DATA_DIR}/adverse_events.csv' (HEADER TRUE)",
    f"COPY raw_sales_volume FROM '{DATA_DIR}/sales_volume.csv' (HEADER TRUE)",
]:
    con.execute(stmt)

for tbl in ['raw_drugs','raw_adverse_events','raw_sales_volume']:
    n = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
    print(f"  {tbl}: {n:,} rows")

# ── 02 Staging views ────────────────────────────────────────
print("\n[2/4] Creating staging views...")
con.execute("""
CREATE OR REPLACE VIEW stg_drugs AS
SELECT drug_id, drug_name, therapeutic_area, indication, launch_date, class_avg_serious_rate,
    DATE_DIFF('month', launch_date, CURRENT_DATE) AS months_since_launch
FROM raw_drugs
""")

con.execute("""
CREATE OR REPLACE VIEW stg_adverse_events AS
SELECT ae.report_id, ae.drug_id, d.drug_name, d.therapeutic_area,
    ae.event_date, ae.quarter,
    YEAR(ae.event_date) AS event_year,
    QUARTER(ae.event_date) AS event_quarter_num,
    ae.months_on_market, ae.reaction,
    ae.is_novel_reaction::BOOLEAN AS is_novel_reaction,
    ae.outcome, ae.is_serious::BOOLEAN AS is_serious,
    CASE ae.outcome
        WHEN 'Death'           THEN 'Critical'
        WHEN 'Disability'      THEN 'Critical'
        WHEN 'Hospitalization' THEN 'Serious'
        WHEN 'Moderate'        THEN 'Moderate'
        ELSE                        'Mild'
    END AS severity_bucket,
    ae.reporter_type, ae.country, ae.age_group, ae.sex
FROM raw_adverse_events ae
INNER JOIN raw_drugs d ON ae.drug_id = d.drug_id
WHERE ae.event_date <= CURRENT_DATE
""")

con.execute("""
CREATE OR REPLACE VIEW stg_quarterly_sales AS
SELECT drug_id,
    CAST(LEFT(year_month,4) AS INTEGER) AS sales_year,
    QUARTER(STRPTIME(year_month || '-01','%Y-%m-%d')) AS sales_quarter_num,
    LEFT(year_month,4) || '-Q' ||
        CAST(QUARTER(STRPTIME(year_month||'-01','%Y-%m-%d')) AS VARCHAR) AS quarter,
    SUM(units_sold) AS quarterly_units_sold
FROM raw_sales_volume
GROUP BY drug_id, LEFT(year_month,4),
    QUARTER(STRPTIME(year_month||'-01','%Y-%m-%d')),
    LEFT(year_month,4)||'-Q'||CAST(QUARTER(STRPTIME(year_month||'-01','%Y-%m-%d')) AS VARCHAR)
""")
print("  stg_drugs, stg_adverse_events, stg_quarterly_sales — OK")

# ── 03 Risk scores ──────────────────────────────────────────
print("\n[3/4] Computing risk signal scores...")
watchlist = con.execute("""
WITH q1 AS (
    SELECT drug_id, COUNT(*) total, SUM(is_serious::INT) serious,
           SUM(is_novel_reaction::INT) novel
    FROM stg_adverse_events WHERE quarter='2024-Q1' GROUP BY drug_id
),
q4 AS (
    SELECT drug_id, COUNT(*) prev
    FROM stg_adverse_events WHERE quarter='2023-Q4' GROUP BY drug_id
),
sales AS (
    SELECT drug_id, quarterly_units_sold
    FROM stg_quarterly_sales WHERE quarter='2024-Q1'
),
pavg AS (
    SELECT AVG(q.total::DOUBLE / NULLIF(s.quarterly_units_sold,0) * 1000) avg_rate
    FROM q1 q JOIN sales s ON q.drug_id = s.drug_id
),
scored AS (
    SELECT
        d.drug_id, d.drug_name, d.therapeutic_area, d.indication,
        d.launch_date, d.months_since_launch, d.class_avg_serious_rate,
        COALESCE(q.total,  0)               AS total_reports,
        COALESCE(q.serious,0)               AS serious_reports,
        COALESCE(q.novel,  0)               AS novel_reports,
        COALESCE(p.prev,   0)               AS prev_reports,
        COALESCE(s.quarterly_units_sold, 1) AS units_sold,
        ROUND(COALESCE(q.serious,0)::DOUBLE / NULLIF(q.total,0) * 100, 1) AS serious_pct,
        ROUND(COALESCE(q.novel,  0)::DOUBLE / NULLIF(q.total,0) * 100, 1) AS novel_pct,
        ROUND(COALESCE(q.total,  0)::DOUBLE / NULLIF(s.quarterly_units_sold,0) * 1000, 2) AS rate_per_1k,
        pa.avg_rate AS portfolio_avg_rate,
        LEAST(100, ROUND(COALESCE(q.total,0)::DOUBLE/NULLIF(s.quarterly_units_sold,0)*1000
            /NULLIF(pa.avg_rate,0)*40, 1)) AS score_reporting_rate,
        LEAST(100, ROUND(COALESCE(q.serious,0)::DOUBLE/NULLIF(q.total,0)
            /NULLIF(d.class_avg_serious_rate,0)*40, 1)) AS score_severity,
        LEAST(100, ROUND(COALESCE(q.novel,0)::DOUBLE/NULLIF(q.total,0)*200, 1)) AS score_novelty,
        LEAST(100, GREATEST(0, ROUND(
            (COALESCE(q.total,0) - COALESCE(p.prev,0))::DOUBLE
            / NULLIF(COALESCE(p.prev,0),0) * 100, 1))) AS score_velocity
    FROM stg_drugs d
    LEFT JOIN q1    q  ON d.drug_id = q.drug_id
    LEFT JOIN q4    p  ON d.drug_id = p.drug_id
    LEFT JOIN sales s  ON d.drug_id = s.drug_id
    CROSS JOIN pavg pa
)
SELECT *,
    ROUND(score_reporting_rate*0.30 + score_severity*0.35
        + score_novelty*0.20 + score_velocity*0.15, 1) AS composite_score,
    CASE
        WHEN ROUND(score_reporting_rate*0.30+score_severity*0.35
                  +score_novelty*0.20+score_velocity*0.15,1) >= 65 THEN 'Investigate'
        WHEN ROUND(score_reporting_rate*0.30+score_severity*0.35
                  +score_novelty*0.20+score_velocity*0.15,1) >= 40 THEN 'Monitor'
        ELSE 'Clear'
    END AS signal_flag
FROM scored ORDER BY composite_score DESC
""").df()

watchlist.to_csv(f"{OUT_DIR}/risk_watchlist.csv", index=False)
print(f"  risk_watchlist.csv — {len(watchlist)} drugs")
for _, r in watchlist[['drug_name','composite_score','signal_flag']].iterrows():
    icon = "!" if r.signal_flag=="Investigate" else ("~" if r.signal_flag=="Monitor" else ".")
    print(f"    [{icon}] {r.drug_name:<14} {r.composite_score:>5}")

# ── 04 Supporting output tables ─────────────────────────────
print("\n[4/4] Exporting supporting tables...")

ae_breakdown = con.execute("""
SELECT drug_id, drug_name, therapeutic_area, quarter,
    reaction, is_novel_reaction, severity_bucket, reporter_type,
    country, age_group, COUNT(*) AS report_count
FROM stg_adverse_events
WHERE quarter IN ('2024-Q1','2023-Q4','2023-Q3','2023-Q2')
GROUP BY ALL ORDER BY drug_id, quarter, report_count DESC
""").df()
ae_breakdown.to_csv(f"{OUT_DIR}/ae_breakdown.csv", index=False)
print(f"  ae_breakdown.csv — {len(ae_breakdown):,} rows")

trend = con.execute("""
SELECT ae.drug_id, ae.drug_name, ae.therapeutic_area,
    ae.quarter, ae.event_year, ae.event_quarter_num,
    COUNT(*) AS total_reports,
    ROUND(AVG(ae.is_serious::INT)*100, 1) AS serious_pct,
    ROUND(AVG(ae.is_novel_reaction::INT)*100, 1) AS novel_pct,
    COALESCE(s.quarterly_units_sold, 0) AS units_sold,
    ROUND(COUNT(*)::DOUBLE / NULLIF(s.quarterly_units_sold,0)*1000, 2) AS reports_per_1k
FROM stg_adverse_events ae
LEFT JOIN stg_quarterly_sales s
    ON ae.drug_id=s.drug_id AND ae.quarter=s.quarter
GROUP BY ae.drug_id, ae.drug_name, ae.therapeutic_area,
    ae.quarter, ae.event_year, ae.event_quarter_num, s.quarterly_units_sold
ORDER BY ae.drug_id, ae.event_year, ae.event_quarter_num
""").df()
trend.to_csv(f"{OUT_DIR}/quarterly_trend.csv", index=False)
print(f"  quarterly_trend.csv — {len(trend):,} rows")

print("\n" + "=" * 40)
print("Pipeline complete. Load outputs/ into Power BI.")
print(f"  Flagged: {watchlist[watchlist.signal_flag=='Investigate'].drug_name.tolist()}")
print(f"  Monitor: {watchlist[watchlist.signal_flag=='Monitor'].drug_name.tolist()}")
print(f"  Clear:   {watchlist[watchlist.signal_flag=='Clear'].drug_name.tolist()}")
