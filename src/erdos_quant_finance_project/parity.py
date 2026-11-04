"""Forwards and discount factors from put–call parity, and the options' own index level (plan §2, §4).

Parity at mids: C − P = D·F − D·K for each expiry, so a weighted least-squares line in K gives the
discount factor D (minus the slope) and the forward F (intercept over D). Three stages:
1. a parity fit per expiry on 0.9 ≤ K/S_close ≤ 1.1, both legs two-sided, at least 6 strikes;
2. a per-session zero-rate curve r(τ), linear in τ, from the stage-1 fits at least 30 days out;
3. each expiry's forward given D(τ_e), from at least 3 strikes.
An expiry is (am_settled, settle_date): A.M. and P.M. contracts on one date have different forwards.
Sensitivity A's level is the forward of the nearest P.M. expiry 0.5–5 days out (else up to 10).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EXPIRY = ["quote_date", "am_settled", "settle_date"]
SPREAD_FLOOR = 0.05


def strike_table(rows: pd.DataFrame) -> pd.DataFrame:
    """Calls and puts side by side per (session, expiry, strike), with τ in years and the WLS weight."""
    k = EXPIRY + ["strike"]
    base = rows[k + ["cp", "bid", "ask", "mid", "S_close", "tau"]]
    c = base[base.cp == "C"].drop(columns="cp")
    p = base[base.cp == "P"].drop(columns=["cp", "S_close", "tau"])
    w = c.merge(p, on=k, suffixes=("_c", "_p"))
    w["two_sided"] = (w.bid_c > 0) & (w.ask_c >= w.bid_c) & (w.bid_p > 0) & (w.ask_p >= w.bid_p)
    w["y"] = w.mid_c - w.mid_p
    w["w"] = 1 / (np.maximum(w.ask_c - w.bid_c, SPREAD_FLOOR) ** 2 + np.maximum(w.ask_p - w.bid_p, SPREAD_FLOOR) ** 2)
    return w


def _wls_line(w: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Per-group WLS of y on (1, K): intercept a = D·F, slope b = −D, with the slope's standard error."""
    w = w.assign(wk=w.w * w.strike, wy=w.w * w.y, wkk=w.w * w.strike**2, wky=w.w * w.strike * w.y)
    g = w.groupby(keys, sort=False, observed=True)
    m = g[["w", "wk", "wy", "wkk", "wky"]].sum()
    m["n"] = g.size()
    sxx = m.wkk - m.wk**2 / m.w
    m["b"] = (m.wky - m.wk * m.wy / m.w) / sxx
    m["a"] = (m.wy - m.b * m.wk) / m.w
    res = w.join(m[["a", "b"]], on=keys)
    res["wee"] = res.w * (res.y - res.a - res.b * res.strike) ** 2
    m["s2"] = res.groupby(keys, sort=False, observed=True).wee.sum() / (m.n - 2)
    m["se_b"] = np.sqrt(m.s2 / sxx)
    return m.drop(columns=["wk", "wy", "wkk", "wky"])


def stage1(w: pd.DataFrame) -> pd.DataFrame:
    """Parity fit per expiry: D_e, F_e and the implied zero rate r_e with its standard error."""
    use = w[w.two_sided & (w.strike / w.S_close).between(0.9, 1.1)]
    m = _wls_line(use, EXPIRY)
    m["tau"] = use.groupby(EXPIRY, sort=False, observed=True).tau.first()
    m = m[(m.n >= 6) & (-m.b > 0)].copy()
    m["D"], m["F"] = -m.b, -m.a / m.b
    m["r"] = -np.log(m.D) / m.tau
    m["se_r"] = m.se_b / (m.D * m.tau)
    return m[["n", "tau", "D", "F", "r", "se_r"]].reset_index()


def _curve(f: pd.DataFrame) -> pd.Series:
    """r(τ) = c0 + c1·τ by WLS on the fits ≥ 30 days out; flat (weighted mean) with fewer than 3."""
    use, kind = f[f.tau >= 30 / 365], "long"
    if use.empty:
        use, kind = f, "all"
    wt = 1 / use.se_r**2
    if len(use) >= 3:
        X = np.column_stack([np.ones(len(use)), use.tau])
        c0, c1 = np.linalg.lstsq(X * np.sqrt(wt.values)[:, None], use.r.values * np.sqrt(wt.values), rcond=None)[0]
        form = "linear"
    else:
        c0, c1, form = np.average(use.r, weights=wt), 0.0, "flat"
    return pd.Series({"c0": c0, "c1": c1, "tau_lo": use.tau.min(), "tau_hi": use.tau.max(), "n_fits": len(use),
                      "basis": kind, "form": form})


def stage2(fits: pd.DataFrame) -> pd.DataFrame:
    fits = fits[np.isfinite(fits.se_r) & (fits.se_r > 0)]
    return fits.groupby("quote_date").apply(_curve, include_groups=False)


def discount(curve: pd.DataFrame, quote_date: pd.Series, tau: pd.Series) -> pd.Series:
    """D(τ) = exp(−r(τ)·τ) from each session's curve, with r flat beyond the fitted range."""
    c = curve.reindex(quote_date.values)
    t = np.clip(tau.values, c.tau_lo.values, c.tau_hi.values)
    r = c.c0.values + c.c1.values * t
    return pd.Series(np.exp(-r * tau.values), index=tau.index)


def stage3(w: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    """Each expiry's forward given D(τ_e): weighted mean of (C − P)/D + K over the stage-1 strikes (≥ 3)."""
    use = w[w.two_sided & (w.strike / w.S_close).between(0.9, 1.1)].copy()
    use["D"] = discount(curve, use.quote_date, use.tau)
    use["fk"] = use.w * (use.y / use.D + use.strike)
    g = use.groupby(EXPIRY, sort=False, observed=True)
    out = g[["w", "fk"]].sum()
    out["n"], out["D"], out["tau"] = g.size(), g.D.first(), g.tau.first()
    out["F"] = out.fk / out.w
    return out[(out.n >= 3) & (out.F > 0)][["n", "tau", "D", "F"]].reset_index()


def level_A(w: pd.DataFrame) -> pd.DataFrame:
    """Sensitivity A: the forward of the nearest P.M. expiry 0.5–5 days out, fitted on strikes within 1.5%
    of the close; if none fits, the nearest up to 10 days. A fit needs ≥ 6 strikes and D in [0.95, 1.01]."""
    days = w.tau * 365
    use = w[w.two_sided & ~w.am_settled.astype(bool) & (days >= 0.5) & (days <= 10)
            & ((w.strike / w.S_close - 1).abs() <= 0.015)]
    m = _wls_line(use, EXPIRY)
    m["days"] = use.groupby(EXPIRY, sort=False, observed=True).tau.first() * 365
    m = m[(m.n >= 6) & (-m.b).between(0.95, 1.01)].reset_index()
    m["S_A"] = -m.a / m.b
    m["tier"] = np.where(m.days <= 5, 1, 2)
    best = m.sort_values(["quote_date", "tier", "days"]).groupby("quote_date").first()
    return best[["S_A", "days", "n", "tier"]].rename(columns={"days": "A_days", "n": "A_strikes", "tier": "A_tier"})
