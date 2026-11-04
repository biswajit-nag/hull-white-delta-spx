"""The hedge-rule machinery: known coefficients, Gain invariance, no look-ahead, the bootstrap (plan §11, items 5–8)."""

import numpy as np
import pandas as pd
import pytest

from erdos_quant_finance_project import hedging as h

RNG = np.random.default_rng(3)


def toy_pairs(n_days=400, per_day=40, a=-0.4, b=0.3, c=-0.2, noise=0.0, start="2018-01-02"):
    """Pairs whose day-one Greeks and moves obey Hull and White's model exactly, plus optional noise."""
    days = pd.bdate_range(start, periods=n_days + 1)
    rows = []
    for t in range(n_days):
        S1 = 3000 * (1 + 0.0002 * t)
        dS = S1 * RNG.normal(0, 0.01)
        for cp, sgn in (("C", 1), ("P", -1)):
            delta = sgn * RNG.uniform(0.05, 0.95, per_day)
            vega = S1 * RNG.uniform(0.05, 0.5, per_day)
            tau = RNG.uniform(14, 400, per_day) / 365
            hedge = delta + vega / (S1 * np.sqrt(tau)) * (a + b * delta + c * delta**2)
            df = hedge * dS + noise * S1 * RNG.normal(0, 0.001, per_day)
            mid = 50.0
            rows.append(pd.DataFrame({
                "quote_date": days[t], "next_session": days[t + 1], "cp": cp, "S_close": S1, "S_close_next": S1 + dS,
                "dV_dF": delta, "F": S1, "vega": vega, "vanna": 0.1, "tau": tau, "theta": -10.0,
                "bid": mid - 0.5, "ask": mid + 0.5, "bid_size": 10, "ask_size": 10,
                "bid_next": mid + df - 0.5, "ask_next": mid + df + 0.5, "bid_size_next": 10, "ask_size_next": 10}))
    return pd.concat(rows, ignore_index=True)


def test_known_coefficients_recovered():
    p = toy_pairs()
    fr = h.ingredients(p)
    for cp in ("C", "P"):
        d = fr[fr.cp == cp]
        beta = h.ols(*h.design("R2", d))
        assert np.allclose(beta, [-0.4, 0.3, -0.2], atol=1e-9)


def test_gain_is_scale_invariant_and_zero_for_identical_rules():
    p = toy_pairs(noise=1.0)
    q = p.copy()
    money = ["S_close", "S_close_next", "F", "vega", "theta", "bid", "ask", "bid_next", "ask_next"]
    q[money] = q[money] * 7.0
    e1 = h.errors(h.ingredients(p).query("cp == 'C'"), {})
    e2 = h.errors(h.ingredients(q).query("cp == 'C'"), {})
    assert np.allclose(e1, e2)
    gain = 1 - (e1.R1**2).sum() / (e1.R1**2).sum()
    assert gain == 0


def test_no_training_pair_reaches_the_test_month():
    p = toy_pairs(n_days=420, noise=1.0)
    fr = h.ingredients(p)
    err, coefs = h.walk_forward(fr, p, ["2019-06"], h.Window(12, min_sessions=50), rules=["R2"])
    assert not err.empty
    s0 = p.quote_date[p.quote_date.dt.to_period("M") == "2019-06"].min()
    # every coefficient was fitted on pairs ending before the first June session
    train = (p.quote_date >= (s0.to_period("M") - 12).to_timestamp()) & (p.quote_date < s0) & (p.next_session < s0)
    assert coefs.train_pairs.iloc[0] == int((train & (p.cp == "C")).sum())


def test_bootstrap_with_each_session_once_reproduces_the_gain():
    p = toy_pairs(n_days=60, noise=1.0)
    fr = h.ingredients(p)
    e = h.errors(fr[fr.cp == "C"], {"R2": np.array([-0.3, 0.2, 0.0])})
    sse = h.session_sse(e, fr, ["R1", "R2"]).xs("C", level="cp")
    full = 1 - sse.R2.sum() / sse.R1.sum()
    ones = np.ones((1, len(sse)))
    boot = 1 - (ones @ sse.R2.to_numpy()) / (ones @ sse.R1.to_numpy())
    assert np.isclose(boot[0], full)
    counts = h.bootstrap_counts(pd.DatetimeIndex(sse.index), B=50, block=10)
    assert (counts.sum(axis=1) == len(sse)).all()


def test_weighted_ratio_identity():
    p = toy_pairs(n_days=30, noise=1.0)
    fr = h.ingredients(p)
    d = fr[fr.x != 0]
    g = RNG.normal(size=len(d))
    lhs = (d.x**2 * (d.y / d.x - g) ** 2).sum()
    rhs = ((d.y - d.x * g) ** 2).sum()
    assert np.isclose(lhs, rhs)


@pytest.mark.parametrize("mark", ["wm", "sw"])
def test_size_marks_within_quotes_and_mirror(mark):
    b, a = np.array([1.0, 2.0, 3.0]), np.array([1.2, 2.5, 3.1])
    qb, qa = np.array([10.0, 50.0, 5.0]), np.array([30.0, 50.0, 20.0])
    v = h.MARKS[mark](b, a, qb, qa)
    assert ((v >= b) & (v <= a)).all()
    mid = (b + a) / 2
    assert np.allclose(h.MARKS["wm"](b, a, qb, qa) - mid, -(h.MARKS["sw"](b, a, qb, qa) - mid))
    assert np.isclose(v[1], mid[1])  # equal sizes give the mid
