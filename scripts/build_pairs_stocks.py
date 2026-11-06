"""Stock and ETF hedge pairs (analysis_plan.md section 16.15): the SPY pair rules, plus day-two dividends and the split rule.

Writes data/processed/pairs/underlying=<u>/year=YYYY/pairs_YYYY.parquet with
- div_next: the cash dividend per share when day two (the next NYSE session) is an ex-date, else 0
  (Nasdaq history, saved under data/external; TSLA and SLV: none paid), and div_source ("nasdaq" | "none_paid");
- E9: False for a pair whose two sessions straddle a split (one-session move in UNDERLYING_LAST above 30%,
  detected on consecutive vendor dates); the pair is kept in the file, as an E-rule column to be applied
  with E1-E8. Detected splits are written to results/stocks/<u>/splits.csv.

Usage: uv run python -I scripts/build_pairs_stocks.py aapl 2016 2023
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import stocks  # noqa: E402
from erdos_quant_finance_project.pairs import build_year  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402


def main(u: str, first: int, last: int) -> None:
    panel = ROOT / f"data/processed/optionsdx_long/underlying={u}"
    greeks = ROOT / f"data/processed/greeks/underlying={u}"
    out = ROOT / f"data/processed/pairs/underlying={u}"
    t = ds.dataset(panel).to_table(columns=["quote_date", "S_close", "is_session"]).to_pandas()
    sessions = t[t.is_session].groupby("quote_date").S_close.first().reset_index()
    sessions["quote_date"] = pd.to_datetime(sessions.quote_date)
    sessions["S_A"] = np.nan  # no options-implied level for these underlyings
    sessions = sessions.sort_values("quote_date")
    closes = sessions.set_index("quote_date").S_close  # the vendor's snapshot is the close for these five
    allS = ds.dataset(ROOT / "data/interim/optionsdx", format="parquet", partitioning="hive").to_table(
        columns=["quote_date", "underlying_last"], filter=ds.field("underlying") == u).to_pandas()
    allS = allS.groupby("quote_date").underlying_last.first()
    allS.index = pd.to_datetime(allS.index)
    splits = stocks.detect_splits(allS)
    (ROOT / f"results/stocks/{u}").mkdir(parents=True, exist_ok=True)
    splits.to_csv(ROOT / f"results/stocks/{u}/splits.csv", index=False)
    div = stocks.dividends(ROOT / "data/external", u).groupby(level=0).sum()
    source = "nasdaq" if u in stocks.PAYERS else "none_paid"
    for year in range(first, last + 1):
        with timed("build_pairs_stocks", inputs=f"{u} {year}") as run:
            p = build_year(year, panel, greeks, sessions, closes)
            p["div_next"] = p.next_session.map(div).fillna(0.0)
            p["div_source"] = source
            p["E9"] = True
            for s in splits.itertuples():
                p.loc[(p.quote_date < s.date) & (p.next_session >= s.date), "E9"] = False
            run["rows_out"] = len(p)
            (out / f"year={year}").mkdir(parents=True, exist_ok=True)
            p.to_parquet(out / f"year={year}" / f"pairs_{year}.parquet", index=False)
            a = p[p.E7]
            print(u, year, len(p), "E7:", len(a), "ok:", int((a.next_status == "ok").sum()),
                  "split-straddling:", int((~p.E9).sum()), "ex-date pairs:", int((a.div_next > 0).sum()), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else int(sys.argv[2]))
