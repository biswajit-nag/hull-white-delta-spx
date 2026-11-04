"""The rehearsal on training data (analysis_plan.md §10): 2019, and 2018 as a second walk-forward year.

Trailing 6-month windows refitted monthly, test months July–December. Writes results/rehearsal/:
gains_YYYY.csv (rules and specification-check variants, with session-block intervals),
spec_checks_YYYY.csv (the §10 criteria), buckets_YYYY.csv, se_ratio_YYYY.csv, attribution_YYYY.csv,
coefficients_YYYY.csv.

Usage: uv run python -I scripts/run_rehearsal.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import diagnostics as dg  # noqa: E402
from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

OUT = ROOT / "results/rehearsal"
DEGREES = [f"deg:{k}" for k in range(4)]
ALPHAS = [f"alpha:{a}" for a in (0, 0.25, 0.5, 0.75, 1)]
RULES = h.FITTED + DEGREES + ALPHAS


def rehearse(year: int, P: pd.DataFrame, fr: pd.DataFrame) -> None:
    # evaluation pairs end before the next year's first session (2019-01-02 or 2020-01-02), plan §10
    keep = P.next_session < pd.Timestamp(f"{year + 1}-01-02")
    P, fr = P[keep], fr[keep]
    months = pd.period_range(f"{year}-07", f"{year}-12", freq="M")
    err, coefs = h.walk_forward(fr, P, months, h.Window(6, min_sessions=0), rules=RULES)
    index = pd.DatetimeIndex(np.sort(fr.loc[err.index, "session"].unique()))
    cols = ["R0", "R1", "R3"] + RULES
    sse = h.aligned_sse(err, fr, cols, index)
    counts = h.bootstrap_counts(index, B=10_000, block=10, seed=2026)
    comps = [("R2", "R1"), ("R2", "R3"), ("R2", "R4"), ("R1", "R0"), ("R2", "R0"), ("R4", "R1"), ("R3", "R1"),
             ("R5", "R1"), ("R6", "R1"), ("deg:3", "deg:2"), ("deg:1", "deg:2"), ("deg:0", "deg:2")]
    comps += [(a, "alpha:0.5") for a in ALPHAS if a != "alpha:0.5"]
    g = h.gain_table(sse, comps, counts)
    g.to_csv(OUT / f"gains_{year}.csv", index=False)
    # §10 criteria: degree 3 against the quadratic (one comparison); the four exponents, Holm per type
    spec = []
    for cp in ("C", "P"):
        gc = g[g.cp == cp]
        d3 = gc[(gc.rule == "deg:3") & (gc.base == "deg:2")].iloc[0]
        spec.append({"cp": cp, "check": "degree 3 vs 2", "gain": d3.gain, "lo": d3.lo, "p_adj": d3.p_plus,
                     "contradicts": bool(d3.p_plus < 0.025)})
        al = gc[gc.base == "alpha:0.5"].reset_index(drop=True)
        adj = h.holm(al.p_plus.to_numpy())
        for i, r in al.iterrows():
            spec.append({"cp": cp, "check": f"{r.rule} vs alpha:0.5", "gain": r.gain, "lo": r.lo, "p_adj": adj[i],
                         "contradicts": bool(adj[i] < 0.025)})
    pd.DataFrame(spec).to_csv(OUT / f"spec_checks_{year}.csv", index=False)
    coefs.to_csv(OUT / f"coefficients_{year}.csv", index=False)
    # the bucket table uses the year's evaluation pairs; the standard-error ratio and the attribution, the whole year
    dg.bucket_kappa(fr.loc[err.index], P).to_csv(OUT / f"buckets_{year}.csv", index=False)
    yr = fr[P.quote_date.dt.year == year]
    dg.clustered_vs_naive(yr).to_csv(OUT / f"se_ratio_{year}.csv", index=False)
    t = dg.attribution(yr, P)
    pd.concat([dg.attribution_summary(t, yr, ["cp"]).assign(group="all"),
               dg.attribution_summary(t, yr, ["cp", "delta_b"]).assign(group="delta"),
               dg.attribution_summary(t, yr, ["cp", "tau_b"]).assign(group="maturity")]).to_csv(OUT / f"attribution_{year}.csv", index=False)
    print(year, "rehearsal done:", len(err), "test pairs,", len(index), "sessions", flush=True)
    print(g[g.base.isin(["R1", "R3", "R4"]) & g.rule.isin(["R2"])].round(4).to_string(index=False), flush=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    P = h.load_pairs([2018, 2019])
    P = P[P.next_session < h.UNBLIND]  # no 2020 outcome before unblinding (the 2019-12-31 pairs)
    fr = h.ingredients(P)
    for year in (2019, 2018):
        with timed("rehearsal", inputs=f"spx {year}, 6-month windows", rows_in=int((P.quote_date.dt.year == year).sum())):
            rehearse(year, P, fr)


if __name__ == "__main__":
    main()
