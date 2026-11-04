"""SPY hedge pairs (analysis_plan.md §16.1): the SPX pair rules, plus each pair's day-two distribution.

Writes data/processed/pairs/underlying=spy/year=YYYY/pairs_YYYY.parquet with `div_next`, the cash
distribution when day two is an ex-date (SSGA's file), else 0.

Usage: uv run python -I scripts/build_pairs_spy.py 2019 2020
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project.pairs import build_year  # noqa: E402
from erdos_quant_finance_project.processed import nyse_sessions, official_closes  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

PANEL = ROOT / "data/processed/optionsdx_long/underlying=spy"
GREEKS = ROOT / "data/processed/greeks/underlying=spy"
OUT = ROOT / "data/processed/pairs/underlying=spy"


def main(first: int, last: int) -> None:
    t = ds.dataset(PANEL).to_table(columns=["quote_date", "S_close", "is_session"]).to_pandas()
    sessions = t[t.is_session].groupby("quote_date").S_close.first().reset_index()
    sessions["quote_date"] = pd.to_datetime(sessions.quote_date)
    sessions["S_A"] = np.nan  # no options-implied level for SPY: American parity gives only bounds
    div = pd.read_csv(ROOT / "data/external/ssga_SPY_distributions.csv", parse_dates=["ex_date"]).set_index("ex_date").dividend
    # the R7/R8 index features use the official close on NYSE sessions, not the vendor's dates
    nyse = nyse_sessions("2009-11-01", "2024-02-28").index
    closes = official_closes(ROOT / "data/external", "spy").S_close.reindex(nyse).dropna()
    for year in range(first, last + 1):
        with timed("build_pairs_spy", inputs=f"spy {year}") as run:
            p = build_year(year, PANEL, GREEKS, sessions.sort_values("quote_date"), closes)
            p["div_next"] = p.next_session.map(div).fillna(0.0)
            run["rows_out"] = len(p)
            (OUT / f"year={year}").mkdir(parents=True, exist_ok=True)
            p.to_parquet(OUT / f"year={year}" / f"pairs_{year}.parquet", index=False)
            a = p[p.E7]
            print(year, len(p), "E7:", len(a), "ok:", int((a.next_status == "ok").sum()), "ex-date pairs:", int((a.div_next > 0).sum()), flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else int(sys.argv[1]))
