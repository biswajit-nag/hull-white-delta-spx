"""Attrition and composition on the final eligible sample (analysis_plan.md §5), and step-1 diagnostics (§4).

Data quality only. Writes results/attrition/: by_status.csv, by_month.csv, by_delta.csv, by_maturity.csv,
by_spread_decile.csv, composition.csv, e7_clause.csv, iv_status.csv, parity_sessions.csv, cp_iv_gap.csv.

Usage: uv run python -I scripts/attrition.py
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

OUT = ROOT / "results/attrition"
GREEKS = ROOT / "data/processed/greeks/underlying=spx"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with timed("attrition", inputs="spx 2019-2020") as run:
        P = h.load_pairs([2019, 2020], analysis_only=False)
        P["year"] = P.quote_date.dt.year
        E = P[P.E7].copy()
        E["usable"] = E.next_status == "ok"
        E["period"] = np.where(E.quote_date.between(*h.STRESS), "stress", E.year.astype(str))
        b = dg.buckets(pd.DataFrame({"delta": E.delta, "tau": E.tau}, index=E.index))
        E = E.join(b)
        E["spread_decile"] = pd.qcut(E.rel_spread, 10, labels=False, duplicates="drop") + 1
        E.groupby(["period", "cp"]).next_status.value_counts().unstack(fill_value=0).to_csv(OUT / "by_status.csv")
        for key, name in ((E.quote_date.dt.to_period("M"), "by_month"), ("delta_b", "by_delta"), ("tau_b", "by_maturity"),
                          ("spread_decile", "by_spread_decile")):
            g = E.groupby([key, "cp"] if isinstance(key, str) else [key, E.cp])
            pd.DataFrame({"eligible": g.size(), "usable": g.usable.sum(), "lost_share": 1 - g.usable.mean()}).to_csv(OUT / f"{name}.csv")
        comp = E[E.usable].groupby(["year", "cp", "delta_b", "tau_b"]).size().rename("pairs").reset_index()
        comp.to_csv(OUT / "composition.csv", index=False)
        e7 = P.assign(clause=np.select([P.volume > 0, P.volume.isna() & (P["last"] > 0)], ["volume > 0", "empty, last > 0"], "ineligible"))
        e7.groupby(["year", "cp", "clause"]).size().unstack(fill_value=0).to_csv(OUT / "e7_clause.csv")
        itm = E[E.usable].assign(itm=lambda x: np.where(x.cp == "C", x.strike < x.F, x.strike > x.F))
        itm.groupby(["year", "cp"]).itm.mean().to_csv(OUT / "itm_share.csv")
        st = []
        for y in (2019, 2020):
            g = pd.read_parquet(GREEKS / f"year={y}" / f"greeks_{y}.parquet", columns=["quote_date", "expire_date", "strike", "cp", "tau", "iv", "iv_status", "F"])
            st.append(g.iv_status.value_counts().rename(y))
            if y == 2020:
                c = g[g.iv_status == "converged"].pivot_table(index=["quote_date", "expire_date", "strike"], columns="cp", values="iv")
                c = c.dropna()
                gap = (c.C - c.P).rename("iv_gap").reset_index().merge(
                    g[["quote_date", "expire_date", "strike", "F", "tau"]].drop_duplicates(["quote_date", "expire_date", "strike"]),
                    on=["quote_date", "expire_date", "strike"])
                gap["m"] = np.log(gap.strike / gap.F)
                gap = gap[(gap.tau * 365 >= 14) & (gap.m.abs() <= 0.1)]
                gap.groupby(pd.cut(gap.m, np.linspace(-0.1, 0.1, 9))).iv_gap.describe().to_csv(OUT / "cp_iv_gap.csv")
        pd.concat(st, axis=1).to_csv(OUT / "iv_status.csv")
        pd.concat([pd.read_parquet(GREEKS / f"sessions_{y}.parquet") for y in (2019, 2020)]).to_csv(OUT / "parity_sessions.csv", index=False)
        run["rows_in"] = len(P)
        run["rows_out"] = int(E.usable.sum())
    print(pd.read_csv(OUT / "by_status.csv").to_string())
    print(pd.read_csv(OUT / "e7_clause.csv").to_string())
    print(pd.read_csv(OUT / "itm_share.csv").to_string())


if __name__ == "__main__":
    main()
