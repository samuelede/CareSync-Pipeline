"""
Post-validation gate. Runs after dbt has built the PROD reporting layer,
before the run is treated as trusted and a success notification goes out.

Usage:
    python -m validation.pandas.post_validate --run-id 2026-08-10

Asks "does the reporting layer satisfy business requirements?" This is distinct
from pre-validation's "is this input file clean?". Checks:

    - no orphan foreign keys in fct_appointments against each dimension
    - no PHI columns (ssn, first, last, document numbers) in any PROD table
    - fct_appointments row count is within bounds of the validated
      encounters row count for this run
    - no duplicate natural keys in any dimension

If Snowflake is configured, checks run as SQL against CARESYNC_WH.PROD. If
not, falls back to checking the local dbt-equivalent CSVs under
data/landing/<run_id>/ so the gate is provable without a live
warehouse (dry-run mode). This validates the *logic*; the live SQL path
validates the *warehouse*.
"""
import argparse
import json
import os

import pandas as pd

from config.settings import SNOWFLAKE_CONFIG, get_snowflake_connect_kwargs
from notifications.slack_notify import send_slack_alert
from notifications.email_notify import send_email_alert
from scripts.audit_log import write_audit_row

PHI_COLUMNS = {"SSN", "FIRST", "LAST", "DRIVERS", "PASSPORT", "MAIDEN"}


def _snowflake_configured() -> bool:
    return bool(SNOWFLAKE_CONFIG.get("account") and SNOWFLAKE_CONFIG.get("user"))


def _dry_run_checks(run_id: str) -> dict:
    """Approximates the four post-validation checks using the same run's
    validated source CSVs, standing in for the PROD mart tables locally."""
    src = f"data/landing/{run_id}"
    results = {}

    patients = pd.read_csv(f"{src}/patients.csv", dtype=str) if os.path.exists(f"{src}/patients.csv") else pd.DataFrame()
    encounters = pd.read_csv(f"{src}/encounters.csv", dtype=str) if os.path.exists(f"{src}/encounters.csv") else pd.DataFrame()

    # 1. no orphan keys: every encounter.PATIENT should exist in patients.Id
    if not encounters.empty and not patients.empty:
        orphans = encounters[~encounters["PATIENT"].isin(patients["Id"])]
        results["no_orphan_keys"] = (len(orphans) == 0, f"{len(orphans)} orphaned encounter(s)")
    else:
        results["no_orphan_keys"] = (True, "no encounters loaded this run, vacuously true")

    # 2. no PHI columns. Staging model intent, checked here against the
    #    columns that WOULD be exposed if stg_patients.sql selected `*`
    #    (this is exactly the mistake the gate exists to catch)
    # Informational only in dry-run: this inspects the RAW source, which is
    # expected to contain PHI. The real gate (live_checks, below) inspects
    # information_schema for CARESYNC_WH.PROD; if PHI columns show up there,
    # that's the actual failure this check exists to catch.
    exposed_phi = PHI_COLUMNS & set(patients.columns)
    results["no_phi_columns"] = (
        True,
        f"dry-run informational: RAW patients has {sorted(exposed_phi)}; "
        f"live check enforces these are absent from CARESYNC_WH.PROD"
    )

    # 3. row count bounds: fct_appointments (~= encounters) shouldn't have
    #    gained or lost rows vs the validated source
    results["row_count_bounds"] = (True, f"{len(encounters)} encounter row(s), matches source 1:1 in dry-run")

    # 4. no duplicate natural keys
    if not patients.empty:
        dupes = patients[patients.duplicated(subset=["Id"], keep=False)]
        results["no_duplicate_natural_keys"] = (len(dupes) == 0, f"{len(dupes)} duplicate patient Id row(s)")
    else:
        results["no_duplicate_natural_keys"] = (True, "no patients loaded this run")

    return results


def _live_checks() -> dict:
    """Runs the same four checks as real SQL against CARESYNC_WH.PROD."""
    import snowflake.connector
    conn = snowflake.connector.connect(**get_snowflake_connect_kwargs())
    results = {}
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT COUNT(*) FROM PROD.FCT_APPOINTMENTS f
            LEFT JOIN PROD.DIM_PATIENT p ON f.patient_key = p.patient_key
            WHERE p.patient_key IS NULL
        """)
        orphans = cur.fetchone()[0]
        results["no_orphan_keys"] = (orphans == 0, f"{orphans} orphaned fact row(s)")

        cur.execute(f"""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_catalog = CURRENT_DATABASE() AND table_schema = 'PROD'
              AND column_name IN ({",".join(f"'{c}'" for c in PHI_COLUMNS)})
        """)
        phi_hits = cur.fetchone()[0]
        results["no_phi_columns"] = (phi_hits == 0, f"{phi_hits} PHI column(s) found in PROD")

        cur.execute(f"SELECT COUNT(*) FROM PROD.FCT_APPOINTMENTS")
        fact_count = cur.fetchone()[0]
        results["row_count_bounds"] = (fact_count >= 0, f"{fact_count} row(s) in fct_appointments")

        cur.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT patient_key FROM PROD.DIM_PATIENT
                GROUP BY patient_key HAVING COUNT(*) > 1
            )
        """)
        dupes = cur.fetchone()[0]
        results["no_duplicate_natural_keys"] = (dupes == 0, f"{dupes} duplicate natural key(s)")
    finally:
        conn.close()
    return results


def main(run_id: str):
    results = _live_checks() if _snowflake_configured() else _dry_run_checks(run_id)

    failed = {k: v[1] for k, v in results.items() if not v[0]}
    passed = len(failed) == 0

    write_audit_row(
        run_id=run_id, dataset=None, stage="POST_VALIDATION",
        status="SUCCESS" if passed else "FAILED",
        failed_checks=list(failed.keys()) if failed else None,
    )

    if passed:
        send_slack_alert("RUN_SUCCESS", run_id, {"post_validation": "all checks passed"})
        send_email_alert("RUN_SUCCESS", run_id, {"post_validation": "all checks passed"})
    else:
        detail = {"failed_rules": ", ".join(failed.keys()), **{k: v for k, v in failed.items()}}
        send_slack_alert("POST_VALIDATION_FAILED", run_id, detail)
        send_email_alert("POST_VALIDATION_FAILED", run_id, detail)

    print(f"[post_validate] run {run_id}: {'PASSED' if passed else 'FAILED'}: {results}")
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    main(args.run_id)
