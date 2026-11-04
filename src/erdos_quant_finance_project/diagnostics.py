"""Descriptive diagnostics: bucket tables, clustered standard errors, the partial second-order attribution (plan §8, §10)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .hedging import poly

DELTA_EDGES = np.round(np.arange(0.05, 0.951, 0.1), 2)          # [0.05, 0.15), …, [0.85, 0.95]
TAU_EDGES = np.array([14, 31, 61, 92, 123, 183, 366, np.inf])    # calendar days, Hull and White's seven
TAU_LABELS = ["14-30", "31-60", "61-91", "92-122", "123-182", "183-365", "366+"]


def buckets(frame: pd.DataFrame) -> pd.DataFrame:
    a = np.abs(frame.delta.to_numpy())
    d = np.clip(np.digitize(a, DELTA_EDGES) - 1, 0, 8)
    t = np.digitize(frame.tau.to_numpy() * 365, TAU_EDGES) - 1
    return pd.DataFrame({"delta_b": np.round(0.1 * (d + 1), 1), "tau_b": np.array(TAU_LABELS + ["?"])[np.clip(t, 0, 7)]},
                        index=frame.index)


def bucket_kappa(frame: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    """Per type × delta × maturity bucket: κ̂ (no-intercept OLS of y on w = (ν/S)(ΔS/S)), √τ_eff·κ̂ with
    τ_eff^(−1/2) = Σw²τ^(−1/2)/Σw², the mean of κ̂·ν/S over the bucket's pairs, and the slope of Δσ on
    ΔS/(S√τ). Pass the rehearsal year's evaluation pairs (plan §10)."""
    b = buckets(frame)
    w = frame.vega_n * frame.dSn
    dsig = (p.loc[frame.index, "iv_next"] - p.loc[frame.index, "iv"]).to_numpy()
    z = frame.dSn / frame.sqrt_tau
    df = pd.DataFrame({"cp": frame.cp, "delta_b": b.delta_b, "tau_b": b.tau_b, "w": w, "y": frame.y, "vega_n": frame.vega_n,
                       "tau": frame.tau, "dsig": dsig, "z": z, "session": frame.session})
    df["ok_sig"] = np.isfinite(df.dsig)

    def one(g):
        ww = (g.w**2).sum()
        kappa = (g.w * g.y).sum() / ww
        tau_eff = ((g.w**2 * g.tau**-0.5).sum() / ww) ** -2
        s = g[g.ok_sig]
        slope = (s.z * s.dsig).sum() / (s.z**2).sum() if len(s) else np.nan
        return pd.Series({"pairs": len(g), "sessions": g.session.nunique(), "kappa": kappa, "tau_eff_days": tau_eff * 365,
                          "sqrt_tau_kappa": np.sqrt(tau_eff) * kappa, "mean_dmv_minus_dbs": kappa * g.vega_n.mean(),
                          "dsig_slope": slope})

    return df.groupby(["cp", "delta_b", "tau_b"]).apply(one, include_groups=False).reset_index()


def clustered_vs_naive(frame: pd.DataFrame) -> pd.DataFrame:
    """R2's coefficients with naive OLS and session-clustered standard errors, per type."""
    rows = []
    for cp in ("C", "P"):
        d = frame[frame.cp == cp]
        X = d.x.to_numpy()[:, None] * poly(d.delta.to_numpy())
        y = d.y.to_numpy()
        XtX_inv = np.linalg.inv(X.T @ X)
        beta = XtX_inv @ X.T @ y
        e = y - X @ beta
        naive = np.sqrt(np.diag(XtX_inv) * (e @ e) / (len(y) - X.shape[1]))
        sc = pd.DataFrame(X * e[:, None]).groupby(d.session.to_numpy()).sum().to_numpy()
        clus = np.sqrt(np.diag(XtX_inv @ (sc.T @ sc) @ XtX_inv))
        for k, name in enumerate("abc"):
            rows.append({"cp": cp, "coef": name, "estimate": beta[k], "se_naive": naive[k], "se_clustered": clus[k],
                         "ratio": clus[k] / naive[k], "pairs": len(y), "sessions": d.session.nunique()})
    return pd.DataFrame(rows)


def attribution(frame: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    """Per-pair terms of Δf − δΔS (in index points): vega, gamma, theta_F, vanna, volga, carry, remainder."""
    q = p.loc[frame.index]
    ok = q.iv_status_next.eq("converged").to_numpy()
    S1 = q.S_close.to_numpy(float)
    dS = (q.S_close_next - q.S_close).to_numpy(float)
    dsig = (q.iv_next - q.iv).to_numpy(float)
    dt = (q.next_session - q.quote_date).dt.days.to_numpy(float) / 365
    df = (q.mid_next - q.mid).to_numpy(float)
    D, F = q.D.to_numpy(float), q.F.to_numpy(float)
    dD, dF = (q.D_next - q.D).to_numpy(float), (q.F_next - q.F).to_numpy(float)
    e = df - q.delta.to_numpy(float) * dS
    t = pd.DataFrame({
        "vega": q.vega.to_numpy(float) * dsig,
        "gamma": 0.5 * q.gamma.to_numpy(float) * dS**2,
        "theta": q.theta_F.to_numpy(float) * dt,
        "vanna": q.vanna.to_numpy(float) * dS * dsig,
        "volga": 0.5 * q.volga.to_numpy(float) * dsig**2,
        "carry": q.mid.to_numpy(float) / D * dD + q.dV_dF.to_numpy(float) * (dF - F / S1 * dS),
    }, index=frame.index)
    t["remainder"] = e - t.sum(axis=1)
    t["error"] = e
    t["dS"] = dS
    t["S1"] = S1
    t["ok"] = ok
    return t


def attribution_summary(t: pd.DataFrame, frame: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    """Per group, on the normalized scale (every term divided by S_t): each term's mean square and every
    pairwise cross-product, relative to the mean squared normalized error; and each term's cross-moment
    and covariance with ΔS/S_t, scaled by E[(ΔS/S_t)²] (its share of the best scalar delta correction)."""
    terms = ["vega", "gamma", "theta", "vanna", "volga", "carry", "remainder"]
    d = t[t.ok].join(buckets(frame.loc[t.index[t.ok]])).join(frame[["cp"]])
    S = d.S1
    n = d[terms].div(S, axis=0)
    e = d.error / S
    x = d.dS / S
    d = pd.concat([n, e.rename("e"), x.rename("x"), d[[c for c in d.columns if c in ("cp", "delta_b", "tau_b")]]], axis=1)
    out = []
    for key, g in d.groupby(by):
        mse = (g.e**2).mean()
        row = dict(zip(by, key if isinstance(key, tuple) else (key,)))
        row["pairs"] = len(g)
        ex2 = (g.x**2).mean()
        for i, a in enumerate(terms):
            row[f"ms_{a}"] = (g[a] ** 2).mean() / mse
            row[f"xmom_{a}"] = (g[a] * g.x).mean() / ex2
            row[f"cov_{a}"] = ((g[a] - g[a].mean()) * (g.x - g.x.mean())).mean() / ex2
            for b in terms[i + 1:]:
                row[f"cross_{a}_{b}"] = 2 * (g[a] * g[b]).mean() / mse
        row["total_check"] = sum(row[f"ms_{a}"] for a in terms) + sum(v for k, v in row.items() if k.startswith("cross_"))
        out.append(row)
    return pd.DataFrame(out)
