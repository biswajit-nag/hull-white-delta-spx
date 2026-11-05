"""The level and the shape of the Hull–White correction (analysis_plan.md §16.9, item 2). Descriptive.

On the normalized scale, y = f − δ·ΔS/S and x = (ν/S)(ΔS/S)/√τ; a correction g(δ) hedges with error
y − x·g(δ). For each W12 refit, 2011–2023: P0's constant c = Σxy/Σx² on the training window; the
constant that fits the test month best, after the fact; and R2's average correction, the x²-weighted
mean of a + bδ + cδ² over the training pairs. Per year: the Gains of P0 over R1 (the level), of R2 over
P0 (the shape added to it), and of the after-the-fact constant over R1 (a ceiling for the level).
Writes level_shape_by_month.csv and level_shape_by_year.csv in results/walkforward/
(results/spy/walkforward/ with --spy).

Usage: uv run python -I scripts/level_shape.py [--spy]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

U = "spy" if "--spy" in sys.argv else "spx"
OUT = ROOT / ("results/spy/walkforward" if U == "spy" else "results/walkforward")


def main() -> None:
    with timed("level_shape", inputs=f"{U} 2010-2023, W12") as log:
        P = h.load_pairs(range(2010, 2024), underlying=U)
        fr = h.ingredients(P)
        fr = fr[fr.avail]
        P = P.loc[fr.index]
        month = P.quote_date.dt.to_period("M")
        rows = []
        for m in pd.period_range("2011-01", "2023-12", freq="M"):
            s0 = P.quote_date[month == m].min()
            if pd.isna(s0):
                continue
            trm = h.training_mask(P.quote_date, P.next_session, s0, 12)
            for cp in "CP":
                tr, te = fr[trm & (fr.cp == cp)], fr[(month == m) & (fr.cp == cp)]
                if te.empty or tr.session.nunique() < 150:
                    continue
                c_fit = float((tr.x * tr.y).sum() / (tr.x ** 2).sum())
                c_post = float((te.x * te.y).sum() / (te.x ** 2).sum())
                beta = h.ols(*h.design("R2", tr))
                g_tr = h.poly(tr.delta.to_numpy()) @ beta
                w = (tr.x ** 2).to_numpy()
                e2 = te.y - h.design("R2", te)[0] @ beta
                rows.append({"month": str(m), "year": m.year, "cp": cp, "pairs": len(te), "c_fit": c_fit, "c_post": c_post,
                             "R2_mean_correction": float((w * g_tr).sum() / w.sum()),
                             "sse_R1": float((te.y ** 2).sum()), "sse_P0": float(((te.y - c_fit * te.x) ** 2).sum()),
                             "sse_P0_post": float(((te.y - c_post * te.x) ** 2).sum()), "sse_R2": float((e2 ** 2).sum())})
        M = pd.DataFrame(rows)
        M.to_csv(OUT / "level_shape_by_month.csv", index=False)
        Y = M.groupby(["year", "cp"]).agg(c_fit=("c_fit", "median"), c_post=("c_post", "median"), R2_mean_correction=("R2_mean_correction", "median"),
                                          sse_R1=("sse_R1", "sum"), sse_P0=("sse_P0", "sum"), sse_P0_post=("sse_P0_post", "sum"),
                                          sse_R2=("sse_R2", "sum")).reset_index()
        Y["G_level_P0_R1"] = 1 - Y.sse_P0 / Y.sse_R1
        Y["G_shape_R2_P0"] = 1 - Y.sse_R2 / Y.sse_P0
        Y["G_R2_R1"] = 1 - Y.sse_R2 / Y.sse_R1
        Y["G_ceiling_P0post_R1"] = 1 - Y.sse_P0_post / Y.sse_R1
        slope = ROOT / "results/walkforward/spot_vol_slope.csv"
        if U == "spx" and slope.exists():
            Y = Y.merge(pd.read_csv(slope)[["year", "vol_points_per_1pct_fall"]], on="year", how="left")
        Y.to_csv(OUT / "level_shape_by_year.csv", index=False)
        log["rows_out"] = len(M)
        print(Y.drop(columns=[c for c in Y if c.startswith("sse")]).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
