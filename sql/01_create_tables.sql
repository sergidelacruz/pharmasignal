-- =============================================================
-- PharmaSignal | 01_create_tables.sql
-- Layer: RAW
-- Purpose: Create source tables and load the three CSV files.
-- Run with: duckdb pharmasignal.db < sql/01_create_tables.sql
-- =============================================================

-- drugs: one row per drug in the portfolio
CREATE OR REPLACE TABLE raw_drugs (
    drug_id                 VARCHAR PRIMARY KEY,
    drug_name               VARCHAR NOT NULL,
    therapeutic_area        VARCHAR NOT NULL,
    indication              VARCHAR,
    launch_date             DATE    NOT NULL,
    class_avg_serious_rate  DOUBLE  NOT NULL   -- benchmark: expected serious AE rate for this class
);

-- adverse_events: one row per reported adverse event
CREATE OR REPLACE TABLE raw_adverse_events (
    report_id           INTEGER PRIMARY KEY,
    drug_id             VARCHAR  NOT NULL,
    drug_name           VARCHAR,
    therapeutic_area    VARCHAR,
    event_date          DATE     NOT NULL,
    quarter             VARCHAR,               -- e.g. '2024-Q1'
    months_on_market    INTEGER,               -- months since drug launch at time of report
    reaction            VARCHAR  NOT NULL,
    is_novel_reaction   INTEGER  NOT NULL,     -- 1 = not seen in first 6 months post-launch
    outcome             VARCHAR  NOT NULL,     -- Non-serious / Moderate / Hospitalization / Disability / Death
    is_serious          INTEGER  NOT NULL,     -- 1 = Hospitalization, Disability, or Death
    reporter_type       VARCHAR,               -- Physician / Consumer / Pharmacist / Other
    country             VARCHAR,
    age_group           VARCHAR,
    sex                 VARCHAR
);

-- sales_volume: monthly units sold per drug (used to normalize AE rates)
CREATE OR REPLACE TABLE raw_sales_volume (
    drug_id     VARCHAR  NOT NULL,
    year_month  VARCHAR  NOT NULL,             -- format: 'YYYY-MM'
    units_sold  INTEGER  NOT NULL,
    PRIMARY KEY (drug_id, year_month)
);

-- Load from CSV files (adjust path if needed)
COPY raw_drugs           FROM 'data/drugs.csv'           (HEADER TRUE);
COPY raw_adverse_events  FROM 'data/adverse_events.csv'  (HEADER TRUE);
COPY raw_sales_volume    FROM 'data/sales_volume.csv'    (HEADER TRUE);

-- Quick sanity check
SELECT 'raw_drugs'           AS table_name, COUNT(*) AS row_count FROM raw_drugs
UNION ALL
SELECT 'raw_adverse_events',                COUNT(*)               FROM raw_adverse_events
UNION ALL
SELECT 'raw_sales_volume',                  COUNT(*)               FROM raw_sales_volume;
