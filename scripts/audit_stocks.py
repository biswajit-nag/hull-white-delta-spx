"""Data audits for the stock/ETF pipeline (analysis_plan.md section 16.15), before any outcome.

Per underlying and year: rows, vendor sessions vs NYSE sessions, maximum volume, IV solve counts, eligible pairs
(E1-E8 = the pair file's rows with E7; E9 = no split), next-session status of the eligible pairs, and the share
with a usable next quote. Writes under results/stocks/<u>/:
  summary_by_year.csv, attrition_by_status.csv (eligible pairs by year, cp and next_status), splits.csv (from the pairs step).

Usage: uv run python -I scripts/audit_stocks.py aapl nvda tsla qqq slv
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project.processed import nyse_sessions  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402


def audit(u: str) -> None:
    sess = nyse_sessions("2016-01-01", "2023-12-31")
    rows, att = [], []
    for year in range(2016, 2024):
        long = ds.dataset(ROOT / f"data/processed/optionsdx_long/underlying={u}/year={year}").to_table(
            columns=["quote_date", "volume", "last", "is_session", "f_non_session", "f_one_sided", "f_crossed", "S_close"]).to_pandas()
        g = pd.read_parquet(ROOT / f"data/processed/greeks/underlying={u}/year={year}/greeks_{year}.parquet",
                            columns=["cp", "iv_status", "q"])
        p = pd.read_parquet(ROOT / f"data/processed/pairs/underlying={u}/year={year}/pairs_{year}.parquet",
                            columns=["quote_date", "cp", "E7", "E9", "next_status", "div_next", "delta"])
        sessions = long[long.is_session & ~long.f_non_session].quote_date.nunique()
        nyse = int((sess.index.year == year).sum())
        attempted = g.iv_status.isin(["converged", "outside_price_bounds", "below_volatility_bracket", "above_volatility_bracket",
                                      "not_identifiable"]) | (~g.iv_status.isin(["expired", "one_sided", "no_rate"]))
        e = p[p.E7]
        e1 = e[e.E9]
        row = {"underlying": u, "year": year, "rows": len(long), "vendor_dates": long.quote_date.nunique(), "sessions": sessions,
               "nyse_sessions": nyse, "volume_max": float(long.volume.max()),
               "greeks_rows": len(g), "iv_attempted": int(attempted.sum()), "iv_converged": int((g.iv_status == "converged").sum()),
               "iv_fail_rate": 1 - (g.iv_status == "converged").sum() / attempted.sum(),
               "iv_fail_rate_calls": 1 - ((g.cp == "C") & (g.iv_status == "converged")).sum() / ((g.cp == "C") & attempted).sum(),
               "iv_fail_rate_puts": 1 - ((g.cp == "P") & (g.iv_status == "converged")).sum() / ((g.cp == "P") & attempted).sum(),
               "q_min": g.q.min(), "q_max": g.q.max(),
               "pairs_E1_6_8": len(p), "pairs_E7": len(e), "split_straddling_E7": int((~e.E9).sum()),
               "pairs_E1_9": len(e1), "pairs_E1_9_next_ok": int((e1.next_status == "ok").sum()),
               "usable_share": float((e1.next_status == "ok").mean()) if len(e1) else np.nan,
               "exdate_pairs": int((e1.div_next > 0).sum())}
        rows.append(row)
        a = e1.groupby(["cp", "next_status"]).size().rename("pairs").reset_index()
        a.insert(0, "year", year)
        att.append(a)
        print(u, year, {k: row[k] for k in ("sessions", "nyse_sessions", "volume_max", "pairs_E1_9", "usable_share", "iv_fail_rate")}, flush=True)
    out = ROOT / f"results/stocks/{u}"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "summary_by_year.csv", index=False)
    pd.concat(att).to_csv(out / "attrition_by_status.csv", index=False)


if __name__ == "__main__":
    for u in sys.argv[1:]:
        with timed("audit_stocks", inputs=u) as run:
            audit(u)
