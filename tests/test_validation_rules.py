"""
Starter unit tests. Extend one test module per rules_<dataset>.py as those
checks are implemented, plus a dedicated test for cascade_skip() since it
is pure logic and the easiest place to catch a dependency-mapping mistake
before it reaches a real run.
"""
import pandas as pd
from validation.pandas.pre_validate import cascade_skip


def test_cascade_skip_propagates_to_direct_dependent():
    status = {"patients": "REJECTED", "encounters": "VALID", "conditions": "VALID",
              "organizations": "VALID", "providers": "VALID", "payers": "VALID"}
    result = cascade_skip(status)
    assert result["encounters"] == "SKIPPED"


def test_cascade_skip_propagates_transitively():
    status = {"patients": "REJECTED", "encounters": "VALID", "conditions": "VALID",
              "organizations": "VALID", "providers": "VALID", "payers": "VALID"}
    result = cascade_skip(status)
    assert result["conditions"] == "SKIPPED"


def test_cascade_skip_leaves_independent_datasets_valid():
    status = {"patients": "REJECTED", "encounters": "VALID", "conditions": "VALID",
              "organizations": "VALID", "providers": "VALID", "payers": "VALID"}
    result = cascade_skip(status)
    assert result["organizations"] == "VALID"
    assert result["providers"] == "VALID"
    assert result["payers"] == "VALID"
