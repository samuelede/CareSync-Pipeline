"""
Writes one row per (run_id, dataset, stage) to the run audit trail.

Always writes locally to data/audit/run_audit.jsonl (append-only, one JSON
object per line) so the pipeline is fully testable without Snowflake
credentials. If Snowflake credentials are present in config.settings, also
inserts into CARESYNC_WH.AUDIT.RUN_AUDIT (see sql/run_audit_table.sql) so
production runs get the same audit trail in the warehouse.
"""
import json
import os
from datetime import datetime, timezone

LOCAL_AUDIT_PATH = "data/audit/run_audit.jsonl"


def write_audit_row(run_id: str, dataset: str, stage: str, status: str,
                     row_count: int = None, failed_checks: list = None,
                     quarantine_path: str = None, notified_slack: bool = False,
                     notified_email: bool = False):
    row = {
        "run_id": run_id,
        "dataset": dataset,
        "stage": stage,
        "status": status,
        "row_count": row_count,
        "failed_checks": failed_checks,
        "quarantine_path": quarantine_path,
        "notified_slack": notified_slack,
        "notified_email": notified_email,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    os.makedirs(os.path.dirname(LOCAL_AUDIT_PATH), exist_ok=True)
    with open(LOCAL_AUDIT_PATH, "a") as f:
        f.write(json.dumps(row) + "\n")

    _write_to_snowflake_if_configured(row)
    return row


def _write_to_snowflake_if_configured(row: dict):
    from config.settings import SNOWFLAKE_CONFIG
    if not SNOWFLAKE_CONFIG.get("account"):
        return  # no Snowflake configured locally, local jsonl is source of truth for now
    try:
        import snowflake.connector
        conn = snowflake.connector.connect(**SNOWFLAKE_CONFIG)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO CARESYNC_WH.AUDIT.RUN_AUDIT
                (run_id, dataset, stage, status, row_count, failed_checks,
                 quarantine_path, notified_slack, notified_email)
            SELECT %(run_id)s, %(dataset)s, %(stage)s, %(status)s, %(row_count)s,
                   PARSE_JSON(%(failed_checks_json)s), %(quarantine_path)s,
                   %(notified_slack)s, %(notified_email)s
            """,
            {**row, "failed_checks_json": json.dumps(row["failed_checks"])},
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:
        print(f"[audit_log] Snowflake write skipped/failed: {exc}")


def read_run(run_id: str) -> list:
    """Reads all local audit rows for a run_id, used by scripts/send_run_summary.py."""
    if not os.path.exists(LOCAL_AUDIT_PATH):
        return []
    rows = []
    with open(LOCAL_AUDIT_PATH) as f:
        for line in f:
            row = json.loads(line)
            if row["run_id"] == run_id:
                rows.append(row)
    return rows
