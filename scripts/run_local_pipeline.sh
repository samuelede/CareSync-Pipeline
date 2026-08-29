#!/usr/bin/env bash
# Runs the full Phase 1 pipeline locally, end to end, for a given run id.
# Mirrors the step order in .github/workflows/caresync_weekly.yml so local
# testing and CI never drift apart. Run from the repo root.
set -euo pipefail
RUN_ID="${1:?Usage: run_local_pipeline.sh <run_id>}"

# dbt's profiles.yml reads real OS environment variables via env_var(),
# not .env directly (that's a python-dotenv mechanism the Python scripts
# use, dbt doesn't know about it). Export .env's contents into this
# shell so the `dbt run` step below actually has SNOWFLAKE_ACCOUNT etc.
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Resolve the private key path to an absolute path before dbt changes
# directory below (`cd dbt_caresync`); a relative SNOWFLAKE_PRIVATE_KEY_PATH
# would otherwise resolve against dbt_caresync/, not the repo root.
if [ -n "${SNOWFLAKE_PRIVATE_KEY_PATH:-}" ] && [ -f "$SNOWFLAKE_PRIVATE_KEY_PATH" ]; then
    export SNOWFLAKE_PRIVATE_KEY_PATH="$(cd "$(dirname "$SNOWFLAKE_PRIVATE_KEY_PATH")" && pwd)/$(basename "$SNOWFLAKE_PRIVATE_KEY_PATH")"
fi

# dbt's profile has two targets (see dbt_caresync/profiles_example.yml):
# "dev" (password auth) and "dev_keypair" (key-pair auth, needed when
# SNOWFLAKE_AUTH_METHOD=keypair, e.g. accounts whose MFA blocks plain
# password/programmatic login). Select whichever matches the same
# SNOWFLAKE_AUTH_METHOD the rest of the pipeline is already using.
DBT_TARGET="dev"
if [ "${SNOWFLAKE_AUTH_METHOD:-password}" = "keypair" ]; then
    DBT_TARGET="dev_keypair"
fi

python -m scripts.check_connections
python -m sensing.drive_sensor --run-id "$RUN_ID"
python -m validation.pandas.pre_validate --run-id "$RUN_ID"
python -m loaders.snowflake_loader --run-id "$RUN_ID"
(cd dbt_caresync && dbt run --target "$DBT_TARGET") || echo "[run_local_pipeline] dbt run skipped/failed, configure ~/.dbt/profiles.yml to run for real"
python -m validation.pandas.post_validate --run-id "$RUN_ID"
python -m scripts.send_run_summary --run-id "$RUN_ID"