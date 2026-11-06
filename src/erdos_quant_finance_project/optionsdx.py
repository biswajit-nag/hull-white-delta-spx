"""Read OptionsDX end-of-day option-chain files and write them as typed Parquet.

The interim layer is a faithful copy of the vendor files: columns are renamed to
snake_case and typed, the "bid x ask" size strings are split into two integer
columns, empty fields become nulls, and no row is changed or dropped.
"""

from __future__ import annotations

import re
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import pyarrow.parquet as pq

VENDOR_COLUMNS = [
    "QUOTE_UNIXTIME", "QUOTE_READTIME", "QUOTE_DATE", "QUOTE_TIME_HOURS", "UNDERLYING_LAST",
    "EXPIRE_DATE", "EXPIRE_UNIX", "DTE",
    "C_DELTA", "C_GAMMA", "C_VEGA", "C_THETA", "C_RHO", "C_IV", "C_VOLUME", "C_LAST", "C_SIZE",
    "C_BID", "C_ASK", "STRIKE", "P_BID", "P_ASK", "P_SIZE", "P_LAST",
    "P_DELTA", "P_GAMMA", "P_VEGA", "P_THETA", "P_RHO", "P_IV", "P_VOLUME",
    "STRIKE_DISTANCE", "STRIKE_DISTANCE_PCT",
]
INT_COLUMNS = {"QUOTE_UNIXTIME", "EXPIRE_UNIX"}
DATE_COLUMNS = {"QUOTE_DATE", "EXPIRE_DATE"}
STRING_COLUMNS = {"QUOTE_READTIME"}
SIZE_COLUMNS = {"C_SIZE": "c", "P_SIZE": "p"}
SIZE_PATTERN = r"^\d+ x \d+$"

MEMBER_RE = re.compile(r"^(spx|spy|aapl|nvda|tsla|qqq|slv)_eod_(\d{4})(\d{2})\.txt$")


def _clean(col: pa.ChunkedArray) -> pa.ChunkedArray:
    """Trim whitespace and turn empty strings into nulls."""
    trimmed = pc.utf8_trim_whitespace(col)
    return pc.if_else(pc.equal(trimmed, ""), pa.scalar(None, pa.string()), trimmed)


def read_month(path: Path) -> tuple[pa.Table, dict]:
    """Parse one vendor month file; return the typed table and parse diagnostics."""
    with open(path, encoding="ascii") as f:
        header = [name.strip().strip("[]") for name in f.readline().split(",")]
    if header != VENDOR_COLUMNS:
        raise ValueError(f"{path.name}: unexpected header {header}")
    # Read every column as text, so no value is coerced before we inspect it.
    raw = pacsv.read_csv(
        path,
        read_options=pacsv.ReadOptions(skip_rows=1, column_names=header),
        convert_options=pacsv.ConvertOptions(column_types={c: pa.string() for c in header}),
    )

    arrays, names, size_failures = [], [], 0
    for name in VENDOR_COLUMNS:
        col = _clean(raw[name])
        if name in SIZE_COLUMNS:
            side = SIZE_COLUMNS[name]
            ok = pc.match_substring_regex(col, SIZE_PATTERN)
            size_failures += pc.sum(pc.and_(pc.is_valid(col), pc.invert(ok))).as_py() or 0
            parts = pc.split_pattern(pc.if_else(ok, col, pa.scalar(None, pa.string())), " x ")
            for i, suffix in enumerate(("bid_size", "ask_size")):
                arrays.append(pc.cast(pc.list_element(parts, i), pa.int64()))
                names.append(f"{side}_{suffix}")
            continue
        if name in INT_COLUMNS:
            col = pc.cast(col, pa.int64())
        elif name in DATE_COLUMNS:
            col = pc.cast(pc.strptime(col, format="%Y-%m-%d", unit="s"), pa.date32())
        elif name not in STRING_COLUMNS:
            col = pc.cast(col, pa.float64())
        arrays.append(col)
        names.append(name.lower())
    table = pa.Table.from_arrays(arrays, names=names)
    return table, {"size_parse_failures": size_failures}


def month_summary(table: pa.Table) -> dict:
    """Row counts and key checks that go into the data manifest."""
    qd, ed = table["quote_date"], table["expire_date"]
    keys = table.group_by(["quote_date", "expire_date", "strike"]).aggregate([([], "count_all")])
    return {
        "rows": table.num_rows,
        "n_quote_dates": pc.count_distinct(qd).as_py(),
        "first_quote_date": pc.min(qd).as_py().isoformat(),
        "last_quote_date": pc.max(qd).as_py().isoformat(),
        "n_expiries": pc.count_distinct(ed).as_py(),
        "rows_expired_before_quote": pc.sum(pc.less(ed, qd)).as_py() or 0,
        "duplicate_keys": int(pc.sum(pc.greater(keys["count_all"], 1)).as_py() or 0),
        "underlying_values_per_date_max": int(pc.max(
            table.group_by("quote_date").aggregate([("underlying_last", "count_distinct")])
            ["underlying_last_count_distinct"]).as_py()),
    }


def write_month(table: pa.Table, out_root: Path, underlying: str, year: str, stem: str) -> Path:
    """Write one month under a Hive-style underlying=/year= partition."""
    out_dir = out_root / f"underlying={underlying}" / f"year={year}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{stem}.parquet"
    pq.write_table(table, out, compression="zstd")
    return out
