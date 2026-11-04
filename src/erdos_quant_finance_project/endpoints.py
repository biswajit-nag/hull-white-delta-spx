"""Endpoint scenarios for pairs whose day-two bid vanished (analysis_plan.md §5).

Each vanished pair gets a day-two band from parity with the other leg at the same strike, else from
the no-arbitrage floor and the ask; two imputations are labelled. The scenarios then set the day-two
value at the band's low end, its high end, or, per comparison, the end that is worst for R2.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

from . import hedging as h

PANEL = Path(__file__).resolve().parents[2] / "data/processed/optionsdx_long/underlying=spx"


def vanished(year: int) -> pd.DataFrame:
    p = h.load_pairs([year], analysis_only=False)
    v = p[p.E7 & (p.next_status == "one_sided_next")].copy()
    sess = sorted(set(v.next_session.dt.date))
    other = []
    for y in sorted({d.year for d in sess}):
        t = ds.dataset(PANEL / f"year={y}").to_table(
            columns=["quote_date", "am_settled", "settle_date", "strike", "cp", "bid", "ask"],
            filter=ds.field("quote_date").isin(sess)).to_pandas()
        other.append(t)
    o = pd.concat(other)
    o["quote_date"], o["settle_date"], o["cp"] = pd.to_datetime(o.quote_date), pd.to_datetime(o.settle_date), o.cp.astype(str)
    o["cp"] = o.cp.map({"C": "P", "P": "C"})  # the other leg, keyed by this pair's type
    o = o.rename(columns={"quote_date": "next_session", "bid": "o_bid", "ask": "o_ask"})
    v = v.merge(o, on=["next_session", "am_settled", "settle_date", "strike", "cp"], how="left")
    v.index = pd.RangeIndex(10**9, 10**9 + len(v))  # keep clear of the analysis pairs' labels
    return band(v)


def band(v: pd.DataFrame) -> pd.DataFrame:
    sgn = np.where(v.cp == "C", 1.0, -1.0)
    D, F, K = v.D_next.to_numpy(float), v.F_next.to_numpy(float), v.strike.to_numpy(float)
    ask = v.ask_next.to_numpy(float)
    have_fd = np.isfinite(D) & np.isfinite(F)
    pv = sgn * D * (F - K)                      # D(F − K) for a call, D(K − F) for a put
    L = np.maximum(0.0, pv)
    o_two = (v.o_bid > 0).to_numpy() & (v.o_ask >= v.o_bid).to_numpy()
    lo = np.where(have_fd, L, 0.0)
    hi = ask.copy()
    kind = np.where(have_fd, "floor-ask", "zero-ask").astype(object)
    par = have_fd & o_two
    plo = np.maximum(L, v.o_bid.to_numpy(float) + pv)
    phi = np.minimum(ask, v.o_ask.to_numpy(float) + pv)
    lo = np.where(par, plo, lo)
    hi = np.where(par, phi, hi)
    kind = np.where(par, "parity", kind)
    # the two imputations, in the plan's order: an ask below the floor first, then a crossed parity band
    below = have_fd & (ask < L)
    crossed = par & ~below & (plo > phi)
    synth = np.clip((v.o_bid.to_numpy(float) + v.o_ask.to_numpy(float)) / 2 + pv, 0, ask)
    lo, hi = np.where(crossed, synth, lo), np.where(crossed, synth, hi)
    kind = np.where(crossed, "imputed: crossed parity band", kind)
    lo, hi = np.where(below, ask, lo), np.where(below, ask, hi)
    kind = np.where(below, "imputed: ask below floor", kind)
    return v.assign(band_lo=lo, band_hi=hi, band_kind=kind)


def errors_at(v: pd.DataFrame, value: np.ndarray, coefs: pd.DataFrame) -> pd.DataFrame:
    """Every rule's error for the vanished pairs with day-two value `value`, under the primary fits."""
    q = v.copy()
    q["bid_next"] = q["ask_next"] = value
    fr = h.ingredients(q)
    out = []
    for (m, cp), d in fr.groupby([q.quote_date.dt.to_period("M").astype(str), "cp"]):
        c = coefs[(coefs.month == m) & (coefs.cp == cp)]
        beta = {r.rule: np.array(r.coef) for r in c.itertuples() if r.coef is not None}
        if "R2" not in beta:
            continue
        e = h.errors(d, beta)
        e["month"] = m
        out.append(e)
    e = pd.concat(out)
    e.attrs["frame"] = fr.loc[e.index]
    return e


def scenario(v: pd.DataFrame, coefs: pd.DataFrame, which: str, comparator: str | None = None) -> pd.DataFrame:
    if which in ("low", "high"):
        return errors_at(v, v.band_lo.to_numpy() if which == "low" else v.band_hi.to_numpy(), coefs)
    # adversarial for R2 against `comparator`: upper end where H_X − H_R2 > 0, else lower
    e_lo = errors_at(v, v.band_lo.to_numpy(), coefs)
    fr = e_lo.attrs["frame"]
    # H_j·ΔS/S_t = f − e_j, so H_X − H_R2 has the sign of e_R2 − e_X at any common value
    worse_high = (e_lo["R2"] - e_lo[comparator]).to_numpy() > 0
    val = np.where(worse_high, v.loc[e_lo.index, "band_hi"], v.loc[e_lo.index, "band_lo"])
    vv = v.loc[e_lo.index]
    return errors_at(vv, val, coefs)
