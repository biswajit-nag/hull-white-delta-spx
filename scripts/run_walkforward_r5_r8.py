"""R5–R8 in the 2010–2023 walk-forward (analysis_plan.md §16.4; SPY under §16.3).

For W12, W36 and W60 over each window's test span (from 2011-01, 2013-01 and 2015-01), monthly refits
with the §7 boundary rule: R5 and R6 by least squares on every analysis pair, R7 (the depth-3 tree) and
R8 (LightGBM boosted from R2) on the feature-complete pairs, against R2's all-pairs fit there. R8's hyperparameters: the 2010 tuning for
test months up to 2016-12, the 2015–2016 tuning from 2017-01. R2 is refitted alongside and re-reported
on each sample. Gains per year and window with session-block intervals, and median yearly Gains over
2015–2023. Writes results/walkforward/r5_r8_by_year.csv (results/spy/walkforward/ with --spy).

Usage: uv run python -I scripts/run_walkforward_r5_r8.py [--spy]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project import learners as L  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

U = "spy" if "--spy" in sys.argv else "spx"
BASE = ROOT / "results" / ("spy" if U == "spy" else "")
OUT = BASE / "walkforward"
REH = BASE / "rehearsal"
START = {12: "2011-01", 36: "2013-01", 60: "2015-01"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    early = json.loads((REH / "r8_params_2010.json").read_text())
    late = json.loads((REH / "r8_params_2015_2016.json").read_text())
    with timed("walkforward_r5_r8", inputs=f"{U} 2010-2023, W12 W36 W60, R5-R8") as log:
        P = h.load_pairs(range(2010, 2024), underlying=U)
        fr = h.ingredients(P)
        z = L.features(fr, P)
        ok = L.complete(fr, z)
        day1, day2, month = P.quote_date, P.next_session, P.quote_date.dt.to_period("M")
        log["rows_in"] = len(P)
        rows = []
        for W, start in START.items():
            E_ls, E_ml = [], []
            for m in pd.period_range(start, "2023-12", freq="M"):
                s0 = day1[month == m].min()
                if pd.isna(s0):
                    continue
                tr_all = fr.avail & h.training_mask(day1, day2, s0, W)
                assert (day2[tr_all] < s0).all(), "look-ahead: a training pair ends in the test period"
                te_all = fr.avail & (month == m)
                params = early if m <= pd.Period("2016-12", "M") else late
                for cp in "CP":
                    tr, te = tr_all & (fr.cp == cp), te_all & (fr.cp == cp)
                    d, dt = fr[tr], fr[te]
                    if dt.empty or d.session.nunique() < 150:
                        continue
                    b = {r: h.ols(*h.design(r, d)) for r in ("R2", "R5", "R6")}
                    if b["R2"] is None:
                        continue
                    e = {"R1": dt.y.to_numpy(), "month": str(m)}
                    for r, beta in b.items():
                        X, t = h.design(r, dt)
                        e[r] = np.asarray(t - X @ beta) if beta is not None else np.full(len(dt), np.nan)
                    E_ls.append(pd.DataFrame(e, index=dt.index))
                    trc, tec = tr & ok, te & ok
                    dc, dtc = fr[trc], fr[tec]
                    if dtc.empty:
                        continue
                    # R2 from the all-pairs fit, as in the 2020 learner comparison (run_test_year.learners)
                    E_ml.append(pd.DataFrame({
                        "R1": dtc.y.to_numpy(), "R2": (dtc.y - h.design("R2", dtc)[0] @ b["R2"]).to_numpy(),
                        "R7": L.tree_error(L.fit_tree(dc, z[trc]), dtc, z[tec]),
                        "R8": L.boost_error(L.fit_boost(dc, z[trc], params[cp]), dtc, z[tec]), "month": str(m)}, index=dtc.index))
                print(f"W{W} {m} done", flush=True) if m.month == 12 else None
            for label, E, rules in (("least squares, all pairs", pd.concat(E_ls), ["R1", "R2", "R5", "R6"]),
                                    ("learners, feature-complete pairs", pd.concat(E_ml), ["R1", "R2", "R7", "R8"])):
                yr = P.loc[E.index, "quote_date"].dt.year
                for year in sorted(yr.unique()):
                    e = E[(yr == year).to_numpy()]
                    for r in rules[2:]:
                        ee = e[e[r].notna()]
                        index = pd.DatetimeIndex(np.sort(fr.loc[ee.index, "session"].unique()))
                        g = h.gain_table(h.aligned_sse(ee, fr, ["R1", "R2", r], index), [(r, "R1"), (r, "R2"), ("R2", "R1")],
                                         h.bootstrap_counts(index, B=10_000, block=10, seed=2026))
                        keep = (g.rule == r) | ((g.rule == "R2") & (r == rules[2]))  # R2 re-reported once per sample
                        rows.append(g[keep].assign(window=W, year=year, sample=label, months=ee.month.nunique()))
        G = pd.concat(rows, ignore_index=True)
        G.to_csv(OUT / "r5_r8_by_year.csv", index=False)
        med = G[G.year >= 2015].groupby(["window", "sample", "cp", "rule", "base"]).gain.median().rename("median_yearly_gain").reset_index()
        med.to_csv(OUT / "r5_r8_median_yearly_gain.csv", index=False)
        log["rows_out"] = len(G)
        print(med.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
