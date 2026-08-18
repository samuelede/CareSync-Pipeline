-- One row per (run_id, dataset) capturing both gates' results, plus a
-- run-level summary row. This is the audit trail referenced throughout
-- the spec: quarantine history, notification history (by joining on
-- run_id), and SLA performance over time.
CREATE SCHEMA IF NOT EXISTS CARESYNC_WH.AUDIT;

CREATE TABLE IF NOT EXISTS CARESYNC_WH.AUDIT.RUN_AUDIT (
    run_id STRING NOT NULL,
    dataset STRING,                         -- NULL for run-level summary rows
    stage STRING,                           -- SENSING | PRE_VALIDATION | LOAD | DBT | POST_VALIDATION
    status STRING,                          -- ON_TIME | SLA_MISSED | VALID | REJECTED | SKIPPED | SUCCESS | FAILED
    row_count NUMBER,
    failed_checks VARIANT,                  -- array of failed rule names, if any
    quarantine_path STRING,
    notified_slack BOOLEAN DEFAULT FALSE,
    notified_email BOOLEAN DEFAULT FALSE,
    recorded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
