"""The fitted corrections g(δ) of R2, R9 and P0 on SPX 2019, for notebook 08's figure (analysis_plan.md §16.7).

On the 2019 feature-complete pairs (day two before 2020-01-02), per option type: R2's quadratic, R9's tuned
LightGBM h(δ) (hyperparameters from results/rehearsal/r9_params_2019.json, written by tune_r8.py --rule R9 2019)
and P0's constant c = Σxy/Σx², on a grid of 91 deltas; and the x²-weighted histogram of δ (45 bins) that shows
where the fit's weight lies. Descriptive. The notebook draws from these tables, so it runs without the vendor data.
Writes results/rehearsal/correction_curves_2019.csv and correction_weights_2019.csv.
Usage: uv run python -I scripts/correction_curves.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import hedging as h, learners as L  # noqa: E402

R = ROOT / "results"


def main() -> None:
    P = h.load_pairs([2018, 2019]); P = P[P.next_session < h.UNBLIND]
    fr = h.ingredients(P); z = L.features(fr, P); ok = L.complete(fr, z)
    p9 = json.loads((R / "rehearsal/r9_params_2019.json").read_text())
    curves, weights = [], []
    for cp in "CP":
        tr = ok & (fr.cp == cp) & (P.quote_date >= "2019-01-01"); dd = fr[tr]
        beta = h.ols(*h.design("R2", dd)); c0 = float((dd.x * dd.y).sum() / (dd.x ** 2).sum())
        m9 = L.fit_direct(dd, z[tr][["delta"]], p9[cp])
        grid = np.linspace(0.05, 0.95, 91) * (1 if cp == "C" else -1)
        curves.append(pd.DataFrame({"cp": cp, "delta": grid, "R2": h.poly(grid) @ beta,
                                    "R9": m9.predict(grid[:, None]), "P0": c0}))
        w, edges = np.histogram(dd.delta, bins=45, weights=dd.x ** 2)
        weights.append(pd.DataFrame({"cp": cp, "left": edges[:-1], "right": edges[1:], "weight": w}))
    pd.concat(curves).to_csv(R / "rehearsal/correction_curves_2019.csv", index=False)
    pd.concat(weights).to_csv(R / "rehearsal/correction_weights_2019.csv", index=False)
    print("wrote results/rehearsal/correction_curves_2019.csv and correction_weights_2019.csv")


if __name__ == "__main__":
    main()
