"""R9–R11, the boosted learner decomposed (analysis_plan.md §16.7), on SPX or (--spy) SPY.

  R9  δ + ν/(S√τ)·h(δ)                      LightGBM from the target's mean, δ only
  R10 δ + ν/(S√τ)·h(z)                      LightGBM from the target's mean, R8's features
  R11 δ + ν/(S√τ)·[a + bδ + cδ² + h(δ)]     LightGBM boosted from R2's polynomial, δ only
(R8, boosted from R2 on z, completes the 2×2.) Hyperparameters frozen from tune_r8.py --rule ...

Mode `year YEAR`: the primary (feature-complete pairs, against R1, R2 and the primary R8 from
learner_hedges.parquet) and the Table 8.1 variants as in run_learners_variants.py. Writes
<outdir>/r9_r11.csv. Mode `walkforward`: W12, W36 and W60, 2011–2023, against R1 and R2 (all-pairs fit) on
the feature-complete pairs, 2010 tuning to 2016-12 and 2015–2016 tuning from 2017-01. Writes
walkforward/r9_r11_by_year.csv and r9_r11_median_yearly_gain.csv.

Usage: uv run python -I scripts/run_r9_r11.py year 2020 [--spy]
       uv run python -I scripts/run_r9_r11.py walkforward [--spy]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project import learners as L  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

U = "spy" if "--spy" in sys.argv else "spx"
BASE = ROOT / "results" / ("spy" if U == "spy" else "")
NEW = ["R9", "R10", "R11"]


def params(tag: str) -> dict:
    return {r: json.loads((BASE / "rehearsal" / f"{r.lower()}_params_{tag}.json").read_text()) for r in NEW}


def fit_month(d, zd, dt, zt, prm) -> dict:
    return {r: L.lgb_error(r, d, zd, dt, zt, prm[r][dt.cp.iloc[0]]) for r in NEW}


def year_mode(year: int) -> None:
    import run_test_year as T  # reads --spy from sys.argv, as this script does
    out = T.BASE / str(year)
    R = T.Run(year, out)
    P, fr = R.P, R.fr
    prm = params(str(year - 1))
    comps = [(r, b) for r in NEW for b in ("R1", "R2")] + [("R2", "R1")]
    rows = []

    def errors_for(frame, variant_err, months_back=12, frozen=None):
        z = L.features(frame, P)
        ok = L.complete(frame, z)
        out_ = []
        for m in R.months:
            s0 = P.quote_date[P.quote_date.dt.to_period("M") == m].min()
            tr_all = ok & h.training_mask(P.quote_date, P.next_session, s0, months_back, frozen)
            assert (P.next_session[tr_all] < (s0 if frozen is None else frozen)).all(), "look-ahead"
            te_all = ok & (P.quote_date.dt.to_period("M") == m) & frame.index.isin(variant_err.index)
            for cp in "CP":
                tr, te = tr_all & (frame.cp == cp), te_all & (frame.cp == cp)
                if not te.any():
                    continue
                e = variant_err.loc[frame[te].index, ["R1", "R2", "month"]].copy()
                for r, v in fit_month(frame[tr], z[tr], frame[te], z[te], prm).items():
                    e[r] = v
                out_.append(e)
        return pd.concat(out_)

    def add(label, E, frame, counts=None, extra=()):
        rules = list(dict.fromkeys(["R1", "R2"] + NEW + [r for c in extra for r in c]))
        g = h.gain_table(h.aligned_sse(E, frame, rules, R.index), comps + list(extra), R.counts if counts is None else counts)
        rows.append(g.assign(variant=label))
        print(label, "done", flush=True)

    with timed("r9_r11_year", inputs=f"{U} {year}, primary and Table 8.1 variants") as log:
        err = pd.read_parquet(out / "errors.parquet")
        Hh = pd.read_parquet(out / "learner_hedges.parquet")
        E0 = errors_for(fr, err)
        E0 = E0.join(Hh[["R8"]], how="inner")  # the primary R8 on the same pairs
        vs8 = [(r, "R8") for r in NEW] + [("R8", "R2")]
        add("primary", E0, fr, extra=vs8)
        q = P.loc[E0.index]
        otm = ((q.cp == "C") & (q.strike >= q.F)) | ((q.cp == "P") & (q.strike <= q.F))
        for label, m in {"S3": q.rel_spread <= 0.05, "V": q.E7_strict.astype(bool), "OTM": otm,
                         "day-two volume > 0": q.volume_next > 0, "day-two volume 0 or empty": ~(q.volume_next > 0)}.items():
            add(label, E0[m.to_numpy()], fr, extra=vs8)
        if year == 2020:
            strata = [(pd.Timestamp("2020-01-01"), pd.Timestamp("2020-02-21")), h.STRESS, (pd.Timestamp("2020-05-01"), pd.Timestamp("2020-12-31"))]
            sc = h.bootstrap_counts(R.index, B=10_000, block=10, seed=2026, strata=strata)
            stress = q.quote_date.between(*h.STRESS).to_numpy()
            add("stress", E0[stress], fr, sc, extra=vs8)
            add(f"rest of {year}", E0[~stress], fr, sc, extra=vs8)
        for b in (5, 20):
            add(f"primary, block {b}", E0, fr, h.bootstrap_counts(R.index, B=10_000, block=b, seed=2026), extra=vs8)
        for label, kw in [("A", {"level": "A"}), ("B", {"level": "B"}), ("P-bid", {"mark": "bid"}), ("P-ask", {"mark": "ask"}),
                          ("P-WM", {"mark": "wm"}), ("P-SW", {"mark": "sw"}), ("T", {"theta": True})]:
            if U == "spy" and label == "A":
                continue
            f2 = h.ingredients(P, **kw)
            f2["avail"] &= fr.avail
            add(label, errors_for(f2, R.fit(f2, rules=["R2", "R4"], label=label)), f2)
        unblind = pd.Timestamp(f"{year}-01-02") if year != 2020 else h.UNBLIND
        add("F", errors_for(fr, R.fit(fr, frozen=unblind, rules=["R2", "R4"], label="F"), frozen=unblind), fr)
        for W in (36, 60):
            add(f"W{W}", errors_for(fr, R.fit(fr, window=h.Window(W), rules=["R2", "R4"], label=f"W{W}"), months_back=W), fr)
        G = pd.concat(rows, ignore_index=True)
        G.to_csv(out / "r9_r11.csv", index=False)
        log["rows_out"] = len(G)
        print(G[G.base.isin(["R2", "R8"])].pivot_table(index="variant", columns=["rule", "base", "cp"], values="gain").round(3).to_string())


def walkforward_mode() -> None:
    early, late = params("2010"), params("2015_2016")
    start = {12: "2011-01", 36: "2013-01", 60: "2015-01"}
    with timed("r9_r11_walkforward", inputs=f"{U} 2010-2023, W12 W36 W60") as log:
        P = h.load_pairs(range(2010, 2024), underlying=U)
        fr = h.ingredients(P)
        z = L.features(fr, P)
        ok = L.complete(fr, z)
        day1, day2, month = P.quote_date, P.next_session, P.quote_date.dt.to_period("M")
        log["rows_in"] = len(P)
        rows = []
        for W, st in start.items():
            E = []
            for m in pd.period_range(st, "2023-12", freq="M"):
                s0 = day1[month == m].min()
                if pd.isna(s0):
                    continue
                tr_all = fr.avail & h.training_mask(day1, day2, s0, W)
                assert (day2[tr_all] < s0).all(), "look-ahead: a training pair ends in the test period"
                prm = early if m <= pd.Period("2016-12", "M") else late
                for cp in "CP":
                    tr, te = tr_all & (fr.cp == cp), fr.avail & (month == m) & (fr.cp == cp)
                    if not te.any() or fr[tr].session.nunique() < 150:
                        continue
                    beta = h.ols(*h.design("R2", fr[tr]))  # R2's all-pairs fit, as in §16.4
                    trc, tec = tr & ok, te & ok
                    if not tec.any() or beta is None:
                        continue
                    dt = fr[tec]
                    e = pd.DataFrame({"R1": dt.y.to_numpy(), "R2": (dt.y - h.design("R2", dt)[0] @ beta).to_numpy(), "month": str(m)},
                                     index=dt.index)
                    for r, v in fit_month(fr[trc], z[trc], dt, z[tec], prm).items():
                        e[r] = v
                    E.append(e)
                if m.month == 12:
                    print(f"W{W} {m} done", flush=True)
            E = pd.concat(E)
            yr = P.loc[E.index, "quote_date"].dt.year
            for year in sorted(yr.unique()):
                e = E[(yr == year).to_numpy()]
                index = pd.DatetimeIndex(np.sort(fr.loc[e.index, "session"].unique()))
                g = h.gain_table(h.aligned_sse(e, fr, ["R1", "R2"] + NEW, index), [(r, b) for r in NEW for b in ("R1", "R2")] + [("R2", "R1")],
                                 h.bootstrap_counts(index, B=10_000, block=10, seed=2026))
                rows.append(g.assign(window=W, year=year, months=e.month.nunique()))
        G = pd.concat(rows, ignore_index=True)
        out = BASE / "walkforward"
        G.to_csv(out / "r9_r11_by_year.csv", index=False)
        med = G[G.year >= 2015].groupby(["window", "cp", "rule", "base"]).gain.median().rename("median_yearly_gain").reset_index()
        med.to_csv(out / "r9_r11_median_yearly_gain.csv", index=False)
        log["rows_out"] = len(G)
        print(med.round(3).to_string(index=False))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--spy"]
    if args[0] == "year":
        year_mode(int(args[1]))
    else:
        walkforward_mode()
