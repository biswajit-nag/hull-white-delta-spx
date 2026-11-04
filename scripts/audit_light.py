"""The light audit of the extra training years (analysis_plan.md §7, W36 and W60), by month.

Data quality only, no hedging outcome: sessions and rows, expiries per session, flag rates, the
next-session status of eligible pairs, the volume coding of §5, implied-volatility failures, and
sensitivity A's coverage. Writes results/audit_light.csv.

Usage: uv run python -I scripts/audit_light.py 2015 2019 [spx|spy]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project.runlog import timed  # noqa: E402

U = sys.argv[3] if len(sys.argv) > 3 else "spx"
PANEL = ROOT / f"data/processed/optionsdx_long/underlying={U}"
GREEKS = ROOT / f"data/processed/greeks/underlying={U}"
PAIRS = ROOT / f"data/processed/pairs/underlying={U}"
FLAGS = ["f_non_session", "f_one_sided", "f_crossed", "f_dup_key", "f_stamp_window", "f_post_settlement",
         "f_restamped", "f_stamp_not_session", "f_settle_uncertain"]


def month_table(year: int) -> pd.DataFrame:
    rows = ds.dataset(PANEL / f"year={year}").to_table(
        columns=["quote_date", "am_settled", "settle_date", "volume", "last", "is_session"] + FLAGS).to_pandas()
    rows["month"] = pd.to_datetime(rows.quote_date).dt.to_period("M")
    g = rows.groupby("month")
    t = pd.DataFrame({"sessions": g.quote_date.nunique(), "rows": g.size()})
    t["expiries_per_session"] = rows.groupby(["month", "quote_date"])[["am_settled", "settle_date"]].apply(
        lambda x: len(x.drop_duplicates())).groupby("month").mean()
    for f in FLAGS:
        t[f] = g[f].mean()
    t["volume_max"] = g.volume.max()
    t["volume_empty"] = g.volume.apply(lambda v: v.isna().mean())
    t["empty_last_pos"] = rows.assign(x=rows.volume.isna() & (rows["last"] > 0)).groupby("month").x.mean()
    gr = pd.read_parquet(GREEKS / f"year={year}" / f"greeks_{year}.parquet", columns=["quote_date", "iv_status"])
    gr["month"] = pd.to_datetime(gr.quote_date).dt.to_period("M")
    t["iv_converged"] = gr.groupby("month").iv_status.apply(lambda s: (s == "converged").mean())
    if (GREEKS / f"sessions_{year}.parquet").exists():
        s = pd.read_parquet(GREEKS / f"sessions_{year}.parquet")
        s["month"] = pd.to_datetime(s.quote_date).dt.to_period("M")
        t["A_missing_sessions"] = s.groupby("month").S_A.apply(lambda x: int(x.isna().sum()))
        t["rate_c0_mean"] = s.groupby("month").c0.mean()
    p = pd.read_parquet(PAIRS / f"year={year}" / f"pairs_{year}.parquet", columns=["quote_date", "E7", "next_status"])
    p = p[p.E7]
    p["month"] = pd.to_datetime(p.quote_date).dt.to_period("M")
    st = p.groupby("month").next_status.value_counts(normalize=True).unstack(fill_value=0)
    t = t.join(st.add_prefix("next_"))
    t["eligible_pairs"] = p.groupby("month").size()
    return t.reset_index()


def main(first: int, last: int) -> None:
    with timed("audit_light", inputs=f"{U} {first}-{last}") as run:
        T = pd.concat([month_table(y) for y in range(first, last + 1)], ignore_index=True)
        T.to_csv(ROOT / ("results/audit_light.csv" if U == "spx" else f"results/audit_light_{U}.csv"), index=False)
        run["rows_out"] = len(T)
    with pd.option_context("display.width", 250, "display.max_columns", 40):
        cols = [c for c in ["month", "sessions", "expiries_per_session", "f_stamp_window", "f_restamped", "volume_max", "volume_empty",
                "empty_last_pos", "iv_converged", "A_missing_sessions", "next_ok", "eligible_pairs"] if c in T]
        print(T[cols].round(4).to_string(index=False))


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
