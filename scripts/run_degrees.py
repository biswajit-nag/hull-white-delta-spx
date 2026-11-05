"""The degree of R2's polynomial (analysis_plan.md §16.8): P0–P8 and the validated choice PCV, 2011–2023.

Pk: δ + ν/(S√τ)·p_k(|δ|), least squares on the Legendre basis in |δ| of the rehearsal; P2 must reproduce R2.
PCV: at each refit, every degree is fitted on the window's months before each of its last three months
and scored on that month (pairs ending before the validation month for the fit, before the test month
for the score); the lowest pooled validation SSE picks the degree, refitted on the whole window.
All fits come from per-session sums of xL·(xL)ᵀ, xL·y and y² (all pairs of a session share day two).
Writes walkforward/degrees_by_year.csv, degrees_median_yearly_gain.csv and degrees_pcv_choice.csv
(results/spy/walkforward/ with --spy).

Usage: uv run python -I scripts/run_degrees.py [--spy]
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
DMAX = 8
START = {12: "2011-01", 36: "2013-01", 60: "2015-01"}


def solve(A, b, k):
    """β for degree k from the summed statistics, or None when singular."""
    M = A[: k + 1, : k + 1]
    if np.linalg.matrix_rank(M) < k + 1:
        return None
    return np.linalg.solve(M, b[: k + 1])


def main() -> None:
    with timed("degrees_walkforward", inputs=f"{U} 2010-2023, P0-P8 and PCV, W12 W36 W60") as log:
        P = h.load_pairs(range(2010, 2024), underlying=U)
        fr = h.ingredients(P)
        fr = fr[fr.avail]
        P = P.loc[fr.index]
        XL = fr.x.to_numpy()[:, None] * h.legendre_basis(fr.delta.to_numpy(), DMAX)
        y = fr.y.to_numpy()
        # per (type, session): the sufficient statistics of every degree
        stats = {}
        nxt = P.groupby("quote_date").next_session.first()
        for (cp, s), idx in fr.groupby(["cp", "session"]).indices.items():
            Xg, yg = XL[idx], y[idx]
            stats[(cp, s)] = (Xg.T @ Xg, Xg.T @ yg, float(yg @ yg))
        sessions = pd.DatetimeIndex(sorted(nxt.index))
        nexts = nxt.reindex(sessions)

        def total(cp, lo, hi, end):
            """Summed statistics over sessions in [lo, hi) whose day two precedes `end`."""
            sel = sessions[(sessions >= lo) & (sessions < hi) & (nexts < end).to_numpy()]
            parts = [stats[(cp, s)] for s in sel if (cp, s) in stats]
            if not parts:
                return None, 0
            return (sum(p[0] for p in parts), sum(p[1] for p in parts), sum(p[2] for p in parts)), len(parts)

        month = P.quote_date.dt.to_period("M")
        rows, choices = [], []
        for W, start in START.items():
            E = []
            for m in pd.period_range(start, "2023-12", freq="M"):
                s0 = P.quote_date[month == m].min()
                if pd.isna(s0):
                    continue
                lo = (m - W).to_timestamp()
                for cp in "CP":
                    T, n = total(cp, lo, s0, s0)
                    te = (month == m) & (fr.cp == cp)
                    if T is None or n < 150 or not te.any():
                        continue
                    betas = {k: solve(T[0], T[1], k) for k in range(DMAX + 1)}
                    if betas[2] is None:
                        continue
                    # PCV: the last three months of the window as validation folds
                    val = np.zeros(DMAX + 1)
                    for v in (m - 3, m - 2, m - 1):
                        v0 = v.to_timestamp()
                        Tf, nf = total(cp, lo, v0, v0)
                        Tv, nv = total(cp, v0, (v + 1).to_timestamp(), s0)
                        if Tf is None or Tv is None:
                            val[:] = np.nan
                            break
                        for k in range(DMAX + 1):
                            b = solve(Tf[0], Tf[1], k)
                            val[k] += np.inf if b is None else Tv[2] - 2 * b @ Tv[1][: k + 1] + b @ Tv[0][: k + 1, : k + 1] @ b
                    kstar = int(np.nanargmin(val)) if np.isfinite(val).any() else 2
                    choices.append({"window": W, "month": str(m), "cp": cp, "degree": kstar})
                    d = fr[te]
                    Xt, yt = XL[te.to_numpy()], d.y.to_numpy()
                    e = {"R1": yt, "month": str(m)}
                    for k, b in betas.items():
                        e[f"P{k}"] = yt - Xt[:, : k + 1] @ b if b is not None else np.full(len(d), np.nan)
                    e["PCV"] = e[f"P{kstar}"]
                    # R2 refitted the usual way: P2 must reproduce it
                    trm = h.training_mask(P.quote_date, P.next_session, s0, W) & (fr.cp == cp)
                    e["R2"] = (d.y - h.design("R2", d)[0] @ h.ols(*h.design("R2", fr[trm]))).to_numpy()
                    E.append(pd.DataFrame(e, index=d.index))
                if m.month == 12:
                    print(f"W{W} {m} done", flush=True)
            E = pd.concat(E)
            log.setdefault("notes", "")
            log["notes"] += f"W{W}: max |P2 - R2| error {np.nanmax(np.abs(E.P2 - E.R2)):.2e}; "
            yr = P.loc[E.index, "quote_date"].dt.year
            rules = [f"P{k}" for k in range(DMAX + 1)] + ["PCV"]
            for year in sorted(yr.unique()):
                e = E[(yr == year).to_numpy()]
                for r in rules:
                    ee = e[e[r].notna()]
                    index = pd.DatetimeIndex(np.sort(fr.loc[ee.index, "session"].unique()))
                    g = h.gain_table(h.aligned_sse(ee, fr, ["R1", "R2", r], index), [(r, "R1"), (r, "R2")],
                                     h.bootstrap_counts(index, B=10_000, block=10, seed=2026))
                    rows.append(g.assign(window=W, year=year, months=ee.month.nunique()))
        G = pd.concat(rows, ignore_index=True)
        G.to_csv(OUT / "degrees_by_year.csv", index=False)
        med = G[G.year >= 2015].groupby(["window", "cp", "rule", "base"]).gain.median().rename("median_yearly_gain").reset_index()
        med.to_csv(OUT / "degrees_median_yearly_gain.csv", index=False)
        C = pd.DataFrame(choices)
        C.to_csv(OUT / "degrees_pcv_choice.csv", index=False)
        log["rows_out"] = len(G)
        print(log["notes"])
        print(med.pivot_table(index="rule", columns=["base", "window", "cp"], values="median_yearly_gain").round(3).to_string())
        print(C.groupby(["window", "cp"]).degree.value_counts().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
