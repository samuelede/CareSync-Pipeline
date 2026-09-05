"""
Day 2 deliverable: explore a real Synthea export and verify referential
integrity, distinct from the pre-validation engine (validation/pandas/),
which runs automatically on every pipeline run. This is a one-off,
human-run exploration step, its job is to catch data-dictionary drift
before it becomes a schemas.py bug, not to gate a pipeline run.

Usage:
    python -m scripts.explore_synthea_data --dir data/real_synthea_sample
    python -m scripts.explore_synthea_data --dir /path/to/full/synthea/export

What it checks, printed as a plain report:
    1. Column headers actually present per file, diffed against
       validation/pandas/schemas.py's SCHEMAS (catches schema drift, this
       is exactly how the MIDDLE/FIPS/INCOME/NPI/SYSTEM/hospice/snf gaps
       documented in schemas.py's docstring were originally found).
    2. Referential integrity: every encounter.PATIENT exists in
       patients.Id, every encounter.ORGANIZATION exists in
       organizations.Id, every encounter.PROVIDER exists in providers.Id,
       every non-null encounter.PAYER exists in payers.Id, every
       condition.ENCOUNTER exists in encounters.Id, every
       condition.PATIENT exists in patients.Id.
    3. Row-count sanity: prints min/max/mean per file so schemas.py's
       min_rows/max_rows bounds can be sanity-checked against real data
       shape rather than guessed.
"""
import argparse
import os

import pandas as pd

from validation.pandas.schemas import SCHEMAS


def load_all(data_dir: str) -> dict:
    datasets = {}
    for name in SCHEMAS:
        path = os.path.join(data_dir, f"{name}.csv")
        if not os.path.exists(path):
            print(f"  [skip] {name}.csv not found in {data_dir}")
            continue
        datasets[name] = pd.read_csv(path, dtype=str)
    return datasets


def check_schema_drift(datasets: dict):
    print("\n=== 1. Schema drift (actual columns vs schemas.py) ===")
    any_drift = False
    for name, df in datasets.items():
        expected = set(SCHEMAS[name]["columns"])
        actual = set(df.columns)
        missing = expected - actual
        extra = actual - expected
        if not missing and not extra:
            print(f"  {name}: matches schemas.py exactly ({len(actual)} columns)")
            continue
        any_drift = True
        if missing:
            print(f"  {name}: schemas.py expects but file lacks: {sorted(missing)}")
        if extra:
            print(f"  {name}: file has columns schemas.py doesn't expect: {sorted(extra)}")
    if not any_drift:
        print("  No drift found, schemas.py matches this export exactly.")


def check_referential_integrity(datasets: dict):
    print("\n=== 2. Referential integrity ===")
    if not {"patients", "encounters"}.issubset(datasets):
        print("  [skip] need patients + encounters loaded")
        return

    patients_ids = set(datasets["patients"]["Id"])
    encounters = datasets["encounters"]

    orphan_patients = encounters[~encounters["PATIENT"].isin(patients_ids)]
    print(f"  encounters with PATIENT not in patients.Id: {len(orphan_patients)}")

    if "organizations" in datasets:
        org_ids = set(datasets["organizations"]["Id"])
        orphan_orgs = encounters[~encounters["ORGANIZATION"].isin(org_ids)]
        print(f"  encounters with ORGANIZATION not in organizations.Id: {len(orphan_orgs)}")

    if "providers" in datasets:
        provider_ids = set(datasets["providers"]["Id"])
        orphan_providers = encounters[~encounters["PROVIDER"].isin(provider_ids)]
        print(f"  encounters with PROVIDER not in providers.Id: {len(orphan_providers)}")

    if "payers" in datasets:
        payer_ids = set(datasets["payers"]["Id"])
        has_payer = encounters["PAYER"].notna()
        orphan_payers = encounters[has_payer & ~encounters["PAYER"].isin(payer_ids)]
        print(f"  encounters with a non-null PAYER not in payers.Id: {len(orphan_payers)}")

    if "conditions" in datasets:
        conditions = datasets["conditions"]
        encounter_ids = set(encounters["Id"])
        orphan_cond_enc = conditions[~conditions["ENCOUNTER"].isin(encounter_ids)]
        print(f"  conditions with ENCOUNTER not in encounters.Id: {len(orphan_cond_enc)}")
        orphan_cond_pat = conditions[~conditions["PATIENT"].isin(patients_ids)]
        print(f"  conditions with PATIENT not in patients.Id: {len(orphan_cond_pat)}")


def check_row_counts(datasets: dict):
    print("\n=== 3. Row counts (compare against schemas.py min_rows/max_rows) ===")
    for name, df in datasets.items():
        bounds = SCHEMAS[name]
        n = len(df)
        in_bounds = bounds["min_rows"] <= n <= bounds["max_rows"]
        flag = "" if in_bounds else "  <-- OUTSIDE configured min_rows/max_rows"
        print(f"  {name}: {n} rows (schemas.py bounds: {bounds['min_rows']}-{bounds['max_rows']}){flag}")


def main(data_dir: str):
    print(f"Exploring Synthea export at: {data_dir}")
    datasets = load_all(data_dir)
    check_schema_drift(datasets)
    check_referential_integrity(datasets)
    check_row_counts(datasets)
    print("\nDone. Any drift or orphan rows above should be fixed in "
          "validation/pandas/schemas.py, not worked around downstream.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="data/real_synthea_sample",
                         help="Directory containing organizations.csv, providers.csv, "
                              "payers.csv, patients.csv, encounters.csv, conditions.csv")
    args = parser.parse_args()
    main(args.dir)
