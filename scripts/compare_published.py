"""Our SPX Gains under the published aggregations and samples (analysis_plan.md §16.9, item 1). Descriptive.

Walk-forwards on W12 (test months 2011–2019) and W36 (2013–2019), R1–R4 under §7's protocol, on three
samples: the analysis sample; the same pairs without E7 (Hull and White apply no volume rule); and the
out-of-the-money subsample of the analysis sample (Ruf and Wang). Each Gain over R1 three ways: pooled;
the mean of monthly Gains (Hull and White); and, per delta bucket (|δ| rounded to the nearest tenth), the
mean over months (their Table 1). Writes results/walkforward/published_comparison.csv and
published_buckets.csv.

Usage: uv run python -I scripts/compare_published.py
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
RULES = ["R2", "R3", "R4"]
PERIODS = {"HW overlap": None, "RW overlap (2012-07 to 2019-06)": ("2012-07", "2019-06"), "2011-2019": ("2011-01", "2019-12")}


def gains(e: pd.DataFrame) -> dict:
    s = (e[["R1"] + RULES] ** 2).sum()
    return {r: 1 - s[r] / s.R1 for r in RULES}


def main() -> None:
    rows, brows = [], []
    with timed("compare_published", inputs="spx 2010-2019, W12 W36, three samples") as log:
        P = h.load_pairs(range(2010, 2020), analysis_only=False)
        P = P[P.next_status == "ok"]
        samples = {"analysis (E7)": P.E7.to_numpy(), "no volume rule": np.ones(len(P), bool)}
        for W, start in ((12, "2011-01"), (36, "2013-01")):
            hw = (start, "2015-12")
            for label, keep in samples.items():
                Q = P[keep]
                fr = h.ingredients(Q)
                err, _ = h.walk_forward(fr, Q, pd.period_range(start, "2019-12", freq="M"), h.Window(W), rules=["R2", "R4"])
                e = err.join(fr[["cp"]])
                q = Q.loc[e.index]
                e["otm"] = (((q.cp == "C") & (q.strike >= q.F)) | ((q.cp == "P") & (q.strike <= q.F))).to_numpy()
                e["bucket"] = np.clip(np.floor(fr.loc[e.index, "delta"].abs() * 10 + 0.5) / 10, 0.1, 0.9)
                subsets = {label: e} | ({"out of the money (E7)": e[e.otm]} if label == "analysis (E7)" else {})
                for sub, x in subsets.items():
                    for pname, rng in PERIODS.items():
                        lo, hi = rng or hw
                        xm = x[(x.month >= lo) & (x.month <= hi)]
                        for cp in "CP":
                            y = xm[xm.cp == cp]
                            pooled = gains(y)
                            monthly = pd.DataFrame({m: gains(z) for m, z in y.groupby("month")}).T
                            for r in RULES:
                                rows.append({"window": W, "sample": sub, "period": pname, "cp": cp, "rule": r, "pairs": len(y),
                                             "months": len(monthly), "pooled": pooled[r], "mean_of_monthly": monthly[r].mean(),
                                             "median_of_monthly": monthly[r].median()})
                            if pname == "HW overlap":
                                for b, z in y.groupby("bucket"):
                                    mb = pd.DataFrame({m: gains(w) for m, w in z.groupby("month")}).T
                                    brows.append({"window": W, "sample": sub, "cp": cp, "bucket": b, "pairs": len(z),
                                                  "R2_mean_of_monthly": mb.R2.mean(), "R2_pooled": gains(z)["R2"]})
                print(f"W{W} {label} done", flush=True)
        T = pd.DataFrame(rows)
        T.to_csv(OUT / "published_comparison.csv", index=False)
        pd.DataFrame(brows).to_csv(OUT / "published_buckets.csv", index=False)
        log["rows_out"] = len(T)
        print(T[T.rule == "R2"].pivot_table(index=["window", "sample", "period"], columns="cp", values=["pooled", "mean_of_monthly"]).round(3).to_string())


if __name__ == "__main__":
    main()
