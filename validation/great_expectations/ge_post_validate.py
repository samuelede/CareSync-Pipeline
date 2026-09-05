"""
Great Expectations post-validation, Phase 2's replacement for
validation/pandas/post_validate.py's _live_checks(). Same eight business
rules, same NEXORA_PROD_WH.PROD tables, different tooling: relevant PROD
data is fetched into a DataFrame via the same Snowflake connector the
rest of the pipeline already uses, then validated with real GE
expectations, the identical pattern proven in
validation/great_expectations/ge_validate.py for pre-validation. This
avoids depending on GE's native SQL/Snowflake datasource API, which
behaves differently from the pandas-backed API already proven correct,
and can't be exercised without a live warehouse in front of the person
building it.

Usage:
    python -m validation.great_expectations.ge_post_validate --run-id 2026-08-10

Selected the same way as pre-validation: set VALIDATION_ENGINE=great_expectations
in .env, and validation.pandas.post_validate dispatches here instead of
running its own pandas-based SQL checks. See config.settings.VALIDATION_ENGINE.
"""
import argparse

import great_expectations as gx
import pandas as pd

from config.settings import DATABASE_RAW, DATABASE_PROD, get_snowflake_connect_kwargs
from notifications.slack_notify import send_slack_alert
from notifications.email_notify import send_email_alert
from scripts.audit_log import write_audit_row

PHI_COLUMNS = {"SSN", "FIRST", "LAST", "DRIVERS", "PASSPORT", "MAIDEN"}
ALLOWED_ENCOUNTER_CLASSES = ["ambulatory", "emergency", "inpatient", "wellness",
                             "urgentcare", "outpatient", "home", "virtual",
                             "hospice", "snf"]

_context = None


def _get_context():
    global _context
    if _context is None:
        _context = gx.get_context(mode="ephemeral")
        _context.variables.progress_bars = {"globally": False}
    return _context


def _fetch_df(cur, query: str, params=None) -> pd.DataFrame:
    cur.execute(query, params or ())
    columns = [c[0].lower() for c in cur.description]  # Snowflake returns uppercase names for unquoted dbt columns
    return pd.DataFrame(cur.fetchall(), columns=columns)


def _has_datasource(context, name: str) -> bool:
    try:
        context.get_datasource(name)
        return True
    except ValueError:
        return False


