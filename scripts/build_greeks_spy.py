"""SPY step 1 (analysis_plan.md §16.1): rates and yields from SPX, American put IVs, and Greeks.

For each SPY session: r(τ) from that session's SPX parity curve; q(τ) from SPX's implied carry
(r − ln(F_e/S_A)/τ_e over SPX expiries 30 days to 2 years, linear in τ, flat beyond) less SPY's 0.0945%
expense ratio. Puts: Lecture 12's bs_american_put_iv (CRR, 150 steps, control variate) with δ and ν
by central differences on the same tree. Calls: bs_euro_iv and analytic Greeks with yield q.
Only day-one candidates are solved: τ ≥ 14 days, two-sided, E7.

Writes data/processed/greeks/underlying=spy/year=YYYY/greeks_YYYY.parquet in the SPX schema, with
F = S·e^{(r−q)τ}, D = e^{−rτ}, and dV_dF = δ·S/F so that δ = dV_dF·F/S as for SPX.

Usage: uv run python -I scripts/build_greeks_spy.py 2019 2021
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
from erdos_quant_finance_project.lecture import option_pricing  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

SPY = ROOT / "data/processed/optionsdx_long/underlying=spy"
SPXG = ROOT / "data/processed/greeks/underlying=spx"
OUT = ROOT / "data/processed/greeks/underlying=spy"
EXPENSE = 0.000945
STEPS = 150


def yield_curve(year: int) -> pd.DataFrame:
    """Per session: SPX's implied carry q(τ) = r(τ) − ln(F_e/S_A)/τ_e, linear in τ over 30 days–2 years."""
    g = pd.read_parquet(SPXG / f"year={year}" / f"greeks_{year}.parquet", columns=["quote_date", "am_settled", "settle_date", "tau", "D", "F"])
    e = g.dropna(subset=["F"]).drop_duplicates(["quote_date", "am_settled", "settle_date"])
    s = pd.read_parquet(SPXG / f"sessions_{year}.parquet")[["quote_date", "S_A"]]
    e = e.merge(s, on="quote_date")
    e = e[(e.tau >= 30 / 365) & (e.tau <= 2) & e.S_A.notna()]
    e["q"] = -np.log(e.D) / e.tau - np.log(e.F / e.S_A) / e.tau
    rows = {}
    for d, x in e.groupby("quote_date"):
        if len(x) >= 2:
            c1, c0 = np.polyfit(x.tau, x.q, 1)
        else:
            c0, c1 = x.q.mean(), 0.0
        rows[d] = {"q0": c0, "q1": c1, "q_lo": x.tau.min(), "q_hi": x.tau.max()}
    return pd.DataFrame(rows).T


def build(year: int) -> pd.DataFrame:
    op = option_pricing()
    t = ds.dataset(SPY / f"year={year}").to_table(
        columns=["quote_date", "quote_unixtime", "expire_date", "strike", "cp", "am_settled", "settle_date", "settle_ts",
                 "bid", "ask", "mid", "volume", "last", "S_close", "is_session", "f_non_session"],
        filter=ds.field("is_session") & ~ds.field("f_non_session")).to_pandas()
    t["cp"] = t.cp.astype(str)
    t["quote_date"], t["settle_date"] = pd.to_datetime(t.quote_date), pd.to_datetime(t.settle_date)
    t["tau"] = (t.settle_ts - pd.to_datetime(t.quote_unixtime, unit="s", utc=True)).dt.total_seconds() / (365 * 86400)
    curve = pd.read_parquet(SPXG / f"sessions_{year}.parquet").set_index("quote_date")
    qc = yield_curve(year)
    r = -np.log(parity.discount(curve, t.quote_date, t.tau)) / t.tau
    qq = qc.reindex(t.quote_date.values)
    tq = np.clip(t.tau.values, qq.q_lo.values.astype(float), qq.q_hi.values.astype(float))
    t["r"] = r.values
    t["q"] = qq.q0.values.astype(float) + qq.q1.values.astype(float) * tq - EXPENSE
    t["D"] = np.exp(-t.r * t.tau)
    t["F"] = t.S_close * np.exp((t.r - t.q) * t.tau)
    cand = (t.tau >= 14 / 365) & (t.bid > 0) & (t.ask >= t.bid) & ((t.volume > 0) | (t.volume.isna() & (t["last"] > 0))) \
        & t.r.notna() & t.q.notna() & t.S_close.notna()
    t["iv"], t["iv_status"] = np.nan, "not_candidate"
    for c in ["delta", "vega", "gamma", "vanna", "volga", "theta_F", "theta", "dV_dF"]:
        t[c] = np.nan
    # calls: European, as the lecture prices SPY calls
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
    # puts: American CRR tree with the control variate
    m = cand & (t.cp == "P")
    x = t[m]
    out = op.bs_american_put_iv(x.mid.values, x.S_close.values, x.strike.values, x.tau.values, r=x.r.values, q=x.q.values,
                                n_steps=STEPS, control_variate=True, return_info=True)
    t.loc[m, "iv"], t.loc[m, "iv_status"] = out["iv"], out["status"]
    ok = m & (t.iv_status == "converged")
    x = t[ok]
    S, K, sg, T, R, Q = (x[c].values for c in ("S_close", "strike", "iv", "tau", "r", "q"))
    px = lambda s, v: op.bs_american_put(s, K, v, T, R, Q, n_steps=STEPS, control_variate=True)
    h = 0.005 * S
    delta = (px(S + h, sg) - px(S - h, sg)) / (2 * h)
    vega = (px(S, sg + 0.01) - px(S, np.maximum(sg - 0.01, 1e-4))) / (sg + 0.01 - np.maximum(sg - 0.01, 1e-4))
    t.loc[ok, "delta"], t.loc[ok, "vega"] = delta, vega
    t.loc[ok, "dV_dF"] = delta * S / x.F.values
    return t.drop(columns=["bid", "ask", "mid", "volume", "last", "quote_unixtime", "settle_ts", "is_session", "f_non_session"])


def main(first: int, last: int) -> None:
    for year in range(first, last + 1):
        with timed("build_greeks_spy", inputs=f"spy {year}, CRR {STEPS} steps") as run:
            g = build(year)
            run["rows_out"] = int((g.iv_status == "converged").sum())
            (OUT / f"year={year}").mkdir(parents=True, exist_ok=True)
            g.to_parquet(OUT / f"year={year}" / f"greeks_{year}.parquet", index=False)
            print(year, dict(g.iv_status.value_counts()), flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else int(sys.argv[1]))
