# Production Readiness (Phase 2)

Status of the CareSync platform's move from the testing stack (pandas +
GitHub Actions + Google Drive) to the production stack (Great
Expectations + Airflow + SFTP), and what's confirmed working versus what
still needs live-environment confirmation.

## What changed, and why nothing else had to

Per the project's core design principle, only the *mechanism* changed
between phases, never the *rules*:

| Layer | Phase 1 (testing) | Phase 2 (production) | Rules identical? |
|---|---|---|---|
| Pre-validation | `validation/pandas/` | `validation/great_expectations/ge_validate.py` | Yes, both read `validation/pandas/schemas.py`, verified to produce identical results on real Synthea data |
| Post-validation | `validation/pandas/post_validate.py` | `validation/great_expectations/ge_post_validate.py` | Yes, same 8 checks, same `NEXORA_PROD_WH.PROD` tables, confirmed matching live |
| Landing zone | Google Drive (`sensing/drive_sensor.py`) | SFTP (`sensing/sftp_sensor.py`) | N/A, delivery mechanism only. Both write to `data/landing/<run_id>/` in the identical shape |
| Orchestration | GitHub Actions (`.github/workflows/`) | Airflow (`orchestration/airflow/dags/`) | N/A, orchestration only, task callables wrap the same modules |

Switching engines is one environment variable:
`VALIDATION_ENGINE=great_expectations` in `.env`.

## Verified (proven with real code, real data, live Snowflake)

- Both validation engines produce identical pass/fail verdicts on all 6
  real Synthea datasets (clean and deliberately corrupted cases)
- GE pre-validation and GE post-validation both confirmed live against a
  real Snowflake account, matching the pandas engine's verdict exactly
  on the same run
- SFTP sensor's local-simulation fallback works exactly like the Drive
  sensor's, same SLA logic, same audit trail, same notification firing
- The full Phase 1 pipeline has run clean end to end against a real
  Snowflake account, locally and in real GitHub Actions
- The Airflow DAG's Python compiles cleanly with all task wiring intact

## Needs live-environment confirmation

- `sensing/sftp_sensor.py`'s live SFTP path (no real SFTP server
  available in the assistant's sandbox; only the local-simulation
  fallback was testable there)
- `orchestration/airflow/dags/caresync_dag.py` under a real Airflow
  scheduler (only Python syntax was verified, not Airflow's DAG parser)

## Recommended rollout order

1. Stand up a test SFTP server (or use an existing one), confirm
   `sftp_sensor.py`'s live path downloads and SLA-checks correctly
2. Install Airflow locally (`pip install apache-airflow`), place the DAG
   file, confirm it appears in `airflow dags list` with no import errors
3. Run the DAG manually once against test data before scheduling it
4. Only then point `SFTP_HOST` at the real third-party delivery server
