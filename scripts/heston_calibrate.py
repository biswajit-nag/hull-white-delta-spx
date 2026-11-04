"""Daily Heston calibrations of SPX, 2019–2020, in the style of Lecture 12 (analysis_plan.md §16.2).

Calibration L (the lecture's): calls 50–100 days, 0.8 < S/K < 1.2, sizes > 10, the size-weighted price;
fitted twice, to price errors and to implied-volatility errors. Calibration B (broad): out-of-the-money
calls and puts 14 days to 1 year, two-sided, E7, mids; implied-volatility errors. scipy least_squares
with the lecture's bounds; sessions within a month in parallel, warm-started from the previous month.
Writes results/heston/params.csv.

Usage: uv run python -I scripts/heston_calibrate.py
"""

from __future__ import annotations

import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from scipy.optimize import least_squares

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import blackscholes as bs  # noqa: E402
from erdos_quant_finance_project.lecture import option_pricing  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

PANEL = ROOT / "data/processed/optionsdx_long/underlying=spx"
GREEKS = ROOT / "data/processed/greeks/underlying=spx"
OUT = ROOT / "results/heston"
LB = np.array([0.01**2, 0.1, 0.01**2, 0.05, -0.999])
UB = np.array([1.5**2, 10.0, 1.0**2, 5.0, 0.0])
X0 = np.array([0.04, 2.0, 0.04, 0.5, -0.7])
NAMES = ["v0", "kappa", "theta", "xi", "rho"]


def day_quotes(day: pd.Timestamp) -> pd.DataFrame:
    p = ds.dataset(PANEL / f"year={day.year}").to_table(
        columns=["quote_date", "expire_date", "strike", "cp", "bid", "ask", "bid_size", "ask_size", "volume", "last", "S_close"],
        filter=(ds.field("quote_date") == day.date()) & ds.field("is_session")).to_pandas()
    g = ds.dataset(GREEKS / f"year={day.year}").to_table(
        columns=["quote_date", "expire_date", "strike", "cp", "tau", "D", "F"], filter=ds.field("quote_date") == day).to_pandas()
    p["cp"], g["cp"] = p.cp.astype(str), g.cp.astype(str)
    p["quote_date"], p["expire_date"] = pd.to_datetime(p.quote_date), pd.to_datetime(p.expire_date)
    g["expire_date"] = pd.to_datetime(g.expire_date)
    return p.merge(g, on=["quote_date", "expire_date", "strike", "cp"]).dropna(subset=["F", "D"])


def model_price(x, d, op):
    v0, ka, th, xi, rho = x
    r, q = bs.carry(d.S_close.values, d.F.values, d.D.values, d.tau.values)
    price = np.empty(len(d))
    for sign, f in ((1.0, op.heston_call), (-1.0, op.heston_put)):
        m = d.sgn.values == sign
        if m.any():
            price[m] = f(d.S_close.values[m], d.strike.values[m], v0, r[m], d.tau.values[m], ka, th, xi, rho, q[m], check_bounds=False)
    return price


def fit(d: pd.DataFrame, target: str, x0) -> dict:
    op = option_pricing()
    ivm = bs.implied_vol(d.px.values, d.S_close.values, d.F.values, d.strike.values, d.D.values, d.tau.values, d.sgn.values)[0]
    keep = np.isfinite(ivm)
    d, ivm = d[keep], ivm[keep]
    if target == "price":
        fun = lambda x: model_price(x, d, op) - d.px.values
    else:
        def fun(x):
            iv = bs.implied_vol(model_price(x, d, op), d.S_close.values, d.F.values, d.strike.values, d.D.values, d.tau.values, d.sgn.values)[0]
            return np.where(np.isfinite(iv), iv - ivm, 1.0)  # an unpriceable model price costs 100 vol points
    res = least_squares(fun, x0=np.clip(x0, LB + 1e-6, UB - 1e-6), bounds=(LB, UB))
    at_bound = bool(np.any(np.minimum(res.x - LB, UB - res.x) < 1e-6))
    iv = bs.implied_vol(model_price(res.x, d, op), d.S_close.values, d.F.values, d.strike.values, d.D.values, d.tau.values, d.sgn.values)[0]
    return {**dict(zip(NAMES, res.x)), "n": len(d), "nfev": res.nfev, "converged": bool(res.success), "at_bound": at_bound,
            "ok": bool(res.success) and not at_bound, "iv_rmse": float(np.sqrt(np.nanmean((iv - ivm) ** 2))),
            "price_rmse": float(np.sqrt(np.mean((model_price(res.x, d, op) - d.px.values) ** 2)))}


def calibrate_day(args) -> list[dict]:
    day, x0 = args
    d = day_quotes(day)
    out = []
    two = (d.bid > 0) & (d.ask >= d.bid)
    L = d[(d.cp == "C") & (d.tau * 365).between(50, 100) & (d.S_close / d.strike).between(0.8, 1.2, inclusive="neither")
          & (d.bid_size > 10) & (d.ask_size > 10) & two].copy()
    L["px"] = (L.bid * L.bid_size + L.ask * L.ask_size) / (L.bid_size + L.ask_size)
    L["sgn"] = 1.0
    B = d[two & (d.tau * 365).between(14, 365) & ((d.volume > 0) | (d.volume.isna() & (d["last"] > 0)))
          & (((d.cp == "C") & (d.strike >= d.F)) | ((d.cp == "P") & (d.strike < d.F)))].copy()
    B["px"] = (B.bid + B.ask) / 2
    B["sgn"] = np.where(B.cp == "C", 1.0, -1.0)
    for name, data, target in (("L-price", L, "price"), ("L-iv", L, "iv"), ("B-iv", B, "iv")):
        if len(data) >= 10:
            out.append({"session": day, "fit": name, **fit(data, target, x0)})
        else:
            out.append({"session": day, "fit": name, "n": len(data), "ok": False})
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    days = pd.read_parquet(GREEKS / "sessions_2019.parquet").quote_date.tolist() + pd.read_parquet(GREEKS / "sessions_2020.parquet").quote_date.tolist()
    days = pd.DatetimeIndex(pd.to_datetime(days)).sort_values()
    x0 = {f: X0 for f in ("L-price", "L-iv", "B-iv")}
    rows = []
    with timed("heston_calibrate", inputs="spx 2019-2020, fits L-price, L-iv, B-iv", rows_in=len(days)) as run:
        with ProcessPoolExecutor(max_workers=6) as pool:
            for m, md in pd.Series(days, index=days).groupby(days.to_period("M")):
                # within a month every session starts from last month's median solution; the B fit is the reference
                res = list(pool.map(calibrate_day, [(d, x0["B-iv"]) for d in md]))
                month = pd.DataFrame([r for day in res for r in day])
                rows.append(month)
                okb = month[(month.fit == "B-iv") & month.ok.fillna(False).astype(bool)]
                if len(okb):
                    x0["B-iv"] = okb[NAMES].median().to_numpy()
                print(m, "B-iv ok", len(okb), "of", len(md), flush=True)
        P = pd.concat(rows, ignore_index=True)
        P.to_csv(OUT / "params.csv", index=False)
        run["rows_out"] = len(P)
        run["notes"] = "; ".join(f"{f} ok {int(P[P.fit == f].ok.fillna(False).sum())}" for f in ("L-price", "L-iv", "B-iv"))


if __name__ == "__main__":
    main()
