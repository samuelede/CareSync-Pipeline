"""Unit tests for the generic pandas check functions against the real
schemas.SCHEMAS definitions, using small hand-built DataFrames."""
import pandas as pd

from validation.pandas.schemas import SCHEMAS
from validation.pandas.check_engine import run_all_checks
from validation.pandas import rules_patients, rules_organizations


def make_valid_patients_df(n=3):
    return pd.DataFrame({
        "Id": [f"{i:08d}-bbbb-cccc-dddd-{'e'*12}" for i in range(n)],
        "BIRTHDATE": ["1980-01-01"] * n, "DEATHDATE": [""] * n,
        "SSN": ["999-11-1111"] * n, "DRIVERS": [""] * n, "PASSPORT": [""] * n,
        "PREFIX": [""] * n, "FIRST": ["Jane"] * n, "MIDDLE": [""] * n, "LAST": ["Doe"] * n,
        "SUFFIX": [""] * n, "MAIDEN": [""] * n, "MARITAL": ["S"] * n,
        "RACE": ["white"] * n, "ETHNICITY": ["nonhispanic"] * n, "GENDER": ["F"] * n,
        "BIRTHPLACE": ["Boston"] * n, "ADDRESS": ["1 St"] * n, "CITY": ["Boston"] * n,
        "STATE": ["MA"] * n, "COUNTY": ["Suffolk"] * n, "FIPS": ["25025"] * n,
        "ZIP": ["02118"] * n, "LAT": ["42.3"] * n, "LON": ["-71.0"] * n,
        "HEALTHCARE_EXPENSES": [100.0] * n, "HEALTHCARE_COVERAGE": [50.0] * n,
        "INCOME": [50000] * n,
    })


def test_valid_patients_frame_passes():
    df = make_valid_patients_df()
    is_valid, results = rules_patients.validate(df)
    assert is_valid, results


def test_missing_mandatory_field_fails():
    df = make_valid_patients_df()
    df.loc[0, "BIRTHDATE"] = ""
    is_valid, results = rules_patients.validate(df)
    assert not is_valid
    assert results["mandatory_fields"][0] is False


def test_bad_id_format_fails():
    df = make_valid_patients_df()
    df.loc[0, "Id"] = "not-a-uuid"
    is_valid, results = rules_patients.validate(df)
    assert not is_valid
    assert results["id_format"][0] is False


def test_disallowed_gender_value_fails():
    df = make_valid_patients_df()
    df.loc[0, "GENDER"] = "X"
    is_valid, results = rules_patients.validate(df)
    assert not is_valid
    assert results["allowed_values"][0] is False


def test_duplicate_ids_fail():
    df = make_valid_patients_df(n=2)
    df.loc[1, "Id"] = df.loc[0, "Id"]
    is_valid, results = rules_patients.validate(df)
    assert not is_valid
    assert results["duplicates"][0] is False


def test_chronology_catches_mixed_date_formats():
    """Regression test: pd.to_datetime(..., errors='coerce') without
    format='mixed' infers one format from the first row and silently NaTs
    any row using a different format, letting a real violation slip past.
    A bad STOP written as 'YYYY-MM-DD' among 'YYYY-MM-DDTHH:MM:SS' rows
    must still be caught."""
    from validation.pandas.check_engine import check_chronology
    df = pd.DataFrame({
        "START": ["2024-03-28T00:00:00", "2024-03-29T00:00:00"],
        "STOP": ["2024-03-28T03:00:00", "1900-01-01"],
    })
    passed, errors = check_chronology(df, [("START", "STOP")])
    assert not passed
    assert "1 row(s)" in errors[0]


def test_organizations_minimal_valid_frame():
    df = pd.DataFrame({
        "Id": ["11111111-1111-1111-1111-111111111111"],
        "NAME": ["Clinic A"], "ADDRESS": ["1 St"], "CITY": ["Boston"], "STATE": ["MA"],
        "ZIP": ["02118"], "LAT": ["42.3"], "LON": ["-71.0"], "PHONE": ["617-555-0100"],
        "REVENUE": [100000.0], "UTILIZATION": [10], "NPI": ["1234567890"],
    })
    is_valid, results = rules_organizations.validate(df)
    assert is_valid, results


def test_all_datasets_pass_against_real_synthea_sample():
    """Regression guard for the schema itself: data/real_synthea_sample/
    is a trimmed export from synthetichealth/synthea-sample-data (real
    Synthea output, not hand-built). If SCHEMAS drifts from what Synthea
    actually produces (a missing column, a narrower allowed_values set),
    this is what catches it, hand-built fixtures in this file can't."""
    import os
    from validation.pandas import rules_providers, rules_payers, rules_encounters, rules_conditions

    rules_by_dataset = {
        "organizations": rules_organizations, "providers": rules_providers,
        "payers": rules_payers, "patients": rules_patients,
        "encounters": rules_encounters, "conditions": rules_conditions,
    }
    fixture_dir = os.path.join(os.path.dirname(__file__), "..", "data", "real_synthea_sample")
    for dataset, module in rules_by_dataset.items():
        path = os.path.join(fixture_dir, f"{dataset}.csv")
        df = pd.read_csv(path, dtype=str)
        is_valid, results = module.validate(df)
        assert is_valid, f"{dataset}: {results}"
