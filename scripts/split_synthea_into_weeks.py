"""
Day 4 deliverable: slices a real, historical Synthea export into weekly
delivery batches, matching what the third-party aggregation agent's
weekly drop actually looks like, rather than generating synthetic data
from scratch (that's scripts.simulate_weekly_drop, still useful for
zero-setup local testing, but not a substitute for this).

For each ISO week present in the export's encounters.START range, writes
a folder shaped exactly like a real weekly delivery:

    <out_dir>/<week_start>/organizations.csv   (full dimension snapshot)
    <out_dir>/<week_start>/providers.csv       (full dimension snapshot)
    <out_dir>/<week_start>/payers.csv          (full dimension snapshot)
    <out_dir>/<week_start>/patients.csv        (full dimension snapshot)
    <out_dir>/<week_start>/encounters.csv      (only that week's encounters)
    <out_dir>/<week_start>/conditions.csv      (only conditions on those encounters)

Dimension tables (organizations/providers/payers/patients) are snapshotted
in full for every week rather than diffed, matching how Synthea itself
has no natural "this week's new patients" concept, a real weekly agent
delivery would most likely re-send the current full dimension state
alongside that week's activity.

Usage:
    python -m scripts.split_synthea_into_weeks --source data/real_synthea_sample --out data/weekly_splits
    python -m scripts.split_synthea_into_weeks --source /path/to/full/export --out data/weekly_splits --limit-weeks 8

Each output folder can be copied directly into data/landing/<run_id>/ and
run through the pipeline exactly like any other weekly batch, sensing,
pre_validate, the loader, and dbt don't know or care whether a file came
from here, scripts.simulate_weekly_drop, or a real Drive folder.
"""
import argparse
import os
import shutil

import pandas as pd


def load_source(source_dir: str) -> dict:
    datasets = {}
    for name in ["organizations", "providers", "payers", "patients", "encounters", "conditions"]:
        path = os.path.join(source_dir, f"{name}.csv")
        datasets[name] = pd.read_csv(path, dtype=str)
    return datasets


def week_start_of(timestamp: pd.Timestamp) -> str:
    """Returns the Monday of that timestamp's ISO week, as YYYY-MM-DD."""
    monday = timestamp - pd.Timedelta(days=timestamp.weekday())
    return monday.strftime("%Y-%m-%d")


def split_into_weeks(datasets: dict, out_dir: str, limit_weeks: int = None) -> list:
    encounters = datasets["encounters"].copy()
    encounters["_start_ts"] = pd.to_datetime(encounters["START"], errors="coerce", format="mixed")
    encounters = encounters.dropna(subset=["_start_ts"])
    encounters["_week"] = encounters["_start_ts"].apply(week_start_of)

    weeks = sorted(encounters["_week"].unique())
    if limit_weeks:
        weeks = weeks[-limit_weeks:]  # most recent N weeks, matches a real rolling delivery window

    conditions = datasets["conditions"]
    written = []

    for week in weeks:
        week_dir = os.path.join(out_dir, week)
        os.makedirs(week_dir, exist_ok=True)

        for name in ["organizations", "providers", "payers", "patients"]:
            datasets[name].to_csv(os.path.join(week_dir, f"{name}.csv"), index=False)

        week_encounters = encounters[encounters["_week"] == week].drop(columns=["_start_ts", "_week"])
        week_encounters.to_csv(os.path.join(week_dir, "encounters.csv"), index=False)

        week_encounter_ids = set(week_encounters["Id"])
        week_conditions = conditions[conditions["ENCOUNTER"].isin(week_encounter_ids)]
        week_conditions.to_csv(os.path.join(week_dir, "conditions.csv"), index=False)

        written.append((week, len(week_encounters), len(week_conditions)))

    return written


def main(source: str, out: str, limit_weeks: int):
    if os.path.exists(out):
        shutil.rmtree(out)
    datasets = load_source(source)
    written = split_into_weeks(datasets, out, limit_weeks)

    print(f"Split {source} into {len(written)} weekly batch(es) under {out}/")
    for week, n_enc, n_cond in written:
        print(f"  {week}: {n_enc} encounters, {n_cond} conditions")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="data/real_synthea_sample",
                         help="Directory with a full historical Synthea CSV export")
    parser.add_argument("--out", default="data/weekly_splits",
                         help="Directory to write <week_start>/ folders into")
    parser.add_argument("--limit-weeks", type=int, default=None,
                         help="Only keep the N most recent weeks (default: all)")
    args = parser.parse_args()
    main(args.source, args.out, args.limit_weeks)
