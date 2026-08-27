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
├── config/          # connection settings, dataset dependency manifest
├── sensing/         # Google Drive polling + 1h SLA check
├── validation/      # pandas (Phase 1) and Great Expectations (Phase 2) validation engines
├── loaders/         # Snowflake loading, skip-not-fail semantics
├── dbt_caresync/    # staging models (PHI dropped) + star schema marts
├── notifications/   # Slack + email, full event matrix
├── orchestration/   # Airflow DAG (Phase 2); GitHub Actions workflow lives in .github/workflows/
├── sql/             # warehouse DDL, run audit table, business questions
├── quarantine/       # rejected files, keyed by run id
├── data/landing/    # the drop zone (local now, SFTP in Week 3, same interface)
├── scripts/         # setup automation, data simulation, dirty-batch demo, connection checks
├── tests/           # unit tests
└── docs/            # architecture, setup guides, ER diagram, full structure reference
```

Full file-by-file tree: [`docs/project_structure.md`](docs/project_structure.md)

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

**Google Drive is not required to run this pipeline.** If you'd rather
skip API setup for now (or come back to it later), copy weekly CSV files
straight into `data/landing/<run_id>/` yourself, no Drive account, no
credentials, no code changes. Set `GDRIVE_FORCE_LOCAL=true` in `.env` to
force this mode even if Drive credentials exist on disk, so you can leave
partially finished OAuth/service account setup in place without it
interfering:

```bash
mkdir -p data/landing/2026-08-10
# copy organizations.csv, providers.csv, payers.csv, patients.csv,
# encounters.csv, conditions.csv into that folder, or generate synthetic
# ones instead:
python -m scripts.simulate_weekly_drop --run-id 2026-08-10
```

`sensing/drive_sensor.py` reads from this same folder either way, live
Drive downloads land here too, so nothing downstream (`pre_validate.py`,
the loader, dbt) knows or cares whether a file arrived via Drive or was
copied in by hand.

### 3. Snowflake

```bash
python -m scripts.check_connections
```

If Snowflake reports `OK`, you're already configured, skip ahead. If it
reports `SKIPPED` or `FAILED`, see
[`docs/snowflake_setup.md`](docs/snowflake_setup.md) for full first-time
setup: creating a trial account, installing SnowSQL, and running the DDL
to create the warehouse and the three databases.

**Database design.** Three databases, one per pipeline layer:
`NEXORA_RAW_WH` (faithful, string-typed copies of validated files),
`NEXORA_STAGING_WH` (typed and standardized), `NEXORA_PROD_WH` (the reporting
marts). Each has one schema of the same name; the run audit trail lives
in `NEXORA_RAW_WH.AUDIT`. dbt reads `NEXORA_RAW_WH` as a cross-database source
and writes marts into `NEXORA_PROD_WH` via `+database:` overrides in
`dbt_project.yml`, see `docs/architecture.md` for the full layout.

### 4. Slack

Recommended channel name: `#nexora-data-alerts`, matching the project brief.

1. Create the channel: in Slack, **+ > Create channel**, name it `nexora-data-alerts`.
2. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps), choosing *From scratch*.
3. Add bot token scopes `chat:write` and `channels:read` (use `groups:read` instead of `channels:read` if the channel is private), install the app to your workspace.
4. Invite the bot to `#nexora-data-alerts` (`/invite @your-app-name`).
5. Copy the channel ID (right-click the channel name > **View channel details**, ID is at the bottom).
6. Set `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` in `.env`.

`channels:read`/`groups:read` is needed for `scripts.check_connections` to confirm the channel is reachable; `chat:write` alone will send messages fine but the connection check will report `missing_scope`. Added a scope after installing? Click **Reinstall to Workspace** on the same page and re-copy the token, it may change.

### 5. Email

Default provider is [Resend](https://resend.com), no app passwords, one API key.

1. Sign up at [resend.com](https://resend.com).
2. Copy your API key from the Resend dashboard. A "Sending access" key is fine, no need for "Full access."
3. Set `RESEND_API_KEY` and `NOTIFY_EMAIL_TO` in `.env`. Leave `RESEND_FROM_EMAIL` at its default (`onboarding@resend.dev`), Resend's built-in test sender that works with zero setup; verify your own domain later if you want a branded from-address.

Prefer SMTP instead (Gmail app password, SES, SendGrid)? Set `EMAIL_PROVIDER=smtp` and fill in `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`.

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
- [`docs/entity_relationship.md`](docs/entity_relationship.md): star schema ER diagram, grain, cardinality
- [`docs/project_structure.md`](docs/project_structure.md): full file-by-file project tree

## Business questions

SQL answers live in [`sql/business_questions.sql`](sql/business_questions.sql),
run against `NEXORA_PROD_WH.PROD` and `NEXORA_RAW_WH.AUDIT.RUN_AUDIT`.

## Contributing

1. Branch from `main`: `git checkout -b feature/<short-description>`
2. Keep pandas (Phase 1) and Great Expectations (Phase 2) logic in sync.
   A rule change in one should be mirrored in the other.
3. Run `pytest` before opening a PR.
4. Open a PR against `main`.

## License

[MIT](LICENSE)
