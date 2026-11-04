"""Black–Scholes in forward form: prices, implied volatility and Greeks from (D, F).

Every option is priced on its expiry's parity forward F and discount factor D (analysis_plan.md §4):
C = D·[F·N(d1) − K·N(d2)], d1 = [ln(F/K) + σ²τ/2]/(σ√τ). No rate or dividend yield is needed.
The implied volatility comes from the Lecture 12 solver, called with r = −ln(D)/τ and
q = r − ln(F/S)/τ, which reproduces the forward-form price for any S.

cp is +1 for calls and −1 for puts. τ is in years, σ a decimal; vega is per unit of σ and the
thetas are per year (divide by 365 for a calendar day).
"""

from __future__ import annotations

import numpy as np
from scipy.special import ndtr

from .lecture import option_pricing

SQRT2PI = np.sqrt(2 * np.pi)


def carry(S, F, D, tau):
    """The (r, q) pair that makes the lectures' dividend-yield formulas price on (D, F)."""
    r = -np.log(D) / tau
    return r, r - np.log(F / S) / tau


def d1d2(F, K, sigma, tau):
    w = sigma * np.sqrt(tau)
    d1 = (np.log(F / K) + 0.5 * w * w) / w
    return d1, d1 - w


def price(F, K, D, sigma, tau, cp):
    d1, d2 = d1d2(F, K, sigma, tau)
    return cp * D * (F * ndtr(cp * d1) - K * ndtr(cp * d2))


def greeks(S, F, K, D, sigma, tau, cp) -> dict[str, np.ndarray]:
    """Spot Greeks at the given (own) implied volatility, and the forward and discount sensitivities."""
    d1, d2 = d1d2(F, K, sigma, tau)
    pdf = np.exp(-0.5 * d1 * d1) / SQRT2PI
    sqt = np.sqrt(tau)
    vega = D * F * pdf * sqt
    dV_dF = cp * D * ndtr(cp * d1)
    return {
        "price": cp * D * (F * ndtr(cp * d1) - K * ndtr(cp * d2)),
        "delta": dV_dF * F / S,
        "vega": vega,
        "gamma": D * (F / S) * pdf / (S * sigma * sqt),
        "vanna": -D * (F / S) * pdf * d2 / sigma,
        "volga": vega * d1 * d2 / sigma,
        # time decay at fixed F and D, per year
        "theta_F": -D * F * pdf * sigma / (2 * sqt),
        "dV_dF": dV_dF,
        "d1": d1,
    }


def theta_spot(S, F, D, tau, g):
    """The lectures' theta (at fixed S, r and q; per year): θ_F + r·V − (r − q)·F·∂V/∂F."""
    r, q = carry(S, F, D, tau)
    return g["theta_F"] + r * g["price"] - (r - q) * F * g["dV_dF"]


def implied_vol(mid, S, F, K, D, tau, cp, *, tol=1e-8):
    """Implied volatility of each mid, with the Lecture 12 solver's status per row."""
    op = option_pricing()
    r, q = carry(S, F, D, tau)
    mid, S, K, tau, r, q, cp = np.broadcast_arrays(*(np.asarray(a, dtype=float) for a in (mid, S, K, tau, r, q, cp)))
    iv = np.full(mid.shape, np.nan)
    status = np.full(mid.shape, "not_attempted", dtype=object)
    for sign, option in ((1, "call"), (-1, "put")):
        m = cp == sign
        if m.any():
            out = op.bs_euro_iv(mid[m], S[m], K[m], tau[m], r[m], q[m], option=option, tol=tol, return_info=True)
            iv[m], status[m] = out["iv"], out["status"]
    return iv, status
