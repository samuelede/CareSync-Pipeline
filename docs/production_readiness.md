# Production Readiness (Phase 2)

Status of the CareSync platform's move from the testing stack (pandas +
GitHub Actions + Google Drive) to the production stack (Great
Expectations + Airflow + SFTP). Every item below marked confirmed was
proven against real infrastructure, not just code review.

## What changed, and why nothing else had to

| Layer | Phase 1 (testing) | Phase 2 (production) | Rules identical? |
|---|---|---|---|
| Pre-validation | `validation/pandas/` | `validation/great_expectations/ge_validate.py` | Yes, verified identical results on real Synthea data |
| Post-validation | `validation/pandas/post_validate.py` | `validation/great_expectations/ge_post_validate.py` | Yes, confirmed live against Snowflake, matches exactly |
| Landing zone | Google Drive (`sensing/drive_sensor.py`) | SFTP (`sensing/sftp_sensor.py`) | N/A, delivery mechanism only |
| Orchestration | GitHub Actions (`.github/workflows/`) | Airflow (`orchestration/airflow/dags/`) | N/A, orchestration only |

Switching validation engines is one environment variable:
`VALIDATION_ENGINE=great_expectations` in `.env`.

## Verified against real infrastructure

- Both validation engines produce identical results on all 6 real
  Synthea datasets, clean and corrupted cases
- GE pre- and post-validation confirmed live against real Snowflake
- Full Phase 1 pipeline run clean end to end, locally and in real
  GitHub Actions
- **SFTP sensor confirmed live**: real Docker SFTP server, real file
  upload, real download via `sensing/sftp_sensor.py`, correct SLA
  evaluation, `(live SFTP)` mode
- **Airflow DAG confirmed live**: real Airflow 2.9.3 stack via Docker
  Compose, `caresync_weekly_pipeline` appears in `airflow dags list`
  with zero import errors, full project modules correctly mounted and
  importable inside the container

## What's still recommended before real production use

- Point `SFTP_HOST` at the actual third-party delivery server instead
  of the test container
- Run the DAG through a full triggered execution (not just parse
  verification) against live data
- Unpause the DAG (`airflow dags unpause caresync_weekly_pipeline`)
  once ready to run on schedule
