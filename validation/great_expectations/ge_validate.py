"""
Great Expectations validation engine, Phase 2's replacement for
validation/pandas/check_engine.py. Same rule families, same schemas.py
source of truth, different tooling, exactly the "prove the logic simple,
then swap the tools" progression the project spec calls for. No business
rule is redefined here: every expectation below is built directly from
validation.pandas.schemas.SCHEMAS, the same dict the pandas engine reads,
so the two can never drift out of sync the way DDL/staging files did
earlier in this project.

Public interface matches validation/pandas/rules_<dataset>.validate()
exactly: validate(dataset, df) -> (is_valid: bool, results: dict[str, tuple[bool, list[str]]])
so pre_validate.py can swap engines without changing its own orchestration
logic, only which validate() function it imports.
"""
import great_expectations as gx

from validation.pandas.schemas import SCHEMAS

_context = None


def _get_context():
    """Ephemeral (in-memory, no project directory) context, created once
    per process. Nothing here needs to persist between runs, the audit
    trail and quarantine store already do that job."""
    global _context
    if _context is None:
        _context = gx.get_context(mode="ephemeral")
        context.progress_bars = False
    return _context


def _build_suite(context, dataset: str, schema: dict):
    """Builds an ExpectationSuite from one schemas.py entry. Mirrors
    check_engine.py's check families one-to-one:
        check_schema           -> expect_table_columns_to_match_set
        check_mandatory_fields  -> expect_column_values_to_not_be_null
        check_id_format         -> expect_column_values_to_match_regex
        check_allowed_values    -> expect_column_values_to_be_in_set
        check_chronology        -> expect_column_pair_values_a_to_be_greater_than_b
        check_duplicates        -> expect_column_values_to_be_unique /
                                    expect_compound_columns_to_be_unique
        check_row_count_sanity  -> expect_table_row_count_to_be_between
    """
    suite_name = f"{dataset}_suite"
    suite = context.add_or_update_expectation_suite(suite_name)

    return suite_name


