#!/usr/bin/env bash
# Runs the full Phase 1 pipeline locally, end to end, for a given run id.
# Mirrors the step order in .github/workflows/caresync_weekly.yml so local
# testing and CI never drift apart. Run from the repo root.
set -euo pipefail
RUN_ID="${1:?Usage: run_local_pipeline.sh <run_id>}"

python -m scripts.check_connections
python -m sensing.drive_sensor --run-id "$RUN_ID"
python -m validation.pandas.pre_validate --run-id "$RUN_ID"
python -m loaders.snowflake_loader --run-id "$RUN_ID"
(cd dbt_caresync && dbt run) || echo "[run_local_pipeline] dbt run skipped/failed, configure ~/.dbt/profiles.yml to run for real"
python -m validation.pandas.post_validate --run-id "$RUN_ID"
python -m scripts.send_run_summary --run-id "$RUN_ID"
