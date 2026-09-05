"""
Generates a locally-simulated weekly drop of the six CareSync CSVs,
structurally matching real Synthea exports, and writes them into
data/landing/<run_id>/, standing in for the third-party agent's Google
Drive delivery so the rest of the pipeline can be built and tested
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
                     "urgentcare", "outpatient", "home", "virtual",
                     "hospice", "snf"]
SPECIALITIES = ["GENERAL PRACTICE", "PEDIATRICS", "CARDIOLOGY", "ORTHOPEDICS"]
CONDITION_SYSTEM = "http://snomed.info/sct"
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
    return [{
        "Id": new_id(), "NAME": f"Clinic {i+1}", "ADDRESS": f"{100+i} Main St",
        "CITY": "Boston", "STATE": "MA", "ZIP": "02118", "LAT": "42.33", "LON": "-71.07",
        "PHONE": "617-555-0100", "REVENUE": round(random.uniform(1e5, 1e6), 2),
        "UTILIZATION": random.randint(50, 500),
        "NPI": str(random.randint(1000000000, 9999999999)),
    } for i in range(n)]


def gen_providers(organizations, n=8):
    return [{
        "Id": new_id(), "ORGANIZATION": (org := random.choice(organizations))["Id"],
        "NAME": f"Dr. Provider {i+1}",
        "GENDER": random.choice(GENDERS), "SPECIALITY": random.choice(SPECIALITIES),
        "ADDRESS": org["ADDRESS"], "CITY": org["CITY"], "STATE": org["STATE"],
        "ZIP": org["ZIP"], "LAT": org["LAT"], "LON": org["LON"],
        "ENCOUNTERS": random.randint(10, 200), "PROCEDURES": random.randint(0, 100),
        "NPI": str(random.randint(1000000000, 9999999999)),
    } for i in range(n)]


def gen_payers(n=3):
    names = ["Nexora Direct", "Medicare", "BlueCross"]
    ownerships = ["GOVERNMENT", "PRIVATE", "NON-PROFIT"]
    return [{
        "Id": new_id(), "NAME": names[i % len(names)],
        "OWNERSHIP": ownerships[i % len(ownerships)], "ADDRESS": "1 Insurance Way",
        "CITY": "Boston", "STATE_HEADQUARTERED": "MA", "ZIP": "02110",
        "PHONE": "617-555-0200", "AMOUNT_COVERED": round(random.uniform(1e4, 1e5), 2),
        "AMOUNT_UNCOVERED": round(random.uniform(1e3, 1e4), 2),
        "REVENUE": round(random.uniform(1e6, 1e7), 2),
        "COVERED_ENCOUNTERS": random.randint(50, 500),
        "UNCOVERED_ENCOUNTERS": random.randint(0, 50),
        "COVERED_MEDICATIONS": random.randint(20, 200),
        "UNCOVERED_MEDICATIONS": random.randint(0, 20),
        "COVERED_PROCEDURES": random.randint(20, 200),
        "UNCOVERED_PROCEDURES": random.randint(0, 20),
        "COVERED_IMMUNIZATIONS": random.randint(5, 50),
        "UNCOVERED_IMMUNIZATIONS": random.randint(0, 5),
        "UNIQUE_CUSTOMERS": random.randint(20, 200),
        "QOLS_AVG": round(random.uniform(0.5, 1.0), 4),
        "MEMBER_MONTHS": random.randint(100, 5000),
    } for i in range(n)]


def gen_patients(n=50):
    # Left as a loop rather than a comprehension: birth/dead are computed
    # once and reused across 3+ fields with a conditional in between, a
    # comprehension here would need several chained walrus assignments and
    # read worse than the loop it replaced.
    rows = []
    for i in range(n):
        birth = rand_date()
        dead = birth + timedelta(days=random.randint(365*20, 365*90)) if random.random() < 0.05 else None
        rows.append({
            "Id": new_id(), "BIRTHDATE": birth.isoformat(),
            "DEATHDATE": dead.isoformat() if dead else "",
            "SSN": f"999-{random.randint(10,99)}-{random.randint(1000,9999)}",
            "DRIVERS": "", "PASSPORT": "", "PREFIX": "", "FIRST": f"Patient{i+1}",
            "MIDDLE": "", "LAST": f"Synthetic{i+1}", "SUFFIX": "", "MAIDEN": "",
            "MARITAL": random.choice(MARITAL), "RACE": random.choice(RACES),
            "ETHNICITY": random.choice(ETHNICITIES), "GENDER": random.choice(GENDERS),
            "BIRTHPLACE": "Boston, MA", "ADDRESS": f"{200+i} Oak St", "CITY": "Boston",
            "STATE": "MA", "COUNTY": "Suffolk", "FIPS": "25025",
            "ZIP": "02118", "LAT": "42.33", "LON": "-71.07",
            "HEALTHCARE_EXPENSES": round(random.uniform(1000, 50000), 2),
            "HEALTHCARE_COVERAGE": round(random.uniform(0, 40000), 2),
            "INCOME": random.randint(20000, 150000),
        })
    return rows


def gen_encounters(patients, organizations, providers, payers, per_patient=3):
    # Left as a loop rather than a comprehension: many interdependent
    # locals per row (start/stop, org/provider, and now cost figures that
    # must be derived from each other in order, not drawn independently).
    #
    # Costs are deliberately NOT independent random draws. total_claim_cost
    # must be >= base_encounter_cost (the claim covers at least the base
    # visit), and payer_coverage must be <= total_claim_cost (a payer can
    # never cover more than the total claim). Generating these three
    # independently (the original bug here) let payer_coverage exceed
    # total_claim_cost by chance, which validation.pandas.post_validate's
    # metric_validity check correctly flags as invalid, exactly the kind
    # of business-rule violation that check exists to catch.
    rows = []
    for patient in patients:
        for _ in range(random.randint(0, per_patient)):
            start = datetime.combine(rand_date(2024, 2026), datetime.min.time())
            stop = start + timedelta(hours=random.randint(1, 4))
            org = random.choice(organizations)
            provider = random.choice([p for p in providers if p["ORGANIZATION"] == org["Id"]] or providers)

            base_cost = round(random.uniform(80, 400), 2)
            total_claim_cost = round(random.uniform(base_cost, base_cost + 1600), 2)
            payer_coverage = round(random.uniform(0, total_claim_cost), 2)

            rows.append({
                "Id": new_id(), "START": start.isoformat(), "STOP": stop.isoformat(),
                "PATIENT": patient["Id"], "ORGANIZATION": org["Id"], "PROVIDER": provider["Id"],
                "PAYER": random.choice(payers)["Id"],
                "ENCOUNTERCLASS": random.choice(ENCOUNTER_CLASSES),
                "CODE": str(random.randint(100000, 999999)), "DESCRIPTION": "General visit",
                "BASE_ENCOUNTER_COST": base_cost,
                "TOTAL_CLAIM_COST": total_claim_cost,
                "PAYER_COVERAGE": payer_coverage,
                "REASONCODE": "", "REASONDESCRIPTION": "",
            })
    return rows


def gen_conditions(encounters, rate=0.4):
    return [{
        "START": enc["START"], "STOP": "", "PATIENT": enc["PATIENT"],
        "ENCOUNTER": enc["Id"], "SYSTEM": CONDITION_SYSTEM,
        "CODE": (cd := random.choice(CONDITION_CODES))[0],
        "DESCRIPTION": cd[1],
    } for enc in encounters if random.random() < rate]


def write_csv(rows, path, fieldnames=None):
    """Writes rows to a CSV, always creating the file, even with zero rows.
    A missing file and a validly-empty dataset are different things
    downstream: pre_validate.py's process_file() treats a missing path as
    file_missing/REJECTED, but conditions.csv having zero rows is a valid
    outcome (schemas.py sets min_rows: 0 for conditions), so the file must
    still exist with just a header row when that happens.
    """
    field_names = fieldnames or (list(rows[0].keys()) if rows else [])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
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
    write_csv(conditions, f"{out_dir}/conditions.csv",
              fieldnames=["START", "STOP", "PATIENT", "ENCOUNTER", "SYSTEM", "CODE", "DESCRIPTION"])

    print(f"[simulate_weekly_drop] wrote 6 files to {out_dir} "
          f"({len(patients)} patients, {len(encounters)} encounters, {len(conditions)} conditions)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--patients", type=int, default=50)
    args = parser.parse_args()
    main(args.run_id, args.patients)
