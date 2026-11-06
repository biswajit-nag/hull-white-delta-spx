"""Stocks and ETFs step 1 (analysis_plan.md section 16.15): rates from SPX, dividend yields, American put IVs, Greeks.

As scripts/build_greeks_spy.py, with: S = the vendor's UNDERLYING_LAST (S_close); r(tau) from the same session's SPX
parity curve; q per session = trailing-12-month cash dividends (split-adjusted to the day's share basis) / S,
0 for TSLA and SLV; EVERY two-sided contract-day with tau > 0 is solved (as the SPX panel), not only day-one
candidates. Puts: Lecture 12's CRR tree (150 steps, control variate); calls: European Black-Scholes with yield q.

Usage: uv run python -I scripts/build_greeks_stocks.py aapl 2016 2023
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
from erdos_quant_finance_project import parity, stocks  # noqa: E402
from erdos_quant_finance_project.lecture import option_pricing  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

SPXG = ROOT / "data/processed/greeks/underlying=spx"
STEPS = 150
CHUNK = 40000


def tree_chunks(x: pd.DataFrame, op):
    """IV, status and tree Greeks for puts, in chunks to bound memory."""
    n = len(x)
    cols = ["iv", "delta", "vega", "gamma", "vanna", "theta"]
    res = {c: np.full(n, np.nan) for c in cols}
    status = np.empty(n, dtype=object)
    for a in range(0, n, CHUNK):
        c = x.iloc[a:a + CHUNK]
        S, K, T, R, Q = (c[k].values for k in ("S_close", "strike", "tau", "r", "q"))
        out = op.bs_american_put_iv(c.mid.values, S, K, T, r=R, q=Q, n_steps=STEPS, control_variate=True, return_info=True)
        st = np.asarray(out["status"], dtype=object)
        status[a:a + CHUNK] = st
        ok = st == "converged"
        if not ok.any():
            continue
        S, K, T, R, Q, sg = S[ok], K[ok], T[ok], R[ok], Q[ok], np.asarray(out["iv"])[ok]
        px = lambda s, v, tt=T: op.bs_american_put(s, K, v, tt, R, Q, n_steps=STEPS, control_variate=True)
        h = 0.005 * S
        up, dn, mid = px(S + h, sg), px(S - h, sg), px(S, sg)
        s_hi, s_lo = sg + 0.01, np.maximum(sg - 0.01, 1e-4)
        d_hi = (px(S + h, s_hi) - px(S - h, s_hi)) / (2 * h)
        d_lo = (px(S + h, s_lo) - px(S - h, s_lo)) / (2 * h)
        idx = np.arange(a, a + len(c))[ok]
        res["iv"][idx] = sg
        res["delta"][idx] = (up - dn) / (2 * h)
        res["vega"][idx] = (px(S, s_hi) - px(S, s_lo)) / (s_hi - s_lo)
        res["gamma"][idx] = (up - 2 * mid + dn) / h**2
        res["vanna"][idx] = (d_hi - d_lo) / (s_hi - s_lo)
        dt = np.minimum(1 / 365, T)  # one calendar day, or the time left if less (early-close expiries)
        res["theta"][idx] = (px(S, sg, T - dt) - mid) / dt  # per year, as the lectures' theta
    return res, status


def build(u: str, year: int, yields: pd.Series) -> pd.DataFrame:
    op = option_pricing()
    t = ds.dataset(ROOT / f"data/processed/optionsdx_long/underlying={u}/year={year}").to_table(
        columns=["quote_date", "quote_unixtime", "expire_date", "strike", "cp", "am_settled", "settle_date", "settle_ts",
                 "bid", "ask", "mid", "S_close", "is_session", "f_non_session"],
        filter=ds.field("is_session") & ~ds.field("f_non_session")).to_pandas()
    t["cp"] = t.cp.astype(str)
    t["quote_date"], t["settle_date"] = pd.to_datetime(t.quote_date), pd.to_datetime(t.settle_date)
    t["tau"] = (t.settle_ts - pd.to_datetime(t.quote_unixtime, unit="s", utc=True)).dt.total_seconds() / (365 * 86400)
    curve = pd.read_parquet(SPXG / f"sessions_{year}.parquet").set_index("quote_date")
    r = -np.log(parity.discount(curve, t.quote_date, t.tau)) / t.tau
    t["r"] = r.values
    t["q"] = t.quote_date.map(yields).astype(float)
    t["D"] = np.exp(-t.r * t.tau)
    t["F"] = t.S_close * np.exp((t.r - t.q) * t.tau)
    two = (t.bid > 0) & (t.ask >= t.bid)
    inputs = t.r.notna() & t.q.notna() & t.S_close.notna()
    live = t.tau > 0
    t["iv"], t["iv_status"] = np.nan, "no_rate"
    t.loc[~live, "iv_status"] = "expired"
    t.loc[inputs & live & ~two, "iv_status"] = "one_sided"
    cand = inputs & live & two
    t.loc[cand, "iv_status"] = "candidate"
    for c in ["delta", "vega", "gamma", "vanna", "volga", "theta_F", "theta", "dV_dF"]:
        t[c] = np.nan
    m = cand & (t.cp == "C")
    x = t[m]
    iv, st = bs.implied_vol(x.mid.values, x.S_close.values, x.F.values, x.strike.values, x.D.values, x.tau.values, 1.0)
    t.loc[m, "iv"], t.loc[m, "iv_status"] = iv, st
    ok = m & (t.iv_status == "converged")
    x = t[ok]
    G = bs.greeks(x.S_close.values, x.F.values, x.strike.values, x.D.values, x.iv.values, x.tau.values, 1.0)
    for k in ("delta", "vega", "gamma", "vanna", "volga", "theta_F", "dV_dF"):
        t.loc[ok, k] = G[k]
    t.loc[ok, "theta"] = bs.theta_spot(x.S_close.values, x.F.values, x.D.values, x.tau.values, G)
    m = cand & (t.cp == "P")
    x = t[m]
    res, st = tree_chunks(x, op)
    t.loc[m, "iv_status"] = st
    for k, v in res.items():
        t.loc[m, k] = v
    ok = m & (t.iv_status == "converged")
    t.loc[ok, "dV_dF"] = t.delta[ok] * t.S_close[ok] / t.F[ok]
    t["q_level"] = "trailing12m"
    return t.drop(columns=["bid", "ask", "mid", "quote_unixtime", "settle_ts", "is_session", "f_non_session"])


def session_yields(u: str) -> pd.Series:
    S = ds.dataset(ROOT / "data/interim/optionsdx", format="parquet", partitioning="hive").to_table(
        columns=["quote_date", "underlying_last"], filter=ds.field("underlying") == u).to_pandas()
    S = S.groupby("quote_date").underlying_last.first()
    S.index = pd.to_datetime(S.index)
    if u not in stocks.PAYERS:
        return pd.Series(0.0, index=S.index)
    sp = stocks.detect_splits(S)
    return stocks.trailing_yield(stocks.dividends(ROOT / "data/external", u), sp, S.index, S)


def main(u: str, first: int, last: int) -> None:
    yields = session_yields(u)
    for year in range(first, last + 1):
        with timed("build_greeks_stocks", inputs=f"{u} {year}, CRR {STEPS} steps") as run:
            g = build(u, year, yields)
            run["rows_in"], run["rows_out"] = len(g), int((g.iv_status == "converged").sum())
            st = g.iv_status.value_counts()
            run["notes"] = "; ".join(f"{k} {v}" for k, v in st.items())
            (ROOT / f"data/processed/greeks/underlying={u}/year={year}").mkdir(parents=True, exist_ok=True)
            g.to_parquet(ROOT / f"data/processed/greeks/underlying={u}/year={year}/greeks_{year}.parquet", index=False)
            print(u, year, len(g), dict(st), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else int(sys.argv[2]))
