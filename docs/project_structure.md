# Full Project Structure

```
caresync-pipeline/
├── config/
│   ├── settings.py              # single source of truth for connections + dataset dependency manifest
│   └── file_manifest.yml        # expected weekly files
├── sensing/
│   └── drive_sensor.py          # Google Drive polling + 1h SLA check
├── validation/
│   ├── pandas/                  # Phase 1: one rules_<dataset>.py per file, pre_validate.py, post_validate.py
│   └── great_expectations/      # Phase 2: suites + checkpoints, same rules re-expressed
├── loaders/
│   └── snowflake_loader.py      # PUT + COPY INTO RAW, skips REJECTED/SKIPPED datasets
├── dbt_caresync/
│   ├── models/staging/          # PHI-minimization boundary
│   └── models/marts/            # fct_appointments + dimensions + conditions_detail
├── notifications/
│   ├── slack_notify.py
│   └── email_notify.py
├── orchestration/
│   ├── github_actions/          # reference copy; live workflow is in .github/workflows/
│   └── airflow/dags/            # Phase 2 production DAG
├── sql/
│   ├── ddl_raw.sql / ddl_staging.sql / ddl_prod.sql
│   ├── run_audit_table.sql
│   └── business_questions.sql
├── quarantine/                  # rejected files land here, keyed by run_id
├── data/
│   └── landing/                 # drop zone: generated batches, gitignored (Week 3: same path, fed by SFTP)
├── scripts/
│   ├── setup_google_drive.sh
│   ├── generate_synthea_data.sh
│   ├── simulate_weekly_drop.py
│   ├── make_dirty_batch.py
│   ├── run_local_pipeline.sh
│   ├── send_run_summary.py
│   ├── audit_log.py
│   ├── check_connections.py
│   └── test_snowflake_connection.py
├── tests/
│   ├── test_validation_rules.py
│   └── test_check_engine.py
├── docs/
│   ├── architecture.md
│   ├── data_dictionary.md
│   ├── notification_matrix.md
│   ├── runbook.md
│   ├── google_drive_setup.md
│   ├── snowflake_setup.md
│   ├── entity_relationship.md
│   └── project_structure.md     # this file
├── .github/workflows/caresync_weekly.yml   # Phase 1 CI orchestration (live path)
├── requirements.txt / requirements-ge.txt / requirements-airflow.txt
├── .env.example
└── .gitignore
```

## Folder purpose, one line each

| Path | Purpose |
|---|---|
| `config/` | Connection settings, dataset dependency manifest, expected-file manifest |
| `sensing/` | Google Drive polling and the 1-hour SLA check |
| `validation/pandas/` | Phase 1 pre/post-validation engine |
| `validation/great_expectations/` | Phase 2 validation engine (same rules, different tooling) |
| `loaders/` | Snowflake loading with skip-not-fail semantics |
| `dbt_caresync/` | Staging models (PHI dropped) and mart models (star schema) |
| `notifications/` | Slack and email, covering the full event matrix |
| `orchestration/` | Airflow DAG (Phase 2); the live GitHub Actions workflow itself lives under `.github/workflows/` |
| `sql/` | Warehouse DDL, run audit table, business question queries |
| `quarantine/` | Rejected files, keyed by run id |
| `data/landing/` | The drop zone (local folder now, SFTP-fed in Week 3, same interface) |
| `scripts/` | Setup automation, data simulation, dirty-batch demo, connection checks, run helpers |
| `tests/` | Unit tests for the validation engine and cascade-skip logic |
| `docs/` | Architecture, data dictionary, setup guides, ER diagram, this file |
