"""Hedge rules, their chronological fits, and the session-block bootstrap (analysis_plan.md §6–§9).

Everything is on Hull and White's normalized scale (S_t = 1 on day one). For a pair,
  f = Δf/S_t,  u = δ·ΔS/S_t,  y = f − u,  x = (ν/S_t)·(ΔS/S_t)/√τ,
and a rule with hedge ratio h has error e = f − h·ΔS/S_t. Fitted rules are ordinary least squares
with no intercept, fitted separately for calls and puts on pairs whose day two precedes the first
test session.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

PAIRS_ROOT = Path(__file__).resolve().parents[2] / "data/processed/pairs"
STRESS = (pd.Timestamp("2020-02-24"), pd.Timestamp("2020-04-30"))
# No step before the 2020 unblinding may use an outcome observed on or after this session (plan §10):
# the pairs that start on 2019-12-31 end here, so the rehearsal and the tuning drop them.
UNBLIND = pd.Timestamp("2020-01-02")
FIXED = {"C": 0.9, "P": 1.1}  # Ruf and Wang's fixed scaling, R3


def load_pairs(years, columns=None, analysis_only=True, underlying="spx", root=PAIRS_ROOT) -> pd.DataFrame:
    frames = []
    for y in years:
        p = pd.read_parquet(root / f"underlying={underlying}" / f"year={y}" / f"pairs_{y}.parquet", columns=columns)
        if analysis_only:
            p = p[p.E7 & (p.next_status == "ok")]
        frames.append(p)
    return pd.concat(frames, ignore_index=True)


# --- the hedging-error ingredients under each measurement variant -------------------------------

MARKS = {
    "mid": lambda b, a, qb, qa: (b + a) / 2,
    "bid": lambda b, a, qb, qa: b,
    "ask": lambda b, a, qb, qa: a,
    # imbalance-weighted mid: leans to the ask when more contracts are bid
    "wm": lambda b, a, qb, qa: (b * qa + a * qb) / (qb + qa),
    # Lecture 12's size-weighted price: leans to the deeper side
    "sw": lambda b, a, qb, qa: (b * qb + a * qa) / (qb + qa),
}
LEVELS = {"close": ("S_close", "S_close_next"), "A": ("S_A", "S_A_next"), "B": ("S", "S_next")}


def ingredients(p: pd.DataFrame, level="close", mark="mid", theta=False) -> pd.DataFrame:
    """f, u, y, x and the rule inputs for each pair, with `avail` marking pairs the variant can use."""
    s1n, s2n = LEVELS[level]
    S1, S2 = p[s1n].to_numpy(float), p[s2n].to_numpy(float)
    m = MARKS[mark]
    v1 = m(p.bid.to_numpy(float), p.ask.to_numpy(float), p.bid_size.to_numpy(float), p.ask_size.to_numpy(float))
    v2 = m(p.bid_next.to_numpy(float), p.ask_next.to_numpy(float), p.bid_size_next.to_numpy(float), p.ask_size_next.to_numpy(float))
    df = v2 - v1
    if theta:
        df = df - p.theta.to_numpy(float) / 365  # one day of the lectures' theta (Hull and White's check)
    dS = S2 - S1
    if "div_next" in p:  # SPY: the share position receives the distribution when day two is an ex-date
        dS = dS + p.div_next.fillna(0).to_numpy(float)
    # δ under this index level: D·N(d1)·F/S, so only the F/S factor changes
    delta = p.dV_dF.to_numpy(float) * p.F.to_numpy(float) / S1
    scale = p.S_close.to_numpy(float) / S1
    out = pd.DataFrame({
        "cp": p.cp.to_numpy(), "session": p.quote_date.to_numpy(), "delta": delta,
        "f": df / S1, "dSn": dS / S1,
        "vega_n": p.vega.to_numpy(float) / S1, "vanna": p.vanna.to_numpy(float) * scale,
        "sqrt_tau": np.sqrt(p.tau.to_numpy(float)), "tau": p.tau.to_numpy(float),
        "theta_day": p.theta.to_numpy(float) / 365 / S1,
    }, index=p.index)
    out["u"] = out.delta * out.dSn
    out["y"] = out.f - out.u
    out["x"] = out.vega_n * out.dSn / out.sqrt_tau
    ok = np.isfinite(out[["f", "u", "x"]].to_numpy()).all(axis=1)
    if mark in ("wm", "sw"):
        ok &= (p.bid_size.to_numpy() > 0) & (p.ask_size.to_numpy() > 0)
        ok &= (p.bid_size_next.fillna(0).to_numpy() > 0) & (p.ask_size_next.fillna(0).to_numpy() > 0)
    out["avail"] = ok
    return out


# --- rules -------------------------------------------------------------------------------------

def poly(delta, deg=2):
    return np.column_stack([delta**k for k in range(deg + 1)])


def legendre_basis(delta, deg):
    """Legendre polynomials in |δ| mapped from [0.05, 0.95] to [−1, 1] (the specification check)."""
    t = (np.abs(delta) - 0.5) / 0.45
    return np.polynomial.legendre.legvander(t, deg)


def design(rule: str, d: pd.DataFrame, **kw) -> tuple[np.ndarray, np.ndarray]:
    """(regressors, target) for a fitted rule, so that the rule's error is target − regressors·β."""
    if rule == "R2":
        return d.x.to_numpy()[:, None] * poly(d.delta.to_numpy()), d.y.to_numpy()
    if rule == "R4":
        return d.u.to_numpy()[:, None], d.f.to_numpy()
    if rule == "R5":
        return np.column_stack([d.u, d.x.to_numpy()[:, None] * poly(d.delta.to_numpy())]), d.f.to_numpy()
    if rule == "R6":
        return np.column_stack([d.u, d.vega_n * d.dSn, d.vanna * d.dSn]), d.f.to_numpy()
    if rule == "deg":  # specification check 1
        return d.x.to_numpy()[:, None] * legendre_basis(d.delta.to_numpy(), kw["deg"]), d.y.to_numpy()
    if rule == "alpha":  # specification check 2: τ^(−α) in place of τ^(−1/2)
        xa = d.vega_n * d.dSn * d.tau ** (-kw["alpha"])
        return xa.to_numpy()[:, None] * poly(d.delta.to_numpy()), d.y.to_numpy()
    raise ValueError(rule)


