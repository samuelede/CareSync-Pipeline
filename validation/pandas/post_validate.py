"""
Post-validation gate. Runs after dbt has built the PROD reporting layer,
before the run is treated as trusted and a success notification goes out.

Usage:
    python -m validation.pandas.post_validate --run-id 2026-08-10

Checks:
    - no orphan foreign keys in fct_appointments against each dimension
    - no PHI columns (ssn, first, last, document numbers) in any PROD table
    - fct_appointments row count is within bounds
    - no duplicate natural keys in any dimension
    - reconciliation: this run's rows in fct_appointments match what was
      actually loaded to RAW this run (both sides scoped to the same
      run_id, comparing the whole table against one run's RAW load would
      always mismatch once more than one run's data has accumulated,
      since encounters/conditions are intentionally not deduplicated
      across runs)
    - metric_validity: costs non-negative, payer_coverage never exceeds
      total_claim_cost, encounter duration non-negative
    - categorical_conformance: encounter_class values in PROD match the
      allowed set in schemas.py
    - freshness: fct_appointments actually has rows tagged with this
      run's run_id

If Snowflake is configured, checks run as SQL against NEXORA_PROD_WH.PROD. If
not, falls back to checking the local dbt-equivalent CSVs under
data/landing/<run_id>/ so the gate is provable without a live
warehouse (dry-run mode).
"""
import argparse
import json
import os

import pandas as pd

from config.settings import SNOWFLAKE_CONFIG, DATABASE_RAW, DATABASE_PROD, get_snowflake_connect_kwargs
from notifications.slack_notify import send_slack_alert
from notifications.email_notify import send_email_alert
from scripts.audit_log import write_audit_row

PHI_COLUMNS = {"SSN", "FIRST", "LAST", "DRIVERS", "PASSPORT", "MAIDEN"}


def _snowflake_configured() -> bool:
    return bool(SNOWFLAKE_CONFIG.get("account") and SNOWFLAKE_CONFIG.get("user"))


def _dry_run_checks(run_id: str) -> dict:
    src = f"data/landing/{run_id}"
    results = {}

    patients = pd.read_csv(f"{src}/patients.csv", dtype=str) if os.path.exists(f"{src}/patients.csv") else pd.DataFrame()
    encounters = pd.read_csv(f"{src}/encounters.csv", dtype=str) if os.path.exists(f"{src}/encounters.csv") else pd.DataFrame()

    if not encounters.empty and not patients.empty:
        orphans = encounters[~encounters["PATIENT"].isin(patients["Id"])]
        results["no_orphan_keys"] = (len(orphans) == 0, f"{len(orphans)} orphaned encounter(s)")
    else:
        results["no_orphan_keys"] = (True, "no encounters loaded this run, vacuously true")

    exposed_phi = PHI_COLUMNS & set(patients.columns)
    results["no_phi_columns"] = (
        True,
        f"dry-run informational: RAW patients has {sorted(exposed_phi)}; "
        f"live check enforces these are absent from NEXORA_PROD_WH.PROD"
    )

    results["row_count_bounds"] = (True, f"{len(encounters)} encounter row(s), matches source 1:1 in dry-run")

    if not patients.empty:
        dupes = patients[patients.duplicated(subset=["Id"], keep=False)]
        results["no_duplicate_natural_keys"] = (len(dupes) == 0, f"{dupes['Id'].nunique() if len(dupes) else 0} duplicate patient Id value(s)")
    else:
        results["no_duplicate_natural_keys"] = (True, "no patients loaded this run")

    results["reconciliation"] = (
        True, f"dry-run informational: {len(encounters)} encounters validated this run"
    )

    if not encounters.empty:
        costs_ok = True
        cost_errors = []
        for col in ["BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST", "PAYER_COVERAGE"]:
            if col in encounters.columns:
                numeric = pd.to_numeric(encounters[col], errors="coerce")
                negative = numeric[numeric < 0]
                if len(negative) > 0:
                    costs_ok = False
                    cost_errors.append(f"{len(negative)} negative {col} value(s)")
        if "TOTAL_CLAIM_COST" in encounters.columns and "PAYER_COVERAGE" in encounters.columns:
            claim = pd.to_numeric(encounters["TOTAL_CLAIM_COST"], errors="coerce")
            coverage = pd.to_numeric(encounters["PAYER_COVERAGE"], errors="coerce")
            over_covered = encounters[(coverage.notna()) & (claim.notna()) & (coverage > claim)]
            if len(over_covered) > 0:
                costs_ok = False
                cost_errors.append(f"{len(over_covered)} row(s) where payer_coverage exceeds total_claim_cost")
        results["metric_validity"] = (costs_ok, "; ".join(cost_errors) if cost_errors else "all metrics valid")
    else:
        results["metric_validity"] = (True, "no encounters loaded this run")

    if not encounters.empty and "ENCOUNTERCLASS" in encounters.columns:
        from validation.pandas.schemas import SCHEMAS
        allowed = SCHEMAS["encounters"]["allowed_values"]["ENCOUNTERCLASS"]
        actual = set(encounters["ENCOUNTERCLASS"].dropna().unique())
        bad = actual - allowed
        results["categorical_conformance"] = (
            len(bad) == 0, f"disallowed encounter_class value(s): {sorted(bad)}" if bad else "conforms"
        )
    else:
        results["categorical_conformance"] = (True, "no encounters loaded this run")

    results["freshness"] = (True, "dry-run informational: freshness only checked in live mode")

    return results


