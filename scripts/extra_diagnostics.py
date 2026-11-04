"""Two declared diagnostics computed after the 2020 run (analysis_plan.md §2, §3).

1. Quote overlap under sensitivity A: 2020 pairs whose contract has ≤ 10 days left on day two, so
   that its own expiry could enter day two's fallback level fit (counted where day two used tier 2
   and the expiry's days match).
2. The size-weighted marks: SSE under P-WM minus SSE under P-SW, for R0 and R1 (whose hedges do not
   depend on the marks), with its decomposition into n·Cov(e, u) + n·mean(e)·mean(u).
Writes results/2020/extra_diagnostics.csv.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import hedging as h  # noqa: E402

P = h.load_pairs([2020])
sess = pd.concat([pd.read_parquet(ROOT / f"data/processed/greeks/underlying=spx/sessions_{y}.parquet") for y in (2020, 2021)])
sess["quote_date"] = pd.to_datetime(sess.quote_date)
s = sess.set_index("quote_date")
days_next = P.tau_next * 365
tier = P.next_session.map(s.A_tier)
adays = P.next_session.map(s.A_days)
overlap = (days_next <= 10) & (tier == 2) & ((adays - days_next).abs() < 0.05)
rows = [{"diagnostic": "A overlap: pairs with <= 10 days left on day two", "value": int((days_next <= 10).sum())},
        {"diagnostic": "A overlap: of those, whose expiry fed day two's tier-2 level fit", "value": int(overlap.sum())}]
fw, fs = h.ingredients(P, mark="wm"), h.ingredients(P, mark="sw")
m = fw.avail & fs.avail
fm = h.ingredients(P)
for cp in "CP":
    k = m & (fw.cp == cp)
    for rule, col in (("R0", "f"), ("R1", "y")):
        ew, es = fw.loc[k, col], fs.loc[k, col]
        e, u = fm.loc[k, col], (fw.loc[k, col] - fm.loc[k, col])
        rows.append({"diagnostic": f"{cp} {rule}: SSE(WM) - SSE(SW)", "value": float((ew**2).sum() - (es**2).sum())})
        rows.append({"diagnostic": f"{cp} {rule}: relative to SSE(mid)", "value": float(((ew**2).sum() - (es**2).sum()) / (e**2).sum())})
        rows.append({"diagnostic": f"{cp} {rule}: n*Cov(e,u) / sum(e*u) (1 = mean product negligible)", "value": float(len(e) * np.cov(e, u, bias=True)[0, 1] / (e * u).sum())})
out = pd.DataFrame(rows)
out.to_csv(ROOT / "results/2020/extra_diagnostics.csv", index=False)
print(out.to_string(index=False))
