"""
Canonical column definitions for the six in-scope Synthea exports.
Single source of truth for schema/mandatory-field/allowed-value/id-format
checks, imported by every rules_<dataset>.py so the rule bodies stay short
and the columns are never redefined twice.

Column lists and allowed_values below are verified against a real Synthea
CSV export (synthetichealth/synthea-sample-data on GitHub, csv bundle,
108 patients / 5571 encounters), not just the generally-known schema from
memory. Two real discrepancies that earlier versions of this file missed:
  - organizations/providers/payers/patients all carry extra columns
    (NPI, ENCOUNTERS, PROCEDURES, OWNERSHIP, MIDDLE, FIPS, INCOME) that a
    strict schema check would have rejected as "unexpected columns".
  - conditions has a SYSTEM column (the code system URI, e.g.
    http://snomed.info/sct) between ENCOUNTER and CODE that was missing
    entirely.
  - ENCOUNTERCLASS's real value set includes "hospice" and "snf", which
    were missing from the allowed_values set.
"""
import re

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

SCHEMAS = {
    "organizations": {
        "columns": ["Id", "NAME", "ADDRESS", "CITY", "STATE", "ZIP", "LAT", "LON",
                    "PHONE", "REVENUE", "UTILIZATION", "NPI"],
        "mandatory": ["Id", "NAME"],
        "id_column": "Id",
        "allowed_values": {},
        "chronology_pairs": [],
        "min_rows": 1,
        "max_rows": 100_000,
    },
    "providers": {
        "columns": ["Id", "ORGANIZATION", "NAME", "GENDER", "SPECIALITY", "ADDRESS",
                    "CITY", "STATE", "ZIP", "LAT", "LON", "ENCOUNTERS", "PROCEDURES",
                    "NPI"],
        "mandatory": ["Id", "ORGANIZATION", "NAME"],
        "id_column": "Id",
        "allowed_values": {"GENDER": {"M", "F"}},
        "chronology_pairs": [],
        "min_rows": 1,
        "max_rows": 100_000,
    },
    "payers": {
        "columns": ["Id", "NAME", "OWNERSHIP", "ADDRESS", "CITY", "STATE_HEADQUARTERED",
                    "ZIP", "PHONE", "AMOUNT_COVERED", "AMOUNT_UNCOVERED", "REVENUE",
                    "COVERED_ENCOUNTERS", "UNCOVERED_ENCOUNTERS", "COVERED_MEDICATIONS",
                    "UNCOVERED_MEDICATIONS", "COVERED_PROCEDURES", "UNCOVERED_PROCEDURES",
                    "COVERED_IMMUNIZATIONS", "UNCOVERED_IMMUNIZATIONS",
                    "UNIQUE_CUSTOMERS", "QOLS_AVG", "MEMBER_MONTHS"],
        "mandatory": ["Id", "NAME"],
        "id_column": "Id",
        "allowed_values": {},
        "chronology_pairs": [],
        "min_rows": 1,
        "max_rows": 10_000,
    },
    "patients": {
        "columns": ["Id", "BIRTHDATE", "DEATHDATE", "SSN", "DRIVERS", "PASSPORT",
                    "PREFIX", "FIRST", "MIDDLE", "LAST", "SUFFIX", "MAIDEN", "MARITAL",
                    "RACE", "ETHNICITY", "GENDER", "BIRTHPLACE", "ADDRESS", "CITY",
                    "STATE", "COUNTY", "FIPS", "ZIP", "LAT", "LON",
                    "HEALTHCARE_EXPENSES", "HEALTHCARE_COVERAGE", "INCOME"],
        "mandatory": ["Id", "BIRTHDATE", "GENDER", "FIRST", "LAST"],
        "id_column": "Id",
        "allowed_values": {
            "GENDER": {"M", "F"},
            "MARITAL": {"M", "S", "D", "W", ""},
        },
        "chronology_pairs": [("BIRTHDATE", "DEATHDATE")],
        "min_rows": 1,
        "max_rows": 1_000_000,
    },
    "encounters": {
        "columns": ["Id", "START", "STOP", "PATIENT", "ORGANIZATION", "PROVIDER",
                    "PAYER", "ENCOUNTERCLASS", "CODE", "DESCRIPTION",
                    "BASE_ENCOUNTER_COST", "TOTAL_CLAIM_COST", "PAYER_COVERAGE",
                    "REASONCODE", "REASONDESCRIPTION"],
        "mandatory": ["Id", "START", "PATIENT", "ORGANIZATION", "PROVIDER",
                      "ENCOUNTERCLASS"],
        "id_column": "Id",
        "allowed_values": {
            "ENCOUNTERCLASS": {"ambulatory", "emergency", "inpatient", "wellness",
                                "urgentcare", "outpatient", "home", "virtual",
                                "hospice", "snf"},
        },
        "chronology_pairs": [("START", "STOP")],
        "min_rows": 1,
        "max_rows": 5_000_000,
        "foreign_keys": {
            "PATIENT": "patients", "ORGANIZATION": "organizations",
            "PROVIDER": "providers", "PAYER": "payers",
        },
    },
    "conditions": {
        "columns": ["START", "STOP", "PATIENT", "ENCOUNTER", "SYSTEM", "CODE",
                    "DESCRIPTION"],
        "mandatory": ["START", "PATIENT", "ENCOUNTER", "CODE"],
        "id_column": None,   # no single-column PK; dedupe on composite key instead
        "composite_key": ["PATIENT", "ENCOUNTER", "CODE"],
        "allowed_values": {},
        "chronology_pairs": [("START", "STOP")],
        "min_rows": 0,
        "max_rows": 5_000_000,
        "foreign_keys": {"PATIENT": "patients", "ENCOUNTER": "encounters"},
    },
}
