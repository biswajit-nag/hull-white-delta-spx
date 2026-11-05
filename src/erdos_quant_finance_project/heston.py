"""Heston European prices, C_S and C_v, and a fast daily calibrator (analysis_plan.md §16.5).

Pricing is Lewis's formula with a Black–Scholes control variate, as in Lecture 12's option_pricing.py.
For a call,

    C = C_BS(w̄) − (√(S·K)·e^{−(r+q)τ/2}/π) ∫_0^∞ Re[e^{iuk}·(φ(u − i/2) − φ_BS(u − i/2))] / (u² + 1/4) du,

with k = ln(S/K) + (r − q)τ, w̄ = E∫_0^τ v_s ds the expected integrated variance, φ the characteristic
function of ln(S_T/F) in Albrecher et al.'s form, and φ_BS(u − i/2) = exp(−w̄(u² + 1/4)/2). Puts follow by
parity. The library integrates on a fixed 256 nodes whatever the range; here the integral uses composite
16-point Gauss–Legendre panels whose width resolves the integrand's phase, out to the library's range
heuristic, so the node count grows with the range.

All options of one expiry share a node grid, and the strike terms e^{iuk}·w/(u² + 1/4) do not depend on
the model parameters. A Chain precomputes them once, so each evaluation is one matrix product per expiry,
for any number of parameter sets at once.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import least_squares
from scipy.special import ndtr, roots_legendre

NAMES = ["v0", "kappa", "theta", "xi", "rho"]
LB = np.array([0.01**2, 0.1, 0.01**2, 0.05, -0.999])  # the lecture's bounds, as in §16.2
UB = np.array([1.5**2, 10.0, 1.0**2, 5.0, 0.0])
X0 = np.array([0.04, 2.0, 0.04, 0.5, -0.7])            # the lecture's default start
_GL_X, _GL_W = roots_legendre(16)
_SQ2PI = np.sqrt(2 * np.pi)


def integrated_variance(tau, v0, kappa, theta):
    """w̄ = τ·[θ + (v0 − θ)·a] with a = (1 − e^{−κτ})/(κτ), and ∂w̄/∂v0 = τ·a."""
    kt = np.asarray(kappa * tau, float)
    safe = np.where(kt > 1e-8, kt, 1.0)
    a = np.where(kt > 1e-8, -np.expm1(-safe) / safe, 1.0 - kt / 2)
    return tau * (theta + (v0 - theta) * a), tau * a


def cf(u, tau, v0, kappa, theta, xi, rho):
    """φ(u − i/2) for ln(S_T/F), and D(u) = ∂ln φ/∂v0. Arrays broadcast."""
    h = u * u + 0.25
    beta = kappa - rho * xi * (0.5 + 1j * u)
    d = np.sqrt(beta * beta + xi * xi * h)       # principal root: Re d ≥ 0
    plus = beta + d
    minus = -(xi * xi * h) / plus                # β − d without cancellation as ξ → 0
    g = minus / plus
    one_minus_e = -np.expm1(-d * tau)
    D = (minus / (xi * xi)) * one_minus_e / (1.0 - g + g * one_minus_e)
    C = (kappa * theta / (xi * xi)) * (minus * tau - 2.0 * np.log1p(g * one_minus_e / (1.0 - g)))
    return np.exp(C + D * v0), D


def range_needed(tau, x) -> float:
    """The library's integration-range heuristic at parameters x = (v0, κ, θ, ξ, ρ)."""
    v0, ka, th, xi, rho = x
    w, _ = integrated_variance(tau, v0, ka, th)
    decay = np.sqrt(1 - rho**2) * (v0 + ka * th * tau) / xi
    return float(max(100.0, 12.0 / np.sqrt(w), 20.0 / decay))


def phase_rate(tau, x, kmax) -> float:
    """Phase per unit u of the integrand at large u: the strike term's |k| plus φ's own drift."""
    v0, ka, th, xi, rho = x
    return float(kmax + abs(rho) * (v0 + ka * th * tau) / xi)


MAX_PANELS = 3000  # 48,000 nodes per expiry; reached only near the variance bounds, and reported as `capped`


