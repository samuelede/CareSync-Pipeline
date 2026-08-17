# CareSync: Quality-Gated Weekly Patient & Appointment Data Platform

CareSync turns six weekly CSV exports, delivered by a third-party
aggregation agent into a shared Google Drive folder, into a trusted
Snowflake reporting layer for Nexora Health's clinic network. Every file is
sensed against a 1-hour arrival SLA, validated before it may enter the
warehouse, transformed by dbt into a single-fact star schema, and
validated again after transformation before it's treated as trusted. A
failed file is quarantined and skipped, never failed, and the skip
cascades to anything that depends on it, while Slack and email notify
stakeholders of every SLA miss, validation failure, task error, and
successful run.

All data is synthetic, generated with [Synthea](https://github.com/synthetichealth/synthea).

## Problem statement

Today nothing stands between a bad file and the reporting layer: no SLA
monitoring on third-party delivery, no pre-ingestion quality gate, one bad
file can fail the entire weekly run, and nobody is notified when something
breaks. CareSync closes all four gaps.

## Architecture

![architecture diagram placeholder](./docs/architecture-placeholder.png)

See [`docs/architecture.md`](docs/architecture.md) for the full flow and the
dataset dependency map that drives cascade-skip.

## Two build stages

| | Phase 1 (testing) | Phase 2 (production) |
|---|---|---|
| Validation | Python + pandas | Great Expectations suites + published Data Docs |
| Orchestration | GitHub Actions | Airflow |
| Landing zone | Google Drive | SFTP |
| Business logic | shared | identical rules, different engine |

The point of building it twice: Phase 1 proves *what* each rule should
check, cheaply and debuggably. Phase 2 re-expresses the same rules in
production-grade tooling without changing the logic. The migration is a
tooling swap, not a redesign.

## Project structure

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
│   └── snowflake_setup.md
├── .github/workflows/caresync_weekly.yml   # Phase 1 CI orchestration (live path)
├── requirements.txt / requirements-ge.txt / requirements-airflow.txt
├── .env.example
└── .gitignore
```

## Setup

### 1. Clone and install (Phase 1)

```bash
git clone https://github.com/<your-username>/caresync-pipeline.git
cd caresync-pipeline
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in every value before running anything
```

### 2. Google Drive access

```bash
python -m scripts.check_connections
```

If Google Drive reports `OK`, you're already configured, skip ahead. If
it reports `SKIPPED` or `FAILED`, run the CLI setup script (requires the
[Google Cloud CLI](https://cloud.google.com/sdk/docs/install)):

```bash
gcloud auth login
./scripts/setup_google_drive.sh caresync-pipeline
```

Or see [`docs/google_drive_setup.md`](docs/google_drive_setup.md) for the
full first-time walkthrough covering two auth paths: a service account
(what the script above sets up, but Google's default org policy blocks
key creation on many projects) or OAuth with your own Google account (no
key file, one-time browser consent, the only path with no CLI
equivalent for the client ID itself). The setup guide includes the fix
and workaround for
that org policy error if you hit it.

### 3. Snowflake

```bash
python -m scripts.check_connections
```

If Snowflake reports `OK`, you're already configured, skip ahead. If it
reports `SKIPPED` or `FAILED`, see
[`docs/snowflake_setup.md`](docs/snowflake_setup.md) for full first-time
setup: creating a trial account, installing SnowSQL, and running the DDL
to create the warehouse, database, and schemas.

**Database design note.** `RAW`/`STAGING`/`PROD` are schemas inside one
`CARESYNC_WH` database, not three separate databases. Cross-schema and
cross-database queries in Snowflake use the same fully-qualified
`database.schema.table` syntax either way, so splitting into databases adds
no query simplicity. Access control between layers (e.g. restricting who
can read `RAW`) is enforced with Snowflake roles and schema-level grants,
which works identically within one database. dbt's standard convention on
Snowflake is also one target database with multiple schemas, which is what
`dbt_caresync/profiles_example.yml` and `models/staging/sources.yml`
assume. Separate databases make more sense for genuinely separate
environments (dev/staging/prod deployments), not for layers within one
pipeline run.

### 4. Slack

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps), choosing *From scratch*.
2. Add the `chat:write` bot token scope, install the app to your workspace.
3. Invite the bot to your target channel.
4. Set `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` in `.env`.

### 5. Email

Set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `NOTIFY_EMAIL_TO`
in `.env`. Any standard SMTP provider works (Gmail app password, SES SMTP,
SendGrid, etc.).

### 6. Verify every connection before proceeding

Steps 2 and 3 already had you run `check_connections` for Drive and
Snowflake individually. Now that Slack and email are configured too, run
it once more to confirm all four services are reachable together:

```bash
python -m scripts.check_connections
```

Reports `OK`, `SKIPPED` (not configured, that piece will run in
local-simulation/dry-run mode instead of failing), or `FAILED` (configured
but unreachable, fix before continuing) for `.env`, Google Drive,
Snowflake, Slack, and SMTP. Add `--strict` to exit non-zero on any
`FAILED` check, useful in CI or before a scripted setup step. This same
check runs automatically as the first step of `run_local_pipeline.sh`.

### 7. Generate a weekly batch

Two options, both writing to the same place (`data/landing/<run_id>/`):

```bash
# Option A: pure Python, no external tools, works everywhere (recommended for dev/CI)
python -m scripts.simulate_weekly_drop --run-id 2026-08-10 --patients 200

# Option B: real Synthea (requires Java 11+ and a local Synthea jar)
./scripts/generate_synthea_data.sh 200 2026-08-10
```

### 8. Run the pipeline locally

```bash
./scripts/run_local_pipeline.sh 2026-08-10
```

Runs sensing, pre-validation, load, `dbt run`, post-validation, and the run
summary notification, in the same order as the GitHub Actions workflow.
Without live Google Drive, Snowflake, Slack, or SMTP credentials, sensing
and loading fall back to local-simulation/dry-run modes and notifications
print what they would have sent. The full control flow (SLA check,
validation, cascade-skip, audit logging) still runs for real.

### 9. dbt

```bash
cd dbt_caresync
cp profiles_example.yml ~/.dbt/profiles.yml   # fill in / confirm env vars
dbt debug
dbt run
dbt test
dbt docs generate && dbt docs serve
```

### 10. Prove the dirty-data path

```bash
python -m scripts.make_dirty_batch --source-run-id 2026-08-10 --run-id dirty-demo-01 --target patients --strategy missing_required
./scripts/run_local_pipeline.sh dirty-demo-01
```

Confirmed result: `patients` is quarantined
(`quarantine/dirty-demo-01/patients.csv`), `encounters` and `conditions`
cascade-skip, `organizations`/`providers`/`payers` load normally, and both
Slack and email fire a `PRE_VALIDATION_FAILED` alert naming the run id,
dataset, and failed checks. Five corruption strategies are available via
`--strategy`: `missing_required`, `bad_id_format`, `duplicate_ids`,
`bad_chronology`, `truncated`.

### 10b. Run the tests

```bash
pytest tests/ -q
```

10 tests cover cascade-skip propagation and the generic check engine,
including a regression test for a real bug found during development:
`pandas.to_datetime` silently drops mixed-format-date violations unless
`format="mixed"` is passed explicitly.

### 11. GitHub Actions (Phase 1 CI)

Add these repository secrets under **Settings > Secrets and variables >
Actions**: `GDRIVE_FOLDER_ID`, `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`,
`SNOWFLAKE_PASSWORD`, `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`, `SMTP_HOST`,
`SMTP_USER`, `SMTP_PASSWORD`. The workflow at
`.github/workflows/caresync_weekly.yml` runs on a weekly schedule and via
manual `workflow_dispatch`.

### 12. Phase 2: Great Expectations

```bash
pip install -r requirements-ge.txt
cd validation/great_expectations
great_expectations init
```

Author one suite per dataset in `expectations/`, mirroring the checks
already proven in `validation/pandas/rules_<dataset>.py`. See
[`validation/great_expectations/great_expectations.yml`](validation/great_expectations/great_expectations.yml)
for the full checklist.

### 13. Phase 2: Airflow

```bash
pip install -r requirements.txt -r requirements-airflow.txt
export AIRFLOW_HOME=./orchestration/airflow
airflow db init
airflow webserver -p 8080 &
airflow scheduler &
```

Place `orchestration/airflow/dags/caresync_dag.py` on your `dags_folder`
(default: `$AIRFLOW_HOME/dags`, already the case above). The DAG wires
per-dataset `GreatExpectationsOperator` pre-validation gates, Snowflake
loads with skip-and-cascade, `dbt run`, post-validation, and a
`notify_run_summary` task with `trigger_rule=ALL_DONE` so a run summary
fires even if an upstream task failed.

## Documentation

- [`docs/architecture.md`](docs/architecture.md): flow diagram, dependency map, two-stage comparison
- [`docs/data_dictionary.md`](docs/data_dictionary.md): source file schemas, PHI fields dropped, PROD star schema
- [`docs/notification_matrix.md`](docs/notification_matrix.md): every event, channel, and payload detail
- [`docs/runbook.md`](docs/runbook.md): what to do when a dataset is rejected, a task errors, or post-validation fails
- [`docs/google_drive_setup.md`](docs/google_drive_setup.md): full first-time Google Drive API setup
- [`docs/snowflake_setup.md`](docs/snowflake_setup.md): full first-time Snowflake account and CLI setup

## Business questions

SQL answers live in [`sql/business_questions.sql`](sql/business_questions.sql),
run against `CARESYNC_WH.PROD` and `CARESYNC_WH.AUDIT.RUN_AUDIT`.

## Contributing

1. Branch from `main`: `git checkout -b feature/<short-description>`
2. Keep pandas (Phase 1) and Great Expectations (Phase 2) logic in sync.
   A rule change in one should be mirrored in the other.
3. Run `pytest` before opening a PR.
4. Open a PR against `main`.

## License

MIT. See [`LICENSE`](LICENSE).
