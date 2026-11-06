"""The rules scored from analysis_plan.md §16.11 on: R0–R4, R6, R9, P0, and Heston's three on SPX.

Monthly refits on a trailing window under §7's boundary rule, as hedging.walk_forward, with two additions
for §16.13: a minimum training coverage per window, and thinning of each training session's pairs. Every
fitted object is kept per (month, type), so that §16.11 can apply a month's fits to the later days of a
held position.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import hedging as h
from . import learners as L
from .processed import CONTRACT_KEY

ROOT = Path(__file__).resolve().parents[2]
BASE = ["R0", "R1", "R2", "R3", "R4", "R6", "R9", "P0"]
HESTON = ["H_model", "H_mv", "H_fit"]
OLS_RULES = ["R2", "R4", "R6", "P0"]
HKEY = ["quote_date"] + CONTRACT_KEY


def rules_for(underlying: str) -> list[str]:
    return BASE + (HESTON if underlying == "spx" else [])


def design(rule: str, d: pd.DataFrame):
    if rule == "P0":  # the constant correction δ + c·ν/(S√τ) (§16.8)
        return d.x.to_numpy()[:, None], d.y.to_numpy()
    return h.design(rule, d)


def r9_params(underlying: str, tag: str | None = None):
    """R9's frozen hyperparameters by test month (§16.7): the 2010 set to 2016-12 and the 2015–2016 set after, or one
    named set (`tag`, e.g. "2019" for the 2020 test year, as in §16.7). The five of §16.15 use SPX's sets."""
    sub = "spy/rehearsal" if underlying == "spy" else "rehearsal"
    if tag is not None:
        one = json.loads((ROOT / "results" / sub / f"r9_params_{tag}.json").read_text())
        return lambda m: one
    early = json.loads((ROOT / "results" / sub / "r9_params_2010.json").read_text())
    late = json.loads((ROOT / "results" / sub / "r9_params_2015_2016.json").read_text())
    if underlying not in ("spx", "spy"):
        return lambda m: late
    return lambda m: early if m <= pd.Period("2016-12", "M") else late


# --- Heston (SPX only; §16.5) -----------------------------------------------------------------------

def heston_inputs(P: pd.DataFrame, fr: pd.DataFrame, years) -> pd.DataFrame:
    """yH = f − C_S·ΔS/S, xH = (C_v/S)·ΔS/S, rx = ρξ of the session, and `have`, aligned to P's index."""
    cache = ROOT / "data/processed/heston2"
    G = pd.concat([pd.read_parquet(cache / f"greeks_{y}.parquet") for y in years if (cache / f"greeks_{y}.parquet").exists()],
                  ignore_index=True)
    keys = P[HKEY].reset_index()
    for d in (keys, G):  # the same datetime resolution on both sides of the join
        d["quote_date"] = pd.to_datetime(d.quote_date).astype("datetime64[ns]")
        d["settle_date"] = pd.to_datetime(d.settle_date).astype("datetime64[ns]")
        d["cp"] = d.cp.astype(str)
    j = keys.merge(G.drop_duplicates(HKEY), on=HKEY, how="left").set_index("index").reindex(P.index)
    prm = []
    for y in years:
        f = ROOT / "results/heston2" / f"params_{y}.csv"
        if f.exists():
            p = pd.read_csv(f, parse_dates=["session"])
            prm.append(p[p.ok.fillna(False).astype(bool)].set_index("session"))
    prm = pd.concat(prm)
    rx = pd.to_datetime(P.quote_date).map(prm.rho * prm.xi)
    S1 = P.S_close.to_numpy(float)
    yH = fr.f - j.h_delta * fr.dSn
    xH = j.h_cv / S1 * fr.dSn
    have = j.h_delta.notna() & j.h_cv.notna() & rx.notna() & np.isfinite(xH) & np.isfinite(yH)
    return pd.DataFrame({"yH": yH, "xH": xH, "rx": rx, "have": have}, index=P.index)


# --- fitting and errors -------------------------------------------------------------------------------

def fit(tr: pd.DataFrame, Htr: pd.DataFrame | None, prm9: dict) -> dict | None:
    """Every fitted rule on one type's training pairs; None when R2 or R4 cannot be fitted."""
    out = {r: h.ols(*design(r, tr)) for r in OLS_RULES}
    if out["R2"] is None or out["R4"] is None:
        return None
    out["R9"] = L.fit_direct(tr, tr[["delta"]], prm9) if len(tr) else None
    if Htr is not None:
        den = float((Htr.xH**2).sum())
        out["H_fit"] = float((Htr.xH * Htr.yH).sum()) / den if den > 0 else np.nan
    return out


