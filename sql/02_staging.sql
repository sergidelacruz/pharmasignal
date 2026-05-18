-- =============================================================
-- PharmaSignal | 02_staging.sql
-- Layer: STAGING
-- Purpose: Clean, standardize, and enrich raw data.
--          These views are the single source of truth for all
--          downstream analytics. No raw tables should be
--          queried directly beyond this layer.
-- =============================================================

-- stg_drugs: canonical drug reference
CREATE OR REPLACE VIEW stg_drugs AS
SELECT
    drug_id,
    drug_name,
    therapeutic_area,
    indication,
    launch_date,
    class_avg_serious_rate,
    -- Derived: months since launch as of today (used in trend normalization)
    DATE_DIFF('month', launch_date, CURRENT_DATE) AS months_since_launch
FROM raw_drugs;

-- stg_adverse_events: cleaned AE records with derived fields
CREATE OR REPLACE VIEW stg_adverse_events AS
SELECT
    report_id,
    ae.drug_id,
    d.drug_name,
    d.therapeutic_area,
    ae.event_date,
    -- Standardize quarter format: '2024-Q1'
    ae.quarter,
    YEAR(ae.event_date) AS event_year,
    QUARTER(ae.event_date) AS event_quarter_num,
    ae.months_on_market,
    -- Capitalize reaction name consistently
    INITCAP(ae.reaction) AS reaction,
    CAST(ae.is_novel_reaction AS BOOLEAN) AS is_novel_reaction,
    ae.outcome,
    CAST(ae.is_serious AS BOOLEAN) AS is_serious,
    -- Classify severity into 3 buckets for simpler visuals
    CASE ae.outcome
        WHEN 'Death'            THEN 'Critical'
        WHEN 'Disability'       THEN 'Critical'
        WHEN 'Hospitalization'  THEN 'Serious'
        WHEN 'Moderate'         THEN 'Moderate'
        ELSE                         'Mild'
    END AS severity_bucket,
    ae.reporter_type,
    ae.country,
    ae.age_group,
    ae.sex
FROM raw_adverse_events ae
-- Only join valid drugs (data quality guard)
INNER JOIN raw_drugs d ON ae.drug_id = d.drug_id
-- Exclude future-dated records (data quality guard)
WHERE ae.event_date <= CURRENT_DATE;

-- stg_quarterly_sales: aggregated sales per drug per quarter
-- Needed to normalize AE reporting rate
CREATE OR REPLACE VIEW stg_quarterly_sales AS
SELECT
    drug_id,
    CAST(LEFT(year_month, 4) AS INTEGER) AS sales_year,
    QUARTER(STRPTIME(year_month || '-01', '%Y-%m-%d')) AS sales_quarter_num,
    LEFT(year_month, 4) || '-Q' || CAST(QUARTER(STRPTIME(year_month || '-01','%Y-%m-%d')) AS VARCHAR) AS quarter,
    SUM(units_sold) AS quarterly_units_sold
FROM raw_sales_volume
GROUP BY drug_id, sales_year, sales_quarter_num, quarter;

-- Verification: check for any AE records with no matching drug
SELECT
    COUNT(*) AS orphan_ae_records
FROM raw_adverse_events ae
LEFT JOIN raw_drugs d ON ae.drug_id = d.drug_id
WHERE d.drug_id IS NULL;
