"""The SPY extension (analysis_plan.md §16.1): the SPX protocol on SPY, 2019 training and 2020 test.

Rules R0–R5 (R6 needs vanna, which the American tree does not give), W12 refitted monthly, the primary
level (SPY's exchange close) and sensitivity B (the vendor's snapshot), with each pair's day-two
distribution in the hedge P&L. Exploratory: no verdict. Writes results/spy/.

Usage: uv run python -I scripts/run_spy.py
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

OUT = ROOT / "results/spy"
RULES = ["R0", "R1", "R2", "R3", "R4", "R5"]
COMPS = [("R2", "R1"), ("R2", "R3"), ("R2", "R4"), ("R1", "R0"), ("R2", "R0"), ("R3", "R1"), ("R4", "R1"), ("R5", "R1")]
MONTHS = pd.period_range("2020-01", "2020-12", freq="M")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with timed("spy_2020", inputs="spy 2019-2020, W12, R0-R5") as log:
        P = h.load_pairs([2019, 2020], underlying="spy")
        T = P.quote_date.dt.year == 2020
        index = pd.DatetimeIndex(np.sort(P.quote_date[T].unique()))
        counts = h.bootstrap_counts(index, B=10_000, block=10, seed=2026)
        rows = []
        for label, kw in (("primary", {}), ("B", {"level": "B"})):
            fr = h.ingredients(P, **kw)
            err, coefs = h.walk_forward(fr, P, MONTHS, h.Window(12), rules=["R2", "R4", "R5"])
            sse = h.aligned_sse(err, fr, RULES, index)
            g = h.gain_table(sse, COMPS, counts)
            rows.append(g.assign(variant=label))
            coefs.to_csv(OUT / f"coefficients_{label}.csv", index=False)
            if label == "primary":
                log["rows_out"] = len(err)
                e = err.join(fr[["cp"]])
                for cp in "CP":
                    m = e[e.cp == cp].groupby("month")[RULES].apply(lambda x: (x**2).sum())
                    pd.DataFrame({"month": m.index, "G_R2_R1": 1 - m.R2 / m.R1, "rel_R2_R4": 1 - m.R2 / m.R4}).to_csv(OUT / f"monthly_{cp}.csv", index=False)
                ex = P.loc[err.index, "div_next"] > 0
                g2 = h.gain_table(h.aligned_sse(err[ex.to_numpy()], fr, RULES, index), [("R2", "R1")], counts)
                rows.append(g2.assign(variant="ex-date pairs only"))
        G = pd.concat(rows, ignore_index=True)
        G.to_csv(OUT / "gains.csv", index=False)
        print(G[G.rule.isin(["R2"]) & G.base.isin(["R1", "R3", "R4"])][["variant", "cp", "base", "gain", "lo", "hi", "pairs"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
