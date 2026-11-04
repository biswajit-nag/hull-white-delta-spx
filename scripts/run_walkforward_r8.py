"""R8 in the walk-forward (analysis_plan.md §14, item 2): tuned once on 2015–2016, tested 2017–2023.

Monthly refits on the 12-month window, against R2 on the feature-complete pairs, with a session-block
bootstrap per year. Writes results/walkforward/r8_by_year.csv.

Usage: uv run python -I scripts/run_walkforward_r8.py
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


def main() -> None:
    params = json.loads((ROOT / "results/rehearsal/r8_params_2015_2016.json").read_text())
    with timed("walkforward_r8", inputs="spx 2016-2023, R8 tuned on 2015-2016") as log:
        P = h.load_pairs(range(2016, 2024))
        fr = h.ingredients(P)
        z = L.features(fr, P)
        ok = L.complete(fr, z)
        out = []
        for m in pd.period_range("2017-01", "2023-12", freq="M"):
            s0 = P.quote_date[P.quote_date.dt.to_period("M") == m].min()
            tr_all = ok & h.training_mask(P.quote_date, P.next_session, s0, 12)
            te_all = ok & (P.quote_date.dt.to_period("M") == m)
            for cp in "CP":
                tr, te = tr_all & (fr.cp == cp), te_all & (fr.cp == cp)
                d, dt = fr[tr], fr[te]
                beta = h.ols(*h.design("R2", d))
                e2 = dt.y - h.design("R2", dt)[0] @ beta
                e8 = L.boost_error(L.fit_boost(d, z[tr], params[cp]), dt, z[te])
                out.append(pd.DataFrame({"R1": dt.y.to_numpy(), "R2": e2.to_numpy(), "R8": e8, "month": str(m)}, index=dt.index))
        E = pd.concat(out)
        rows = []
        y = P.loc[E.index, "quote_date"].dt.year
        for year in sorted(y.unique()):
            e = E[(y == year).to_numpy()]
            index = pd.DatetimeIndex(np.sort(fr.loc[e.index, "session"].unique()))
            g = h.gain_table(h.aligned_sse(e, fr, ["R1", "R2", "R8"], index), [("R8", "R2"), ("R2", "R1")],
                             h.bootstrap_counts(index, B=10_000, block=10, seed=2026))
            rows.append(g.assign(year=year))
        G = pd.concat(rows, ignore_index=True)
        G.to_csv(ROOT / "results/walkforward/r8_by_year.csv", index=False)
        log["rows_out"] = len(E)
        print(G[G.rule == "R8"][["year", "cp", "gain", "lo", "hi"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
