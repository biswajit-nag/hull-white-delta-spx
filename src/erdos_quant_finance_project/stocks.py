"""Single stocks and ETFs (analysis_plan.md section 16.15): dividends, trailing yields and split detection."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

PAYERS = ("aapl", "nvda", "qqq")  # TSLA and SLV paid no distributions 2016-2023
SPLIT_JUMP = 0.30  # a one-session move in UNDERLYING_LAST above 30%


def dividends(external: Path, ticker: str) -> pd.Series:
    """Cash dividends per share, indexed by ex-date, from the saved Nasdaq response (empty for non-payers).
    Amounts are as paid, i.e. on the share basis of the day (checked against the vendor's unadjusted prices)."""
    d = json.loads((external / f"nasdaq_{ticker.upper()}_dividends.json").read_text())["data"]["dividends"]["rows"]
    if not d:
        return pd.Series(dtype=float, name="dividend")
    df = pd.DataFrame(d)
    df = df[df.type == "Cash"]
    ex = pd.to_datetime(df.exOrEffDate, format="%m/%d/%Y")
    amt = df.amount.str.replace("$", "", regex=False).astype(float)
    return pd.Series(amt.values, index=ex, name="dividend").sort_index()


def detect_splits(s: pd.Series) -> pd.DataFrame:
    """s: UNDERLYING_LAST by vendor quote date. Returns, where the move between consecutive vendor dates exceeds 30%:
    date (first date on the new basis), prev_date, move, and ratio (old shares per new share, rounded to a half)."""
    s = s.sort_index()
    ch = s / s.shift() - 1
    hit = ch.abs() > SPLIT_JUMP
    prev = s.index.to_series().shift()[hit]
    r = (s.shift() / s)[hit].values
    with np.errstate(divide="ignore"):  # np.where evaluates both branches
        ratio = np.where(r > 1, np.round(r * 2) / 2, 1 / (np.round(2 / r) / 2))
    return pd.DataFrame({"date": s.index[hit], "prev_date": prev.values, "move": ch[hit].values, "ratio": ratio}).reset_index(drop=True)


def trailing_yield(div: pd.Series, splits: pd.DataFrame, dates: pd.DatetimeIndex, S: pd.Series) -> pd.Series:
    """q per session: dividends with ex-date in (d - 365 days, d], each converted to the share basis of
    date d (divided by the product of split ratios between its ex-date and d), over S on d."""
    out = {}
    for d in dates:
        w = div[(div.index > d - pd.Timedelta(days=365)) & (div.index <= d)]
        w = w.iloc[-4:]  # quarterly payers: an ex-date drifting by a day or two must not count a fifth payment
        adj = 0.0
        for e, a in w.items():
            f = splits.ratio[(splits.date > e) & (splits.date <= d)].prod() if len(splits) else 1.0
            adj += a / f
        out[d] = adj / S[d]
    return pd.Series(out)