def nodes(limit: float, rate: float, rad_per_panel: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
    """Composite 16-point Gauss–Legendre on [0, limit], each panel spanning at most rad_per_panel radians."""
    width = min(limit / 8, rad_per_panel / max(rate, 1e-3))
    n = min(int(np.ceil(limit / width)), MAX_PANELS)
    edges = np.linspace(0.0, limit, n + 1)
    half = np.diff(edges) / 2
    u = (edges[:-1, None] + half[:, None] * (_GL_X[None, :] + 1)).ravel()
    w = (half[:, None] * _GL_W[None, :]).ravel()
    return u, w


@dataclass
class _Expiry:
    idx: np.ndarray       # positions of the expiry's options in the chain
    tau: float
    k: np.ndarray         # forward log-moneyness ln(S/K) + (r − q)τ
    sd: float             # S·e^{−qτ}
    kd: np.ndarray        # K·e^{−rτ}
    amp: np.ndarray       # √(S·K)·e^{−(r+q)τ/2}/π
    u: np.ndarray
    h: np.ndarray         # u² + 1/4
    E: np.ndarray         # m × n: e^{iuk}·w/(u² + 1/4)
    limit: float


class Chain:
    """One session's options (single spot S), grouped by expiry with a fixed node grid per expiry.

    tau, r, q, K, cp are per option (r and q constant within an expiry); grid_params is a list of
    parameter vectors the grid must serve (the starts, or a solution): each expiry's range is the
    largest the heuristic needs over them, times `range_factor`.
    """

    def __init__(self, S, K, tau, r, q, cp, grid_params, range_factor=1.0, rad_per_panel=3.0):
        self.S = float(S)
        self.K, self.tau, self.cp = np.asarray(K, float), np.asarray(tau, float), np.asarray(cp, float)
        r, q = np.asarray(r, float), np.asarray(q, float)
        self.n = len(self.K)
        self.grid_params = [np.asarray(x, float) for x in grid_params]
        self.expiries = []
        for t in np.unique(self.tau):
            idx = np.flatnonzero(self.tau == t)
            re, qe = r[idx].mean(), q[idx].mean()
            k = np.log(self.S / self.K[idx]) + (re - qe) * t
            kmax = float(np.abs(k).max())
            limit = range_factor * max(range_needed(t, x) for x in self.grid_params)
            rate = max(phase_rate(t, x, kmax) for x in self.grid_params)
            u, w = nodes(limit, rate, rad_per_panel)
            self.capped = getattr(self, "capped", False) or len(u) >= 16 * MAX_PANELS
            h = u * u + 0.25
            E = np.exp(1j * np.outer(k, u)) * (w / h)[None, :]
            self.expiries.append(_Expiry(idx, float(t), k, self.S * np.exp(-qe * t), self.K[idx] * np.exp(-re * t),
                                         np.sqrt(self.S * self.K[idx]) * np.exp(-0.5 * (re + qe) * t) / np.pi,
                                         u, h, E, limit))

    def evaluate(self, X, greeks=False) -> dict:
        """Prices (and with greeks=True, C_S and C_v) for parameter sets X of shape (s, 5): arrays (s, n)."""
        X = np.atleast_2d(np.asarray(X, float))
        s = len(X)
        price = np.empty((s, self.n))
        if greeks:
            delta, cv = np.empty((s, self.n)), np.empty((s, self.n))
        v0, ka, th, xi, rho = (X[:, j, None] for j in range(5))
        for e in self.expiries:
            w, dw = integrated_variance(e.tau, X[:, 0], X[:, 1], X[:, 2])   # (s,)
            phi, D = cf(e.u[None, :], e.tau, v0, ka, th, xi, rho)          # (s, n_u)
            phi_bs = np.exp(-0.5 * w[:, None] * e.h[None, :])
            Z = phi - phi_bs
            root = np.sqrt(w)[None, :]                                      # (1, s)
            d1 = (e.k[:, None] + 0.5 * w[None, :]) / root                    # (m, s)
            call = e.sd * ndtr(d1) - e.kd[:, None] * ndtr(d1 - root) - e.amp[:, None] * (e.E @ Z.T).real
            sign = self.cp[e.idx][:, None]
            price[:, e.idx] = np.where(sign > 0, call, call - (e.sd - e.kd[:, None])).T
            if greeks:
                Eu = e.E * (0.5 + 1j * e.u)[None, :]
                dc = e.sd / self.S * ndtr(d1) - e.amp[:, None] / self.S * (Eu @ Z.T).real
                delta[:, e.idx] = np.where(sign > 0, dc, dc - e.sd / self.S).T
                dbs = e.sd * np.exp(-0.5 * d1 * d1) / (_SQ2PI * 2 * root)   # ∂C_BS/∂w̄
                dZ = D * phi + 0.5 * e.h[None, :] * phi_bs * dw[:, None]     # ∂(φ − φ_BS)/∂v0
                cv[:, e.idx] = (dbs * dw[None, :] - e.amp[:, None] * (e.E @ dZ.T).real).T
        out = {"price": price}
        if greeks:
            out |= {"delta": delta, "cv": cv}
        return out

    def prices(self, x) -> np.ndarray:
        return self.evaluate(np.asarray(x)[None, :])["price"][0]

    def adequate(self, x) -> bool:
        """Whether every expiry's grid covers the range and phase the heuristic needs at x."""
        return all(e.limit >= range_needed(e.tau, x) for e in self.expiries)


def _steps(x):
    h = 1e-6 * (UB - LB)
    up = np.minimum(x + h, UB)
    dn = np.maximum(x - h, LB)
    return up, dn


def calibrate(chain: Chain, mid, weight, starts, max_nfev=300) -> dict:
    """Least squares of the weighted price errors (model − mid)·weight from each start; the lowest cost wins.

    The Jacobian is a central difference, all 10 shifted parameter sets priced in one evaluation.
    """
    mid, weight = np.asarray(mid, float), np.asarray(weight, float)

    def fun(x):
        return (chain.prices(x) - mid) * weight

    def jac(x):
        up, dn = _steps(x)
        X = np.vstack([np.where(np.arange(5)[:, None] == np.arange(5)[None, :], up[None, :], x[None, :]),
                       np.where(np.arange(5)[:, None] == np.arange(5)[None, :], dn[None, :], x[None, :])])
        P = chain.evaluate(X)["price"]
        return ((P[:5] - P[5:]) / (up - dn)[:, None]).T * weight[:, None]

    best = None
    for x0 in starts:
        x0 = np.clip(np.asarray(x0, float), LB + 1e-6 * (UB - LB), UB - 1e-6 * (UB - LB))
        res = least_squares(fun, x0, jac=jac, bounds=(LB, UB), x_scale="jac", method="trf",
                            ftol=1e-10, xtol=1e-10, gtol=1e-8, max_nfev=max_nfev)
        if best is None or res.cost < best.cost:
            best = res
    return {"x": best.x, "cost": float(best.cost), "status": int(best.status), "nfev": int(best.nfev),
            "njev": int(best.njev or 0), "success": bool(best.status >= 1)}
