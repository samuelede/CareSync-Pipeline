"""
Day 5 deliverable: a single batch that injects multiple distinct failure
modes across different files at once, matching the brief's "manufactured
bad batch proving a failing file is quarantined, its tasks skip,
dependents cascade-skip, notifications fire, and healthy files still
load" for real, with more than one corruption type demonstrated
simultaneously, not one strategy at a time (that's what
scripts.make_dirty_batch is for, still useful for testing one rule at a
time).

This batch corrupts two independent datasets with two different
strategies:
    - patients: missing_required (a blanked mandatory field)
    - organizations: bad_id_format (a malformed UUID)

Cascade consequence (per config.settings.DATASET_MANIFEST):
    patients      REJECTED (direct failure)
    organizations REJECTED (direct failure)
    providers     SKIPPED  (depends on organizations)
    payers        VALID    (independent of both)
    encounters    SKIPPED  (depends on patients AND organizations)
    conditions    SKIPPED  (depends on patients AND encounters)

Only payers should load. Two different pre-validation failure reasons
should appear in the audit trail and in Slack/email for this one run.

Usage:
    python -m scripts.make_comprehensive_dirty_batch --source-run-id 2026-08-10 --run-id comprehensive-dirty-01
"""
import argparse
import os
import shutil

from scripts.make_dirty_batch import corrupt_missing_required, corrupt_bad_id_format


def main(source_run_id: str, run_id: str):
    src = f"data/landing/{source_run_id}"
    dst = f"data/landing/{run_id}"
    if not os.path.exists(src):
        raise SystemExit(f"source run not found: {src}. Run simulate_weekly_drop first")
    shutil.copytree(src, dst, dirs_exist_ok=True)

    print(f"[make_comprehensive_dirty_batch] corrupting patients.csv (missing_required)")
    corrupt_missing_required(f"{dst}/patients.csv")

    print(f"[make_comprehensive_dirty_batch] corrupting organizations.csv (bad_id_format)")
    corrupt_bad_id_format(f"{dst}/organizations.csv")

    print(f"[make_comprehensive_dirty_batch] batch ready at {dst}")
    print("  expected outcome: patients + organizations REJECTED, "
          "providers + encounters + conditions SKIPPED (cascade), payers VALID")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    main(args.source_run_id, args.run_id)
