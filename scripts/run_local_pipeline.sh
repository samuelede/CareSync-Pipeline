#!/usr/bin/env bash
# Runs the full Phase 1 pipeline locally, end to end, for a given run id.
# Mirrors the step order in .github/workflows/caresync_weekly.yml so local
# testing and CI never drift apart. Run from the repo root.
set -euo pipefail
RUN_ID="${1:?Usage: run_local_pipeline.sh <run_id>}"

if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

if [ -n "${SNOWFLAKE_PRIVATE_KEY_PATH:-}" ] && [ -f "$SNOWFLAKE_PRIVATE_KEY_PATH" ]; then
    export SNOWFLAKE_PRIVATE_KEY_PATH="$(cd "$(dirname "$SNOWFLAKE_PRIVATE_KEY_PATH")" && pwd)/$(basename "$SNOWFLAKE_PRIVATE_KEY_PATH")"
fi

DBT_TARGET="dev"
if [ "${SNOWFLAKE_AUTH_METHOD:-password}" = "keypair" ]; then
    DBT_TARGET="dev_keypair"
fi

# TASK_ERROR: fires only when a step crashes unexpectedly (a Python
# exception -> non-zero exit), not when pre_validate/post_validate report
# REJECTED/FAILED on data, those are handled explicitly below and already
# send their own specific alerts.
CURRENT_STEP="unknown step"
on_error() {
    python -m scripts.notify_task_error "$RUN_ID" "$CURRENT_STEP" || true
}
trap on_error ERR

FINAL_EXIT_CODE=0

CURRENT_STEP="scripts.check_connections"
python -m scripts.check_connections

CURRENT_STEP="sensing.drive_sensor"
python -m sensing.drive_sensor --run-id "$RUN_ID"

CURRENT_STEP="validation.pandas.pre_validate"
python -m validation.pandas.pre_validate --run-id "$RUN_ID"

CURRENT_STEP="loaders.snowflake_loader"
python -m loaders.snowflake_loader --run-id "$RUN_ID"

CURRENT_STEP="dbt run"
(cd dbt_caresync && dbt run --target "$DBT_TARGET") || echo "[run_local_pipeline] dbt run skipped/failed, configure ~/.dbt/profiles.yml to run for real"

# post_validate exits: 0 = passed, 2 = business-rule failure (already
# alerted via Slack/email inside post_validate.py itself, so the ERR trap
# must NOT also fire a redundant TASK_ERROR for this), anything else =
# a genuine crash, handled the normal way. `set +e`/`set -e` alone do NOT
# suppress the ERR trap, so the trap must be explicitly disabled and
# restored around this one call, otherwise it fires on ANY non-zero exit
# regardless of set -e state.
CURRENT_STEP="validation.pandas.post_validate"
trap - ERR
set +e
python -m validation.pandas.post_validate --run-id "$RUN_ID"
PV_EXIT=$?
set -e
trap on_error ERR

if [ "$PV_EXIT" -eq 2 ]; then
    echo "[run_local_pipeline] post-validation failed business-rule checks; already alerted, marking this run as failed"
    FINAL_EXIT_CODE=1
elif [ "$PV_EXIT" -ne 0 ]; then
    trap - ERR
    on_error
    exit "$PV_EXIT"
fi

CURRENT_STEP="scripts.send_run_summary"
python -m scripts.send_run_summary --run-id "$RUN_ID"

exit "$FINAL_EXIT_CODE"
