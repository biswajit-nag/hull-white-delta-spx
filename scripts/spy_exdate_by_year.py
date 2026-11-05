"""SPY's ex-date pairs, reported separately each year (analysis_plan.md §16.3).

A pair whose day two is an ex-date carries the distribution in its hedge P&L. Under the 12-month
walk-forward, the Gains of R2, R3 and R4 over R1 on those pairs and on the rest, per year. With only
four ex-dates a year the session bootstrap has four blocks at most, so the ex-date rows are point
estimates with their session count. Writes results/spy/walkforward/exdate_by_year.csv.

Usage: uv run python -I scripts/spy_exdate_by_year.py
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

OUT = ROOT / "results/spy/walkforward"


def main() -> None:
    with timed("spy_exdate_by_year", inputs="spy 2010-2023, W12") as log:
        P = h.load_pairs(range(2010, 2024), underlying="spy")
        fr = h.ingredients(P)
        err, _ = h.walk_forward(fr, P, pd.period_range("2011-01", "2023-12", freq="M"), h.Window(12), rules=["R2", "R4"])
        e = err.join(fr[["cp"]])
        e["year"] = P.loc[e.index, "quote_date"].dt.year.to_numpy()
        e["ex"] = (P.loc[e.index, "div_next"] > 0).to_numpy()
        e["session"] = fr.loc[e.index, "session"].to_numpy()
        rows = []
        for (year, cp, ex), x in e.groupby(["year", "cp", "ex"]):
            s = (x[["R1", "R2", "R3", "R4"]] ** 2).sum()
            rows.append({"year": year, "cp": cp, "pairs": "ex-date" if ex else "other", "n": len(x), "sessions": x.session.nunique(),
                         "G_R2_R1": 1 - s.R2 / s.R1, "G_R3_R1": 1 - s.R3 / s.R1, "G_R4_R1": 1 - s.R4 / s.R1,
                         "share_of_year_R1_sse": s.R1 / (e[(e.year == year) & (e.cp == cp)].R1 ** 2).sum()})
        T = pd.DataFrame(rows)
        T.to_csv(OUT / "exdate_by_year.csv", index=False)
        log["rows_out"] = len(T)
        print(T[T.pairs == "ex-date"].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