def errors(fits: dict, d: pd.DataFrame, Hd: pd.DataFrame | None, cp: str) -> pd.DataFrame:
    """Each rule's normalized error on the pairs in d (one type), given that month's fits."""
    e = {"R0": d.f.to_numpy(), "R1": d.y.to_numpy(), "R3": (d.f - h.FIXED[cp] * d.u).to_numpy()}
    for r in OLS_RULES:
        X, t = design(r, d)
        b = fits.get(r)
        e[r] = t - X @ b if b is not None else np.full(len(d), np.nan)
    e["R9"] = L.direct_error(fits["R9"], d, d[["delta"]]) if fits.get("R9") is not None else np.full(len(d), np.nan)
    if Hd is not None:
        yH, xH = Hd.yH.to_numpy(float), Hd.xH.to_numpy(float)
        e["H_model"] = yH
        e["H_mv"] = yH - Hd.rx.to_numpy(float) * xH
        e["H_fit"] = yH - fits["H_fit"] * xH
    return pd.DataFrame(e, index=d.index)


def thin_mask(sessions: pd.Series, mode: tuple, rng: np.random.Generator) -> np.ndarray:
    """Keep a fraction (("frac", φ), at least one) or a fixed number (("k", k)) of each session's pairs, at random."""
    n = len(sessions)
    order = rng.permutation(n)
    s = sessions.to_numpy()[order]
    rank = pd.Series(s).groupby(s).cumcount().to_numpy()
    size = pd.Series(s).map(pd.Series(s).value_counts()).to_numpy()
    cap = np.maximum(1, np.ceil(mode[1] * size)) if mode[0] == "frac" else np.full(n, mode[1])
    keep = np.zeros(n, bool)
    keep[order] = rank < cap
    return keep


def walk(fr: pd.DataFrame, P: pd.DataFrame, months, W: int, prm9, H: pd.DataFrame | None = None,
         min_sessions: int = 150, thin: tuple | None = None, seed: int | None = None, keep_fits: bool = False,
         frozen: pd.Timestamp | None = None):
    """Monthly refits on the W months before each test month (§7); errors on the test pairs, and the fits.
    With `frozen`, one fit on the W months of pairs whose day two precedes that date, for every month (sensitivity F)."""
    day1, day2 = P.quote_date, P.next_session
    sessions = pd.DatetimeIndex(np.sort(day1.unique()))
    starts = h.month_starts(pd.PeriodIndex(months, freq="M"), sessions)
    month = day1.dt.to_period("M")
    base = fr.avail if H is None else fr.avail & H.have
    rng = np.random.default_rng(seed)
    errs, fits = [], {}
    for m, s0 in starts.items():
        if pd.isna(s0):
            continue
        train = base & h.training_mask(day1, day2, s0, W, frozen)
        assert (day2[train] < (s0 if frozen is None else frozen)).all(), "look-ahead: a training pair ends in the test period"
        test = base & (month == m)
        for cp in ("C", "P"):
            tr_m, te_m = train & (fr.cp == cp), test & (fr.cp == cp)
            if not te_m.any() or fr.session[tr_m].nunique() < min_sessions:
                continue
            idx = fr.index[tr_m]
            if thin is not None:
                idx = idx[thin_mask(fr.session[idx], thin, rng)]
            f = fit(fr.loc[idx], None if H is None else H.loc[idx], prm9(m)[cp])
            if f is None:
                continue
            e = errors(f, fr[te_m], None if H is None else H[te_m], cp)
            e["month"] = str(m)
            errs.append(e)
            if keep_fits:
                fits[(str(m), cp)] = f
    return (pd.concat(errs) if errs else pd.DataFrame()), fits


# --- Gains from per-session sums ---------------------------------------------------------------------

def session_gains(S: pd.DataFrame, comps: list[tuple[str, str]], counts: np.ndarray) -> pd.DataFrame:
    """Gains 1 − ΣS[rule]/ΣS[base] with percentile intervals, from per-session sums S (rows = the bootstrap index)."""
    rows = []
    B = counts.shape[0]
    for rule, base in comps:
        if rule not in S or base not in S:
            continue
        num, den = S[rule].to_numpy(float), S[base].to_numpy(float)
        g = 1 - num.sum() / den.sum()
        rep = 1 - (counts @ num) / (counts @ den)
        rows.append({"rule": rule, "base": base, "gain": g, "lo": np.quantile(rep, 0.025), "hi": np.quantile(rep, 0.975),
                     "p_plus": (1 + (rep <= 0).sum()) / (B + 1), "p_minus": (1 + (rep >= 0).sum()) / (B + 1)})
    return pd.DataFrame(rows)


def comparisons(rules: list[str]) -> list[tuple[str, str]]:
    return [("R1", "R0")] + [(r, "R1") for r in rules if r not in ("R0", "R1")] + [(r, "R2") for r in rules if r not in ("R0", "R1", "R2")]
