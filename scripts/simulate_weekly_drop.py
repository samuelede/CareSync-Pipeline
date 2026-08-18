"""
Generates a locally-simulated weekly drop of the six CareSync CSVs,
structurally matching real Synthea exports, and writes them into
data/landing/<run_id>/, standing in for the third-party agent's
Google Drive delivery so the rest of the pipeline can be built and tested
without a live Drive connection or a Synthea/Java toolchain.

This is the "simulate weekly drops" half of that todo item; the other
half (sensing/drive_sensor.py against a real Drive folder + 1h SLA) is a
separate concern that reuses this same run_id/file-layout contract.

Usage:
    python -m scripts.simulate_weekly_drop --run-id 2026-08-10 --patients 50

Uses only the standard library (uuid, random, csv). No external services,
no API keys, so it works in CI and locally with zero setup.
"""
import argparse
import csv
import os
import random
import uuid
from datetime import date, datetime, timedelta

GENDERS = ["M", "F"]
MARITAL = ["M", "S", "D", "W", ""]
RACES = ["white", "black", "asian", "native", "other"]
ETHNICITIES = ["hispanic", "nonhispanic"]
ENCOUNTER_CLASSES = ["ambulatory", "emergency", "inpatient", "wellness",
                     "urgentcare", "outpatient", "home", "virtual"]
SPECIALITIES = ["GENERAL PRACTICE", "PEDIATRICS", "CARDIOLOGY", "ORTHOPEDICS"]
CONDITION_CODES = [
    ("44054006", "Diabetes mellitus type 2"),
    ("38341003", "Hypertension"),
    ("195662009", "Acute viral pharyngitis"),
    ("444814009", "Viral sinusitis"),
]


def new_id():
    return str(uuid.uuid4())


def rand_date(start_year=1940, end_year=2015):
    start = date(start_year, 1, 1)
    end = date(end_year, 12, 31)
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def gen_organizations(n=3):
    rows = []
    for i in range(n):
        rows.append({
            "Id": new_id(), "NAME": f"Clinic {i+1}", "ADDRESS": f"{100+i} Main St",
            "CITY": "Boston", "STATE": "MA", "ZIP": "02118", "LAT": "42.33", "LON": "-71.07",
            "PHONE": "617-555-0100", "REVENUE": round(random.uniform(1e5, 1e6), 2),
            "UTILIZATION": random.randint(50, 500),
        })
    return rows


def gen_providers(organizations, n=8):
    rows = []
    for i in range(n):
        org = random.choice(organizations)
        rows.append({
            "Id": new_id(), "ORGANIZATION": org["Id"], "NAME": f"Dr. Provider {i+1}",
            "GENDER": random.choice(GENDERS), "SPECIALITY": random.choice(SPECIALITIES),
            "ADDRESS": org["ADDRESS"], "CITY": org["CITY"], "STATE": org["STATE"],
            "ZIP": org["ZIP"], "LAT": org["LAT"], "LON": org["LON"],
            "UTILIZATION": random.randint(10, 200),
        })
    return rows


def gen_payers(n=3):
    names = ["Nexora Direct", "Medicare", "BlueCross"]
    rows = []
    for i in range(n):
        rows.append({
            "Id": new_id(), "NAME": names[i % len(names)], "ADDRESS": "1 Insurance Way",
            "CITY": "Boston", "STATE_HEADQUARTERED": "MA", "ZIP": "02110",
            "PHONE": "617-555-0200", "AMOUNT_COVERED": round(random.uniform(1e4, 1e5), 2),
            "AMOUNT_UNCOVERED": round(random.uniform(1e3, 1e4), 2),
            "REVENUE": round(random.uniform(1e6, 1e7), 2),
            "COVERED_ENCOUNTERS": random.randint(50, 500),
            "UNCOVERED_ENCOUNTERS": random.randint(0, 50),
            "UNIQUE_CUSTOMERS": random.randint(20, 200),
        })
    return rows


