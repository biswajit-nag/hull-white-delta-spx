"""The yearly spot–volatility slope near the money, to read the walk-forward (descriptive).

Per session, the median one-session change in implied volatility of options with |δ| in [0.4, 0.6]
and 20–60 days to expiry, regressed on the index return. Writes results/walkforward/spot_vol_slope.csv.

Usage: uv run python -I scripts/spot_vol_slope.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import hedging as h  # noqa: E402

COLS = ["quote_date", "next_session", "cp", "delta", "tau", "iv", "iv_next", "iv_status_next", "S_close", "S_close_next", "E7", "next_status"]

rows = []
for y in range(2011, 2024):
    p = h.load_pairs([y], columns=COLS)
    p = p[p.delta.abs().between(0.4, 0.6) & (p.tau * 365).between(20, 60) & (p.iv_status_next == "converged")]
    s = pd.DataFrame({"r": p.S_close_next / p.S_close - 1, "d": p.iv_next - p.iv, "q": p.quote_date}).groupby("q").median()
    b = np.polyfit(s.r, s.d, 1)[0]
    rows.append({"year": y, "sessions": len(s), "vol_points_per_1pct_fall": -b, "corr": s.r.corr(s.d)})
out = pd.DataFrame(rows)
out.to_csv(ROOT / "results/walkforward/spot_vol_slope.csv", index=False)
print(out.round(3).to_string(index=False))
