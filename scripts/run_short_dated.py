"""Short-dated SPX options (analysis_plan.md §16.6): R1, R2s and R2m, 2011–2023.

The pairs (data/processed/pairs_short/) have under 14 days to expiry on day one and end before settlement.
R2s is R2 refitted monthly on short-dated training pairs over the trailing 12 months (§7's boundary rule,
150 sessions); R2m applies the main study's 12-month R2 coefficients (results/walkforward/coefficients_W12.csv,
fitted on options of 14 days or more) to the short-dated pairs. Gains per year with session-block
intervals, and point Gains by day-one maturity bucket. Writes results/short_dated/.

Usage: uv run python -I scripts/run_short_dated.py
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
from erdos_quant_finance_project.runlog import timed  # noqa: E402

SHORT = ROOT / "data/processed/pairs_short"
OUT = ROOT / "results/short_dated"
COMPS = [("R2s", "R1"), ("R2m", "R1"), ("R2s", "R2m"), ("R1", "R0")]
BUCKETS = pd.IntervalIndex.from_breaks([0, 3, 7, 14], closed="left")  # day-one calendar days: 1–2, 3–6, 7–13


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    main_coefs = pd.read_csv(ROOT / "results/walkforward/coefficients_W12.csv")
    main_coefs = main_coefs[main_coefs.rule == "R2"].set_index(["month", "cp"]).coef.map(json.loads)
    rows, brows, coefs = [], [], []
    with timed("short_dated", inputs="spx 2010-2023 short-dated pairs, W12") as log:
        n_in = 0
        for year in range(2011, 2024):
            P = h.load_pairs([year - 1, year], root=SHORT)
            fr = h.ingredients(P)
            n_in += int((P.quote_date.dt.year == year).sum())
            months = pd.period_range(f"{year}-01", f"{year}-12", freq="M")
            err, c = h.walk_forward(fr, P, months, h.Window(12), rules=["R2", "R4"])
            coefs.append(c)
            E = err[["R0", "R1", "R2", "month"]].rename(columns={"R2": "R2s"})
            E["R2m"] = np.nan
            for (m, cp), idx in E.groupby(["month", fr.loc[E.index, "cp"]]).groups.items():
                if (m, cp) in main_coefs.index:
                    d = fr.loc[idx]
                    E.loc[idx, "R2m"] = (d.y - h.design("R2", d)[0] @ np.asarray(main_coefs[(m, cp)])).to_numpy()
            E = E[E.R2m.notna()]
            index = pd.DatetimeIndex(np.sort(fr.loc[E.index, "session"].unique()))
            g = h.gain_table(h.aligned_sse(E, fr, ["R0", "R1", "R2s", "R2m"], index), COMPS,
                             h.bootstrap_counts(index, B=10_000, block=10, seed=2026))
            rows.append(g.assign(year=year, months=E.month.nunique(), sessions=len(index)))
            e = E.join(fr[["cp"]])
            e["bucket"] = pd.cut(fr.loc[E.index, "tau"] * 365, BUCKETS)
            for (cp, b), x in e.groupby(["cp", "bucket"], observed=True):
                s = (x[["R1", "R2s", "R2m"]] ** 2).sum()
                brows.append({"year": year, "cp": cp, "days": f"{int(b.left)}-{int(b.right) - 1}", "pairs": len(x),
                              "G_R2s_R1": 1 - s.R2s / s.R1, "G_R2m_R1": 1 - s.R2m / s.R1})
            print(year, len(E), "pairs", flush=True)
        G = pd.concat(rows, ignore_index=True)
        G.to_csv(OUT / "gains_by_year.csv", index=False)
        pd.DataFrame(brows).to_csv(OUT / "buckets.csv", index=False)
        pd.concat(coefs).to_csv(OUT / "coefficients_R2s.csv", index=False)
        log["rows_in"], log["rows_out"] = n_in, int(G[G.rule == "R2s"].pairs.sum())
        print(G.pivot_table(index="year", columns=["rule", "base", "cp"], values="gain").round(3).to_string())


if __name__ == "__main__":
    main()
