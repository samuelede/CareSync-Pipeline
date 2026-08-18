"""
Manufactures the dirty-data demonstration batch required by the spec:
takes a clean simulated run and deliberately corrupts one file so the
full skip-and-cascade-and-notify path can be proven end to end.

Usage:
    python -m scripts.make_dirty_batch --source-run-id 2026-08-10 --run-id dirty-demo-01 --target patients

Then run the pipeline against the new run id, e.g.:
    python -m validation.pandas.pre_validate --run-id dirty-demo-01

Expected outcome: --target dataset is quarantined, its dependents
cascade-skip (per DATASET_MANIFEST), all other files load normally, and
Slack + email fire a PRE_VALIDATION_FAILED notification naming the run
id, dataset, and failed checks.
"""
import argparse
import os
import shutil

import pandas as pd


def corrupt_missing_required(path: str):
    """Blanks out a mandatory column on ~20% of rows."""
    df = pd.read_csv(path, dtype=str)
    mandatory_candidates = [c for c in ["BIRTHDATE", "NAME", "START", "GENDER"] if c in df.columns]
    col = mandatory_candidates[0] if mandatory_candidates else df.columns[0]
    n = max(1, int(len(df) * 0.2))
    idx = df.sample(n=n, random_state=42).index
    df.loc[idx, col] = ""
    df.to_csv(path, index=False)
    print(f"  blanked '{col}' on {n} row(s)")


def corrupt_bad_id_format(path: str):
    """Replaces the primary key on a few rows with a non-UUID string."""
    df = pd.read_csv(path, dtype=str)
    id_col = "Id" if "Id" in df.columns else df.columns[0]
    n = min(3, len(df))
    idx = df.sample(n=n, random_state=42).index
    df.loc[idx, id_col] = ["not-a-uuid-" + str(i) for i in range(n)]
    df.to_csv(path, index=False)
    print(f"  corrupted '{id_col}' format on {n} row(s)")


def corrupt_duplicate_ids(path: str):
    """Duplicates a handful of existing primary key rows."""
    df = pd.read_csv(path, dtype=str)
    n = min(3, len(df))
    dupes = df.sample(n=n, random_state=42)
    df = pd.concat([df, dupes], ignore_index=True)
    df.to_csv(path, index=False)
    print(f"  duplicated {n} row(s)")


def corrupt_bad_chronology(path: str):
    """Sets an end-date column earlier than its start-date column."""
    df = pd.read_csv(path, dtype=str)
    pairs = [("BIRTHDATE", "DEATHDATE"), ("START", "STOP")]
    start_col, end_col = next(((s, e) for s, e in pairs if s in df.columns and e in df.columns), (None, None))
    if not start_col:
        print("  no chronology pair found in this file, skipping")
        return
    n = min(3, len(df))
    idx = df.sample(n=n, random_state=42).index
    df.loc[idx, end_col] = "1900-01-01"
    df.to_csv(path, index=False)
    print(f"  set '{end_col}' before '{start_col}' on {n} row(s)")


def corrupt_truncated(path: str):
    """Writes only the header + first row, simulating a cut-off transfer."""
    df = pd.read_csv(path, dtype=str)
    df.head(1).to_csv(path, index=False)
    print("  truncated file to 1 data row")


STRATEGIES = {
    "missing_required": corrupt_missing_required,
    "bad_id_format": corrupt_bad_id_format,
    "duplicate_ids": corrupt_duplicate_ids,
    "bad_chronology": corrupt_bad_chronology,
    "truncated": corrupt_truncated,
}


def main(source_run_id, run_id, target, strategy):
    src = f"data/landing/{source_run_id}"
    dst = f"data/landing/{run_id}"
    if not os.path.exists(src):
        raise SystemExit(f"source run not found: {src}. Run simulate_weekly_drop first")
    shutil.copytree(src, dst, dirs_exist_ok=True)
    target_path = f"{dst}/{target}.csv"
    STRATEGIES[strategy](target_path)
    print(f"[make_dirty_batch] dirty batch ready at {dst} ({target}.csv corrupted via '{strategy}')")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target", required=True, choices=[
        "organizations", "providers", "payers", "patients", "encounters", "conditions"
    ])
    parser.add_argument("--strategy", default="missing_required", choices=list(STRATEGIES.keys()))
    args = parser.parse_args()
    main(args.source_run_id, args.run_id, args.target, args.strategy)
