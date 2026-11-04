"""The runtime log appends one row per timed block, including blocks that fail."""

import csv

import pytest

from erdos_quant_finance_project.runlog import FIELDS, timed


def test_rows_appended_with_status(tmp_path):
    log = tmp_path / "runtime_log.csv"
    with timed("fit", inputs="toy", rows_in=10, log=log) as run:
        run["rows_out"] = 3
    with pytest.raises(ValueError):
        with timed("boom", log=log):
            raise ValueError
    rows = list(csv.DictReader(log.open(encoding="utf-8")))
    assert list(rows[0]) == FIELDS
    assert [(r["step"], r["status"]) for r in rows] == [("fit", "ok"), ("boom", "failed")]
    assert (rows[0]["rows_in"], rows[0]["rows_out"], rows[0]["inputs"]) == ("10", "3", "toy")
    assert float(rows[0]["wall_seconds"]) >= 0
