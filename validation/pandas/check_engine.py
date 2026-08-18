"""
Generic pandas check functions, parameterized by the schema definitions in
schemas.py. Each rules_<dataset>.py module is now a thin wrapper that binds
these generic checks to its dataset's SCHEMAS entry. This is the pandas
equivalent of what a Great Expectations suite will look like in Phase 2:
declarative rule definitions, not bespoke code per file.

Every check returns (passed: bool, errors: list[str]).
"""
import pandas as pd
from validation.pandas.schemas import UUID_RE


def check_schema(df: pd.DataFrame, expected_columns: list) -> tuple:
    missing = [c for c in expected_columns if c not in df.columns]
    extra = [c for c in df.columns if c not in expected_columns]
    errors = []
    if missing:
        errors.append(f"missing columns: {missing}")
    if extra:
        errors.append(f"unexpected columns: {extra}")
    return (len(errors) == 0, errors)


def check_mandatory_fields(df: pd.DataFrame, mandatory: list) -> tuple:
    errors = []
    for col in mandatory:
        if col not in df.columns:
            errors.append(f"mandatory column '{col}' absent")
            continue
        n_null = df[col].isna().sum() + (df[col].astype(str).str.strip() == "").sum()
        if n_null > 0:
            errors.append(f"'{col}' has {n_null} null/blank value(s)")
    return (len(errors) == 0, errors)


def check_id_format(df: pd.DataFrame, id_column: str = None, composite_key: list = None) -> tuple:
    errors = []
    if id_column:
        if id_column not in df.columns:
            return (False, [f"id column '{id_column}' absent"])
        bad = df[~df[id_column].astype(str).str.match(UUID_RE)]
        if len(bad) > 0:
            errors.append(f"{len(bad)} row(s) with malformed '{id_column}' (not UUID)")
    elif composite_key:
        missing_cols = [c for c in composite_key if c not in df.columns]
        if missing_cols:
            errors.append(f"composite key columns missing: {missing_cols}")
    return (len(errors) == 0, errors)


def check_allowed_values(df: pd.DataFrame, allowed_values: dict) -> tuple:
    errors = []
    for col, allowed in allowed_values.items():
        if col not in df.columns:
            continue
        actual = set(df[col].dropna().astype(str).unique())
        bad = actual - {str(a) for a in allowed}
        if bad:
            errors.append(f"'{col}' has disallowed values: {sorted(bad)}")
    return (len(errors) == 0, errors)


def _parse_dates(series: pd.Series) -> pd.Series:
    """pd.to_datetime with errors='coerce' infers ONE format from the first
    non-null value and silently NaTs any row that doesn't match it. A real
    trap when a corrupted/malformed row uses a different date format than
    the rest of the column (exactly the case this check exists to catch).
    format='mixed' parses each value independently instead."""
    return pd.to_datetime(series, errors="coerce", format="mixed")


def check_chronology(df: pd.DataFrame, chronology_pairs: list) -> tuple:
    errors = []
    for start_col, end_col in chronology_pairs:
        if start_col not in df.columns or end_col not in df.columns:
            continue
        start = _parse_dates(df[start_col])
        end = _parse_dates(df[end_col])
        violations = df[(end.notna()) & (start.notna()) & (end < start)]
        if len(violations) > 0:
            errors.append(f"{len(violations)} row(s) where '{end_col}' precedes '{start_col}'")
    return (len(errors) == 0, errors)


def check_duplicates(df: pd.DataFrame, id_column: str = None, composite_key: list = None) -> tuple:
    errors = []
    if id_column and id_column in df.columns:
        dupes = df[df.duplicated(subset=[id_column], keep=False)]
        if len(dupes) > 0:
            errors.append(f"{dupes[id_column].nunique()} duplicate '{id_column}' value(s)")
    elif composite_key:
        present = [c for c in composite_key if c in df.columns]
        if present:
            dupes = df[df.duplicated(subset=present, keep=False)]
            if len(dupes) > 0:
                errors.append(f"{len(dupes)} duplicate row(s) on composite key {present}")
    return (len(errors) == 0, errors)


def check_row_count_sanity(df: pd.DataFrame, min_rows: int, max_rows: int) -> tuple:
    n = len(df)
    if n < min_rows:
        return (False, [f"row count {n} below minimum {min_rows}"])
    if n > max_rows:
        return (False, [f"row count {n} above maximum {max_rows}"])
    return (True, [])


def check_parseability(df: pd.DataFrame) -> tuple:
    """Confirms the frame actually parsed (non-empty, has columns). Called
    before the other checks. A file that fails this should short-circuit
    the rest, since column-based checks are meaningless on a malformed file."""
    if df is None:
        return (False, ["file could not be parsed"])
    if df.shape[1] == 0:
        return (False, ["file parsed with zero columns"])
    return (True, [])


def run_all_checks(df: pd.DataFrame, schema: dict) -> tuple:
    """Runs every check for one dataset's schema definition, in the order
    the spec lists them: schema, mandatory fields, id format, parseability
    (implicitly first), allowed values, chronology, duplicates, row-count
    sanity. Returns (is_valid, {check_name: (passed, errors)})."""
    results = {}

    ok, errs = check_parseability(df)
    results["parseability"] = (ok, errs)
    if not ok:
        return False, results

    ok, errs = check_schema(df, schema["columns"])
    results["schema"] = (ok, errs)

    ok, errs = check_mandatory_fields(df, schema["mandatory"])
    results["mandatory_fields"] = (ok, errs)

    ok, errs = check_id_format(df, schema.get("id_column"), schema.get("composite_key"))
    results["id_format"] = (ok, errs)

    ok, errs = check_allowed_values(df, schema["allowed_values"])
    results["allowed_values"] = (ok, errs)

    ok, errs = check_chronology(df, schema["chronology_pairs"])
    results["chronology"] = (ok, errs)

    ok, errs = check_duplicates(df, schema.get("id_column"), schema.get("composite_key"))
    results["duplicates"] = (ok, errs)

    ok, errs = check_row_count_sanity(df, schema["min_rows"], schema["max_rows"])
    results["row_count_sanity"] = (ok, errs)

    is_valid = all(passed for passed, _ in results.values())
    return is_valid, results
