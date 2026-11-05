"""Daily Heston calibration B2 of SPX (analysis_plan.md §16.5), with the project's own pricer.

Calibration B's sample and the lecture's bounds: out-of-the-money calls and puts 14 days to 1 year,
two-sided, E7, mids, at least 10 options. Residuals (model − mid)/ν, ν the option's Black–Scholes vega at
its own IV floored at 1% of its expiry's at-the-money vega. Two starts per session (the previous session's
solution, a start from that day's at-the-money IV; the first session of a year uses the latter and the
lecture default); the lower cost wins. Sessions run in order within a calendar year, years in parallel.
Per session: wall and CPU time, evaluations, cost, the exact IV RMSE, bound hits, and an accuracy check
against a grid of twice the range and node density. Writes results/heston2/params_YYYY.csv.

Usage: uv run python -I scripts/heston2_calibrate.py FIRST LAST [WORKERS]
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")  # one core per process: years run in parallel
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.dataset as ds  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import blackscholes as bs  # noqa: E402
from erdos_quant_finance_project import heston as H  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

PANEL = ROOT / "data/processed/optionsdx_long/underlying=spx"
GREEKS = ROOT / "data/processed/greeks/underlying=spx"
OUT = ROOT / "results/heston2"


def sample_b(day: pd.Timestamp | None, year: int | None = None) -> pd.DataFrame:
    """Calibration B's options on one session (or, with day=None, every session of `year`), with each
    option's IV, vega and the expiry's D and F."""
    year = day.year if day is not None else year
    pf, gf = ds.field("is_session"), ds.field("iv_status") == "converged"
    if day is not None:
        pf, gf = pf & (ds.field("quote_date") == day.date()), gf & (ds.field("quote_date") == day)
    p = ds.dataset(PANEL / f"year={year}").to_table(
        columns=["quote_date", "expire_date", "strike", "cp", "bid", "ask", "volume", "last", "S_close"], filter=pf).to_pandas()
    g = ds.dataset(GREEKS / f"year={year}").to_table(
        columns=["quote_date", "expire_date", "strike", "cp", "tau", "D", "F", "iv", "iv_status"], filter=gf).to_pandas()
    p["cp"], g["cp"] = p.cp.astype(str), g.cp.astype(str)
    p["quote_date"], p["expire_date"] = pd.to_datetime(p.quote_date), pd.to_datetime(p.expire_date)
    g["expire_date"] = pd.to_datetime(g.expire_date)
    d = p.merge(g, on=["quote_date", "expire_date", "strike", "cp"]).dropna(subset=["F", "D"])
    two = (d.bid > 0) & (d.ask >= d.bid)
    B = d[two & (d.tau * 365).between(14, 365) & ((d.volume > 0) | (d.volume.isna() & (d["last"] > 0)))
          & (((d.cp == "C") & (d.strike >= d.F)) | ((d.cp == "P") & (d.strike < d.F)))
          & d.iv_status.eq("converged")].copy()
    B["mid"] = (B.bid + B.ask) / 2
    B["sgn"] = np.where(B.cp == "C", 1.0, -1.0)
    root = np.sqrt(B.tau.to_numpy())
    d1 = (np.log(B.F / B.strike) + 0.5 * B.iv**2 * B.tau) / (B.iv * root)
    B["vega"] = B.D * B.F * np.exp(-0.5 * d1**2) / np.sqrt(2 * np.pi) * root
    atm = B.D * B.F * root / np.sqrt(2 * np.pi)
    B["weight"] = 1.0 / np.maximum(B.vega, 0.01 * atm)
    return B.reset_index(drop=True)


def data_start(B: pd.DataFrame) -> np.ndarray:
    """v0 = θ = σ_ATM² of the nearest expiry, κ = 2, ξ = 1, ρ = −0.7."""
    e = B[B.tau == B.tau.min()]
    s = float(e.iloc[(np.log(e.strike / e.F)).abs().argsort()[:2]].iv.mean())
    return np.array([s * s, 2.0, s * s, 1.0, -0.7])


def model_iv(price, B):
    S = B.S_close.to_numpy(float)
    return bs.implied_vol(price, S, B.F.to_numpy(float), B.strike.to_numpy(float), B.D.to_numpy(float),
                          B.tau.to_numpy(float), B.sgn.to_numpy(float))[0]


def chain_for(B: pd.DataFrame, grid_params, **kw) -> H.Chain:
    S = float(B.S_close.iloc[0])
    r, q = bs.carry(B.S_close.to_numpy(float), B.F.to_numpy(float), B.D.to_numpy(float), B.tau.to_numpy(float))
    return H.Chain(S, B.strike.to_numpy(float), B.tau.to_numpy(float), r, q, B.sgn.to_numpy(float), grid_params, **kw)


def calibrate_session(day: pd.Timestamp, prev: np.ndarray | None, year_sample: pd.DataFrame | None = None) -> dict:
    w0, c0 = time.perf_counter(), time.process_time()
    B = sample_b(day) if year_sample is None else year_sample[year_sample.quote_date == day].reset_index(drop=True)
    row = {"session": day, "n": len(B)}
    if len(B) < 10:
        return row | {"ok": False}
    starts = [prev, data_start(B)] if prev is not None else [data_start(B), H.X0]
    # the search runs on panels three times as wide, then polishes on the specified grid (plan §15, 2026-11-05)
    f0 = H.calibrate(chain_for(B, starts, rad_per_panel=9.0), B.mid.to_numpy(), B.weight.to_numpy(), starts)
    ch = chain_for(B, [f0["x"]] + starts)
    fit = H.calibrate(ch, B.mid.to_numpy(), B.weight.to_numpy(), [f0["x"]])
    fit["nfev"] += f0["nfev"]
    fit["njev"] += f0["njev"]
    regrid = not ch.adequate(fit["x"])
    if regrid:  # the solution needs a longer range than the starts did: rebuild the grid there and refit
        ch = chain_for(B, [fit["x"]])
        f2 = H.calibrate(ch, B.mid.to_numpy(), B.weight.to_numpy(), [fit["x"]])
        f2["nfev"] += fit["nfev"]
        f2["njev"] += fit["njev"]
        fit = f2
    x = fit["x"]
    price = ch.prices(x)
    fine = chain_for(B, [x], range_factor=2.0, rad_per_panel=1.5).prices(x)
    iv, iv_fine = model_iv(price, B), model_iv(fine, B)
    span = H.UB - H.LB
    row |= dict(zip(H.NAMES, x)) | {
        "ok": fit["success"], "status": fit["status"], "nfev": fit["nfev"], "njev": fit["njev"], "cost": fit["cost"],
        "iv_rmse": float(np.sqrt(np.nanmean((iv - B.iv.to_numpy()) ** 2))), "iv_unpriced": int(np.isnan(iv).sum()),
        "at_bound": bool(np.any(np.minimum(x - H.LB, H.UB - x) < 1e-3 * span)),
        "accuracy_check_vp": float(np.nanmax(np.abs(iv - iv_fine)) * 100), "regridded": regrid, "capped": bool(ch.capped),
        "nodes": int(sum(len(e.u) for e in ch.expiries)), "expiries": len(ch.expiries),
        "wall_s": time.perf_counter() - w0, "cpu_s": time.process_time() - c0}
    return row


def calibrate_year(year: int) -> pd.DataFrame:
    days = pd.DatetimeIndex(pd.to_datetime(pd.read_parquet(GREEKS / f"sessions_{year}.parquet").quote_date)).sort_values()
    rows, prev = [], None
    Y = sample_b(None, year)  # the year's calibration sample, loaded once
    for d in days:
        r = calibrate_session(d, prev, Y)
        rows.append(r)
        if r.get("ok"):
            prev = np.array([r[k] for k in H.NAMES])
    P = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    P.to_csv(OUT / f"params_{year}.csv", index=False)
    return P


def main(first: int, last: int, workers: int) -> None:
    years = list(range(first, last + 1))
    with timed("heston2_calibrate", inputs=f"spx {first}-{last}, calibration B2, {workers} processes") as run:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            out = list(pool.map(calibrate_year, years))
        P = pd.concat(out, ignore_index=True)
        run["rows_in"], run["rows_out"] = len(P), int(P.ok.fillna(False).sum())
        run["notes"] = (f"ok {int(P.ok.fillna(False).sum())} of {len(P)}; session CPU s median {P.cpu_s.median():.2f}, "
                        f"sum {P.cpu_s.sum():.0f}; at bound {int(P.at_bound.fillna(False).sum())}")
    print(P.groupby(P.session.dt.year).agg(sessions=("n", "size"), ok=("ok", "sum"), cpu_med=("cpu_s", "median"),
                                           iv_rmse_med=("iv_rmse", "median"), acc_max=("accuracy_check_vp", "max")).round(4).to_string())


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 4)