def run_ge_post_validation(run_id: str) -> dict:
    import snowflake.connector
    conn = snowflake.connector.connect(**get_snowflake_connect_kwargs())
    try:
        cur = conn.cursor()

        fact_df = _fetch_df(cur, f"""
            SELECT encounter_id, patient_key, provider_key, clinic_key, payer_key,
                   start_ts, stop_ts, encounter_class,
                   base_encounter_cost, total_claim_cost, payer_coverage, _run_id
            FROM {DATABASE_PROD}.PROD.FCT_APPOINTMENTS
            WHERE _run_id = %s
        """, (run_id,))

        patients_df = _fetch_df(cur, f"SELECT patient_key FROM {DATABASE_PROD}.PROD.DIM_PATIENTS")
        known_patient_keys = patients_df["patient_key"].tolist()

        cur.execute(f"""
            SELECT COUNT(*) FROM (
                SELECT patient_key FROM {DATABASE_PROD}.PROD.DIM_PATIENTS
                GROUP BY patient_key HAVING COUNT(*) > 1
            )
        """)
        dim_dupes = cur.fetchone()[0]

        cur.execute(f"""
            SELECT COUNT(*) FROM information_schema.columns
            WHERE table_catalog = '{DATABASE_PROD}' AND table_schema = 'PROD'
              AND column_name IN ({",".join(f"'{c}'" for c in PHI_COLUMNS)})
        """)
        phi_hits = cur.fetchone()[0]

        cur.execute(f"SELECT COUNT(*) FROM {DATABASE_RAW}.RAW.ENCOUNTERS WHERE _run_id = %s", (run_id,))
        raw_count = cur.fetchone()[0]
    finally:
        conn.close()

    context = _get_context()
    ds_name = f"ge_pv_{run_id}"
    datasource = context.get_datasource(ds_name) if _has_datasource(context, ds_name) else context.sources.add_pandas(ds_name)
    asset_name = "fct_appointments_asset"
    try:
        asset = datasource.get_asset(asset_name)
    except LookupError:
        asset = datasource.add_dataframe_asset(name=asset_name)
    batch_request = asset.build_batch_request(dataframe=fact_df)
    suite_name = "post_validation_suite"
    context.add_or_update_expectation_suite(suite_name)
    validator = context.get_validator(batch_request=batch_request, expectation_suite_name=suite_name)

    results = {}
    n = len(fact_df)

    if n > 0:
        r = validator.expect_column_values_to_be_in_set(
            column="patient_key", value_set=known_patient_keys, result_format="SUMMARY"
        )
        orphans = r["result"]["unexpected_count"]
        results["no_orphan_keys"] = (orphans == 0, f"{orphans} orphaned fact row(s)")
    else:
        results["no_orphan_keys"] = (True, "no rows for this run")

    results["no_phi_columns"] = (phi_hits == 0, f"{phi_hits} PHI column(s) found in PROD")
    results["row_count_bounds"] = (True, f"{n} row(s) tagged with this run_id in fct_appointments")
    results["no_duplicate_natural_keys"] = (dim_dupes == 0, f"{dim_dupes} duplicate natural key(s)")
    results["reconciliation"] = (
        n == raw_count,
        f"{n} row(s) tagged with this run in fct_appointments vs {raw_count} loaded to RAW this run"
    )

    if n > 0:
        r_base = validator.expect_column_values_to_be_between(column="base_encounter_cost", min_value=0, result_format="SUMMARY")
        r_total = validator.expect_column_values_to_be_between(column="total_claim_cost", min_value=0, result_format="SUMMARY")
        r_coverage = validator.expect_column_values_to_be_between(column="payer_coverage", min_value=0, result_format="SUMMARY")
        over_covered = fact_df[
            fact_df["payer_coverage"].notna() & fact_df["total_claim_cost"].notna()
            & (fact_df["payer_coverage"] > fact_df["total_claim_cost"])
        ]
        bad_duration = fact_df[
            fact_df["stop_ts"].notna() & fact_df["start_ts"].notna()
            & (fact_df["stop_ts"] < fact_df["start_ts"])
        ]
        metric_ok = r_base["success"] and r_total["success"] and r_coverage["success"] \
            and len(over_covered) == 0 and len(bad_duration) == 0
        metric_errors = []
        if not r_base["success"]:
            metric_errors.append(f"{r_base['result']['unexpected_count']} negative base_encounter_cost value(s)")
        if not r_total["success"]:
            metric_errors.append(f"{r_total['result']['unexpected_count']} negative total_claim_cost value(s)")
        if not r_coverage["success"]:
            metric_errors.append(f"{r_coverage['result']['unexpected_count']} negative payer_coverage value(s)")
        if len(over_covered) > 0:
            metric_errors.append(f"{len(over_covered)} row(s) where payer_coverage exceeds total_claim_cost")
        if len(bad_duration) > 0:
            metric_errors.append(f"{len(bad_duration)} row(s) with negative duration")
        results["metric_validity"] = (metric_ok, "; ".join(metric_errors) if metric_errors else "all metrics valid")
    else:
        results["metric_validity"] = (True, "no rows for this run")

    if n > 0:
        r = validator.expect_column_values_to_be_in_set(
            column="encounter_class", value_set=ALLOWED_ENCOUNTER_CLASSES, result_format="SUMMARY"
        )
        bad = r["result"]["unexpected_count"]
        results["categorical_conformance"] = (bad == 0, f"{bad} disallowed encounter_class value(s)")
    else:
        results["categorical_conformance"] = (True, "no rows for this run")

    results["freshness"] = (n > 0, f"{n} row(s) tagged with this run_id in fct_appointments")

    return results


def main(run_id: str):
    results = run_ge_post_validation(run_id)
    failed = {k: v[1] for k, v in results.items() if not v[0]}
    passed = len(failed) == 0

    write_audit_row(
        run_id=run_id, dataset=None, stage="POST_VALIDATION",
        status="SUCCESS" if passed else "FAILED",
        failed_checks=list(failed.keys()) if failed else None,
    )

    if passed:
        send_slack_alert("RUN_SUCCESS", run_id, {"post_validation": "all checks passed (great_expectations)"})
        send_email_alert("RUN_SUCCESS", run_id, {"post_validation": "all checks passed (great_expectations)"})
    else:
        detail = {"failed_rules": ", ".join(failed.keys()), **{k: v for k, v in failed.items()}}
        send_slack_alert("POST_VALIDATION_FAILED", run_id, detail)
        send_email_alert("POST_VALIDATION_FAILED", run_id, detail)

    print(f"[ge_post_validate] run {run_id}: {'PASSED' if passed else 'FAILED'}: {results}")
    return passed


if __name__ == "__main__":
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    passed = main(args.run_id)
    sys.exit(0 if passed else 2)
