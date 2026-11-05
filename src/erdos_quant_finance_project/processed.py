"""Step 3: reshape the interim OptionsDX files into a long contract-day panel.

One row per quote date x expiry stamp x strike x call/put. Nothing is dropped or
repaired: contract identity, calendar facts and quality problems are added as
columns, and each contract-day is joined to the same contract on the next NYSE
session. The rules are documented in DATA.md.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

NY = "America/New_York"

# Before this quote date the vendor stamps the SPX A.M. monthly on its last trading day; from it on,
# on its settlement day, and a last-trading-day stamp is a P.M. weekly or daily (DATA.md).
LTD_STAMP_END = pd.Timestamp("2016-09-01")
# Quote dates on which the vendor shifted expiry stamps and listed some monthlies twice (DATA.md).
STAMP_WINDOWS = {"spx": [("2019-04-04", "2019-04-16")], "spy": []}
AM_SETTLE_TIME = dt.time(9, 30)

SHARED = ["quote_date", "quote_unixtime", "expire_date", "expire_unix", "dte", "strike", "underlying_last"]
SIDE = ["bid", "ask", "bid_size", "ask_size", "last", "volume", "iv", "delta", "gamma", "vega", "theta", "rho"]
VENDOR_MODEL = {"iv", "delta", "gamma", "vega", "theta", "rho"}
CONTRACT_KEY = ["am_settled", "settle_date", "strike", "cp"]
NEXT_FIELDS = ["bid", "ask", "mid", "volume", "S", "S_close"]
DATE_COLUMNS = ["quote_date", "expire_date", "settle_date", "next_session"]


def nyse_sessions(start: str, end: str) -> pd.Series:
    """NYSE session dates (naive midnight index) mapped to their close time in New York."""
    sched = mcal.get_calendar("XNYS").schedule(start_date=start, end_date=end)
    close = sched.market_close.dt.tz_convert(NY)
    close.index = pd.DatetimeIndex(sched.index).normalize()
    return close


def third_friday(d: pd.Series) -> pd.Series:
    first = d - pd.to_timedelta(d.dt.day - 1, unit="D")
    return first + pd.to_timedelta((4 - first.dt.day_of_week) % 7 + 14, unit="D")


def previous_session(d: pd.Series, sessions: pd.DatetimeIndex) -> pd.Series:
    """The last session strictly before each date."""
    return pd.Series(sessions[np.searchsorted(sessions, d.values, side="left") - 1], index=d.index)


def next_session(d: pd.Series, sessions: pd.DatetimeIndex) -> pd.Series:
    """The first session strictly after each date."""
    return pd.Series(sessions[np.searchsorted(sessions, d.values, side="right")], index=d.index)


def settlement(pairs: pd.DataFrame, underlying: str, sessions: pd.Series) -> pd.DataFrame:
    """Settlement class, date and time for unique (quote_date, expire_date) pairs."""
    out = pairs.copy()
    e, q = out.expire_date, out.quote_date
    days = sessions.index
    if e.max() >= days[-1] or q.min() <= days[0]:
        raise ValueError(f"NYSE calendar {days[0].date()}..{days[-1].date()} does not cover these dates")
    if underlying == "spx":
        tf = third_friday(e)
        settle_day = tf.where(tf.isin(days), previous_session(tf, days))  # Thursday when Friday is a holiday
        last_trading_day = previous_session(settle_day, days)
        am = (e == settle_day) | ((e == last_trading_day) & (q < LTD_STAMP_END))
        out["settle_date"] = e.where(~am, settle_day)
        # 2010 weeklies are stamped Thursday but still hold time value at the stamp, so settle later.
        out["f_settle_uncertain"] = ~am & (e.dt.day_of_week == 3) & (e.dt.year == 2010)
    else:
        am = pd.Series(False, index=out.index)
        out["settle_date"] = e
        out["f_settle_uncertain"] = False
    out["am_settled"] = am
    sd = out.settle_date
    pm_close = sd.map(sessions).fillna(sd.dt.tz_localize(NY) + pd.Timedelta(hours=16))
    am_open = sd.dt.tz_localize(NY) + pd.Timedelta(hours=AM_SETTLE_TIME.hour, minutes=AM_SETTLE_TIME.minute)
    out["settle_ts"] = am_open.where(am, pm_close)
    out["f_stamp_not_session"] = ~sd.isin(days)
    return out


def stooq_unadjusted(external: Path) -> pd.Series:
    """Stooq's dividend-adjusted SPY closes with the adjustment reversed (analysis_plan.md §16.3).

    Going back from the last session with f = 1, at each SSGA ex-date e the factor for earlier sessions
    becomes f / (1 + f·Div_e / C̃_{e−1}), with C̃ Stooq's adjusted close; the close is C̃ / f.
    """
    adj = pd.read_csv(external / "stooq_spy_us_d.csv", parse_dates=["Date"]).set_index("Date").Close.sort_index()
    div = pd.read_csv(external / "ssga_SPY_distributions.csv", parse_dates=["ex_date"]).set_index("ex_date").dividend
    div = div[(div.index > adj.index[0]) & (div.index <= adj.index[-1])].sort_index(ascending=False)
    factor = pd.Series(1.0, index=adj.index)
    f = 1.0
    for e, d in div.items():
        f = f / (1 + f * d / adj[adj.index < e].iloc[-1])
        factor[factor.index < e] = f
    return adj / factor


def official_closes(external: Path, underlying: str = "spx") -> pd.DataFrame:
    """Official closes. SPX: FRED where available (2016-10 on), else Cboe's SPX history.
    SPY: the exchange close from Nasdaq's historical quotes (2016-11-03 on); before that, Stooq's close
    with its dividend adjustment reversed (stooq_unadjusted)."""
    if underlying == "spy":
        nasdaq = pd.read_csv(external / "nasdaq_SPY_history.csv", parse_dates=["date"]).set_index("date").close
        stooq = stooq_unadjusted(external)
        stooq = stooq[stooq.index < nasdaq.index.min()]
        return pd.DataFrame({"S_close": pd.concat([stooq, nasdaq]).sort_index(),
                             "S_close_source": ["stooq_unadjusted"] * len(stooq) + ["nasdaq"] * len(nasdaq)}).sort_index()
    fred = pd.read_csv(external / "fred_SP500.csv", na_values=".").dropna()
    fred = pd.Series(fred.SP500.values, index=pd.to_datetime(fred.observation_date), name="fred")
    cboe = pd.read_csv(external / "cboe_SPX_History.csv")
    cboe = pd.Series(cboe.SPX.values, index=pd.to_datetime(cboe.DATE, format="%m/%d/%Y"), name="cboe")
    both = pd.concat([fred, cboe], axis=1)
    return pd.DataFrame({
        "S_close": both.fred.fillna(both.cboe),
        "S_close_source": np.where(both.fred.notna(), "fred", np.where(both.cboe.notna(), "cboe", None)),
    })


def to_long(wide: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for cp in ("c", "p"):
        names = {f"{cp}_{f}": (f"vendor_{f}" if f in VENDOR_MODEL else f) for f in SIDE}
        part = wide[SHARED + list(names)].rename(columns=names)
        part["cp"] = cp.upper()
        parts.append(part)
    long = pd.concat(parts, ignore_index=True).rename(columns={"underlying_last": "S", "dte": "vendor_dte"})
    long["cp"] = long.cp.astype("category")
    return long


def add_columns(long: pd.DataFrame, underlying: str, sessions: pd.Series, closes: pd.DataFrame) -> pd.DataFrame:
    """Derived prices, calendar facts, contract identity and quality flags."""
    days = sessions.index
    long["mid"] = (long.bid + long.ask) / 2
    long["spread"] = long.ask - long.bid
    long["rel_spread"] = long.spread / long.mid.where(long.mid > 0)

    long["is_session"] = long.quote_date.isin(days)
    long["early_close"] = long.quote_date.map(sessions.dt.hour < 16).fillna(False).astype(bool)
    long["next_session"] = next_session(long.quote_date, days)
    long["vendor_has_next_session"] = long.next_session.isin(set(long.quote_date.unique()))

    pair_cols = ["quote_date", "expire_date"]
    rules = settlement(long[pair_cols].drop_duplicates(), underlying, sessions).set_index(pair_cols)
    at = pd.MultiIndex.from_frame(long[pair_cols])
    for c in ["am_settled", "settle_date", "settle_ts", "f_settle_uncertain", "f_stamp_not_session"]:
        long[c] = rules[c].reindex(at).to_numpy()
    long["am_settled"] = long.am_settled.astype(bool)

    long["S_close"] = long.quote_date.map(closes.S_close)
    long["S_close_source"] = long.quote_date.map(closes.S_close_source).astype("category")
    long["f_non_session"] = ~long.is_session
    long["f_one_sided"] = long.bid.isna() | long.ask.isna() | (long.bid <= 0)
    long["f_crossed"] = long.ask < long.bid
    long["f_dup_key"] = long.duplicated(["quote_date"] + CONTRACT_KEY, keep=False)
    # A pair touches a stamp window if either its quote date or its next session lies in one.
    in_window = pd.Series(False, index=long.index)
    for lo, hi in STAMP_WINDOWS.get(underlying, []):
        lo, hi = pd.Timestamp(lo), pd.Timestamp(hi)
        in_window |= long.quote_date.between(lo, hi) | long.next_session.between(lo, hi)
    long["f_stamp_window"] = in_window
    long["f_post_settlement"] = long.am_settled & (long.quote_date >= long.settle_date)

    # A contract whose vendor stamp differs from the one it carried on its previous quote date.
    uniq = long[~long.f_dup_key].sort_values(CONTRACT_KEY + ["quote_date"])
    prev_stamp = uniq.groupby(CONTRACT_KEY, sort=False).expire_date.shift()
    long["f_restamped"] = False
    long.loc[uniq.index, "f_restamped"] = prev_stamp.notna() & (prev_stamp != uniq.expire_date)
    return long


def join_next(long: pd.DataFrame) -> pd.DataFrame:
    """Join each contract-day to the same contract key on the next NYSE session, with a status."""
    key = ["quote_date"] + CONTRACT_KEY
    right = long[key + NEXT_FIELDS].copy()
    right["n_key_next"] = right.groupby(key).bid.transform("size")
    right = right.drop_duplicates(key).rename(columns={"quote_date": "next_session", **{c: f"{c}_next" for c in NEXT_FIELDS}})
    # Merge only the key columns (left order is preserved), then attach the matched values.
    matched = long[["next_session"] + CONTRACT_KEY].merge(right, on=["next_session"] + CONTRACT_KEY, how="left")
    for c in [f"{c}_next" for c in NEXT_FIELDS] + ["n_key_next"]:
        long[c] = matched[c].to_numpy()

    expired = (long.am_settled & (long.next_session >= long.settle_date)) | (~long.am_settled & (long.next_session > long.settle_date))
    two_sided_next = (long.bid_next > 0) & (long.ask_next >= long.bid_next)
    long["next_status"] = pd.Categorical(np.select(
        [long.f_non_session, expired, long.f_dup_key | (long.n_key_next > 1), ~long.vendor_has_next_session,
         long.n_key_next.isna(), ~two_sided_next],
        ["non_session_row", "expired", "ambiguous_key", "vendor_missing_session", "contract_absent", "one_sided_next"],
        default="ok",
    ))
    # Values from an ambiguous or missing match are not a usable endpoint.
    unusable = long.next_status.isin(["non_session_row", "expired", "ambiguous_key"])
    long.loc[unusable, [f"{c}_next" for c in NEXT_FIELDS]] = np.nan
    return long.drop(columns="n_key_next")


def read_interim(interim: Path, underlying: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    dset = ds.dataset(interim, format="parquet", partitioning="hive")
    years = list(range(start.year, end.year + 1))
    filt = ((ds.field("underlying") == underlying) & ds.field("year").isin(years)
            & (ds.field("quote_date") >= start.date()) & (ds.field("quote_date") <= end.date()))
    wide = dset.to_table(columns=SHARED + [f"{s}_{f}" for s in "cp" for f in SIDE], filter=filt).to_pandas()
    for c in ("quote_date", "expire_date"):
        wide[c] = pd.to_datetime(wide[c])
    return wide


def build_year(interim: Path, underlying: str, year: int, sessions: pd.Series, closes: pd.DataFrame) -> pd.DataFrame:
    """Processed rows for quote dates in one year; a few weeks either side supply the joins."""
    lo, hi = pd.Timestamp(year - 1, 12, 1), pd.Timestamp(year + 1, 1, 31)
    long = to_long(read_interim(interim, underlying, lo, hi))
    long = join_next(add_columns(long, underlying, sessions, closes))
    long = long[long.quote_date.dt.year == year].reset_index(drop=True)
    for c in DATE_COLUMNS:
        long[c] = long[c].dt.date
    return long


def write_year(long: pd.DataFrame, out_root: Path, underlying: str, year: int) -> Path:
    out_dir = out_root / f"underlying={underlying}" / f"year={year}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{underlying}_long_{year}.parquet"
    pq.write_table(pa.Table.from_pandas(long, preserve_index=False), out, compression="zstd")
    return out
