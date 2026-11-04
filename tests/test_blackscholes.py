"""Forward-form Black–Scholes: parity, finite differences, the lecture library, IV round trips (plan §11, items 1–3)."""

import numpy as np
import pytest

from erdos_quant_finance_project import blackscholes as bs
from erdos_quant_finance_project.lecture import lecture12_path

RNG = np.random.default_rng(0)
N = 400
S = RNG.uniform(2000, 4000, N)
TAU = RNG.uniform(14 / 365, 3, N)
SIG = RNG.uniform(0.08, 0.9, N)
D = np.exp(-RNG.uniform(0.0, 0.03, N) * TAU)
F = S * np.exp(RNG.uniform(-0.02, 0.02, N) * TAU)
K = F * np.exp(RNG.normal(0, 1, N) * SIG * np.sqrt(TAU))
CP = np.where(RNG.random(N) < 0.5, 1.0, -1.0)


def test_put_call_parity():
    assert np.allclose(bs.price(F, K, D, SIG, TAU, 1) - bs.price(F, K, D, SIG, TAU, -1), D * (F - K), atol=1e-8)


def _fd(f, x, h):
    return (f(x + h) - f(x - h)) / (2 * h)


def test_greeks_match_finite_differences():
    g = bs.greeks(S, F, K, D, SIG, TAU, CP)
    # spot moves carry the forward with them: F(S') = F·S'/S
    v = lambda s: bs.price(F * s / S, K, D, SIG, TAU, CP)
    h = 1e-4 * S
    assert np.allclose(g["delta"], _fd(v, S, 1e-6 * S), rtol=1e-6, atol=1e-8)
    assert np.allclose(g["gamma"], (v(S + h) - 2 * v(S) + v(S - h)) / h**2, rtol=1e-4, atol=1e-8)
    vs = lambda s: bs.price(F, K, D, s, TAU, CP)
    assert np.allclose(g["vega"], _fd(vs, SIG, 1e-6), rtol=1e-6, atol=1e-6)
    assert np.allclose(g["volga"], (vs(SIG + 1e-4) - 2 * vs(SIG) + vs(SIG - 1e-4)) / 1e-8, rtol=1e-3, atol=1e-3)
    dlt = lambda s: bs.greeks(S, F, K, D, s, TAU, CP)["delta"]
    assert np.allclose(g["vanna"], _fd(dlt, SIG, 1e-6), rtol=1e-5, atol=1e-7)
    # decay at fixed F and D: dV/dt = -dV/dtau
    assert np.allclose(g["theta_F"], -_fd(lambda t: bs.price(F, K, D, SIG, t, CP), TAU, 1e-6), rtol=1e-5, atol=1e-5)
    assert np.allclose(g["dV_dF"], _fd(lambda f: bs.price(f, K, D, SIG, TAU, CP), F, 1e-6 * F), rtol=1e-6, atol=1e-8)
    assert np.allclose(g["price"] / D, _fd(lambda d: bs.price(F, K, d, SIG, TAU, CP), D, 1e-6), rtol=1e-6, atol=1e-6)


needs_lecture = pytest.mark.skipif(not lecture12_path().exists(), reason="Lecture 12 clone absent (set ERDOS_LECTURE12)")


@needs_lecture
def test_agrees_with_lecture_library():
    from erdos_quant_finance_project.lecture import option_pricing
    op = option_pricing()
    r, q = bs.carry(S, F, D, TAU)
    g = bs.greeks(S, F, K, D, SIG, TAU, CP)
    for sign, option in ((1, "call"), (-1, "put")):
        m = CP == sign
        ref = op.bs_euro_greeks(S[m], K[m], SIG[m], TAU[m], r[m], q[m], option=option)
        assert np.allclose(g["price"][m], ref["price"], rtol=1e-10, atol=1e-8)
        assert np.allclose(g["delta"][m], ref["delta"], rtol=1e-10, atol=1e-12)
        assert np.allclose(g["gamma"][m], ref["gamma"], rtol=1e-10, atol=1e-14)
        assert np.allclose(g["vega"][m], ref["vega"], rtol=1e-10, atol=1e-8)
        theta = bs.theta_spot(S, F, D, TAU, g)[m]
        assert np.allclose(theta, ref["theta"], rtol=1e-9, atol=1e-8)


@needs_lecture
def test_implied_vol_round_trip_and_bounds():
    sig = RNG.uniform(0.01, 3.0, N)
    p = bs.price(F, K, D, sig, TAU, CP)
    # with less time value than this, the price carries no volatility information at double precision
    ok = p - np.maximum(CP * D * (F - K), 0) > 1e-6 * S
    iv, status = bs.implied_vol(p[ok], S[ok], F[ok], K[ok], D[ok], TAU[ok], CP[ok])
    assert (status == "converged").all()
    assert np.allclose(iv, sig[ok], rtol=1e-5)
    # a call worth less than its discounted intrinsic value has no implied volatility
    k = 0.8 * F[:5]
    iv, status = bs.implied_vol(0.5 * D[:5] * (F[:5] - k), S[:5], F[:5], k, D[:5], TAU[:5], 1)
    assert np.isnan(iv).all() and (status == "outside_price_bounds").all()
