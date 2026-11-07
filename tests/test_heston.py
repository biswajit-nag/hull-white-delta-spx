"""The project's Heston pricer (plan §16.5): an adaptive-quadrature reference, parity, C_S and C_v, the calibrator."""

import numpy as np
import pytest
from scipy.integrate import quad

from erdos_quant_finance_project import blackscholes as bs
from erdos_quant_finance_project import heston as H
from erdos_quant_finance_project.lecture import lecture12_path

needs_lecture = pytest.mark.skipif(not lecture12_path().exists(), reason="Lecture 12 clone absent (set ERDOS_LECTURE12)")

S, R, Q = 3000.0, 0.02, 0.018
SETS = [(0.027, 10.0, 0.041, 2.8, -0.65),   # a typical 2019–2020 calibration
        (0.03, 10.0, 0.04, 5.0, -0.7),       # ξ at its bound: the library's 256 nodes fail here
        (0.89, 10.0, 0.239, 5.0, -0.86),     # 2020-03-16
        (0.01, 10.0, 0.25, 5.0, -0.999)]     # ρ near its bound
DAYS = np.array([14, 60, 365])
MNY = np.array([0.6, 0.9, 1.0, 1.1, 1.3])


def _cf(z, t, v0, ka, th, xi, rho):
    b = ka - rho * xi * 1j * z
    d = np.sqrt(b * b + xi * xi * (z * z + 1j * z))
    g = (b - d) / (b + d)
    e = np.exp(-d * t)
    return np.exp(ka * th / xi**2 * ((b - d) * t - 2 * np.log((1 - g * e) / (1 - g))) + (b - d) / xi**2 * (1 - e) / (1 - g * e) * v0)


def _reference_call(K, t, p):
    k = np.log(S / K) + (R - Q) * t
    f = lambda u: (np.exp(1j * u * k) * _cf(u - 0.5j, t, *p)).real / (u * u + 0.25)
    cuts = (0, 20, 200, 2000, 20000, np.inf)
    I = sum(quad(f, a, b, limit=5000, epsabs=1e-14, epsrel=1e-13)[0] for a, b in zip(cuts[:-1], cuts[1:]))
    return S * np.exp(-Q * t) - np.sqrt(S * K) * np.exp(-0.5 * (R + Q) * t) / np.pi * I


def _grid():
    T, M = np.meshgrid(DAYS / 365, MNY, indexing="ij")
    T, K = T.ravel(), S * M.ravel()
    cp = np.where(K < S, -1.0, 1.0)
    return K, T, cp


@needs_lecture  # bs.implied_vol calls the lecture library's IV solver
@pytest.mark.parametrize("p", SETS)
def test_matches_adaptive_quadrature_within_a_hundredth_of_a_vol_point(p):
    K, T, cp = _grid()
    p = np.array(p)
    ch = H.Chain(S, K, T, np.full_like(T, R), np.full_like(T, Q), cp, [p])
    ref = np.array([_reference_call(k, t, p) for k, t in zip(K, T)])
    ref = np.where(cp > 0, ref, ref - (S * np.exp(-Q * T) - K * np.exp(-R * T)))
    F, D = S * np.exp((R - Q) * T), np.exp(-R * T)
    iv = bs.implied_vol(ch.prices(p), np.full_like(T, S), F, K, D, T, cp)[0]
    iv_ref = bs.implied_vol(ref, np.full_like(T, S), F, K, D, T, cp)[0]
    ok = np.isfinite(iv_ref)
    assert ok.sum() >= len(K) - 1
    assert np.nanmax(np.abs(iv - iv_ref)[ok]) < 1e-4


def test_put_call_parity_and_sensitivities():
    K, T, _ = _grid()
    p = np.array(SETS[0])
    args = (K, T, np.full_like(T, R), np.full_like(T, Q))
    c = H.Chain(S, *args, np.ones_like(T), [p]).evaluate(p[None], greeks=True)
    pu = H.Chain(S, *args, -np.ones_like(T), [p]).evaluate(p[None], greeks=True)
    assert np.allclose(c["price"][0] - pu["price"][0], S * np.exp(-Q * T) - K * np.exp(-R * T), atol=1e-8)
    assert np.allclose(c["delta"][0] - pu["delta"][0], np.exp(-Q * T), atol=1e-10)
    hS = 1e-4 * S
    fd = (H.Chain(S + hS, *args, np.ones_like(T), [p]).prices(p) - H.Chain(S - hS, *args, np.ones_like(T), [p]).prices(p)) / (2 * hS)
    assert np.allclose(c["delta"][0], fd, atol=1e-5)
    ch = H.Chain(S, *args, np.ones_like(T), [p])
    hv = 1e-5 * p[0]
    cv = (ch.prices(p + [hv, 0, 0, 0, 0]) - ch.prices(p - [hv, 0, 0, 0, 0])) / (2 * hv)
    assert np.allclose(c["cv"][0], cv, rtol=1e-6, atol=1e-6)
    assert np.allclose(c["cv"][0], pu["cv"][0], atol=1e-8)


def test_calibrator_recovers_known_parameters():
    days = np.repeat([20, 45, 90, 180, 300], 9)
    T = days / 365
    K = S * np.tile(np.linspace(0.8, 1.15, 9), 5)
    cp = np.where(K < S * np.exp((R - Q) * T), -1.0, 1.0)
    true = np.array([0.03, 3.0, 0.05, 1.2, -0.7])
    ch = H.Chain(S, K, T, np.full_like(T, R), np.full_like(T, Q), cp, [true, H.X0])
    fit = H.calibrate(ch, ch.prices(true), np.ones_like(T), [H.X0])
    assert fit["success"]
    assert np.allclose(fit["x"], true, rtol=1e-3, atol=1e-4)
