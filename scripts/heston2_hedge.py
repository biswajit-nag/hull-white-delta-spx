"""Heston hedges on the SPX analysis sample, 2010–2023 (analysis_plan.md §16.5).

With each session's calibration-B2 parameters (results/heston2/params_YYYY.csv), per pair: C_S and C_v from
the project's pricer (cached in data/processed/heston2/). Three hedges, against R1 and R2 (the 12-month
walk-forward fit) on the same pairs:
  H_model = C_S;  H_mv = C_S + (ρξ/S)·C_v;
  H_fit = C_S + β̂·C_v/S, β̂ per type by OLS without intercept of (Δf − C_S·ΔS)/S_t on (C_v/S_t)·ΔS/S_t over
  the trailing 12 months (day two before the test month's first session), applied one month out, from 2011.
Gains per year with session-block intervals. Writes results/heston2/gains_by_year.csv and beta.csv.

Usage: uv run python -I scripts/heston2_hedge.py [WORKERS]
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import blackscholes as bs  # noqa: E402
from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project import heston as H  # noqa: E402
from erdos_quant_finance_project.processed import CONTRACT_KEY  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

RES = ROOT / "results/heston2"
CACHE = ROOT / "data/processed/heston2"
KEY = ["quote_date"] + CONTRACT_KEY
YEARS = range(2010, 2024)


def params(year: int) -> pd.DataFrame:
    p = pd.read_csv(RES / f"params_{year}.csv", parse_dates=["session"])
    return p[p.ok.fillna(False).astype(bool)].set_index("session")


def greeks_year(year: int) -> int:
    out = CACHE / f"greeks_{year}.parquet"
    if out.exists():
        return 0
    prm = params(year)
    P = h.load_pairs([year], columns=KEY + ["S_close", "F", "D", "tau", "E7", "next_status"])
    rows = []
    for day, q in P[P.quote_date.isin(prm.index)].groupby("quote_date"):
        x = prm.loc[day, H.NAMES].to_numpy(float)
        S = q.S_close.to_numpy(float)
        r, qq = bs.carry(S, q.F.to_numpy(float), q.D.to_numpy(float), q.tau.to_numpy(float))
        sgn = np.where(q.cp.to_numpy() == "C", 1.0, -1.0)
        g = H.Chain(S[0], q.strike.to_numpy(float), q.tau.to_numpy(float), r, qq, sgn, [x]).evaluate(x[None], greeks=True)
        rows.append(q[KEY].assign(h_price=g["price"][0], h_delta=g["delta"][0], h_cv=g["cv"][0]))
    CACHE.mkdir(parents=True, exist_ok=True)
    G = pd.concat(rows, ignore_index=True)
    G.to_parquet(out, index=False)
    return len(G)


def year_errors(year: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Errors of R1, R2, H_model, H_mv and (from 2011) H_fit for pairs with day one in `year`."""
    yrs = [y for y in (year - 1, year) if y in YEARS]
    P = h.load_pairs(yrs)
    fr = h.ingredients(P)
    G = pd.concat([pd.read_parquet(CACHE / f"greeks_{y}.parquet") for y in yrs], ignore_index=True)
    keys = P[KEY].reset_index()
    for d in (keys, G):  # the same datetime resolution on both sides of the join
        d["quote_date"], d["settle_date"] = pd.to_datetime(d.quote_date).astype("datetime64[ns]"), pd.to_datetime(d.settle_date).astype("datetime64[ns]")
        d["cp"] = d.cp.astype(str)
    j = keys.merge(G, on=KEY, how="left").set_index("index")
    prm = pd.concat([params(y) for y in yrs])
    rx = P.quote_date.map(prm.rho * prm.xi)
    S1 = P.S_close.to_numpy(float)
    yH = fr.f - j.h_delta * fr.dSn
    xH = j.h_cv / S1 * fr.dSn
    E = pd.DataFrame({"R1": fr.y, "H_model": yH, "H_mv": yH - rx * xH}, index=P.index)
    have = fr.avail & j.h_delta.notna() & j.h_cv.notna() & rx.notna()
    months = pd.period_range(f"{year}-01", f"{year}-12", freq="M")
    betas = []
    if year - 1 in YEARS:
        err, _ = h.walk_forward(fr, P, months, h.Window(12), rules=["R2", "R4"])
        E["R2"] = err.R2.reindex(E.index)
        E["H_fit"] = np.nan
        for m in months:
            s0 = P.quote_date[P.quote_date.dt.to_period("M") == m].min()
            if pd.isna(s0):
                continue
            tr = have & h.training_mask(P.quote_date, P.next_session, s0, 12)
            te = have & (P.quote_date.dt.to_period("M") == m)
            for cp in "CP":
                a, b = tr & (fr.cp == cp), te & (fr.cp == cp)
                beta = float((xH[a] * yH[a]).sum() / (xH[a] ** 2).sum())
                E.loc[b, "H_fit"] = (yH[b] - beta * xH[b]).to_numpy()
                betas.append({"month": str(m), "cp": cp, "beta": beta, "train_pairs": int(a.sum()),
                              "rho_xi_median_month": float(rx[b].median())})
    keep = have & (P.quote_date.dt.year == year)
    E = E[keep].dropna(axis=1, how="all")
    E = E[E.notna().all(axis=1)]
    return E, fr.loc[E.index], pd.DataFrame(betas)


def main(workers: int) -> None:
    with timed("heston2_hedge", inputs=f"spx {YEARS.start}-{YEARS.stop - 1}, calibration B2") as run:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            n = list(pool.map(greeks_year, YEARS))
        print("Heston greeks cached:", dict(zip(YEARS, n)), flush=True)
        rows, betas = [], []
        for year in YEARS:
            E, fr, b = year_errors(year)
            rules = [c for c in ("R1", "R2", "H_model", "H_mv", "H_fit") if c in E]
            comps = [c for c in [("H_model", "R1"), ("H_mv", "R1"), ("H_fit", "R1"), ("R2", "R1"), ("H_mv", "R2"),
                                 ("H_fit", "R2"), ("H_fit", "H_mv"), ("H_mv", "H_model")] if c[0] in E and c[1] in E]
            index = pd.DatetimeIndex(np.sort(fr.session.unique()))
            g = h.gain_table(h.aligned_sse(E, fr, rules, index), comps, h.bootstrap_counts(index, B=10_000, block=10, seed=2026))
            rows.append(g.assign(year=year, sessions=len(index)))
            betas.append(b.assign(year=year))
            print(year, len(E), "pairs", flush=True)
        Gt = pd.concat(rows, ignore_index=True)
        Gt.to_csv(RES / "gains_by_year.csv", index=False)
        pd.concat(betas, ignore_index=True).to_csv(RES / "beta.csv", index=False)
        run["rows_out"] = int(Gt[Gt.rule == "H_model"].pairs.sum())
        print(Gt.pivot_table(index="year", columns=["rule", "base", "cp"], values="gain").round(3).to_string())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
