"""The SPY protocol on one of the five underlyings of analysis_plan.md §16.15 (AAPL, NVDA, TSLA, QQQ, SLV).

Rules: §16.11's preamble without Heston (R0–R4, R6, R9, P0), monthly refits under §7 (ruleset.walk).
  1. 2020 as the test year (2019 training, W12) under §8's verdict procedure, as a descriptive replication;
     variants W36, F (frozen at 2020-01-02), S3 (day-one relative spread ≤ 5%), V (strict volume), the rest of 2020.
  2. The walk-forward: W12 from 2017-01, W36 from 2019-01, W60 from 2021-01; Gains per year and median yearly Gains;
     Hull and White's Table 3 aggregation on W36 (mean of monthly Gains, overall and by |δ| tenth).
  3. §16.10 item 1: the S&P 500's RV and DD episodes (market-wide stress) and the underlying's own RV episodes,
     with the threshold at twice its own 2016–2023 median 20-session realized volatility (§15, 2026-11-06); W12, W36.
  4. §16.10 item 2: R2's (a, b, c), R4's â and P0's c at every refit, with session-clustered standard errors.
  5. §16.9 item 2: level and shape on W12, with the after-the-fact ceiling.
  6. §16.10 item 3: τ^(−α) for α ∈ {0, 0.25, 0.75, 1} against α = 0.5 (R2), by year and by stress and calm, on W12.
Writes results/stocks/<u>/.

Usage: uv run python -I scripts/run_protocol_stocks.py aapl|nvda|tsla|qqq|slv
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252
sys.path.insert(0, str(ROOT / "scripts"))

from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project import ruleset as RS  # noqa: E402
from erdos_quant_finance_project.processed import nyse_sessions  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402
from erdos_quant_finance_project.verdict import secondary_tests, verdict  # noqa: E402

U = sys.argv[1].lower()
YEARS = range(2016, 2024)
OUT = ROOT / "results/stocks" / U
RULES = RS.rules_for(U)
COMPS = RS.comparisons(RULES)
STRESS = h.STRESS
START = {12: "2017-01", 36: "2019-01", 60: "2021-01"}
COLS = ["quote_date", "next_session", "am_settled", "settle_date", "strike", "cp", "E7", "E7_strict", "next_status", "rel_spread",
        "S_close", "S_close_next", "bid", "ask", "bid_size", "ask_size", "bid_next", "ask_next", "bid_size_next", "ask_size_next",
        "theta", "dV_dF", "F", "vega", "vanna", "tau"]


def load():
    import pyarrow.parquet as pq
    f = next((h.PAIRS_ROOT / f"underlying={U}").glob("year=*/pairs_*.parquet"))
    names = pq.read_schema(f).names
    cols = COLS + [c for c in ("div_next", "E9") if c in names]
    P = h.load_pairs(YEARS, columns=cols, underlying=U)
    if "E9" in P:  # §16.15: pairs straddling a split are ineligible (an E-rule column, applied with E1–E8)
        P = P[P.E9.astype(bool)].copy()
    return P, h.ingredients(P)


def sums(E, fr, rules, index):
    v = E[rules].pow(2)
    v["cp"], v["session"], v["n"] = fr.loc[E.index, "cp"].to_numpy(), fr.loc[E.index, "session"].to_numpy(), 1
    s = v.groupby(["session", "cp"]).sum()
    return s.reindex(pd.MultiIndex.from_product([index, ["C", "P"]], names=["session", "cp"]), fill_value=0)


def gains(E, fr, rules, comps, block=10, **label) -> pd.DataFrame:
    E = E[E[rules].notna().all(axis=1)]
    index = pd.DatetimeIndex(np.sort(fr.loc[E.index, "session"].unique()))
    if len(index) < 3:
        return pd.DataFrame()
    block = int(min(block, max(1, len(index) // 5)))
    counts = h.bootstrap_counts(index, B=10_000, block=block, seed=2026)
    S = sums(E, fr, rules, index)
    rows = [RS.session_gains(S.xs(cp, level="cp"), comps, counts).assign(cp=cp, pairs=int(S.xs(cp, level="cp").n.sum()))
            for cp in ("C", "P")]
    return pd.concat(rows, ignore_index=True).assign(sessions=len(index), block=block, **label)


def by_year(E, fr, rules, comps, **label):
    yr = fr.loc[E.index, "session"].dt.year.to_numpy()
    return pd.concat([gains(E[yr == y], fr, rules, comps, year=int(y), **label) for y in sorted(np.unique(yr))], ignore_index=True)


def clustered(X: np.ndarray, t: np.ndarray, g: np.ndarray):
    """OLS without intercept and its session-clustered standard errors."""
    A = X.T @ X
    if np.linalg.matrix_rank(A) < X.shape[1]:
        return None, None
    beta = np.linalg.solve(A, X.T @ t)
    s = pd.DataFrame(X * (t - X @ beta)[:, None]).groupby(g).sum().to_numpy()
    Ai = np.linalg.inv(A)
    return beta, np.sqrt(np.diag(Ai @ (s.T @ s) @ Ai))


def own_rv_episodes(P) -> pd.DataFrame:
    lvl = P.groupby("quote_date").S_close.first()
    nyse = nyse_sessions("2015-12-01", "2023-12-31").index
    lvl = lvl.reindex(nyse).dropna()
    r = np.log(lvl).diff()
    jump = r.abs() > np.log(1.3)                      # split sessions (§16.15) are not returns
    rv = r.mask(jump).rolling(20, min_periods=15).std() * np.sqrt(252)
    thr = 2 * float(rv["2016":"2023"].median())
    hot, rows = rv[rv > thr].index, []
    if len(hot):
        pos = {d: i for i, d in enumerate(lvl.index)}
        start = prev = hot[0]
        for d in hot[1:]:
            if pos[d] - pos[prev] > 10:
                rows.append(("own RV", start, prev))
                start = d
            prev = d
        rows.append(("own RV", start, prev))
    E = pd.DataFrame(rows, columns=["definition", "start", "end"])
    E["threshold"] = thr
    E["sessions"] = [len(lvl[a:b]) for a, b in zip(E.start, E.end)]
    E["peak_rv20"] = [float(rv[a:b].max()) for a, b in zip(E.start, E.end)]
    return E


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with timed("protocol_stocks", inputs=f"{U} 2016-2023, §16.15 items 2-5, 7") as log:
        P, fr = load()
        prm9 = RS.r9_params(U)
        log["rows_in"] = len(P)
        sess = fr.session

        # 1. 2020 as the test year
        m20 = pd.period_range("2020-01", "2020-12", freq="M")
        p20 = RS.r9_params(U, tag="2019")  # §16.7: the 2020 test year uses the set tuned on 2019 (SPX's, for these five)
        V_COMPS = COMPS + [("R2", "R3"), ("R2", "R4")]  # §8's verdict needs R2 over R3 and R4
        E12, _ = RS.walk(fr, P, m20, 12, p20)
        in_stress = sess.loc[E12.index].between(*STRESS).to_numpy()
        variants = {"primary": E12, "W36": RS.walk(fr, P, m20, 36, p20)[0], "F": RS.walk(fr, P, m20, 12, p20, frozen=h.UNBLIND)[0],
                    "S3": E12[(P.loc[E12.index, "rel_spread"] <= 0.05).to_numpy()], "V": E12[P.loc[E12.index, "E7_strict"].to_numpy()],
                    "rest of 2020": E12[~in_stress], "stress period": E12[in_stress]}
        T, V = [], []
        for name, E in variants.items():
            g = gains(E, fr, RULES, V_COMPS, variant=name)
            T.append(g)
            if name != "stress period":
                V.append({"variant": name, **verdict(g)})
                T.append(secondary_tests(g).assign(variant=name, table="secondary"))
        pd.concat(T, ignore_index=True).to_csv(OUT / "test2020_gains.csv", index=False)
        pd.DataFrame(V).to_csv(OUT / "test2020_verdict.csv", index=False)
        print(pd.DataFrame(V)[["variant", "verdict", "G_C", "G_C_lo", "G_C_hi", "G_P", "G_P_lo", "G_P_hi"]].round(3).to_string(index=False), flush=True)

        # 2. the walk-forward
        WF, fits, errs = [], {}, {}
        for W, st in START.items():
            E, f = RS.walk(fr, P, pd.period_range(st, "2023-12", freq="M"), W, prm9, keep_fits=True)
            errs[W], fits[W] = E, f
            WF.append(by_year(E, fr, RULES, COMPS, window=W))
        WF = pd.concat(WF, ignore_index=True)
        WF.to_csv(OUT / "walkforward_gains_by_year.csv", index=False)
        med = WF.groupby(["window", "cp", "rule", "base"]).gain.median().rename("median_yearly_gain").reset_index()
        med.to_csv(OUT / "walkforward_median_yearly_gain.csv", index=False)
        # Hull and White's Table 3 aggregation, W36: the mean over months of the Gain of R2 over R1, by |δ| tenth
        E = errs[36].join(fr[["cp", "delta"]])
        E["bucket"] = (E.delta.abs() * 10).round() / 10
        mon = E.groupby(["month", "cp", "bucket"])[["R1", "R2"]].apply(lambda x: 1 - (x.R2**2).sum() / (x.R1**2).sum()).rename("gain").reset_index()
        allm = E.groupby(["month", "cp"])[["R1", "R2"]].apply(lambda x: 1 - (x.R2**2).sum() / (x.R1**2).sum()).rename("gain").reset_index()
        hw = pd.concat([mon.groupby(["cp", "bucket"]).gain.mean().reset_index(),
                        allm.groupby("cp").gain.mean().reset_index().assign(bucket="all")], ignore_index=True)
        hw.to_csv(OUT / "hw_table3_comparison.csv", index=False)

        # 3. stress episodes
        from stress_episodes import episodes  # the S&P 500's RV and DD episodes, as for SPY
        EP = pd.concat([episodes(), own_rv_episodes(P)], ignore_index=True)
        EP = EP[EP.end >= pd.Timestamp(START[12])].reset_index(drop=True)
        EP.to_csv(OUT / "stress_episodes.csv", index=False)
        SG, SY = [], []
        mkt_rv = set()
        for a, b in EP[EP.definition == "RV"][["start", "end"]].itertuples(index=False):
            mkt_rv |= set(pd.date_range(a, b))
        for W in (12, 36):
            E = errs[W]
            s = sess.loc[E.index]
            for i, ep in EP.iterrows():
                m = s.between(ep.start, ep.end).to_numpy()
                if m.sum() == 0:
                    continue
                e = E[m]
                g = gains(e, fr, RULES, COMPS, episode=i, definition=ep.definition, start=ep.start, end=ep.end, window=W)
                yrs = s.dt.year.between(ep.start.year, ep.end.year).to_numpy()
                d = fr.loc[e.index]
                for cp in ("C", "P"):
                    k = (d.cp == cp).to_numpy()
                    best = float((d.x[k] * d.y[k]).sum() / (d.x[k] ** 2).sum())
                    cfit = pd.Series({mm: float(fits[W][(mm, cp)]["P0"][0]) for (mm, c2) in fits[W] if c2 == cp})
                    w = d.x[k] ** 2
                    fitted = float((e.month[k].map(cfit) * w).sum() / w.sum())
                    share = float((E.R1[m & (fr.loc[E.index, "cp"] == cp).to_numpy()] ** 2).sum() / (E.R1[yrs & (fr.loc[E.index, "cp"] == cp).to_numpy()] ** 2).sum())
                    g.loc[g.cp == cp, ["best_constant", "fitted_constant", "share_of_years_R1_sse"]] = [best, fitted, share]
                SG.append(g)
            hot = s.isin(mkt_rv).to_numpy()
            for y in sorted(s.dt.year.unique()):
                for lab, mm in (("stress", hot), ("calm", ~hot)):
                    sel = mm & (s.dt.year == y).to_numpy()
                    if sel.sum():
                        SY.append(gains(E[sel], fr, RULES, COMPS, year=y, sessions_kind=lab, window=W))
        pd.concat(SG, ignore_index=True).to_csv(OUT / "stress_gains.csv", index=False)
        pd.concat(SY, ignore_index=True).to_csv(OUT / "stress_by_year.csv", index=False)

        # 4. parameter stability, with session-clustered standard errors
        day1, day2 = P.quote_date, P.next_session
        sessions = pd.DatetimeIndex(np.sort(day1.unique()))
        rows = []
        for W, st in START.items():
            for m, s0 in h.month_starts(pd.period_range(st, "2023-12", freq="M"), sessions).items():
                if pd.isna(s0):
                    continue
                tr = fr.avail & h.training_mask(day1, day2, s0, W)
                for cp in ("C", "P"):
                    d = fr[tr & (fr.cp == cp)]
                    if d.session.nunique() < 150:
                        continue
                    for rule, names in (("R2", ["a", "b", "c"]), ("R4", ["a_hat"]), ("P0", ["c"])):
                        X, t = RS.design(rule, d)
                        b, se = clustered(X, t, d.session.to_numpy())
                        if b is None:
                            continue
                        for n, bb, ss in zip(names, b, se):
                            rows.append({"window": W, "month": str(m), "cp": cp, "rule": rule, "coef": n, "value": bb, "se": ss})
        PP = pd.DataFrame(rows)
        PP.to_csv(OUT / "parameter_paths.csv", index=False)
        summ = []
        for (W, cp, rule, n), g in PP.groupby(["window", "cp", "rule", "coef"]):
            g = g.sort_values("month")
            ch = (g.value.diff().abs() / g.se).median()
            z = (g.value - g.value.shift(12)) / np.sqrt(g.se**2 + g.se.shift(12) ** 2)
            summ.append({"window": W, "cp": cp, "rule": rule, "coef": n, "min": g.value.min(), "max": g.value.max(),
                         "median_se": g.se.median(), "median_abs_change_over_se": ch,
                         "share_abs_z12_gt2": float((z.abs() > 2).mean()) if W == 12 and z.notna().any() else np.nan})
        pd.DataFrame(summ).to_csv(OUT / "parameter_stability_summary.csv", index=False)

        # 5. level and shape, W12
        E = errs[12].join(fr[["cp", "x", "y"]])
        LS = []
        for (mm, cp), g in E.groupby(["month", "cp"]):
            best = float((g.x * g.y).sum() / (g.x**2).sum())
            LS.append({"month": mm, "cp": cp, "c_fitted": float(fits[12][(mm, cp)]["P0"][0]), "c_best": best,
                       "sse_R1": float((g.R1**2).sum()), "sse_P0": float((g.P0**2).sum()), "sse_R2": float((g.R2**2).sum()),
                       "sse_best": float(((g.y - best * g.x) ** 2).sum())})
        LS = pd.DataFrame(LS)
        LS.to_csv(OUT / "level_shape_by_month.csv", index=False)
        LS["year"] = LS.month.str[:4].astype(int)
        y = LS.groupby(["year", "cp"])[["sse_R1", "sse_P0", "sse_R2", "sse_best"]].sum()
        pd.DataFrame({"level_P0_over_R1": 1 - y.sse_P0 / y.sse_R1, "shape_R2_over_P0": 1 - y.sse_R2 / y.sse_P0,
                      "R2_over_R1": 1 - y.sse_R2 / y.sse_R1, "ceiling_best_over_R1": 1 - y.sse_best / y.sse_R1}).reset_index().to_csv(
            OUT / "level_shape_by_year.csv", index=False)

        # 6. the maturity check, W12
        alphas = ["alpha:0", "alpha:0.25", "alpha:0.75", "alpha:1"]
        err, _ = h.walk_forward(fr, P, pd.period_range(START[12], "2023-12", freq="M"), h.Window(12), rules=["R2", "R4"] + alphas)
        s = sess.loc[err.index]
        hot = s.isin(mkt_rv).to_numpy()
        MA = [by_year(err, fr, ["R1", "R2"] + alphas, [(a, "R2") for a in alphas], sessions_kind="all")]
        for lab, mm in (("stress", hot), ("calm", ~hot)):
            MA.append(gains(err[mm], fr, ["R1", "R2"] + alphas, [(a, "R2") for a in alphas], sessions_kind=lab, year="all"))
        pd.concat(MA, ignore_index=True).to_csv(OUT / "maturity_by_year.csv", index=False)
        log["rows_out"] = len(WF)
        print(med[(med.base == "R1") & med.rule.isin(["R2", "R3", "R4", "P0", "R9"])].pivot_table(index=["window", "rule"], columns="cp", values="median_yearly_gain").round(3).to_string())


if __name__ == "__main__":
    main()
