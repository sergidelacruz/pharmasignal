-- =============================================================
-- PharmaSignal | 03_risk_scores.sql
-- Layer: ANALYTICS
-- Purpose: Compute the composite Risk Signal Score per drug.
--
-- BUSINESS QUESTION:
--   Which drugs are showing early signs of unexpected adverse
--   events that could indicate a safety problem?
--
-- SCORING MODEL (4 components → 1 composite score 0–100):
--   Component 1 – Reporting Rate Index  (30% weight)
--     Reports per 1,000 units sold vs portfolio average.
--     Normalizes for drug popularity so big sellers don't look falsely risky.
--
--   Component 2 – Severity Ratio        (35% weight)
--     % serious outcomes vs therapeutic class benchmark.
--     Oncology and CNS have different baselines — this accounts for that.
--
--   Component 3 – Novelty Index         (20% weight)
--     % of reactions not seen in first 6 months post-launch.
--     Novel reactions = real-world risk diverging from trial findings.
--
--   Component 4 – Velocity Flag         (15% weight)
--     QoQ growth in report volume.
--     Early warning: a spike often leads formal signal detection by 1–2 quarters.
--
-- THRESHOLD:
--   Score >= 65 → Investigate
--   Score 40-64 → Monitor
--   Score  < 40 → Clear
-- =============================================================

-- ── Step 1: Q1 2024 AE counts per drug ───────────────────
WITH q1_2024 AS (
    SELECT
        drug_id,
        COUNT(*)                                        AS total_reports,
        SUM(is_serious::INTEGER)                        AS serious_reports,
        SUM(is_novel_reaction::INTEGER)                 AS novel_reports,
        COUNT(DISTINCT reaction)                        AS distinct_reactions
    FROM stg_adverse_events
    WHERE quarter = '2024-Q1'
    GROUP BY drug_id
),

-- ── Step 2: Q4 2023 counts (for velocity calculation) ────
q4_2023 AS (
    SELECT
        drug_id,
        COUNT(*) AS total_reports_prev
    FROM stg_adverse_events
    WHERE quarter = '2023-Q4'
    GROUP BY drug_id
),

-- ── Step 3: Q1 2024 sales (for rate normalization) ───────
q1_sales AS (
    SELECT drug_id, quarterly_units_sold
    FROM stg_quarterly_sales
    WHERE quarter = '2024-Q1'
),

-- ── Step 4: Portfolio-wide average reporting rate ─────────
-- Used to benchmark each drug's rate against the whole portfolio
portfolio_avg_rate AS (
    SELECT
        AVG(q.total_reports::DOUBLE / NULLIF(s.quarterly_units_sold, 0) * 1000) AS avg_rate_per_1k
    FROM q1_2024 q
    JOIN q1_sales s ON q.drug_id = s.drug_id
),

-- ── Step 5: Compute raw score components per drug ─────────
raw_components AS (
    SELECT
        d.drug_id,
        d.drug_name,
        d.therapeutic_area,
        d.indication,
        d.launch_date,
        d.months_since_launch,
        d.class_avg_serious_rate,

        COALESCE(q.total_reports,  0)                  AS total_reports,
        COALESCE(q.serious_reports, 0)                 AS serious_reports,
        COALESCE(q.novel_reports,   0)                 AS novel_reports,
        COALESCE(p.total_reports_prev, 0)              AS total_reports_prev,
        COALESCE(s.quarterly_units_sold, 1)            AS units_sold,

        -- Serious rate this quarter
        ROUND(
            COALESCE(q.serious_reports, 0)::DOUBLE
            / NULLIF(q.total_reports, 0) * 100
        , 1)                                           AS serious_pct,

        -- Novel reaction rate this quarter
        ROUND(
            COALESCE(q.novel_reports, 0)::DOUBLE
            / NULLIF(q.total_reports, 0) * 100
        , 1)                                           AS novel_pct,

        -- Reporting rate per 1,000 units sold
        ROUND(
            COALESCE(q.total_reports, 0)::DOUBLE
            / NULLIF(s.quarterly_units_sold, 0) * 1000
        , 2)                                           AS reports_per_1k_units,

        -- Portfolio average rate (scalar, same value for all rows)
        ROUND(pa.avg_rate_per_1k, 2)                  AS portfolio_avg_rate_per_1k

    FROM stg_drugs d
    LEFT JOIN q1_2024   q  ON d.drug_id = q.drug_id
    LEFT JOIN q4_2023   p  ON d.drug_id = p.drug_id
    LEFT JOIN q1_sales  s  ON d.drug_id = s.drug_id
    CROSS JOIN portfolio_avg_rate pa
),

-- ── Step 6: Score each component (0–100) ──────────────────
scored AS (
    SELECT
        *,

        -- Component 1: Reporting Rate Index
        -- How many times above the portfolio average is this drug's rate?
        -- Capped at 100.
        LEAST(100,
            ROUND(
                (reports_per_1k_units / NULLIF(portfolio_avg_rate_per_1k, 0)) * 40
            , 1)
        )                                              AS score_reporting_rate,

        -- Component 2: Severity Ratio
        -- How much higher is the serious rate vs the class benchmark?
        -- A 2× excess maps to ~80/100.
        LEAST(100,
            ROUND(
                (serious_pct / 100.0) / NULLIF(class_avg_serious_rate, 0) * 40
            , 1)
        )                                              AS score_severity,

        -- Component 3: Novelty Index
        -- Pure % novel reactions, scaled to 0–100.
        LEAST(100,
            ROUND(novel_pct * 2.0, 1)
        )                                              AS score_novelty,

        -- Component 4: Velocity
        -- QoQ growth rate, capped at 100.
        LEAST(100, GREATEST(0,
            ROUND(
                (total_reports - total_reports_prev)::DOUBLE
                / NULLIF(total_reports_prev, 0) * 100
            , 1)
        ))                                             AS score_velocity

    FROM raw_components
),

-- ── Step 7: Weighted composite score ──────────────────────
composite AS (
    SELECT
        *,
        ROUND(
            score_reporting_rate * 0.30 +
            score_severity       * 0.35 +
            score_novelty        * 0.20 +
            score_velocity       * 0.15
        , 1)                                           AS composite_score
    FROM scored
)

-- ── Final output: ranked watchlist ────────────────────────
SELECT
    drug_id,
    drug_name,
    therapeutic_area,
    indication,
    launch_date,
    months_since_launch,
    total_reports,
    serious_pct,
    novel_pct,
    reports_per_1k_units,
    portfolio_avg_rate_per_1k,
    score_reporting_rate,
    score_severity,
    score_novelty,
    score_velocity,
    composite_score,
    -- Signal flag
    CASE
        WHEN composite_score >= 65 THEN 'Investigate'
        WHEN composite_score >= 40 THEN 'Monitor'
        ELSE                             'Clear'
    END                                                AS signal_flag
FROM composite
ORDER BY composite_score DESC;
