"""The three-stage parity fit recovers a known D and F from noisy synthetic quotes (plan §11, item 4)."""

import numpy as np
import pandas as pd

from erdos_quant_finance_project import blackscholes as bs
from erdos_quant_finance_project import parity

RNG = np.random.default_rng(1)
S0, RATE, YIELD = 3000.0, 0.02, 0.018


def synthetic_session(day, expiries_days, half_spread=0.3, sigma=0.2):
    rows = []
    for days in expiries_days:
        tau = days / 365
        D, F = np.exp(-RATE * tau), S0 * np.exp((RATE - YIELD) * tau)
        # a 14-day expiry with few strikes near the money; shorter ones on a 5-point grid; longer ones wide
        K = (np.arange(2700, 3301, 25.0) if days > 14 else np.array([2950, 2975, 3000, 3025, 3050.0]) if days == 14
             else np.arange(2950, 3051, 5.0))
        for cp, name in ((1, "C"), (-1, "P")):
            mid = bs.price(F, K, D, sigma, tau, cp) + RNG.normal(0, half_spread / 3, K.size)
            rows.append(pd.DataFrame({"quote_date": pd.Timestamp(day), "am_settled": False,
                                      "settle_date": pd.Timestamp(day) + pd.Timedelta(days=days), "strike": K,
                                      "cp": name, "bid": mid - half_spread, "ask": mid + half_spread, "mid": mid,
                                      "S_close": S0, "tau": tau}))
    return pd.concat(rows, ignore_index=True)


def test_recovers_discount_and_forward():
    w = parity.strike_table(synthetic_session("2020-01-02", [14, 30, 60, 91, 182, 365, 730]))
    curve = parity.stage2(parity.stage1(w))
    assert curve.iloc[0].form == "linear" and curve.iloc[0].basis == "long"
    fwd = parity.stage3(w, curve)
    D_true = np.exp(-RATE * fwd.tau)
    F_true = S0 * np.exp((RATE - YIELD) * fwd.tau)
    assert np.allclose(fwd.D, D_true, rtol=2e-3)
    # the 14-day expiry, with five strikes, gets its forward from the curve's D
    assert (fwd.n >= 3).all() and len(fwd) == 7
    assert np.allclose(fwd.F, F_true, rtol=2e-4)


def test_level_A_reads_a_short_expiry():
    w = parity.strike_table(synthetic_session("2020-01-02", [1, 3, 30]))
    A = parity.level_A(w)
    assert A.A_tier.iloc[0] == 1 and np.isclose(A.A_days.iloc[0], 1)
    assert abs(A.S_A.iloc[0] / (S0 * np.exp((RATE - YIELD) / 365)) - 1) < 2e-4
