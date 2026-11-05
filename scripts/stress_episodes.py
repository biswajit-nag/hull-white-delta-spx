"""Stress periods 2010–2023 and the maturity assumption by year (analysis_plan.md §16.10, items 1 and 3).

Episodes come from the S&P 500 close alone (for SPY too, as the market's stress):
  RV: sessions with trailing 20-session realized volatility above 25%, runs within 10 sessions merged;
  DD: drawdowns of 10% or more from the running peak, peak to trough;
plus the 2020 window of plan §8. On the W12 and W36 walk-forwards (R2, R4, R5, R6, P0 refitted monthly;
R3 fixed): each episode's Gains over R1 and R2 with a session-block bootstrap inside the episode, its share
of the year's Black–Scholes squared error, and the after-the-fact constant against the fitted one; the
same for each year's RV-stress and calm sessions. On W12, the τ^(−α) check of plan §10 by year and by
stress/calm. Writes stress_episodes.csv, stress_gains.csv, stress_by_year.csv and maturity_by_year.csv in
results/walkforward/ (results/spy/walkforward/ with --spy).

Usage: uv run python -I scripts/stress_episodes.py [--spy]
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project.processed import nyse_sessions, official_closes  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

U = "spy" if "--spy" in sys.argv else "spx"
OUT = ROOT / ("results/spy/walkforward" if U == "spy" else "results/walkforward")
FITTED = ["R2", "R4", "R5", "R6", "deg:0"]
ALPHAS = ["alpha:0", "alpha:0.25", "alpha:0.75", "alpha:1"]
RULES = ["R1", "R2", "R3", "R4", "R5", "R6", "P0"]
COMPS = [(r, "R1") for r in RULES[1:]] + [(r, "R2") for r in RULES[2:]]


def episodes() -> pd.DataFrame:
    nyse = nyse_sessions("2009-06-01", "2023-12-31").index
    s = official_closes(ROOT / "data/external", "spx").S_close.reindex(nyse).dropna()
    rv = np.log(s).diff().rolling(20).std() * np.sqrt(252)
    rows = []
    hot = rv[rv > 0.25].index
    if len(hot):
        pos = {d: i for i, d in enumerate(s.index)}
        start = prev = hot[0]
        for d in hot[1:]:
            if pos[d] - pos[prev] > 10:
                rows.append(("RV", start, prev))
                start = d
            prev = d
        rows.append(("RV", start, prev))
    dd = s / s.cummax() - 1
    inside, peak = False, None
    for d, v in dd.items():
        if not inside and v <= -0.10:
            inside, peak = True, s[:d].idxmax()
        if inside and v == 0:
            rows.append(("DD", peak, s[peak:d].idxmin()))
            inside = False
    if inside:
        rows.append(("DD", peak, s[peak:].idxmin()))
    rows.append(("plan 2020 window", pd.Timestamp("2020-02-24"), pd.Timestamp("2020-04-30")))
    E = pd.DataFrame(rows, columns=["definition", "start", "end"])
    E = E[E.end >= "2010-01-01"].reset_index(drop=True)
    E["sessions"] = [len(s[a:b]) for a, b in zip(E.start, E.end)]
    E["peak_rv20"] = [float(rv[a:b].max()) for a, b in zip(E.start, E.end)]
    E["index_change"] = [float(s[b] / s[a] - 1) for a, b in zip(E.start, E.end)]
    return E


def gains(e, fr, rules, comps, label_cols: dict) -> pd.DataFrame:
    e = e[e[rules].notna().all(axis=1)]
    index = pd.DatetimeIndex(np.sort(fr.loc[e.index, "session"].unique()))
    if len(index) < 3:
        return pd.DataFrame()
    block = int(min(10, max(1, len(index) // 5)))
    g = h.gain_table(h.aligned_sse(e, fr, rules, index), comps, h.bootstrap_counts(index, B=10_000, block=block, seed=2026))
    return g.assign(sessions=len(index), block=block, **label_cols)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with timed("stress_episodes", inputs=f"{U} 2010-2023, W12 W36, RV and DD episodes") as log:
        E = episodes()
        E.to_csv(OUT / "stress_episodes.csv", index=False)
        P = h.load_pairs(range(2010, 2024), underlying=U)
        fr = h.ingredients(P)
        rv_sessions = pd.DatetimeIndex(sorted(set().union(*[set(pd.date_range(a, b)) for a, b in E[E.definition == "RV"][["start", "end"]].itertuples(index=False)])))
        rows, yrows, mrows = [], [], []
        for W, start in ((12, "2011-01"), (36, "2013-01")):
            rules_fit = FITTED + (ALPHAS if W == 12 else [])
            err, coefs = h.walk_forward(fr, P, pd.period_range(start, "2023-12", freq="M"), h.Window(W), rules=rules_fit)
            err = err.rename(columns={"deg:0": "P0"})
            c_fit = coefs[coefs.rule == "deg:0"].assign(c=lambda d: d.coef.map(lambda v: v[0] if v is not None else np.nan))
            c_fit = c_fit.set_index(["month", "cp"]).c
            e = err.join(fr[["cp", "session", "x", "y"]])
            e["year"] = e.session.dt.year
            sse_year = (e.R1 ** 2).groupby([e.year, e.cp]).sum()
            for ep in E.itertuples():
                sub = e[(e.session >= ep.start) & (e.session <= ep.end)]
                if sub.empty:
                    continue
                g = gains(sub, fr, RULES, COMPS, {"window": W, "definition": ep.definition, "start": ep.start.date(), "end": ep.end.date()})
                if g.empty:
                    continue
                for cp in "CP":
                    x = sub[sub.cp == cp]
                    yrs = sorted(x.year.unique())
                    share = float((x.R1 ** 2).sum() / sum(sse_year.get((y, cp), np.nan) for y in yrs)) if len(x) else np.nan
                    cpost = float((x.x * x.y).sum() / (x.x ** 2).sum()) if len(x) else np.nan
                    cfit = float(c_fit.reindex([(m, cp) for m in x.month.unique()]).mean()) if len(x) else np.nan
                    g.loc[g.cp == cp, ["share_of_year_R1_sse", "c_post", "c_fit_mean"]] = [share, cpost, cfit]
                rows.append(g)
            e["regime"] = np.where(e.session.isin(rv_sessions), "RV stress", "calm")
            for (year, regime), sub in e.groupby(["year", "regime"]):
                g = gains(sub, fr, RULES, COMPS, {"window": W, "year": year, "regime": regime})
                if not g.empty:
                    for cp in "CP":
                        x = sub[sub.cp == cp]
                        g.loc[g.cp == cp, ["share_of_year_R1_sse", "c_post"]] = [float((x.R1 ** 2).sum() / sse_year.get((year, cp), np.nan)),
                                                                                  float((x.x * x.y).sum() / (x.x ** 2).sum())]
                    yrows.append(g)
            if W == 12:  # the maturity check of plan §10, by year and by regime
                for keys, sub in list(e.groupby("year")) + [((y, r), s) for (y, r), s in e.groupby(["year", "regime"])]:
                    year, regime = (keys, "all") if not isinstance(keys, tuple) else keys
                    g = gains(sub, fr, ["R2"] + ALPHAS, [(a, "R2") for a in ALPHAS], {"year": year, "regime": regime})
                    if not g.empty:
                        mrows.append(g)
            print(f"W{W} done", flush=True)
        G = pd.concat(rows, ignore_index=True)
        G.to_csv(OUT / "stress_gains.csv", index=False)
        pd.concat(yrows, ignore_index=True).to_csv(OUT / "stress_by_year.csv", index=False)
        pd.concat(mrows, ignore_index=True).to_csv(OUT / "maturity_by_year.csv", index=False)
        log["rows_out"] = len(G)
        print(E.to_string(index=False))
        print(G[(G.window == 12) & (G.rule == "R2") & (G.base == "R1")][["definition", "start", "end", "cp", "gain", "lo", "hi", "sessions", "share_of_year_R1_sse"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
