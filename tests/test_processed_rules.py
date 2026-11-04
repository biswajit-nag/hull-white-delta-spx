"""The step-3 contract-identity and next-session rules, on dated cases from the audit."""

import pandas as pd
import pytest

from erdos_quant_finance_project.processed import join_next, nyse_sessions, settlement, third_friday

SESSIONS = nyse_sessions("2009-12-01", "2024-02-01")


def rule(underlying, quote, stamp):
    pairs = pd.DataFrame({"quote_date": [pd.Timestamp(quote)], "expire_date": [pd.Timestamp(stamp)]})
    return settlement(pairs, underlying, SESSIONS).iloc[0]


@pytest.mark.parametrize("day, expected", [("2020-03-01", "2020-03-20"), ("2019-02-01", "2019-02-15"), ("2016-09-30", "2016-09-16")])
def test_third_friday(day, expected):
    assert third_friday(pd.Series([pd.Timestamp(day)]))[0] == pd.Timestamp(expected)


@pytest.mark.parametrize("quote, stamp, am, settle", [
    ("2020-02-03", "2020-03-20", True, "2020-03-20"),   # Friday-stamped monthly, 2016-09 on
    ("2013-12-02", "2014-01-16", True, "2014-01-17"),   # Thursday-stamped monthly, before 2016-09
    ("2019-03-01", "2019-04-18", True, "2019-04-18"),   # Good Friday on the third Friday: Thursday settlement
    ("2014-03-03", "2014-04-16", True, "2014-04-17"),   # same, last trading day stamp (Wednesday)
    ("2015-01-05", "2016-12-15", True, "2016-12-16"),   # long-dated monthly, Thursday stamp in January 2015
    ("2019-04-01", "2019-04-17", False, "2019-04-17"),  # Wednesday weekly before the Good Friday monthly
    ("2019-04-08", "2019-05-16", False, "2019-05-16"),  # April 2019 window: a separate series, left to the window flag
    ("2023-01-05", "2023-01-19", False, "2023-01-19"),  # Thursday P.M. daily, 2022-05-11 on
    ("2020-03-02", "2020-03-13", False, "2020-03-13"),  # ordinary Friday weekly
])
def test_spx_settlement(quote, stamp, am, settle):
    r = rule("spx", quote, stamp)
    assert bool(r.am_settled) is am
    assert r.settle_date == pd.Timestamp(settle)
    assert r.settle_ts.hour == (9 if am else 16)


def test_spy_is_always_pm():
    r = rule("spy", "2020-02-03", "2020-03-20")
    assert not r.am_settled and r.settle_date == pd.Timestamp("2020-03-20")


def test_early_close_settles_at_13():
    assert rule("spx", "2020-11-02", "2020-11-27").settle_ts.hour == 13  # day after Thanksgiving


def test_2010_thursday_weekly_is_uncertain():
    assert rule("spx", "2010-01-04", "2010-01-07").f_settle_uncertain


def panel(rows):
    df = pd.DataFrame(rows, columns=["quote_date", "next_session", "strike", "bid", "ask", "f_dup_key", "vendor_has_next_session"])
    for c in ("quote_date", "next_session"):
        df[c] = pd.to_datetime(df[c])
    df["am_settled"], df["settle_date"], df["cp"] = False, pd.Timestamp("2020-06-19"), "C"
    df["mid"], df["volume"], df["S"], df["S_close"] = (df.bid + df.ask) / 2, 1.0, 3000.0, 3000.0
    df["f_non_session"] = False
    return df


def test_next_session_statuses():
    out = join_next(panel([
        ("2020-06-01", "2020-06-02", 3000, 10.0, 11.0, False, True),   # ok
        ("2020-06-02", "2020-06-03", 3000, 10.5, 11.5, False, True),   # next row one-sided
        ("2020-06-03", "2020-06-04", 3000, 0.0, 1.0, False, True),     # contract absent on 06-04
        ("2020-06-01", "2020-06-02", 3100, 5.0, 6.0, False, False),    # vendor lacks the next session
        ("2020-06-01", "2020-06-02", 3200, 5.0, 6.0, True, True),      # duplicated key
    ]))
    assert list(out.next_status) == ["ok", "one_sided_next", "contract_absent", "vendor_missing_session", "ambiguous_key"]
    assert out.mid_next[0] == 11.0
