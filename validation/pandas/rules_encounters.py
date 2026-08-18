"""
Pandas pre-validation rules for the 'encounters' dataset.

Binds the generic check functions in check_engine.py to this dataset's
schema definition (schemas.SCHEMAS["encounters"]). Kept as a thin wrapper
rather than duplicated logic, so Phase 2's Great Expectations suite can
be written against the same SCHEMAS dict and the two stay in lockstep.
"""
import pandas as pd
from validation.pandas.schemas import SCHEMAS
from validation.pandas.check_engine import run_all_checks

DATASET = "encounters"


def validate(df: pd.DataFrame):
    """Returns (is_valid: bool, results: dict[str, tuple[bool, list[str]]])."""
    return run_all_checks(df, SCHEMAS[DATASET])
