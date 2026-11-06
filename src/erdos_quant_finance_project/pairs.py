"""Hedge pairs: a contract on day one joined to the same contract on the next NYSE session (plan §2, §5).

Each pair carries the day-one quotes, Greeks and eligibility flags E1–E8, the day-two quote, implied
volatility, forward and discount factor, both days' index levels (the close, the vendor's snapshot,
and sensitivity A's options-implied level), and the day-one features of rules R7 and R8.
No hedging error is computed here.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

from .processed import CONTRACT_KEY

ROW = ["quote_date", "expire_date", "strike", "cp"]
PANEL_COLS = ["quote_date", "expire_date", "strike", "cp", "am_settled", "settle_date", "S", "S_close", "bid", "ask",
              "bid_size", "ask_size", "last", "volume", "mid", "rel_spread", "next_session", "f_stamp_window",
              "f_post_settlement", "f_settle_uncertain", "f_stamp_not_session", "f_dup_key", "bid_next", "ask_next",
              "mid_next", "volume_next", "S_next", "S_close_next", "next_status"]
GREEK_COLS = ["tau", "D", "F", "iv", "iv_status", "delta", "vega", "gamma", "vanna", "volga", "theta_F", "theta", "dV_dF"]


def _read(path: Path, columns, flt=None) -> pd.DataFrame:
    df = ds.dataset(path).to_table(columns=columns, filter=flt).to_pandas()
    for c in ("quote_date", "settle_date", "next_session", "expire_date"):
        if c in df:
            df[c] = pd.to_datetime(df[c])
    for c in ("cp", "next_status", "iv_status"):
        if c in df:
            df[c] = df[c].astype(str)
    return df


def sigma_atm(g: pd.DataFrame) -> pd.Series:
    """Each expiry's at-the-money IV: linear in ln K between the strikes bracketing F, each strike's IV
    taken from its out-of-the-money option (the call at K ≥ F, the put below)."""
    otm = g[g.iv_status.eq("converged") & (((g.cp == "C") & (g.strike >= g.F)) | ((g.cp == "P") & (g.strike < g.F)))]
    out = {}
    for key, e in otm.groupby(["quote_date", "am_settled", "settle_date"], sort=False):
        e = e.sort_values("strike")
        x, F = np.log(e.strike.values), e.F.iloc[0]
        i = np.searchsorted(x, np.log(F))
        if 0 < i < len(x):
            out[key] = e.iv.values[i - 1] + (e.iv.values[i] - e.iv.values[i - 1]) * (np.log(F) - x[i - 1]) / (x[i] - x[i - 1])
    return pd.Series(out, name="sigma_atm", dtype=float).rename_axis(["quote_date", "am_settled", "settle_date"])


def index_features(closes: pd.Series) -> pd.DataFrame:
    """Trailing 20-session realized volatility (annualized, √252, ddof 1) and 5-session return of the
    official close on NYSE sessions, each through day one's own close."""
    s = closes.sort_index()
    lr = np.log(s).diff()
    return pd.DataFrame({"rv20": lr.rolling(20).std() * np.sqrt(252), "ret5": np.log(s / s.shift(5))})


def build_year(year: int, panel: Path, greeks: Path, sessions: pd.DataFrame, closes: pd.Series, maturity: str = "main") -> pd.DataFrame:
    """Pairs with day one in `year` passing E1–E6 and E8 (E7 and next_status kept as columns).

    maturity="short" replaces E5 by τ < 14 days on day one and keeps only pairs that end before
    settlement, τ > 0 at day two's snapshot (analysis_plan.md §16.6)."""
    day1 = _read(panel / f"year={year}", PANEL_COLS, ds.field("is_session") & ~ds.field("f_non_session"))
    g1 = _read(greeks / f"year={year}", ROW + ["am_settled", "settle_date"] + GREEK_COLS)
    p = day1.merge(g1.drop(columns=["am_settled", "settle_date"]), on=ROW, how="inner")

    atm = sigma_atm(g1)
    p = p.join(atm, on=["quote_date", "am_settled", "settle_date"])
    p["smile_pos"] = p.iv / p.sigma_atm - 1

    flags = p.f_post_settlement | p.f_settle_uncertain | p.f_stamp_not_session | p.f_dup_key
    p["E2"] = ~p.f_stamp_window
    p["E3"] = ~flags
    p["E4"] = (p.bid > 0) & (p.ask >= p.bid)
    # maturity="any" (plan §16.11): every maturity and delta, for the later days of a held position;
    # E6 is then not a filter, and `in_band` records E5 and E6 of the main sample
    p["E5"] = {"main": p.tau >= 14 / 365, "short": p.tau < 14 / 365, "any": p.tau > 0}[maturity]
    p["E6"] = p.delta.abs().between(0.05, 0.95)
    if maturity == "any":
        p["in_band"] = p.E6 & (p.tau >= 14 / 365)
        p["E6"] = True
    # the vendor codes "no last price" as 0; empty volume with a positive last is a day of 1,000+ contracts
    p["E7"] = (p.volume > 0) | (p.volume.isna() & (p["last"] > 0))
    p["E7_strict"] = p.volume > 0
    p["E8"] = p.iv_status.eq("converged")
    p = p[p.E2 & p.E3 & p.E4 & p.E5 & p.E6 & p.E8].drop(
        columns=["f_post_settlement", "f_settle_uncertain", "f_stamp_not_session", "f_dup_key", "f_stamp_window", "E2", "E3", "E4", "E5", "E6", "E8"])

    # day two: the same contract key on the next NYSE session (possibly in next year's files)
    two = []
    for y in (year, year + 1):
        if (greeks / f"year={y}").exists():
            gy = _read(greeks / f"year={y}", ["quote_date"] + CONTRACT_KEY + ["iv", "iv_status", "F", "D", "tau"])
            py = _read(panel / f"year={y}", ["quote_date"] + CONTRACT_KEY + ["bid_size", "ask_size"],
                       ds.field("is_session") & ~ds.field("f_non_session"))
            two.append(py.merge(gy, on=["quote_date"] + CONTRACT_KEY, how="left"))
    two = pd.concat(two).rename(columns={"quote_date": "next_session", "iv": "iv_next", "iv_status": "iv_status_next",
                                         "F": "F_next", "D": "D_next", "tau": "tau_next",
                                         "bid_size": "bid_size_next", "ask_size": "ask_size_next"})
    p = p.merge(two.drop_duplicates(["next_session"] + CONTRACT_KEY), on=["next_session"] + CONTRACT_KEY, how="left")
    if maturity in ("short", "any"):
        p = p[~(p.tau_next <= 0)]  # rows without a day-two quote stay, as attrition

    lvl = sessions.set_index("quote_date")
    p["S_A"] = p.quote_date.map(lvl.S_A)
    p["S_A_next"] = p.next_session.map(lvl.S_A)
    feats = index_features(closes)
    p = p.join(feats, on="quote_date")
    return p.reset_index(drop=True)
