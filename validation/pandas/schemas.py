"""
Canonical column definitions for the six in-scope Synthea exports.
Single source of truth for schema/mandatory-field/allowed-value/id-format
checks, imported by every rules_<dataset>.py so the rule bodies stay short
and the columns are never redefined twice.
"""
import re

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

SCHEMAS = {
    "organizations": {
        "columns": ["Id", "NAME", "ADDRESS", "CITY", "STATE", "ZIP", "LAT", "LON",
                    "PHONE", "REVENUE", "UTILIZATION"],
        "mandatory": ["Id", "NAME"],
        "id_column": "Id",
        "allowed_values": {},
        "chronology_pairs": [],
        "min_rows": 1,
        "max_rows": 100_000,
    },
    "providers": {
        "columns": ["Id", "ORGANIZATION", "NAME", "GENDER", "SPECIALITY", "ADDRESS",
                    "CITY", "STATE", "ZIP", "LAT", "LON", "UTILIZATION"],
        "mandatory": ["Id", "ORGANIZATION", "NAME"],
        "id_column": "Id",
        "allowed_values": {"GENDER": {"M", "F"}},
        "chronology_pairs": [],
        "min_rows": 1,
        "max_rows": 100_000,
    },
    "payers": {
        "columns": ["Id", "NAME", "ADDRESS", "CITY", "STATE_HEADQUARTERED", "ZIP",
                    "PHONE", "AMOUNT_COVERED", "AMOUNT_UNCOVERED", "REVENUE",
                    "COVERED_ENCOUNTERS", "UNCOVERED_ENCOUNTERS", "UNIQUE_CUSTOMERS"],
        "mandatory": ["Id", "NAME"],
        "id_column": "Id",
        "allowed_values": {},
        "chronology_pairs": [],
        "min_rows": 1,
        "max_rows": 10_000,
    },
    "patients": {
        "columns": ["Id", "BIRTHDATE", "DEATHDATE", "SSN", "DRIVERS", "PASSPORT",
                    "PREFIX", "FIRST", "LAST", "SUFFIX", "MAIDEN", "MARITAL", "RACE",
                    "ETHNICITY", "GENDER", "BIRTHPLACE", "ADDRESS", "CITY", "STATE",
                    "COUNTY", "ZIP", "LAT", "LON", "HEALTHCARE_EXPENSES",
                    "HEALTHCARE_COVERAGE"],
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
                                "urgentcare", "outpatient", "home", "virtual"},
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
        "columns": ["START", "STOP", "PATIENT", "ENCOUNTER", "CODE", "DESCRIPTION"],
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
