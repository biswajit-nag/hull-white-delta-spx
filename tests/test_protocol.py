"""Protocol checks: look-ahead by perturbation, Gains and Holm, R8's baseline, the attribution remainder,
the adversarial endpoint scenario, and the verdict table (plan §8–§11)."""

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

from erdos_quant_finance_project import blackscholes as bs
from erdos_quant_finance_project import diagnostics as dg
from erdos_quant_finance_project import endpoints as ep
from erdos_quant_finance_project import hedging as h
from erdos_quant_finance_project import learners as L
from erdos_quant_finance_project.verdict import verdict

from test_hedging import toy_pairs


def test_outcomes_after_the_boundary_never_reach_a_fit():
    p = toy_pairs(n_days=420, noise=1.0)
    s0 = p.quote_date[p.quote_date.dt.to_period("M") == "2019-06"].min()
    base = h.walk_forward(h.ingredients(p), p, ["2019-06"], h.Window(12, min_sessions=50), rules=["R2", "R4"])[1]
    q = p.copy()
    late = q.next_session >= s0  # every pair whose day two is on or after the first test session
    q.loc[late, ["bid_next", "ask_next"]] += 25.0
    q.loc[late, "S_close_next"] *= 1.07
    pert = h.walk_forward(h.ingredients(q), q, ["2019-06"], h.Window(12, min_sessions=50), rules=["R2", "R4"])[1]
    for a, b in zip(base.coef, pert.coef):
        assert np.allclose(a, b)


def test_gain_table_matches_a_manual_computation():
    sessions = pd.bdate_range("2020-01-02", periods=30)
    idx = pd.MultiIndex.from_product([sessions, ["C", "P"]], names=["session", "cp"])
    rng = np.random.default_rng(5)
    sse = pd.DataFrame({"R1": rng.uniform(1, 2, len(idx)), "R2": rng.uniform(0.5, 1.5, len(idx)), "n": 3}, index=idx)
    counts = h.bootstrap_counts(sessions, B=200, block=5, seed=1)
    g = h.gain_table(sse, [("R2", "R1")], counts).set_index("cp")
    s = sse.xs("C", level="cp")
    assert np.isclose(g.loc["C", "gain"], 1 - s.R2.sum() / s.R1.sum())
    rep = 1 - (counts @ s.R2.to_numpy()) / (counts @ s.R1.to_numpy())
    assert np.isclose(g.loc["C", "lo"], np.quantile(rep, 0.025))
    assert np.isclose(g.loc["C", "p_plus"], (1 + (rep <= 0).sum()) / 201)


def test_holm_matches_statsmodels():
    p = np.array([0.003, 0.04, 0.012, 0.3])
    assert np.allclose(h.holm(p), multipletests(p, method="holm")[1])


def test_r8_with_no_correction_is_r2():
    p = toy_pairs(n_days=60, noise=1.0)
    d = h.ingredients(p).query("cp == 'C'")
    beta = h.ols(*h.design("R2", d))

    class Zero:
        def predict(self, X, raw_score=True):
            return np.zeros(len(X))

    z = pd.DataFrame({"a": np.ones(len(d))}, index=d.index)
    e8 = L.boost_error((Zero(), beta), d, z)
    e2 = (d.y - h.design("R2", d)[0] @ beta).to_numpy()
    assert np.allclose(e8, e2)


