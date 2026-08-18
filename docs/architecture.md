# CareSync Architecture

![architecture diagram placeholder](./architecture-placeholder.png)

## Flow

1. **Delivery**: a third-party aggregation agent drops six weekly CSVs into
   a shared Google Drive folder (Phase 1) / SFTP server (Phase 2).
2. **Sensing**: the pipeline polls for each expected file; anything absent
   1 hour past the scheduled delivery time triggers an SLA-miss alert.
3. **Pre-validation gate**: every arrived file is checked (schema,
   mandatory fields, id format, parseability, allowed values, chronology,
   duplicates, row-count sanity) before it may reach Snowflake.
   - Pass: proceeds to load.
   - Fail: quarantined, its load/transform tasks are **skipped** (not
     failed), the skip cascades to foreign-key-dependent datasets, and
     Slack + email fire with the failure detail.
4. **Load**: validated files load into `CARESYNC_WH.RAW` (Snowflake).
5. **Transform**: dbt builds `CARESYNC_WH.STAGING` (PHI stripped here) and
   `CARESYNC_WH.PROD` (single-fact star schema: `fct_appointments` +
   dimensions + `conditions_detail`).
6. **Post-validation gate**: the PROD layer is checked against business
   requirements (no orphan keys, no PHI leakage, row counts in bounds, no
   duplicate natural keys). Pass/fail is notified via Slack + email.
7. **Audit**: every stage writes to `CARESYNC_WH.AUDIT.RUN_AUDIT`,
   traceable by `run_id`.

## Dependency map (drives cascade-skip)

```
organizations ─┐
providers ─────┼──► encounters ──► conditions
payers ────────┘
patients ──────────► encounters
```

## Two build stages

| | Phase 1 (testing) | Phase 2 (production) |
|---|---|---|
| Validation | Python + pandas (`validation/pandas/`) | Great Expectations suites (`validation/great_expectations/`) |
| Orchestration | GitHub Actions (`.github/workflows/`) | Airflow (`orchestration/airflow/dags/`) |
| Landing zone | Google Drive | SFTP |
| Business logic | Identical | Identical |