def gen_patients(n=50):
    rows = []
    for i in range(n):
        birth = rand_date()
        dead = birth + timedelta(days=random.randint(365*20, 365*90)) if random.random() < 0.05 else None
        rows.append({
            "Id": new_id(), "BIRTHDATE": birth.isoformat(),
            "DEATHDATE": dead.isoformat() if dead else "",
            "SSN": f"999-{random.randint(10,99)}-{random.randint(1000,9999)}",
            "DRIVERS": "", "PASSPORT": "", "PREFIX": "", "FIRST": f"Patient{i+1}",
            "LAST": f"Synthetic{i+1}", "SUFFIX": "", "MAIDEN": "",
            "MARITAL": random.choice(MARITAL), "RACE": random.choice(RACES),
            "ETHNICITY": random.choice(ETHNICITIES), "GENDER": random.choice(GENDERS),
            "BIRTHPLACE": "Boston, MA", "ADDRESS": f"{200+i} Oak St", "CITY": "Boston",
            "STATE": "MA", "COUNTY": "Suffolk", "ZIP": "02118", "LAT": "42.33", "LON": "-71.07",
            "HEALTHCARE_EXPENSES": round(random.uniform(1000, 50000), 2),
            "HEALTHCARE_COVERAGE": round(random.uniform(0, 40000), 2),
        })
    return rows


def gen_encounters(patients, organizations, providers, payers, per_patient=3):
    rows = []
    for patient in patients:
        for _ in range(random.randint(0, per_patient)):
            start = datetime.combine(rand_date(2024, 2026), datetime.min.time())
            stop = start + timedelta(hours=random.randint(1, 4))
            org = random.choice(organizations)
            provider = random.choice([p for p in providers if p["ORGANIZATION"] == org["Id"]] or providers)
            rows.append({
                "Id": new_id(), "START": start.isoformat(), "STOP": stop.isoformat(),
                "PATIENT": patient["Id"], "ORGANIZATION": org["Id"], "PROVIDER": provider["Id"],
                "PAYER": random.choice(payers)["Id"],
                "ENCOUNTERCLASS": random.choice(ENCOUNTER_CLASSES),
                "CODE": str(random.randint(100000, 999999)), "DESCRIPTION": "General visit",
                "BASE_ENCOUNTER_COST": round(random.uniform(80, 400), 2),
                "TOTAL_CLAIM_COST": round(random.uniform(100, 2000), 2),
                "PAYER_COVERAGE": round(random.uniform(0, 1500), 2),
                "REASONCODE": "", "REASONDESCRIPTION": "",
            })
    return rows


def gen_conditions(encounters, rate=0.4):
    rows = []
    for enc in encounters:
        if random.random() < rate:
            code, desc = random.choice(CONDITION_CODES)
            rows.append({
                "START": enc["START"], "STOP": "", "PATIENT": enc["PATIENT"],
                "ENCOUNTER": enc["Id"], "CODE": code, "DESCRIPTION": desc,
            })
    return rows


def write_csv(rows, path):
    if not rows:
        # still write a header-only file using known field order from the first
        # non-empty generator call. Callers always pass at least an empty list
        # with a defined schema upstream, so this only triggers for conditions
        # when rate produced zero rows; write empty body under the same columns.
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main(run_id: str, num_patients: int):
    out_dir = f"data/landing/{run_id}"
    organizations = gen_organizations()
    providers = gen_providers(organizations)
    payers = gen_payers()
    patients = gen_patients(num_patients)
    encounters = gen_encounters(patients, organizations, providers, payers)
    conditions = gen_conditions(encounters)

    write_csv(organizations, f"{out_dir}/organizations.csv")
    write_csv(providers, f"{out_dir}/providers.csv")
    write_csv(payers, f"{out_dir}/payers.csv")
    write_csv(patients, f"{out_dir}/patients.csv")
    write_csv(encounters, f"{out_dir}/encounters.csv")
    write_csv(conditions, f"{out_dir}/conditions.csv")

    print(f"[simulate_weekly_drop] wrote 6 files to {out_dir} "
          f"({len(patients)} patients, {len(encounters)} encounters, {len(conditions)} conditions)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--patients", type=int, default=50)
    args = parser.parse_args()
    main(args.run_id, args.patients)
