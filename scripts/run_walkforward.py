"""The 2010–2023 walk-forward (analysis_plan.md §14, item 2): W12, W36 and W60, refitted monthly.

Common test months 2015-01 to 2023-12; W12 also from 2011-01 and W36 from 2013-01, as supplements.
Gains of R2 over R1, R3 and R4 per year and window, with session-block intervals (each year its own
bootstrap), and the median yearly Gain. Reported beside the year ledger: 2019 and 2020 were seen,
2015–2018 were fit-only or evaluated, so only 2021–2023 (and 2011–2013 for the supplements) are clean.
Writes results/walkforward/.

Usage: uv run python -I scripts/run_walkforward.py
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

OUT = ROOT / "results/walkforward"
RULES = ["R0", "R1", "R2", "R3", "R4"]
COMPS = [("R2", "R1"), ("R2", "R3"), ("R2", "R4"), ("R4", "R1"), ("R3", "R1"), ("R1", "R0")]
START = {12: "2011-01", 36: "2013-01", 60: "2015-01"}
STATUS = {2011: "untouched", 2012: "untouched", 2013: "untouched", 2014: "fit-only (2019 dry run)", 2015: "fit-only", 2016: "fit-only",
          2017: "fit-only", 2018: "evaluated (rehearsal)", 2019: "evaluated (rehearsal, dry run)", 2020: "evaluated (unblinding)",
          2021: "untouched", 2022: "untouched", 2023: "untouched"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with timed("walkforward", inputs="spx 2010-2023, W12 W36 W60") as log:
        P = h.load_pairs(range(2010, 2024))
        fr = h.ingredients(P)
        log["rows_in"] = len(P)
        rows, errs = [], {}
        for W, start in START.items():
            months = pd.period_range(start, "2023-12", freq="M")
            err, coefs = h.walk_forward(fr, P, months, h.Window(W), rules=["R2", "R4"])
            errs[W] = err
            coefs.to_csv(OUT / f"coefficients_W{W}.csv", index=False)
            y = P.loc[err.index, "quote_date"].dt.year
            for year in sorted(y.unique()):
                e = err[(y == year).to_numpy()]
                index = pd.DatetimeIndex(np.sort(fr.loc[e.index, "session"].unique()))
                counts = h.bootstrap_counts(index, B=10_000, block=10, seed=2026)
                g = h.gain_table(h.aligned_sse(e, fr, RULES, index), COMPS, counts)
                months_run = e.month.nunique()
                rows.append(g.assign(window=W, year=year, months=months_run, status=STATUS.get(year, "")))
            print(f"W{W}: {len(err)} test pairs, {err.month.nunique()} months", flush=True)
        G = pd.concat(rows, ignore_index=True)
        G.to_csv(OUT / "gains_by_year.csv", index=False)
        common = G[(G.year >= 2015) & (G.rule == "R2")]
        med = common.groupby(["window", "cp", "base"]).gain.median().rename("median_yearly_gain").reset_index()
        med.to_csv(OUT / "median_yearly_gain.csv", index=False)
        # monthly Gains, for the stability-across-years figure
        for W, err in errs.items():
            e = err.join(fr[["cp"]])
            m = e.groupby(["month", "cp"])[RULES].apply(lambda x: (x**2).sum())
            pd.DataFrame({"G_R2_R1": 1 - m.R2 / m.R1, "rel_R2_R4": 1 - m.R2 / m.R4}).to_csv(OUT / f"monthly_W{W}.csv")
        log["rows_out"] = int(sum(len(e) for e in errs.values()))
        print(med.round(3).to_string(index=False))
        print(G[(G.rule == "R2") & (G.base == "R1")].pivot_table(index="year", columns=["window", "cp"], values="gain").round(3).to_string())


if __name__ == "__main__":
    main()
