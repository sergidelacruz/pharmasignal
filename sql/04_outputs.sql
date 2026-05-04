-- =============================================================
-- PharmaSignal | 04_outputs.sql
-- Layer: OUTPUT
-- Purpose: Materialize final reporting tables as CSV exports
--          for Power BI to consume directly.
--
-- Run after 01, 02, 03. Each COPY statement produces one file
-- in the outputs/ folder, ready to load into Power BI.
-- =============================================================

-- ── Output 1: Risk watchlist ──────────────────────────────
-- Powers Page 1 (watchlist table + KPI cards + bar chart)
CREATE OR REPLACE TABLE out_risk_watchlist AS
WITH q1_2024 AS (
    SELECT drug_id, COUNT(*) AS total_reports,
           SUM(is_serious::INT) AS serious_reports,
           SUM(is_novel_reaction::INT) AS novel_reports
    FROM stg_adverse_events WHERE quarter = '2024-Q1' GROUP BY drug_id
),
q4_2023 AS (
    SELECT drug_id, COUNT(*) AS total_reports_prev
    FROM stg_adverse_events WHERE quarter = '2023-Q4' GROUP BY drug_id
),
q1_sales AS (
    SELECT drug_id, quarterly_units_sold
    FROM stg_quarterly_sales WHERE quarter = '2024-Q1'
),
portfolio_avg AS (
    SELECT AVG(q.total_reports::DOUBLE / NULLIF(s.quarterly_units_sold,0)*1000) AS avg_rate
    FROM q1_2024 q JOIN q1_sales s ON q.drug_id = s.drug_id
),
scored AS (
    SELECT
        d.drug_id, d.drug_name, d.therapeutic_area, d.indication,
        d.launch_date, d.months_since_launch,
        d.class_avg_serious_rate,
        COALESCE(q.total_reports,0)  AS total_reports,
        COALESCE(q.serious_reports,0)AS serious_reports,
        COALESCE(q.novel_reports,0)  AS novel_reports,
        COALESCE(p.total_reports_prev,0) AS prev_reports,
        COALESCE(s.quarterly_units_sold,1) AS units_sold,
        ROUND(COALESCE(q.serious_reports,0)::DOUBLE/NULLIF(q.total_reports,0)*100,1) AS serious_pct,
        ROUND(COALESCE(q.novel_reports,0)::DOUBLE/NULLIF(q.total_reports,0)*100,1) AS novel_pct,
        ROUND(COALESCE(q.total_reports,0)::DOUBLE/NULLIF(s.quarterly_units_sold,0)*1000,2) AS rate_per_1k,
        ROUND(pa.avg_rate,2) AS portfolio_avg_rate,
        LEAST(100,ROUND(COALESCE(q.total_reports,0)::DOUBLE/NULLIF(s.quarterly_units_sold,0)*1000/NULLIF(pa.avg_rate,0)*40,1)) AS score_rr,
        LEAST(100,ROUND(COALESCE(q.serious_reports,0)::DOUBLE/NULLIF(q.total_reports,0)/NULLIF(d.class_avg_serious_rate,0)*40,1)) AS score_sv,
        LEAST(100,ROUND(COALESCE(q.novel_reports,0)::DOUBLE/NULLIF(q.total_reports,0)*200,1)) AS score_nv,
        LEAST(100,GREATEST(0,ROUND((COALESCE(q.total_reports,0)-COALESCE(p.total_reports_prev,0))::DOUBLE/NULLIF(COALESCE(p.total_reports_prev,0),0)*100,1))) AS score_vl
    FROM stg_drugs d
    LEFT JOIN q1_2024 q ON d.drug_id=q.drug_id
    LEFT JOIN q4_2023 p ON d.drug_id=p.drug_id
    LEFT JOIN q1_sales s ON d.drug_id=s.drug_id
    CROSS JOIN portfolio_avg pa
)
SELECT *,
    ROUND(score_rr*0.30 + score_sv*0.35 + score_nv*0.20 + score_vl*0.15, 1) AS composite_score,
    CASE
        WHEN ROUND(score_rr*0.30+score_sv*0.35+score_nv*0.20+score_vl*0.15,1) >= 65 THEN 'Investigate'
        WHEN ROUND(score_rr*0.30+score_sv*0.35+score_nv*0.20+score_vl*0.15,1) >= 40 THEN 'Monitor'
        ELSE 'Clear'
    END AS signal_flag
FROM scored ORDER BY composite_score DESC;

COPY out_risk_watchlist TO 'outputs/risk_watchlist.csv' (HEADER TRUE);
SELECT 'risk_watchlist.csv exported — ' || COUNT(*) || ' rows' AS status FROM out_risk_watchlist;

-- ── Output 2: AE detail breakdown ────────────────────────
-- Powers Page 2 (reaction bars, severity donut, reporter breakdown)
CREATE OR REPLACE TABLE out_ae_breakdown AS
SELECT
    drug_id,
    drug_name,
    therapeutic_area,
    quarter,
    reaction,
    is_novel_reaction,
    severity_bucket,
    reporter_type,
    country,
    age_group,
    COUNT(*) AS report_count
FROM stg_adverse_events
WHERE quarter IN ('2024-Q1','2023-Q4','2023-Q3','2023-Q2')
GROUP BY ALL
ORDER BY drug_id, quarter, report_count DESC;

COPY out_ae_breakdown TO 'outputs/ae_breakdown.csv' (HEADER TRUE);
SELECT 'ae_breakdown.csv exported — ' || COUNT(*) || ' rows' AS status FROM out_ae_breakdown;

-- ── Output 3: Quarterly trend ─────────────────────────────
-- Powers Page 3 (trend line chart per drug)
CREATE OR REPLACE TABLE out_quarterly_trend AS
SELECT
    ae.drug_id,
    ae.drug_name,
    ae.therapeutic_area,
    ae.quarter,
    ae.event_year,
    ae.event_quarter_num,
    COUNT(*)                                                         AS total_reports,
    ROUND(AVG(ae.is_serious::INT)*100, 1)                           AS serious_pct,
    ROUND(AVG(ae.is_novel_reaction::INT)*100, 1)                    AS novel_pct,
    COALESCE(s.quarterly_units_sold, 0)                             AS units_sold,
    -- Reporting rate per 1k units — comparable across time
    ROUND(
        COUNT(*)::DOUBLE / NULLIF(s.quarterly_units_sold, 0) * 1000
    , 2)                                                             AS reports_per_1k,
    -- QoQ change in report count using window function
    LAG(COUNT(*)) OVER (
        PARTITION BY ae.drug_id
        ORDER BY ae.event_year, ae.event_quarter_num
    )                                                                AS prev_quarter_reports,
    COUNT(*) - LAG(COUNT(*)) OVER (
        PARTITION BY ae.drug_id
        ORDER BY ae.event_year, ae.event_quarter_num
    )                                                                AS qoq_change
FROM stg_adverse_events ae
LEFT JOIN stg_quarterly_sales s
    ON ae.drug_id = s.drug_id
    AND ae.quarter = s.quarter
GROUP BY
    ae.drug_id, ae.drug_name, ae.therapeutic_area,
    ae.quarter, ae.event_year, ae.event_quarter_num,
    s.quarterly_units_sold
ORDER BY ae.drug_id, ae.event_year, ae.event_quarter_num;

COPY out_quarterly_trend TO 'outputs/quarterly_trend.csv' (HEADER TRUE);
SELECT 'quarterly_trend.csv exported — ' || COUNT(*) || ' rows' AS status FROM out_quarterly_trend;