FITTED = ["R2", "R4", "R5", "R6"]
REQUIRED = ["R2", "R4"]


def design_for(rule: str, d: pd.DataFrame):
    """design() for a rule name, where "deg:3" and "alpha:0.25" name the specification-check variants."""
    if ":" not in rule:
        return design(rule, d)
    name, arg = rule.split(":", 1)
    return design(name, d, **({"deg": int(arg)} if name == "deg" else {"alpha": float(arg)}))


def ols(X: np.ndarray, y: np.ndarray) -> np.ndarray | None:
    if len(y) == 0 or np.linalg.matrix_rank(X.T @ X) < X.shape[1]:
        return None
    return np.linalg.solve(X.T @ X, X.T @ y)


def errors(d: pd.DataFrame, coefs: dict[str, np.ndarray | None]) -> pd.DataFrame:
    """Each rule's normalized error on the pairs in d (one option type), given fitted coefficients."""
    cp = d.cp.iloc[0]
    e = {"R0": d.f.to_numpy(), "R1": d.y.to_numpy(), "R3": (d.f - FIXED[cp] * d.u).to_numpy()}
    for rule, beta in coefs.items():
        X, t = design_for(rule, d)
        e[rule] = t - X @ beta if beta is not None else np.full(len(d), np.nan)
    return pd.DataFrame(e, index=d.index)


# --- the chronological protocol -----------------------------------------------------------------

@dataclass
class Window:
    months: int        # trailing window length
    min_sessions: int = 150


def month_starts(test_months: pd.PeriodIndex, sessions: pd.DatetimeIndex) -> dict:
    """First session of each test month."""
    return {m: sessions[sessions.to_period("M") == m].min() for m in test_months}


def training_mask(day1: pd.Series, day2: pd.Series, s0: pd.Timestamp, months: int, frozen: pd.Timestamp | None = None) -> pd.Series:
    """Pairs that may train the fit for a test month starting on session s0: day one in the `months`
    calendar months before s0's month and day two strictly before s0. With `frozen`, the one fit on
    pairs whose day two precedes that date (sensitivity F)."""
    if frozen is not None:
        return (day2 < frozen) & (day1 >= frozen - pd.DateOffset(months=months))
    lo = (s0.to_period("M") - months).to_timestamp()
    return (day1 >= lo) & (day1 < s0) & (day2 < s0)


