"""Pairs at every maturity and delta, for the later days of a held position (analysis_plan.md §16.11).

The SPX, SPY or stock pair rules of build_pairs.py / build_pairs_spy.py / build_pairs_stocks.py with
build_year(maturity="any"): every
two-sided contract-day with a converged IV and τ > 0, ending before settlement; E7 and `in_band` (E5 and E6
of the main sample) kept as columns. A path's first day still comes from the analysis sample.

Writes data/processed/pairs_any/underlying=<u>/year=YYYY/pairs_YYYY.parquet.

Usage: uv run python -I scripts/build_pairs_any.py FIRST LAST [--spy | --underlying U]
  (U one of aapl nvda tsla qqq slv; e.g. 2016 2023 --underlying aapl)
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

U = sys.argv[sys.argv.index("--underlying") + 1] if "--underlying" in sys.argv else ("spy" if "--spy" in sys.argv else "spx")
PANEL = ROOT / f"data/processed/optionsdx_long/underlying={U}"
GREEKS = ROOT / f"data/processed/greeks/underlying={U}"
OUT = ROOT / f"data/processed/pairs_any/underlying={U}"
STOCK = U not in ("spx", "spy")


def stock_inputs():
    """As scripts/build_pairs_stocks.py: the vendor's snapshot as the close, Nasdaq dividends, the split rule (E9)."""
    from erdos_quant_finance_project import stocks
    t = ds.dataset(PANEL).to_table(columns=["quote_date", "S_close", "is_session"]).to_pandas()
    s = t[t.is_session].groupby("quote_date").S_close.first().reset_index()
    s["quote_date"] = pd.to_datetime(s.quote_date)
    s["S_A"] = np.nan
    s = s.sort_values("quote_date")
    div = stocks.dividends(ROOT / "data/external", U).groupby(level=0).sum()
    splits = pd.read_csv(ROOT / f"results/stocks/{U}/splits.csv", parse_dates=["date"])
    return s, s.set_index("quote_date").S_close, div, splits


def sessions_and_divs():
    if U == "spx":
        s = pd.concat([pd.read_parquet(p) for p in sorted(GREEKS.glob("sessions_*.parquet"))])
        s["quote_date"] = pd.to_datetime(s.quote_date)
        return s.sort_values("quote_date"), None
    t = ds.dataset(PANEL).to_table(columns=["quote_date", "S_close", "is_session"]).to_pandas()
    s = t[t.is_session].groupby("quote_date").S_close.first().reset_index()
    s["quote_date"] = pd.to_datetime(s.quote_date)
    s["S_A"] = np.nan
    div = pd.read_csv(ROOT / "data/external/ssga_SPY_distributions.csv", parse_dates=["ex_date"]).set_index("ex_date").dividend
    return s.sort_values("quote_date"), div


def main(first: int, last: int) -> None:
    splits = None
    if STOCK:
        sessions, closes, div, splits = stock_inputs()
    else:
        sessions, div = sessions_and_divs()
        nyse = nyse_sessions("2009-11-01", "2024-02-28").index
        closes = official_closes(ROOT / "data/external", U).S_close.reindex(nyse).dropna()
    for year in range(first, last + 1):
        with timed("build_pairs_any", inputs=f"{U} {year}") as run:
            p = build_year(year, PANEL, GREEKS, sessions, closes, maturity="any")
            if div is not None:
                p["div_next"] = p.next_session.map(div).fillna(0.0)
            if splits is not None:
                p["E9"] = True
                for s in splits.itertuples():
                    p.loc[(p.quote_date < s.date) & (p.next_session >= s.date), "E9"] = False
            run["rows_out"] = len(p)
            (OUT / f"year={year}").mkdir(parents=True, exist_ok=True)
            p.to_parquet(OUT / f"year={year}" / f"pairs_{year}.parquet", index=False)
            ok = int((p.next_status == "ok").sum())
            run["notes"] = f"ok {ok}; in band {int(p.in_band.sum())}"
            print(U, year, len(p), "ok:", ok, "in band:", int(p.in_band.sum()), flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(int(args[0]), int(args[1]) if len(args) > 1 else int(args[0]))
