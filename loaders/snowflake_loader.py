"""
Loads pre-validated CSVs into Snowflake NEXORA_RAW_WH.RAW.

Usage:
    python -m loaders.snowflake_loader --run-id 2026-08-10

Behaviour:
    - Reads data/landing/<run_id>/validation_manifest.json
    - For every dataset with status == "VALID": PUT the local CSV to the
      dataset's internal stage, then COPY INTO the RAW table with
      FORCE=TRUE for idempotent re-runs of the same run_id.
    - For "REJECTED" / "SKIPPED" datasets: no-op, but an audit row is
      still written so the skip is visible in the audit trail.
    - Adds _run_id / _loaded_at metadata via the COPY INTO's default values
      (see sql/ddl_raw.sql).

If SNOWFLAKE_ACCOUNT is not configured (e.g. local/CI dry run), falls back
to a local "load" that just confirms the file is readable and logs what
would have been executed. This keeps the rest of the pipeline runnable
end-to-end without live Snowflake credentials.
"""
import argparse
import json

import pandas as pd

from config.settings import SNOWFLAKE_CONFIG, DATABASE_RAW, get_snowflake_connect_kwargs
from scripts.audit_log import write_audit_row
from validation.pandas.schemas import SCHEMAS

TABLE_MAP = {
    "organizations": "ORGANIZATIONS", "providers": "PROVIDERS", "payers": "PAYERS",
    "patients": "PATIENTS", "encounters": "ENCOUNTERS", "conditions": "CONDITIONS",
}


def _snowflake_configured() -> bool:
    return bool(SNOWFLAKE_CONFIG.get("account") and SNOWFLAKE_CONFIG.get("user"))


def load_dataset(dataset: str, run_id: str) -> int:
    """PUT + COPY INTO NEXORA_RAW_WH.RAW.<table> FORCE=TRUE. Returns row count loaded."""
    csv_path = f"data/landing/{run_id}/{dataset}.csv"
    table = TABLE_MAP[dataset]

    if not _snowflake_configured():
        df = pd.read_csv(csv_path, dtype=str)
        print(f"  [dry-run, no Snowflake creds] would PUT {csv_path} to @{dataset}_stage "
              f"and COPY INTO {DATABASE_RAW}.RAW.{table} FORCE=TRUE ({len(df)} rows)")
        return len(df)

    import snowflake.connector
    conn = snowflake.connector.connect(**get_snowflake_connect_kwargs())
    try:
        cur = conn.cursor()
        cur.execute(f"USE DATABASE {DATABASE_RAW}")
        cur.execute("USE SCHEMA RAW")
        cur.execute(f"PUT file://{csv_path} @%{table} OVERWRITE = TRUE")
        columns = SCHEMAS[dataset]["columns"]
        quoted_columns = ", ".join(f'"{c}"' for c in columns)
        cur.execute(f"""
            COPY INTO RAW.{table} ({quoted_columns})
            FROM @%{table}
            FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"')
            FORCE = TRUE
        """)
        result = cur.fetchall()
        rows_loaded = sum(r[3] for r in result) if result else 0
        cur.execute(f"UPDATE RAW.{table} SET _run_id = %s WHERE _run_id IS NULL", (run_id,))
        conn.commit()
        return rows_loaded
    finally:
        conn.close()


def main(run_id: str):
    manifest_path = f"data/landing/{run_id}/validation_manifest.json"
    with open(manifest_path) as f:
        manifest = json.load(f)

    for dataset, status in manifest.items():
        if status == "VALID":
            row_count = load_dataset(dataset, run_id)
            write_audit_row(run_id=run_id, dataset=dataset, stage="LOAD",
                             status="SUCCESS", row_count=row_count)
            print(f"[load] {dataset}: loaded {row_count} row(s)")
        else:
            write_audit_row(run_id=run_id, dataset=dataset, stage="LOAD",
                             status=status, row_count=0,
                             failed_checks=["not loaded, pre-validation status: " + status])
            print(f"[skip] {dataset}: {status}, not loaded, audit row written")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    main(args.run_id)
