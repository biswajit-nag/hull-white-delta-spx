"""Design step 1: parity forwards and discount factors, implied volatilities and Greeks (analysis_plan.md §4).

For each year, reads the step-3 panel (session rows only) and writes:
- data/processed/greeks/underlying=spx/year=YYYY/greeks_YYYY.parquet: one row per contract-day with
  τ, D, F, the mid's implied volatility and its solver status, and the Greeks at that volatility;
- data/processed/greeks/underlying=spx/sessions_YYYY.parquet: per session, the rate curve, how the
  stages bound, and sensitivity A's index level.

Usage: uv run python -I scripts/build_greeks.py 2015 2021
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import blackscholes as bs  # noqa: E402
from erdos_quant_finance_project import parity  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

PANEL = ROOT / "data/processed/optionsdx_long/underlying=spx"
OUT = ROOT / "data/processed/greeks/underlying=spx"
COLS = ["quote_date", "quote_unixtime", "expire_date", "strike", "cp", "am_settled", "settle_date", "settle_ts",
        "bid", "ask", "mid", "S_close", "is_session", "f_non_session",
        "f_post_settlement", "f_settle_uncertain", "f_stamp_not_session", "f_dup_key"]
E3_FLAGS = ["f_post_settlement", "f_settle_uncertain", "f_stamp_not_session", "f_dup_key"]
KEY = ["quote_date", "expire_date", "strike", "cp"]


def load(year: int) -> pd.DataFrame:
    t = ds.dataset(PANEL / f"year={year}").to_table(columns=COLS, filter=ds.field("is_session") & ~ds.field("f_non_session"))
    rows = t.to_pandas()
    rows["cp"] = rows.cp.astype(str)
    rows["quote_date"] = pd.to_datetime(rows.quote_date)
    rows["settle_date"] = pd.to_datetime(rows.settle_date)
    rows["tau"] = (rows.settle_ts - pd.to_datetime(rows.quote_unixtime, unit="s", utc=True)).dt.total_seconds() / (365 * 86400)
    return rows[rows.S_close.notna()].drop(columns=["is_session", "f_non_session", "quote_unixtime", "settle_ts"])


def build(year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = load(year)
    # parity candidates: session rows with time left and none of E3's flags (plan §4)
    w = parity.strike_table(rows[(rows.tau > 0) & ~rows[E3_FLAGS].any(axis=1)])
    fits = parity.stage1(w)
    curve = parity.stage2(fits)
    fwd = parity.stage3(w, curve)
    rows = rows.merge(fwd[parity.EXPIRY + ["D", "F"]], on=parity.EXPIRY, how="left")

    ok = rows.F.notna() & (rows.tau > 0) & (rows.bid > 0) & (rows.ask >= rows.bid)
    r = rows[ok]
    cp = np.where(r.cp == "C", 1.0, -1.0)
    iv, status = bs.implied_vol(r.mid.values, r.S_close.values, r.F.values, r.strike.values, r.D.values, r.tau.values, cp)
    rows["iv"], rows["iv_status"] = np.nan, "no_forward"
    rows.loc[~(rows.tau > 0), "iv_status"] = "expired"
    rows.loc[rows.F.notna() & (rows.tau > 0) & ~((rows.bid > 0) & (rows.ask >= rows.bid)), "iv_status"] = "one_sided"
    rows.loc[ok, "iv"], rows.loc[ok, "iv_status"] = iv, status
    good = rows.iv_status == "converged"
    g = rows[good]
    G = bs.greeks(g.S_close.values, g.F.values, g.strike.values, g.D.values, g.iv.values, g.tau.values,
                  np.where(g.cp == "C", 1.0, -1.0))
    G["theta"] = bs.theta_spot(g.S_close.values, g.F.values, g.D.values, g.tau.values, G)
    for k in ["delta", "vega", "gamma", "vanna", "volga", "theta_F", "theta", "dV_dF"]:
        rows[k] = np.nan
        rows.loc[good, k] = G[k]
    rows = rows.drop(columns=["bid", "ask", "mid"] + E3_FLAGS)

    sess = curve.join(parity.level_A(w), how="outer")
    sess["S_close"] = rows.groupby("quote_date").S_close.first()
    sess["expiries"] = rows.groupby("quote_date")[parity.EXPIRY].apply(lambda x: x.drop_duplicates().shape[0])
    sess["stage1_fits"] = fits.groupby("quote_date").size()
    sess["stage3_forwards"] = fwd.groupby("quote_date").size()
    return rows, sess.reset_index().rename(columns={"index": "quote_date"})


def main(first: int, last: int) -> None:
    for year in range(first, last + 1):
        with timed("build_greeks", inputs=f"spx {year}") as run:
            rows, sess = build(year)
            run["rows_in"], run["rows_out"] = len(rows), int((rows.iv_status == "converged").sum())
            (OUT / f"year={year}").mkdir(parents=True, exist_ok=True)
            rows.to_parquet(OUT / f"year={year}" / f"greeks_{year}.parquet", index=False)
            sess.to_parquet(OUT / f"sessions_{year}.parquet", index=False)
            st = rows.iv_status.value_counts()
            run["notes"] = "; ".join(f"{k} {v}" for k, v in st.items())
            print(year, len(rows), dict(st), f"sessions {len(sess)}, A missing {sess.S_A.isna().sum()}", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else int(sys.argv[1]))
