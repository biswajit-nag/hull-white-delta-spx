"""Heston deltas on the 2020 analysis sample (analysis_plan.md §16.2), compared with R1 and R2.

With each session's calibration-B parameters: the model delta C_S and the minimum-variance delta
C_S + (ρξ/S)·C_v, C_v a central difference in v0 (±1%). Errors are on the normalized scale of
§6, on the pairs whose day-one calibration succeeded, beside R1 and R2 from the primary run.
Writes results/heston/hedge_errors.parquet and results/heston/gains.csv.

Usage: uv run python -I scripts/heston_hedge.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import blackscholes as bs  # noqa: E402
from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project.lecture import option_pricing  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

OUT = ROOT / "results/heston"


def main() -> None:
    op = option_pricing()
    prm = pd.read_csv(OUT / "params.csv", parse_dates=["session"])
    prm = prm[(prm.fit == "B-iv") & prm.ok.fillna(False).astype(bool)].set_index("session")
    P = h.load_pairs([2020])
    fr = h.ingredients(P)
    prim = pd.read_parquet(ROOT / "results/2020/errors.parquet")
    with timed("heston_hedge", inputs="spx 2020, calibration B", rows_in=len(P)) as run:
        out = []
        for day, q in P[P.quote_date.isin(prm.index)].groupby("quote_date"):
            x = prm.loc[day]
            S, K, T = q.S_close.to_numpy(float), q.strike.to_numpy(float), q.tau.to_numpy(float)
            r, qq = bs.carry(S, q.F.to_numpy(float), q.D.to_numpy(float), T)
            res = {}
            for sign, opt in ((1.0, "call"), (-1.0, "put")):
                m = (q.cp == ("C" if sign > 0 else "P")).to_numpy()
                if not m.any():
                    continue
                args = (S[m], K[m])
                g = op.heston_european_greeks(*args, x.v0, r[m], T[m], x.kappa, x.theta, x.xi, x.rho, qq[m], option=opt, check_bounds=False)
                f = op.heston_call if opt == "call" else op.heston_put
                hv = 0.01 * x.v0
                cv = (f(*args, x.v0 + hv, r[m], T[m], x.kappa, x.theta, x.xi, x.rho, qq[m], check_bounds=False)
                      - f(*args, x.v0 - hv, r[m], T[m], x.kappa, x.theta, x.xi, x.rho, qq[m], check_bounds=False)) / (2 * hv)
                res[opt] = (np.flatnonzero(m), g["delta"], g["delta"] + x.rho * x.xi * cv / S[m])
            idx = q.index.to_numpy()
            for opt, (pos, d_model, d_mv) in res.items():
                ii = idx[pos]
                d = fr.loc[ii]
                out.append(pd.DataFrame({"H_model": (d.f - d_model * d.dSn).to_numpy(), "H_mv": (d.f - d_mv * d.dSn).to_numpy(),
                                         "delta_model": d_model, "delta_mv": d_mv}, index=ii))
        E = pd.concat(out).join(prim[["R1", "R2", "month"]], how="inner")
        E.to_parquet(OUT / "hedge_errors.parquet")
        index = pd.DatetimeIndex(np.sort(fr.loc[E.index, "session"].unique()))
        sse = h.aligned_sse(E, fr, ["R1", "R2", "H_model", "H_mv"], index)
        counts = h.bootstrap_counts(index, B=10_000, block=10, seed=2026)
        G = h.gain_table(sse, [("H_model", "R1"), ("H_mv", "R1"), ("R2", "R1"), ("H_mv", "R2"), ("H_mv", "H_model")], counts)
        G.to_csv(OUT / "gains.csv", index=False)
        run["rows_out"] = len(E)
        print(G.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