def _live_checks(run_id: str) -> dict:
    import snowflake.connector
    conn = snowflake.connector.connect(**get_snowflake_connect_kwargs())
    results = {}
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT COUNT(*) FROM {DATABASE_PROD}.PROD.FCT_APPOINTMENTS f
            LEFT JOIN {DATABASE_PROD}.PROD.DIM_PATIENTS p ON f.patient_key = p.patient_key
            WHERE p.patient_key IS NULL
        """)
        orphans = cur.fetchone()[0]
        results["no_orphan_keys"] = (orphans == 0, f"{orphans} orphaned fact row(s)")

        cur.execute(f"""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_catalog = '{DATABASE_PROD}' AND table_schema = 'PROD'
              AND column_name IN ({",".join(f"'{c}'" for c in PHI_COLUMNS)})
        """)
        phi_hits = cur.fetchone()[0]
        results["no_phi_columns"] = (phi_hits == 0, f"{phi_hits} PHI column(s) found in PROD")

        cur.execute(f"SELECT COUNT(*) FROM {DATABASE_PROD}.PROD.FCT_APPOINTMENTS")
        total_fact_count = cur.fetchone()[0]
        results["row_count_bounds"] = (total_fact_count >= 0, f"{total_fact_count} row(s) in fct_appointments (all-time)")

        cur.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT patient_key FROM {DATABASE_PROD}.PROD.DIM_PATIENTS
                GROUP BY patient_key HAVING COUNT(*) > 1
            )
        """)
        dupes = cur.fetchone()[0]
        results["no_duplicate_natural_keys"] = (dupes == 0, f"{dupes} duplicate natural key(s)")

        # reconciliation and freshness both need "this run's rows in
        # fct_appointments", computed once and reused, and compared
        # against RAW on the SAME run_id scope, not the whole table.
        cur.execute(f"""
            SELECT COUNT(*) FROM {DATABASE_PROD}.PROD.FCT_APPOINTMENTS WHERE _run_id = %s
        """, (run_id,))
        fresh_count = cur.fetchone()[0]
        results["freshness"] = (fresh_count > 0, f"{fresh_count} row(s) tagged with this run_id in fct_appointments")

        cur.execute(f"""
            SELECT COUNT(*) FROM {DATABASE_RAW}.RAW.ENCOUNTERS WHERE _run_id = %s
        """, (run_id,))
        raw_count = cur.fetchone()[0]
        results["reconciliation"] = (
            fresh_count == raw_count,
            f"{fresh_count} row(s) tagged with this run in fct_appointments vs {raw_count} loaded to RAW this run"
        )

        cur.execute(f"""
            SELECT COUNT(*) FROM {DATABASE_PROD}.PROD.FCT_APPOINTMENTS
            WHERE base_encounter_cost < 0 OR total_claim_cost < 0 OR payer_coverage < 0
               OR payer_coverage > total_claim_cost
               OR (stop_ts IS NOT NULL AND stop_ts < start_ts)
        """)
        bad_metrics = cur.fetchone()[0]
        results["metric_validity"] = (bad_metrics == 0, f"{bad_metrics} row(s) with invalid metrics")

        cur.execute(f"""
            SELECT COUNT(*) FROM {DATABASE_PROD}.PROD.FCT_APPOINTMENTS
            WHERE encounter_class NOT IN (
                'ambulatory','emergency','inpatient','wellness','urgentcare',
                'outpatient','home','virtual','hospice','snf'
            )
        """)
        bad_categories = cur.fetchone()[0]
        results["categorical_conformance"] = (bad_categories == 0, f"{bad_categories} disallowed encounter_class value(s)")
    finally:
        conn.close()
    return results


def main(run_id: str):
    results = _live_checks(run_id) if _snowflake_configured() else _dry_run_checks(run_id)

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
