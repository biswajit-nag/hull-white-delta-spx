"""Parameter stability (analysis_plan.md §16.10, item 2): R2's (a, b, c), R4's â and P0's c at every refit.

W12, W36 and W60, test months 2011–2023 (W36 from 2013, W60 from 2015), with session-clustered standard
errors from per-session sums: for regressors X and target t on session g, A_g = XᵀX and b_g = Xᵀt, so a fit
is β = (ΣA)⁻¹Σb and session g's score is b_g − A_g·β (sandwich (ΣA)⁻¹·Σ s_g s_gᵀ·(ΣA)⁻¹). Summaries per
window and coefficient: range, median |month-to-month change| / SE, and for W12 the z-statistic between
fits 12 months apart (non-overlapping windows). With --heston (SPX only), the yearly stability of the
calibration-B2 parameters. Writes parameter_paths.csv and parameter_stability_summary.csv in
results/walkforward/ (results/spy/walkforward/ with --spy), and results/heston2/parameter_stability.csv.

Usage: uv run python -I scripts/parameter_stability.py [--spy] [--heston]
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

U = "spy" if "--spy" in sys.argv else "spx"
OUT = ROOT / ("results/spy/walkforward" if U == "spy" else "results/walkforward")
NAMES = {"R2": ["a", "b", "c"], "R4": ["a_hat"], "P0": ["c0"]}


def fit(stats, sessions):
    A = sum(stats[s][0] for s in sessions)
    b = sum(stats[s][1] for s in sessions)
    beta = np.linalg.solve(A, b)
    Ai = np.linalg.inv(A)
    meat = sum(np.outer(stats[s][1] - stats[s][0] @ beta, stats[s][1] - stats[s][0] @ beta) for s in sessions)
    return beta, Ai @ meat @ Ai


def heston_stability() -> None:
    P = pd.concat([pd.read_csv(f, parse_dates=["session"]) for f in sorted((ROOT / "results/heston2").glob("params_*.csv"))])
    P = P[P.ok.fillna(False).astype(bool)].sort_values("session")
    lb = {"v0": 1e-4, "kappa": 0.1, "theta": 1e-4, "xi": 0.05, "rho": -0.999}
    ub = {"v0": 2.25, "kappa": 10.0, "theta": 1.0, "xi": 5.0, "rho": 0.0}
    rows = []
    for k in lb:
        span = ub[k] - lb[k]
        d = P[k].diff().abs()
        for y, g in P.groupby(P.session.dt.year):
            x = g[k]
            rows.append({"parameter": k, "year": y, "median": x.median(), "q25": x.quantile(0.25), "q75": x.quantile(0.75),
                         "median_abs_daily_change": d.loc[g.index].median(),
                         "median_abs_daily_change_rel": float((d.loc[g.index] / x.abs()).median()),
                         "share_at_bound": float(((x - lb[k] < 1e-3 * span) | (ub[k] - x < 1e-3 * span)).mean())})
    pd.DataFrame(rows).to_csv(ROOT / "results/heston2/parameter_stability.csv", index=False)
    print(pd.DataFrame(rows).pivot_table(index="year", columns="parameter", values=["median", "share_at_bound"]).round(3).to_string())


def main() -> None:
    if "--heston" in sys.argv:
        heston_stability()
        return
    with timed("parameter_stability", inputs=f"{U} 2010-2023, W12 W36 W60") as log:
        P = h.load_pairs(range(2010, 2024), underlying=U)
        fr = h.ingredients(P)
        fr = fr[fr.avail]
        P = P.loc[fr.index]
        X2 = fr.x.to_numpy()[:, None] * h.poly(fr.delta.to_numpy())
        y, u, f = fr.y.to_numpy(), fr.u.to_numpy(), fr.f.to_numpy()
        stats = {"R2": {}, "R4": {}, "P0": {}}
        for (cp, s), idx in fr.groupby(["cp", "session"]).indices.items():
            Xg = X2[idx]
            stats["R2"][(cp, s)] = (Xg.T @ Xg, Xg.T @ y[idx])
            stats["R4"][(cp, s)] = (np.array([[u[idx] @ u[idx]]]), np.array([u[idx] @ f[idx]]))
            stats["P0"][(cp, s)] = (Xg[:, :1].T @ Xg[:, :1], Xg[:, :1].T @ y[idx])
        nxt = P.groupby("quote_date").next_session.first()
        sessions = pd.DatetimeIndex(sorted(nxt.index))
        month = P.quote_date.dt.to_period("M")
        first = P.groupby(month).quote_date.min()
        rows = []
        for W, start in ((12, "2011-01"), (36, "2013-01"), (60, "2015-01")):
            for m in pd.period_range(start, "2023-12", freq="M"):
                if m not in first.index:
                    continue
                s0, lo = first[m], (m - W).to_timestamp()
                tr = sessions[(sessions >= lo) & (sessions < s0) & (nxt.reindex(sessions) < s0).to_numpy()]
                for cp in "CP":
                    sel = [(cp, s) for s in tr if (cp, s) in stats["R2"]]
                    if len(sel) < 150:
                        continue
                    for rule in ("R2", "R4", "P0"):
                        st = {k: stats[rule][k] for k in sel}
                        beta, cov = fit(st, sel)
                        se = np.sqrt(np.diag(cov))
                        corr = cov / np.outer(se, se)
                        for i, nm in enumerate(NAMES[rule]):
                            row = {"window": W, "month": str(m), "cp": cp, "rule": rule, "coef": nm, "value": beta[i], "se": se[i]}
                            if rule == "R2":
                                row |= {"corr_ab": corr[0, 1], "corr_ac": corr[0, 2], "corr_bc": corr[1, 2]}
                            rows.append(row)
        T = pd.DataFrame(rows)
        T.to_csv(OUT / "parameter_paths.csv", index=False)
        summ = []
        for (W, cp, rule, nm), g in T.groupby(["window", "cp", "rule", "coef"]):
            g = g.sort_values("month").reset_index(drop=True)
            dchg = g.value.diff().abs() / g.se
            row = {"window": W, "cp": cp, "rule": rule, "coef": nm, "refits": len(g), "min": g.value.min(), "max": g.value.max(),
                   "median": g.value.median(), "median_se": g.se.median(), "median_abs_change_over_se": dchg.median()}
            if W == 12:
                g["p"] = pd.PeriodIndex(g.month, freq="M")
                lag = g.set_index("p")[["value", "se"]]
                prev = lag.reindex(lag.index - 12)
                z = (lag.value.to_numpy() - prev.value.to_numpy()) / np.sqrt(lag.se.to_numpy() ** 2 + prev.se.to_numpy() ** 2)
                z = z[np.isfinite(z)]
                row |= {"z12_pairs": len(z), "share_abs_z12_gt_2": float((np.abs(z) > 2).mean()), "median_abs_z12": float(np.median(np.abs(z)))}
            if rule == "R2":
                row |= {"median_corr_ab": g.corr_ab.median(), "median_corr_ac": g.corr_ac.median(), "median_corr_bc": g.corr_bc.median()}
            summ.append(row)
        S = pd.DataFrame(summ)
        S.to_csv(OUT / "parameter_stability_summary.csv", index=False)
        log["rows_out"] = len(T)
        print(S.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
