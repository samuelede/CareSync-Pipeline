"""
Pre-validation gate. Runs before any file reaches Snowflake RAW.

Usage:
    python -m validation.pandas.pre_validate --run-id 2026-08-10

Validation engine is selectable via VALIDATION_ENGINE in .env: "pandas"
(default, Phase 1) or "great_expectations" (Phase 2). Both read the exact
same validation.pandas.schemas.SCHEMAS definitions, so switching engines
never changes which rules are enforced, only how they're checked, see
validation/great_expectations/ge_validate.py's docstring for how the two
were verified to agree on real data.

For each dataset in config.settings.DATASET_MANIFEST:
    1. Load the downloaded CSV from data/landing/<run_id>/<dataset>.csv
    2. Run every check via the selected engine's validate()
    3. If ALL pass -> mark dataset VALID, leave file in place for the loader
    4. If ANY fail  -> move file to quarantine/<run_id>/<dataset>.csv,
       mark dataset REJECTED, write failure detail to the run audit log,
       fire a Slack + email pre-validation-failure notification, and let
       cascade_skip() propagate the skip to dependents.

Output: data/landing/<run_id>/validation_manifest.json
"""
import argparse
import json
import os
import shutil

import pandas as pd

from config.settings import DATASET_MANIFEST, VALIDATION_ENGINE
from validation.pandas import (
    rules_organizations, rules_providers, rules_payers,
    rules_patients, rules_encounters, rules_conditions,
)
from notifications.slack_notify import send_slack_alert
from notifications.email_notify import send_email_alert
from scripts.audit_log import write_audit_row

PANDAS_RULES = {
    "organizations": rules_organizations,
    "providers": rules_providers,
    "payers": rules_payers,
    "patients": rules_patients,
    "encounters": rules_encounters,
    "conditions": rules_conditions,
}


def run_validation(dataset: str, df) -> tuple:
    """Dispatches to whichever engine VALIDATION_ENGINE selects. Both
    branches return the identical (is_valid, results) shape, so nothing
    downstream of this function needs to know or care which engine ran.
    """
    if VALIDATION_ENGINE == "great_expectations":
        from validation.great_expectations.ge_validate import validate as ge_validate
        return ge_validate(dataset, df)
    return PANDAS_RULES[dataset].validate(df)


def cascade_skip(status: dict) -> dict:
    """Propagate REJECTED status to dependents. Pure function, easy to unit test."""
    changed = True
    while changed:
        changed = False
        for dataset, meta in DATASET_MANIFEST.items():
            if status.get(dataset) == "VALID" and any(
                status.get(dep) in ("REJECTED", "SKIPPED") for dep in meta["depends_on"]
            ):
                status[dataset] = "SKIPPED"
                changed = True
    return status


def flatten_errors(results: dict) -> dict:
    """Turns {check: (passed, [errs])} into {failed_check: [errs]} for logging/alerting."""
    return {check: errs for check, (passed, errs) in results.items() if not passed}


def process_file(dataset: str, run_id: str) -> tuple:
    """Loads and validates one dataset's file. Returns (status, row_count, failed_checks)."""
    src_dir = f"data/landing/{run_id}"
    src_path = f"{src_dir}/{dataset}.csv"

    if not os.path.exists(src_path):
        return "REJECTED", 0, {"file_missing": [f"{src_path} not found"]}

    try:
        df = pd.read_csv(src_path, dtype=str)
    except Exception as exc:
        return "REJECTED", 0, {"parseability": [str(exc)]}

    is_valid, results = run_validation(dataset, df)
    row_count = len(df)

    if is_valid:
        return "VALID", row_count, {}

    failed = flatten_errors(results)
    quarantine_dir = f"quarantine/{run_id}"
    os.makedirs(quarantine_dir, exist_ok=True)
    shutil.move(src_path, f"{quarantine_dir}/{dataset}.csv")
    return "REJECTED", row_count, failed


def notify_rejection(run_id: str, dataset: str, failed_checks: dict, row_count: int):
    detail = {
        "dataset": dataset,
        "row_count": row_count,
        "failed_checks": ", ".join(failed_checks.keys()) or "unknown",
    }
    send_slack_alert("PRE_VALIDATION_FAILED", run_id, detail)
    send_email_alert("PRE_VALIDATION_FAILED", run_id, detail)


def main(run_id: str):
    status = {}
    row_counts = {}
    failures = {}

    for dataset in DATASET_MANIFEST:
        result_status, row_count, failed_checks = process_file(dataset, run_id)
        status[dataset] = result_status
        row_counts[dataset] = row_count
        if failed_checks:
            failures[dataset] = failed_checks

        write_audit_row(
            run_id=run_id, dataset=dataset, stage="PRE_VALIDATION",
            status=result_status, row_count=row_count,
            failed_checks=list(failed_checks.keys()) if failed_checks else None,
            quarantine_path=f"quarantine/{run_id}/{dataset}.csv" if result_status == "REJECTED" else None,
        )

        if result_status == "REJECTED":
            notify_rejection(run_id, dataset, failed_checks, row_count)

    status = cascade_skip(status)

    for dataset, final_status in status.items():
        if final_status == "SKIPPED" and dataset not in failures:
            write_audit_row(
                run_id=run_id, dataset=dataset, stage="PRE_VALIDATION",
                status="SKIPPED", row_count=row_counts.get(dataset, 0),
                failed_checks=["cascade_skip: upstream dependency rejected"],
                quarantine_path=None,
            )

    manifest_path = f"data/landing/{run_id}/validation_manifest.json"
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(status, f, indent=2)

    print(f"[pre_validate] run {run_id} (engine: {VALIDATION_ENGINE}): {status}")
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    main(args.run_id)