def _bs_pairs(dS_frac):
    """Synthetic Black–Scholes pairs in which only S moves (F as F·S′/S; D, σ, τ fixed)."""
    S, K, sig, tau, D = 3000.0, np.array([2800.0, 3000.0, 3200.0]), 0.2, 60 / 365, 0.996
    F = S * 1.001
    S2, F2 = S * (1 + dS_frac), F * (1 + dS_frac)
    g = bs.greeks(S, F, K, D, sig, tau, 1.0)
    p = pd.DataFrame({"S_close": S, "S_close_next": S2, "mid": g["price"], "mid_next": bs.price(F2, K, D, sig, tau, 1.0),
                      "iv": sig, "iv_next": sig, "iv_status_next": "converged", "D": D, "D_next": D, "F": F, "F_next": F2,
                      "quote_date": pd.Timestamp("2020-01-02"), "next_session": pd.Timestamp("2020-01-02"),
                      **{k: g[k] for k in ("delta", "vega", "gamma", "vanna", "volga", "theta_F", "dV_dF")}})
    fr = pd.DataFrame({"cp": "C", "delta": g["delta"], "tau": tau}, index=p.index)
    return p, fr


def test_attribution_remainder_is_third_order_when_only_S_moves():
    r = []
    for x in (0.02, 0.01):
        p, fr = _bs_pairs(x)
        t = dg.attribution(fr, p)
        assert np.allclose(t[["vega", "vanna", "volga", "theta", "carry"]], 0, atol=1e-12)
        r.append(np.abs(t.remainder.to_numpy()))
    assert (r[1] < r[0] / 6).all()  # halving ΔS cuts a third-order remainder by about 8


def test_adversarial_scenario_is_the_worst_end_per_pair():
    # e_R2² − e_X² is affine in v with slope 2(H_X − H_R2)/S²: the worst end is the upper one when H_X > H_R2
    v1, S, dS = 10.0, 3000.0, 30.0
    lo, hi = np.array([8.0, 8.0]), np.array([12.0, 12.0])
    H2, HX = np.array([5.0, 5.0]), np.array([7.0, 3.0])
    worst = np.where(HX - H2 > 0, hi, lo)
    diff = lambda v: ((v - v1 - H2) ** 2 - (v - v1 - HX) ** 2) / S**2
    for alt in (lo, hi):
        assert (diff(worst) >= diff(alt) - 1e-15).all()


def test_band_imputation_order():
    v = pd.DataFrame({"cp": ["C", "C"], "D_next": [0.99, 0.99], "F_next": [3000.0, 3000.0], "strike": [2500.0, 2990.0],
                      "ask_next": [400.0, 30.0], "o_bid": [1.0, 40.0], "o_ask": [1.2, 41.0]})
    b = ep.band(v)
    assert b.band_kind.iloc[0] == "imputed: ask below floor"  # ask 400 < floor 0.99·500 = 495
    assert b.band_kind.iloc[1] == "imputed: crossed parity band" and b.band_lo.iloc[1] == b.band_hi.iloc[1]


def _gains(gc, gp, lo_c, lo_p, hi_c=0.4, hi_p=0.4, r4="beats"):
    rows = [{"cp": cp, "rule": "R2", "base": "R1", "gain": g, "lo": lo, "hi": hi, "p_plus": 0.001, "p_minus": 0.999}
            for cp, g, lo, hi in (("C", gc, lo_c, hi_c), ("P", gp, lo_p, hi_p))]
    for cp in "CP":
        for base in ("R3", "R4"):
            pp = 0.001 if (base == "R4" and r4 == "beats") else 0.3
            rows.append({"cp": cp, "rule": "R2", "base": base, "gain": 0.05, "lo": -0.01, "hi": 0.1, "p_plus": pp, "p_minus": 0.5})
    return pd.DataFrame(rows)


def test_verdict_rows():
    assert verdict(_gains(0.2, 0.15, 0.1, 0.05))["verdict"] == "Approve"
    assert verdict(_gains(0.2, 0.15, 0.1, 0.05, r4="nd"))["verdict"] == "Approve with conditions"
    assert verdict(_gains(0.02, 0.01, -0.01, -0.02, hi_c=0.04, hi_p=0.03))["verdict"] == "Reject (b)"
    assert verdict(_gains(0.2, -0.1, 0.1, -0.2, hi_p=-0.01))["verdict"] == "Reject (a)"
    assert verdict(_gains(0.2, 0.03, 0.1, 0.01))["verdict"] == "Inconclusive"