def walk_forward(frame: pd.DataFrame, p: pd.DataFrame, test_months, window: Window, rules=FITTED,
                 frozen: pd.Timestamp | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Monthly refits on a trailing window; returns test-pair errors for every rule, and the coefficients.

    frame: ingredients(); p: the pairs (for quote_date and next_session). A training pair has day one in
    the W months before the test month's first session and day two strictly before it. With `frozen`,
    a single fit on pairs with day two before that date is used for every month (sensitivity F).
    """
    day1, day2 = p.quote_date, p.next_session
    sessions = pd.DatetimeIndex(np.sort(day1.unique()))
    starts = month_starts(pd.PeriodIndex(test_months, freq="M"), sessions)
    errs, coef_rows = [], []
    for m, s0 in starts.items():
        if pd.isna(s0):
            continue
        test = frame.avail & (day1.dt.to_period("M") == m)
        train = frame.avail & training_mask(day1, day2, s0, window.months, frozen)
        assert (day2[train] < (s0 if frozen is None else frozen)).all(), "look-ahead: a training pair ends in the test period"
        for cp in ("C", "P"):
            tr = frame[train & (frame.cp == cp)]
            te = frame[test & (frame.cp == cp)]
            if te.empty:
                continue
            ok = tr.session.nunique() >= window.min_sessions
            coefs = {r: ols(*design_for(r, tr)) if ok else None for r in rules}
            # only a failed R2 or R4 drops the month for every rule of this type (common sample);
            # a failed R5–R6 or check variant leaves just that rule missing
            if not ok or any(coefs.get(r) is None for r in REQUIRED if r in coefs):
                continue
            e = errors(te, coefs)
            e["month"] = str(m)
            errs.append(e)
            for r, b in coefs.items():
                coef_rows.append({"month": str(m), "cp": cp, "rule": r, "coef": None if b is None else b.tolist(),
                                  "train_pairs": len(tr), "train_sessions": tr.session.nunique()})
    return pd.concat(errs) if errs else pd.DataFrame(), pd.DataFrame(coef_rows)


# --- aggregation and the bootstrap --------------------------------------------------------------

def session_sse(err: pd.DataFrame, frame: pd.DataFrame, rules: list[str]) -> pd.DataFrame:
    """Per session × type: the sum of squared errors of each rule and the pair count."""
    e = err[rules].pow(2)
    e["cp"] = frame.loc[err.index, "cp"].to_numpy()
    e["session"] = frame.loc[err.index, "session"].to_numpy()
    e["n"] = 1
    return e.groupby(["session", "cp"]).sum()


def circular_block_counts(n: int, B: int, block: int, rng: np.random.Generator) -> np.ndarray:
    """B × n matrix of how often each of n sessions is drawn in a circular block bootstrap."""
    k = int(np.ceil(n / block))
    starts = rng.integers(0, n, size=(B, k))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(B, -1)[:, :n] % n
    counts = np.zeros((B, n), dtype=np.int32)
    np.add.at(counts, (np.repeat(np.arange(B), n), idx.ravel()), 1)
    return counts


def bootstrap_counts(sessions: pd.DatetimeIndex, B=10_000, block=10, seed=2026, strata=None) -> np.ndarray:
    """Session draw counts; with strata (a list of (start, end)), each stratum is resampled within itself."""
    rng = np.random.default_rng(seed)
    n = len(sessions)
    if strata is None:
        return circular_block_counts(n, B, block, rng)
    counts = np.zeros((B, n), dtype=np.int32)
    for lo, hi in strata:
        m = np.flatnonzero((sessions >= lo) & (sessions <= hi))
        if len(m):
            counts[:, m] = circular_block_counts(len(m), B, block, rng)
    return counts


def gain_table(sse: pd.DataFrame, comparisons: list[tuple[str, str]], counts: np.ndarray) -> pd.DataFrame:
    """Relative Gains 1 − SSE_rule/SSE_base per option type, with percentile intervals and p-values.

    sse: per (session, cp) sums from session_sse(), every session of the bootstrap index present;
    counts: B × sessions draw counts from bootstrap_counts() on that index. p₊ is the share of
    replicates ≤ 0 (for "rule beats base"), p₋ the share ≥ 0 ("rule is worse"), each (1 + #)/(B + 1).
    """
    rows = []
    for cp in ("C", "P"):
        s = sse.xs(cp, level="cp")
        for rule, base in comparisons:
            num, den = s[rule].to_numpy(), s[base].to_numpy()
            g = 1 - num.sum() / den.sum()
            rep = 1 - (counts @ num) / (counts @ den)
            B = len(rep)
            rows.append({"cp": cp, "rule": rule, "base": base, "gain": g,
                         "lo": np.quantile(rep, 0.025), "hi": np.quantile(rep, 0.975),
                         "p_plus": (1 + (rep <= 0).sum()) / (B + 1), "p_minus": (1 + (rep >= 0).sum()) / (B + 1),
                         "pairs": int(s.n.sum())})
    return pd.DataFrame(rows)


def holm(p: np.ndarray) -> np.ndarray:
    """Holm-adjusted p-values (step-down, monotone)."""
    p = np.asarray(p, float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    run = 0.0
    for k, i in enumerate(order):
        run = max(run, (m - k) * p[i])
        adj[i] = min(1.0, run)
    return adj


def aligned_sse(err: pd.DataFrame, frame: pd.DataFrame, rules: list[str], index: pd.DatetimeIndex) -> pd.DataFrame:
    """session_sse() reindexed to a fixed session index, with zeros where a session has no pairs."""
    s = session_sse(err, frame, rules)
    full = pd.MultiIndex.from_product([index, ["C", "P"]], names=["session", "cp"])
    return s.reindex(full, fill_value=0)