def validate(dataset: str, df) -> tuple:
    """Runs the Great Expectations suite for `dataset` against `df`.
    Returns (is_valid, results) in the exact same shape as
    validation.pandas.rules_<dataset>.validate(), so pre_validate.py can
    use either engine interchangeably.
    """
    schema = SCHEMAS[dataset]

    # Normalize blank strings to real nulls before GE sees the frame.
    # GE's ignore_row_if="either_value_is_missing" (used by the chronology
    # check below) only treats actual None/NaN as missing, not "", so an
    # empty STOP/DEATHDATE would otherwise be compared as a literal string
    # and could be flagged as "before START", a false positive the pandas
    # engine doesn't have (it explicitly coerces blanks to NaT first via
    # pd.to_datetime). This keeps both engines' behavior identical on the
    # same input, the whole point of re-expressing the same rules here.
    df = df.replace(r"^\s*$", None, regex=True)

    context = _get_context()
    suite_name = _build_suite(context, dataset, schema)

    datasource_name = f"{dataset}_datasource"
    asset_name = f"{dataset}_asset"
    try:
        datasource = context.get_datasource(datasource_name)
    except ValueError:
        datasource = context.sources.add_pandas(datasource_name)
    try:
        asset = datasource.get_asset(asset_name)
    except LookupError:
        asset = datasource.add_dataframe_asset(name=asset_name)

    batch_request = asset.build_batch_request(dataframe=df)
    validator = context.get_validator(batch_request=batch_request, expectation_suite_name=suite_name)

    results = {}

    r = validator.expect_table_columns_to_match_set(column_set=schema["columns"], result_format="SUMMARY")
    results["schema"] = (r["success"], [] if r["success"] else _schema_errors(r, schema["columns"]))

    mandatory_errors = []
    mandatory_ok = True
    for col in schema["mandatory"]:
        if col not in df.columns:
            mandatory_ok = False
            mandatory_errors.append(f"mandatory column '{col}' absent")
            continue
        r = validator.expect_column_values_to_not_be_null(column=col, result_format="SUMMARY")
        if not r["success"]:
            mandatory_ok = False
            n_null = r["result"]["unexpected_count"]
            mandatory_errors.append(f"'{col}' has {n_null} null/blank value(s)")
    results["mandatory_fields"] = (mandatory_ok, mandatory_errors)

    id_errors = []
    id_ok = True
    if schema.get("id_column"):
        col = schema["id_column"]
        r = validator.expect_column_values_to_match_regex(
            column=col,
            regex=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            result_format="SUMMARY",
        )
        if not r["success"]:
            id_ok = False
            n_bad = r["result"]["unexpected_count"]
            id_errors.append(f"{n_bad} row(s) with malformed '{col}' (not UUID)")
    elif schema.get("composite_key"):
        missing = [c for c in schema["composite_key"] if c not in df.columns]
        if missing:
            id_ok = False
            id_errors.append(f"composite key columns missing: {missing}")
    results["id_format"] = (id_ok, id_errors)

    allowed_errors = []
    allowed_ok = True
    for col, allowed in schema["allowed_values"].items():
        if col not in df.columns:
            continue
        r = validator.expect_column_values_to_be_in_set(column=col, value_set=list(allowed), result_format="SUMMARY")
        if not r["success"]:
            allowed_ok = False
            bad_values = sorted(set(r["result"].get("partial_unexpected_list", [])))
            allowed_errors.append(f"'{col}' has disallowed values: {bad_values}")
    results["allowed_values"] = (allowed_ok, allowed_errors)

    chrono_errors = []
    chrono_ok = True
    for start_col, end_col in schema["chronology_pairs"]:
        if start_col not in df.columns or end_col not in df.columns:
            continue
        r = validator.expect_column_pair_values_a_to_be_greater_than_b(
            column_A=end_col, column_B=start_col, or_equal=True,
            ignore_row_if="either_value_is_missing", result_format="SUMMARY",
        )
        if not r["success"]:
            chrono_ok = False
            n_bad = r["result"]["unexpected_count"]
            chrono_errors.append(f"{n_bad} row(s) where '{end_col}' precedes '{start_col}'")
    results["chronology"] = (chrono_ok, chrono_errors)

    dup_errors = []
    dup_ok = True
    if schema.get("id_column") and schema["id_column"] in df.columns:
        r = validator.expect_column_values_to_be_unique(column=schema["id_column"], result_format="SUMMARY")
        if not r["success"]:
            dup_ok = False
            n_dupes = r["result"]["unexpected_count"]
            dup_errors.append(f"{n_dupes} duplicate '{schema['id_column']}' value(s)")
    elif schema.get("composite_key"):
        present = [c for c in schema["composite_key"] if c in df.columns]
        if present:
            r = validator.expect_compound_columns_to_be_unique(column_list=present, result_format="SUMMARY")
            if not r["success"]:
                dup_ok = False
                n_dupes = r["result"]["unexpected_count"]
                dup_errors.append(f"{n_dupes} duplicate row(s) on composite key {present}")
    results["duplicates"] = (dup_ok, dup_errors)

    r = validator.expect_table_row_count_to_be_between(
        min_value=schema["min_rows"], max_value=schema["max_rows"], result_format="SUMMARY"
    )
    n = len(df)
    results["row_count_sanity"] = (
        r["success"],
        [] if r["success"] else [f"row count {n} outside [{schema['min_rows']}, {schema['max_rows']}]"]
    )

    is_valid = all(passed for passed, _ in results.values())
    return is_valid, results


def _schema_errors(result, expected_columns) -> list:
    details = result["result"].get("details", {})
    mismatched = details.get("mismatched", {})
    errors = []
    if mismatched.get("missing"):
        errors.append(f"missing columns: {sorted(mismatched['missing'])}")
    if mismatched.get("unexpected"):
        errors.append(f"unexpected columns: {sorted(mismatched['unexpected'])}")
    if not errors:
        errors.append("column set mismatch")
    return errors
