"""Build the hedge-pair files from the step-3 panel and the step-1 Greeks (plan §2, §5).

Writes data/processed/pairs/underlying=spx/year=YYYY/pairs_YYYY.parquet: pairs with day one in YYYY
that pass E1–E6 and E8, with E7, its strict reading and next_status as columns. No hedging error
is computed.

Usage: uv run python -I scripts/build_pairs.py 2010 2023
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project.pairs import build_year  # noqa: E402
from erdos_quant_finance_project.processed import nyse_sessions, official_closes  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

PANEL = ROOT / "data/processed/optionsdx_long/underlying=spx"
GREEKS = ROOT / "data/processed/greeks/underlying=spx"
OUT = ROOT / "data/processed/pairs/underlying=spx"


def main(first: int, last: int) -> None:
    sessions = pd.concat([pd.read_parquet(p) for p in sorted(GREEKS.glob("sessions_*.parquet"))])
    sessions["quote_date"] = pd.to_datetime(sessions.quote_date)
    sessions = sessions.sort_values("quote_date")
    # the R7/R8 index features use the official close on NYSE sessions, not the vendor's dates
    nyse = nyse_sessions("2009-11-01", "2024-02-28").index
    closes = official_closes(ROOT / "data/external", "spx").S_close.reindex(nyse).dropna()
    for year in range(first, last + 1):
        with timed("build_pairs", inputs=f"spx {year}") as run:
            p = build_year(year, PANEL, GREEKS, sessions, closes)
            run["rows_out"] = len(p)
            (OUT / f"year={year}").mkdir(parents=True, exist_ok=True)
            p.to_parquet(OUT / f"year={year}" / f"pairs_{year}.parquet", index=False)
            a = p[p.E7]
            run["notes"] = f"E7 {len(a)}; ok {int((a.next_status == 'ok').sum())}"
            print(year, len(p), "E7:", len(a), "ok:", int((a.next_status == "ok").sum()), dict(a.next_status.value_counts()), flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else int(sys.argv[1]))
