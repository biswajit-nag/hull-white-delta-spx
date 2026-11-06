"""Held positions, data starvation and books (analysis_plan.md §16.11, §16.13, §16.14), for any underlying.

Rules: the preamble of §16.11 (R0–R4, R6, R9, P0; Heston's H_model, H_mv, H_fit on SPX), via ruleset.walk on the
12-month window unless stated. On SPX every rule is scored on the pairs with Heston Greeks (the analysis sample;
every B2 session converged), so that all rules share one sample.

  books   §16.14: four books per session; book Gains, per-option Gains and the common share, per year.
  starve  §16.13: windows of 1, 2, 3, 6 months; W12 fits on thinned sessions (five seeds); per-year Gains over R1
          and over the full-data W12 R2, and median yearly Gains.
  paths   §16.11: H ∈ {5, 10} one-session hedges in a row on one contract, later days from pairs_any; per-year and
          pooled path Gains, the one-session Gain on the same pairs, mean path errors and attrition.

Writes results/extensions/<u>/.

Usage: uv run python -I scripts/run_extensions.py books|starve|paths [--underlying spx|spy|aapl|nvda|tsla|qqq|slv]
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252

from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project import ruleset as RS  # noqa: E402
from erdos_quant_finance_project.processed import CONTRACT_KEY, nyse_sessions  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

MODE = sys.argv[1]
U = sys.argv[sys.argv.index("--underlying") + 1] if "--underlying" in sys.argv else "spx"
INDEX = U in ("spx", "spy")
FIRST_DATA, FIRST_TEST = (2010, "2011-01") if INDEX else (2016, "2017-01")
YEARS = range(FIRST_DATA, 2024)
MONTHS = pd.period_range(FIRST_TEST, "2023-12", freq="M")
OUT = ROOT / "results/extensions" / U
RULES = RS.rules_for(U)
COMPS = RS.comparisons(RULES)
COLS = ["quote_date", "next_session", "am_settled", "settle_date", "strike", "cp", "E7", "next_status", "S_close", "S_close_next",
        "bid", "ask", "bid_size", "ask_size", "bid_next", "ask_next", "bid_size_next", "ask_size_next", "theta", "dV_dF", "F",
        "vega", "vanna", "tau"]
POOLS = ({"2011-2019": range(2011, 2020), "2020": [2020], "2021-2023": range(2021, 2024)} if INDEX else
         {"2017-2019": range(2017, 2020), "2020": [2020], "2021-2023": range(2021, 2024)})


def cols(root: Path) -> list[str]:
    import pyarrow.parquet as pq
    f = next(root.glob(f"underlying={U}/year=*/pairs_*.parquet"))
    names = pq.read_schema(f).names
    return COLS + [c for c in ("div_next", "in_band", "E9") if c in names]


def e9(P: pd.DataFrame) -> pd.DataFrame:
    """§16.15: a pair straddling a split is ineligible (the five underlyings' E9 column)."""
    return P[P.E9.astype(bool)].copy() if "E9" in P else P


def load():
    P = e9(h.load_pairs(YEARS, columns=cols(h.PAIRS_ROOT), underlying=U))
    fr = h.ingredients(P)
    H = RS.heston_inputs(P, fr, YEARS) if U == "spx" else None
    return P, fr, H


def per_session(E: pd.DataFrame, fr: pd.DataFrame, rules, index, square=True) -> pd.DataFrame:
    """Per (session, cp) sums of e² (or e), reindexed to a session index with zeros."""
    v = E[rules].pow(2) if square else E[rules].copy()
    v["cp"], v["session"], v["n"] = fr.loc[E.index, "cp"].to_numpy(), fr.loc[E.index, "session"].to_numpy(), 1
    s = v.groupby(["session", "cp"]).sum()
    return s.reindex(pd.MultiIndex.from_product([index, ["C", "P"]], names=["session", "cp"]), fill_value=0)


def yearly(E: pd.DataFrame, fr: pd.DataFrame, P: pd.DataFrame, rules, comps, label: dict) -> pd.DataFrame:
    rows = []
    yr = P.loc[E.index, "quote_date"].dt.year.to_numpy()
    for year in sorted(np.unique(yr)):
        e = E[yr == year]
        index = pd.DatetimeIndex(np.sort(fr.loc[e.index, "session"].unique()))
        counts = h.bootstrap_counts(index, B=10_000, block=10, seed=2026)
        S = per_session(e, fr, rules, index)
        for cp in ("C", "P"):
            g = RS.session_gains(S.xs(cp, level="cp"), comps, counts)
            rows.append(g.assign(cp=cp, year=year, pairs=int(S.xs(cp, level="cp").n.sum()), **label))
    return pd.concat(rows, ignore_index=True)


def medians(G: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    out = []
    first = 2011 if INDEX else 2017
    for span, lo in ((f"{first}-2023", first), ("2015-2023", 2015)):
        if not INDEX and span == "2015-2023":
            continue
        m = G[G.year >= lo].groupby(by + ["cp", "rule", "base"]).gain.median().rename("median_yearly_gain").reset_index()
        out.append(m.assign(span=span))
    return pd.concat(out, ignore_index=True)


# --- §16.14 books --------------------------------------------------------------------------------------

def books() -> None:
    with timed("ext_books", inputs=f"{U} W12, §16.14") as log:
        P, fr, H = load()
        prm9 = RS.r9_params(U)
        E, _ = RS.walk(fr, P, MONTHS, 12, prm9, H)
        log["rows_in"] = len(E)
        cp, K, F = P.loc[E.index, "cp"].to_numpy(), P.loc[E.index, "strike"].to_numpy(float), P.loc[E.index, "F"].to_numpy(float)
        otm_c, otm_p = (cp == "C") & (K >= F), (cp == "P") & (K <= F)
        BOOKS = {"calls": (cp == "C", np.ones(len(E))), "puts": (cp == "P", np.ones(len(E))),
                 "long_vol": (otm_c | otm_p, np.ones(len(E))), "risk_reversal": (otm_c | otm_p, np.where(otm_c, 1.0, -1.0))}
        sess = fr.loc[E.index, "session"].to_numpy()
        yr = pd.DatetimeIndex(sess).year.to_numpy()
        rows, shares = [], []
        for name, (mem, w) in BOOKS.items():
            e = E.loc[mem, RULES].mul(w[mem], axis=0)
            s = sess[mem]
            Bt = e.groupby(s).mean()                                  # the book's error per session (weights 1/N_t)
            per = E.loc[mem, RULES].pow(2).groupby(s).sum()           # the per-option sums on the same members
            msq = E.loc[mem, RULES].pow(2).groupby(s).mean()
            for year in sorted(np.unique(yr[mem])):
                idx = pd.DatetimeIndex(Bt.index[pd.DatetimeIndex(Bt.index).year == year])
                counts = h.bootstrap_counts(idx, B=10_000, block=10, seed=2026)
                for measure, S in (("book", Bt.loc[idx] ** 2), ("per_option", per.loc[idx])):
                    rows.append(RS.session_gains(S, COMPS, counts).assign(book=name, measure=measure, year=year, sessions=len(idx)))
                shares.append({"book": name, "year": year, "common_share_R1": float((Bt.loc[idx, "R1"] ** 2).sum() / msq.loc[idx, "R1"].sum()),
                               "members": int(mem[yr == year].sum())})
        OUT.mkdir(parents=True, exist_ok=True)
        G = pd.concat(rows, ignore_index=True)
        G.to_csv(OUT / "books_by_year.csv", index=False)
        pd.DataFrame(shares).to_csv(OUT / "books_common_share.csv", index=False)
        med = G.groupby(["book", "measure", "rule", "base"]).gain.median().rename("median_yearly_gain").reset_index()
        med.to_csv(OUT / "books_median_yearly_gain.csv", index=False)
        log["rows_out"] = len(G)
        print(med[(med.base == "R1") & med.rule.isin(["R2", "P0", "R4", "H_mv"])].pivot_table(index=["book", "rule"], columns="measure", values="median_yearly_gain").round(3).to_string())


# --- §16.13 starvation -----------------------------------------------------------------------------------

def starve() -> None:
    with timed("ext_starve", inputs=f"{U} §16.13") as log:
        P, fr, H = load()
        prm9 = RS.r9_params(U)
        E0, _ = RS.walk(fr, P, MONTHS, 12, prm9, H)
        configs = [("W12", 12, 150, None, None)]
        configs += [(f"W{W}", W, math.ceil(0.7 * 21 * W), None, None) for W in (1, 2, 3, 6)]
        configs += [(f"{m}{v}", 12, 150, (m, v), s) for (m, v) in (("frac", 0.25), ("frac", 0.05), ("frac", 0.01), ("k", 10), ("k", 3))
                    for s in range(2026, 2031)]
        fitted = [r for r in RULES if r not in ("R0", "R1", "R3", "H_model", "H_mv")]
        comps = COMPS + [(r, "R2full") for r in fitted]
        out = []
        for name, W, mins, thin, seed in configs:
            E = E0 if name == "W12" else RS.walk(fr, P, MONTHS, W, prm9, H, min_sessions=mins, thin=thin, seed=seed)[0]
            E = E.join(E0.R2.rename("R2full"), how="inner")
            out.append(yearly(E, fr, P, RULES + ["R2full"], comps, {"config": name, "window": W, "seed": seed if seed else 0}))
            print(name, seed, len(E), "test pairs", flush=True)
        OUT.mkdir(parents=True, exist_ok=True)
        G = pd.concat(out, ignore_index=True)
        G.to_csv(OUT / "starve_by_year.csv", index=False)
        med = medians(G, ["config", "seed"])
        med.to_csv(OUT / "starve_median_yearly_gain.csv", index=False)
        spread = med.groupby(["config", "span", "cp", "rule", "base"]).median_yearly_gain.agg(["min", "median", "max"]).reset_index()
        spread.to_csv(OUT / "starve_seed_spread.csv", index=False)
        log["rows_out"] = len(G)
        show = spread[(spread.base == "R1") & spread.rule.isin(["R2", "P0", "R9"]) & (spread.span == spread.span.iloc[0])]
        print(show.pivot_table(index=["config"], columns=["rule", "cp"], values="median").round(3).to_string())


# --- §16.11 held positions -------------------------------------------------------------------------------

def paths() -> None:
    with timed("ext_paths", inputs=f"{U} H 5 10, §16.11") as log:
        P, fr, H = load()
        prm9 = RS.r9_params(U)
        Ew, fits = RS.walk(fr, P, MONTHS, 12, prm9, H, keep_fits=True)
        wkey = P.loc[Ew.index, CONTRACT_KEY + ["quote_date"]].assign(R2_walk=Ew.R2.to_numpy())
        for c in ("quote_date", "settle_date"):
            wkey[c] = pd.to_datetime(wkey[c]).astype("datetime64[ns]")
        day0_check = []
        start_ok = fr.avail if H is None else fr.avail & H.have
        nyse = nyse_sessions("2009-11-01", "2024-03-31").index
        nyse = nyse[nyse >= MONTHS[0].to_timestamp()]
        any_root = ROOT / "data/processed/pairs_any" / f"underlying={U}"
        acols = cols(ROOT / "data/processed/pairs_any")
        OUT.mkdir(parents=True, exist_ok=True)
        results, means, attr = [], [], []
        for Hn in (5, 10):
            grid = nyse[::Hn]
            pos = {s: i for i, s in enumerate(nyse)}
            day_rows = []
            for year in sorted(set(grid.year)):
                if year > 2023:
                    continue
                g_year = grid[(grid.year == year)]
                st = P.loc[start_ok & P.quote_date.isin(g_year), CONTRACT_KEY + ["quote_date"]].copy()
                st["end2"] = [nyse[pos[d] + Hn] if pos[d] + Hn < len(nyse) else pd.NaT for d in st.quote_date]
                st["eligible"] = pd.to_datetime(st.settle_date) > st.end2
                attr.append({"H": Hn, "year": year, "starts_candidates": len(st), "eligible": int(st.eligible.sum())})
                st = st[st.eligible].reset_index(drop=True)
                st["path"] = np.arange(len(st)) + (year * 10_000_000)
                A = pd.concat([pd.read_parquet(any_root / f"year={y}" / f"pairs_{y}.parquet", columns=acols)
                               for y in (year, year + 1) if (any_root / f"year={y}").exists()], ignore_index=True)
                A = e9(A[A.next_status == "ok"])
                A = A.merge(st[CONTRACT_KEY].drop_duplicates(), on=CONTRACT_KEY, how="inner").reset_index(drop=True)
                fa = h.ingredients(A)
                HA = RS.heston_inputs(A, fa, [y for y in (year, year + 1) if y <= 2023]) if U == "spx" else None
                key = A[CONTRACT_KEY + ["quote_date"]].assign(row=np.arange(len(A)))
                for k in range(Hn):
                    tgt = st[CONTRACT_KEY + ["path"]].assign(quote_date=[nyse[pos[d] + k] for d in st.quote_date], k=k)
                    day_rows.append(tgt.merge(key, on=CONTRACT_KEY + ["quote_date"], how="left").assign(year=year, block=len(day_rows)))
                # errors for every matched day, with that day's month's fits
                D = pd.concat(day_rows[-Hn:], ignore_index=True)
                D = D[D.row.notna()].astype({"row": int})
                Dr = fa.iloc[D.row.to_numpy()].copy()
                Dr.index = D.index
                Dr["month"] = pd.to_datetime(A.quote_date.iloc[D.row.to_numpy()].to_numpy()).to_period("M").astype(str)
                ok = Dr.avail.to_numpy()
                E = pd.DataFrame(np.nan, index=D.index, columns=RULES)
                for (m, cp), grp in Dr[ok].groupby(["month", "cp"]):
                    f = fits.get((m, cp))
                    if f is None:
                        continue
                    Hd = None if HA is None else HA.iloc[D.row[grp.index].to_numpy()].set_axis(grp.index)
                    e = RS.errors(f, grp, Hd if Hd is None else Hd.where(Hd.have), cp)
                    E.loc[grp.index, e.columns] = e.to_numpy()
                # check: on day 0 the path's error is the walk-forward's error on the same pair
                z = D[D.k == 0][CONTRACT_KEY + ["quote_date"]].assign(R2_path=E.R2[D.k == 0].to_numpy())
                for c in ("quote_date", "settle_date"):
                    z[c] = pd.to_datetime(z[c]).astype("datetime64[ns]")
                z = z.merge(wkey, on=CONTRACT_KEY + ["quote_date"], how="inner")
                day0_check.append({"H": Hn, "year": year, "matched": len(z), "max_abs_diff": float((z.R2_path - z.R2_walk).abs().max())})
                S1 = A.S_close.iloc[D.row.to_numpy()].to_numpy(float)
                D = D.join(E.mul(S1, axis=0).add_prefix("d_")).join(E.pow(2).add_prefix("q_"))
                D["in_band"] = A.in_band.iloc[D.row.to_numpy()].to_numpy() if "in_band" in A else True
                D["S"] = S1
                # one row per path: complete when every day matched and every non-Heston rule has an error
                gp = D.groupby("path")
                days = gp.size()
                base_ok = gp[[f"d_{r}" for r in RULES if not r.startswith("H_")]].count().min(axis=1) == days
                heston_ok = (gp[[f"d_{r}" for r in RULES if r.startswith("H_")]].count().min(axis=1) == days) if U == "spx" else base_ok
                comp = (days == Hn) & base_ok
                S0 = st.set_index("path").loc[comp.index, "quote_date"]
                first_S = gp.S.first()
                R = gp[[c for c in D.columns if c.startswith("d_")]].sum().div(first_S, axis=0)          # E = Σ S_k e_k / S_0
                R.columns = [c[2:] for c in R.columns]
                Q = gp[[c for c in D.columns if c.startswith("q_")]].sum()
                Q.columns = [c[2:] for c in Q.columns]
                info = pd.DataFrame({"start": S0, "cp": st.set_index("path").loc[comp.index, "cp"], "complete": comp,
                                     "heston_complete": comp & heston_ok, "left_band": ~gp.in_band.all()})
                for sub, m in (("all", info.complete), ("heston", info.heston_complete)):
                    if sub == "heston" and U != "spx":
                        continue
                    sel = m[m].index
                    results.append(dict(H=Hn, year=year, subset=sub, R=R.loc[sel], Q=Q.loc[sel], info=info.loc[sel], grid=g_year))
                attr[-1].update(complete=int(comp.sum()), left_band=int((comp & info.left_band).sum()),
                                heston_complete=int((comp & heston_ok).sum()) if U == "spx" else None)
                day_rows = []
                print(U, "H", Hn, year, "eligible", len(st), "complete", int(comp.sum()), flush=True)
        # gains per year and pooled, over start sessions in blocks of max(1, round(10/H))
        rows = []
        groups = [(r["H"], r["subset"], str(r["year"]), [r]) for r in results]
        for Hn in (5, 10):
            for sub in ("all", "heston"):
                for pname, yrs in POOLS.items():
                    sel = [r for r in results if r["H"] == Hn and r["subset"] == sub and r["year"] in yrs]
                    if sel and (len(yrs) > 1):
                        groups.append((Hn, sub, pname, sel))
        for Hn, sub, period, sel in groups:
            Rr = pd.concat([r["R"] for r in sel]); Qq = pd.concat([r["Q"] for r in sel]); In = pd.concat([r["info"] for r in sel])
            # every start session of the grid in the period, including those with no complete path (zero rows)
            index = pd.DatetimeIndex(np.sort(np.unique(np.concatenate([np.asarray(r["grid"]) for r in sel]))))
            counts = h.bootstrap_counts(index, B=10_000, block=max(1, round(10 / Hn)), seed=2026)
            rules = [r for r in RULES if Rr[r].notna().all()]
            comps = [c for c in COMPS if c[0] in rules and c[1] in rules]
            for cp in ("C", "P"):
                m = (In.cp == cp).to_numpy()
                key = pd.Series(In.start.to_numpy()[m])
                SE = (Rr[m][rules] ** 2).groupby(key.to_numpy()).sum().reindex(index, fill_value=0)
                S1 = Qq[m][rules].groupby(key.to_numpy()).sum().reindex(index, fill_value=0)
                SM = Rr[m][rules].groupby(key.to_numpy()).sum().reindex(index, fill_value=0)
                N = pd.Series(1, index=key.to_numpy()).groupby(level=0).sum().reindex(index, fill_value=0).to_numpy(float)
                for measure, S in (("path", SE), ("one_session", S1)):
                    rows.append(RS.session_gains(S, comps, counts).assign(H=Hn, subset=sub, period=period, cp=cp, measure=measure,
                                                                          paths=int(m.sum())))
                cn = counts @ N
                for r in rules:
                    mu = SM[r].to_numpy().sum() / N.sum()
                    d = (counts @ (SM[r].to_numpy() - SM["R1"].to_numpy())) / cn
                    means.append({"H": Hn, "subset": sub, "period": period, "cp": cp, "rule": r, "mean_path_error": mu,
                                  "diff_vs_R1": (SM[r].to_numpy() - SM["R1"].to_numpy()).sum() / N.sum(),
                                  "diff_lo": np.quantile(d, 0.025), "diff_hi": np.quantile(d, 0.975), "paths": int(m.sum())})
        G = pd.concat(rows, ignore_index=True)
        G.to_csv(OUT / "paths_gains.csv", index=False)
        pd.DataFrame(means).to_csv(OUT / "paths_mean_error.csv", index=False)
        pd.DataFrame(attr).to_csv(OUT / "paths_attrition.csv", index=False)
        pd.DataFrame(day0_check).to_csv(OUT / "paths_day0_check.csv", index=False)
        print("day-0 check, max |path − walk| R2 error:", pd.DataFrame(day0_check).max_abs_diff.max(), flush=True)
        log["rows_out"] = len(G)
        show = G[(G.subset == "all") & (G.base == "R1") & G.rule.isin(["R2", "P0", "R3"]) & G.period.isin(list(POOLS))]
        print(show.pivot_table(index=["H", "period", "rule"], columns=["cp", "measure"], values="gain").round(3).to_string())


if __name__ == "__main__":
    {"books": books, "starve": starve, "paths": paths}[MODE]()
