"""Evaluate a test year (analysis_plan.md §6–§9): the primary and secondary endpoints, every Table 8.1
variant, the verdict and its robustness, the descriptives, the attribution, and R7/R8.

The confirmatory run is 2020. The same script runs first on 2019 (a dry run on training data, with the
2019-12-31 pairs excluded) so that no code is debugged with 2020 results in view.

Usage: uv run python -I scripts/run_test_year.py YEAR PLAN_COMMIT [OUTDIR]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import diagnostics as dg  # noqa: E402
from erdos_quant_finance_project import endpoints as ep  # noqa: E402
from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project import learners as L  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402
from erdos_quant_finance_project.verdict import secondary_tests, verdict  # noqa: E402

RULES = ["R0", "R1", "R2", "R3", "R4", "R5", "R6"]
REQUIRED = ["R0", "R1", "R2", "R3", "R4"]
COMPS = [("R2", "R1"), ("R2", "R3"), ("R2", "R4"), ("R1", "R0"), ("R2", "R0"), ("R3", "R1"), ("R4", "R1"), ("R5", "R1"), ("R6", "R1")]


class Run:
    def __init__(self, year: int, out: Path):
        self.year, self.out = year, out
        self.months = pd.period_range(f"{year}-01", f"{year}-12", freq="M")
        P = h.load_pairs(range(year - 5, year + 1))
        if year < 2020:
            P = P[P.next_session < h.UNBLIND]  # a dry run must not touch 2020 outcomes
        self.P = P
        self.T = P.quote_date.dt.year == year
        self.fr = h.ingredients(P)
        self.vanished = ep.vanished(year)
        if year < 2020:
            self.vanished = self.vanished[self.vanished.next_session < h.UNBLIND]
        self.index = pd.DatetimeIndex(np.sort(pd.unique(np.concatenate([P.quote_date[self.T].unique(), self.vanished.quote_date.unique()]))))
        self.counts = h.bootstrap_counts(self.index, B=10_000, block=10, seed=2026)
        self.gains, self.verdicts, self.coefs, self.coverage = [], [], [], []

    def fit(self, frame, window=h.Window(12), frozen=None, rules=h.FITTED, label=""):
        err, coefs = h.walk_forward(frame, self.P, self.months, window, rules=rules, frozen=frozen)
        months = err.join(frame[["cp"]]).groupby("cp").month.nunique() if len(err) else pd.Series(dtype=int)
        for cp in "CP":
            n = int(months.get(cp, 0))
            self.coverage.append({"variant": label, "cp": cp, "months": n})
            if n < 12:
                print(f"WARNING: {label} {cp} has {n} of 12 months", flush=True)
        self.coefs.append(coefs.assign(variant=label))
        return err

    def add(self, label, err, frame, subset=None, counts=None, robust=False, comps=COMPS):
        e = err if subset is None else err[subset.reindex(err.index, fill_value=False)]
        assert e[REQUIRED].notna().all().all(), f"{label}: a required rule has missing errors"
        ok = [c for c in comps if e[c[0]].notna().all() and e[c[1]].notna().all()]
        rules = [r for r in dict.fromkeys(RULES + [r for c in comps for r in c]) if r in e]
        sse = h.aligned_sse(e, frame, rules, self.index)
        g = h.gain_table(sse, ok, self.counts if counts is None else counts)
        g.insert(0, "variant", label)
        self.gains.append(g)
        for c in set(comps) - set(ok):  # a failed R5/R6 fit: compared on its own non-missing pairs
            ee = e[e[c[0]].notna() & e[c[1]].notna()]
            gg = h.gain_table(h.aligned_sse(ee, frame, list(c), self.index), [c], self.counts if counts is None else counts)
            self.gains.append(gg.assign(variant=f"{label} (rule-specific sample)"))
        if robust:
            self.verdicts.append({"variant": label, **verdict(g)})
        return g, sse


def main(year: int, plan_commit: str, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    with timed(f"test_year_{year}", inputs=f"spx {year}", notes=f"plan {plan_commit}") as log:
        R = Run(year, out)
        P, fr, T = R.P, R.fr, R.T
        log["rows_in"] = int(T.sum())

        # --- the primary
        err = R.fit(fr, label="primary")
        err.to_parquet(out / "errors.parquet")
        g, sse_primary = R.add("primary", err, fr, robust=True)
        secondary_tests(g).to_csv(out / "secondary.csv", index=False)
        log["rows_out"] = len(err)

        # --- Table 8.1: refitted measurement variants, each with the primary on its intersection
        for label, kw in [("A", {"level": "A"}), ("B", {"level": "B"}), ("P-bid", {"mark": "bid"}), ("P-ask", {"mark": "ask"}),
                          ("P-WM", {"mark": "wm"}), ("P-SW", {"mark": "sw"}), ("T", {"theta": True})]:
            f2 = h.ingredients(P, **kw)
            f2["avail"] &= fr.avail
            e2 = R.fit(f2, label=label)
            R.add(label, e2, f2, robust=label in ("A", "B", "P-bid", "P-ask"))
            R.add(f"primary on {label} sample", err, fr, subset=f2.avail)
            if label == "T":
                gap = (P.next_session - P.quote_date).dt.days
                pd.concat([e2.join(gap.rename("gap")).groupby("gap")[RULES].mean().assign(variant="T"),
                           err.join(gap.rename("gap")).groupby("gap")[RULES].mean().assign(variant="primary")]).to_csv(out / "mean_error_by_gap.csv")
        R.add("F", R.fit(fr, frozen=pd.Timestamp(f"{year}-01-02") if year != 2020 else h.UNBLIND, label="F"), fr, robust=True)
        for W in (36, 60):
            R.add(f"W{W}", R.fit(fr, window=h.Window(W), label=f"W{W}"), fr, robust=True)

        # --- subsamples under the primary fits
        q = P.loc[err.index]
        otm = ((q.cp == "C") & (q.strike >= q.F)) | ((q.cp == "P") & (q.strike <= q.F))
        R.add("S3", err, fr, subset=q.rel_spread <= 0.05, robust=True)
        R.add("V", err, fr, subset=q.E7_strict)
        R.add("OTM", err, fr, subset=otm)
        R.add("day-two volume > 0", err, fr, subset=q.volume_next > 0)
        R.add("day-two volume 0 or empty", err, fr, subset=~(q.volume_next > 0))
        # OTM-refit: R2 and R4 refitted on out-of-the-money training pairs; R5 and R6 keep the primary fits
        Potm = ((P.cp == "C") & (P.strike >= P.F)) | ((P.cp == "P") & (P.strike <= P.F))
        fo = fr.copy()
        fo["avail"] &= Potm
        eo = R.fit(fo, rules=["R2", "R4"], label="OTM-refit")
        eo[["R5", "R6"]] = err.loc[eo.index, ["R5", "R6"]]
        R.add("OTM-refit", eo, fo, subset=otm.reindex(eo.index, fill_value=False))
        if year == 2020:
            strata = [(pd.Timestamp("2020-01-01"), pd.Timestamp("2020-02-21")), h.STRESS, (pd.Timestamp("2020-05-01"), pd.Timestamp("2020-12-31"))]
            sc = h.bootstrap_counts(R.index, B=10_000, block=10, seed=2026, strata=strata)
            stress = q.quote_date.between(*h.STRESS)
            R.add("stress", err, fr, subset=stress, counts=sc)
            R.add("rest of 2020", err, fr, subset=~stress, counts=sc, robust=True)

        # --- endpoint scenarios for vanished quotes (primary fits, unchanged)
        coefs = R.coefs[0]
        if len(R.vanished):
            for scen in ("low", "high"):
                ev = ep.scenario(R.vanished, coefs, scen)
                R.add(f"endpoint {scen}", pd.concat([err, ev[err.columns]]), pd.concat([fr, ev.attrs["frame"]]), robust=True)
            for base in ("R1", "R3", "R4"):
                ev = ep.scenario(R.vanished, coefs, "adversarial", comparator=base)
                R.add(f"endpoint adversarial vs {base}", pd.concat([err, ev[err.columns]]), pd.concat([fr, ev.attrs["frame"]]),
                      comps=[("R2", base)])
            R.vanished.band_kind.value_counts().to_csv(out / "vanished_band_kinds.csv")

        # --- block-length checks
        for b in (5, 20):
            R.add(f"primary, block {b}", err, fr, counts=h.bootstrap_counts(R.index, B=10_000, block=b, seed=2026))

        # --- R7 and R8 on the feature-complete subsample, against the primary R2 there
        params = json.loads((ROOT / "results/rehearsal/r8_params_2019.json").read_text()) if (ROOT / "results/rehearsal/r8_params_2019.json").exists() else None
        learners(R, err, params)

        # --- specification variants that contradicted R2's form in the rehearsal, carried as exploratory rules
        carried = carried_variants()
        if carried:
            ec = R.fit(fr, rules=["R2", "R4"] + carried, label="carried variants")
            R.add("carried variants", ec.assign(R5=err.R5, R6=err.R6), fr, comps=[(c, "R2") for c in carried] + [("R2", "R1")])

        pd.concat(R.gains, ignore_index=True).to_csv(out / "gains.csv", index=False)
        pd.DataFrame(R.verdicts).to_csv(out / "verdict.csv", index=False)
        pd.concat(R.coefs).to_csv(out / "coefficients.csv", index=False)
        pd.DataFrame(R.coverage).to_csv(out / "coverage.csv", index=False)
        descriptives(R, err, sse_primary)
        stability(R)
        ceiling_and_monitoring(R, err)
        attribution(R, err)
        print(pd.DataFrame(R.verdicts).to_string(index=False), flush=True)


def learners(R: Run, err: pd.DataFrame, params) -> None:
    P, fr = R.P, R.fr
    z = L.features(fr, P)
    ok = L.complete(fr, z)
    rows, hedges = [], []
    for m in R.months:
        s0 = P.quote_date[P.quote_date.dt.to_period("M") == m].min()
        tr_all = ok & h.training_mask(P.quote_date, P.next_session, s0, 12)
        te_all = ok & (P.quote_date.dt.to_period("M") == m) & fr.index.isin(err.index)
        for cp in "CP":
            tr, te = tr_all & (fr.cp == cp), te_all & (fr.cp == cp)
            if not te.any():
                continue
            d, dt = fr[tr], fr[te]
            tree = L.fit_tree(d, z[tr])
            e7 = L.tree_error(tree, dt, z[te])
            g7 = tree.predict(z[te].to_numpy())
            out = pd.DataFrame({"R7": e7, "h_R7": dt.delta + dt.vega_n / dt.sqrt_tau * g7}, index=dt.index)
            if params:
                mb = L.fit_boost(d, z[tr], params[cp])
                out["R8"] = L.boost_error(mb, dt, z[te])
                g8 = h.poly(dt.delta.to_numpy()) @ mb[1] + mb[0].predict(z[te].to_numpy(), raw_score=True)
                out["h_R8"] = dt.delta + dt.vega_n / dt.sqrt_tau * g8
            hedges.append(out)
    H = pd.concat(hedges).join(err[["R1", "R2", "month"]])
    # R2's hedge ratio, from the primary errors: h = (f − e)/(ΔS/S)
    dsn = fr.loc[H.index, "dSn"].replace(0, np.nan)
    H["h_R2"] = (fr.loc[H.index, "f"] - H.R2) / dsn
    comps = [("R7", "R2"), ("R2", "R1")] + ([("R8", "R2"), ("R8", "R7")] if params else [])
    rules = ["R1", "R2", "R7"] + (["R8"] if params else [])
    sse = h.aligned_sse(H, fr, rules, R.index)
    g = h.gain_table(sse, comps, R.counts)
    g.insert(0, "variant", "learners (feature-complete)")
    R.gains.append(g)
    H.to_parquet(R.out / "learner_hedges.parquet")
    H["h_R1"] = fr.loc[H.index, "delta"]
    smoothness(H, P, [r for r in ("h_R1", "h_R2", "h_R7", "h_R8") if r in H], R.out)


def smoothness(H: pd.DataFrame, P: pd.DataFrame, cols: list[str], out: Path) -> None:
    """Out-of-order adjacent strikes (hedge ratios should fall as K rises) and mean daily |Δh| per contract."""
    q = P.loc[H.index, ["quote_date", "am_settled", "settle_date", "strike", "cp", "next_session"]].join(H[cols])
    rows = []
    for c in cols:
        s = q.sort_values(["quote_date", "am_settled", "settle_date", "cp", "strike"])
        dh = s.groupby(["quote_date", "am_settled", "settle_date", "cp"])[c].diff()
        k = ["am_settled", "settle_date", "strike", "cp"]
        nxt = q[["quote_date"] + k + [c]].rename(columns={"quote_date": "next_session", c: "h2"})
        j = q[["next_session"] + k + [c]].merge(nxt, on=["next_session"] + k)
        rows.append({"rule": c, "adjacent_pairs": int(dh.notna().sum()), "out_of_order_share": float((dh > 1e-12).sum() / dh.notna().sum()),
                     "mean_daily_abs_change": float((j.h2 - j[c]).abs().mean())})
    pd.DataFrame(rows).to_csv(out / "smoothness.csv", index=False)


def carried_variants() -> list[str]:
    out = []
    for y in (2018, 2019):
        f = ROOT / f"results/rehearsal/spec_checks_{y}.csv"
        if f.exists():
            s = pd.read_csv(f)
            for r in s[s.contradicts].itertuples():
                out.append(r.check.split(" vs ")[0].replace("degree 3", "deg:3"))
    return sorted(set(out))


def descriptives(R: Run, err, sse):
    P, fr, out = R.P, R.fr, R.out
    q = P.loc[err.index]
    e = err.join(fr[["cp"]])
    rows = []
    for cp in "CP":
        d, dq, s = e[e.cp == cp], q[q.cp == cp], sse.xs(cp, level="cp")
        stress_share = s.loc[(s.index >= h.STRESS[0]) & (s.index <= h.STRESS[1]), "R1"].sum() / s.R1.sum()
        for r in RULES:
            rows.append({"cp": cp, "rule": r, "pairs": len(d), "sse": (d[r] ** 2).sum(), "mean_error": d[r].mean(),
                         "rms_dollars_per_contract": np.sqrt(((d[r] * dq.S_close) ** 2).mean()) * 100,
                         "effectiveness_vs_R0": 1 - (d[r] ** 2).sum() / (d.R0 ** 2).sum(), "stress_share_R1": stress_share})
        top = s.R1.sort_values(ascending=False).head(10)
        pd.DataFrame({"session": top.index, "sse_R1": top.values, "share": top.values / s.R1.sum()}).to_csv(out / f"top_sessions_{cp}.csv", index=False)
        m = d.groupby("month")[RULES].apply(lambda x: (x**2).sum())
        mg = pd.DataFrame({"cp": cp, "month": m.index, "G_R2_R1": 1 - m.R2 / m.R1, "G_R4_R1": 1 - m.R4 / m.R1, "G_R3_R1": 1 - m.R3 / m.R1,
                           "rel_R2_R4": 1 - m.R2 / m.R4, "pairs": d.groupby("month").size().values})
        mg.to_csv(out / f"monthly_{cp}.csv", index=False)
        lb = acorr_ljungbox((s.R2 - s.R1).to_numpy(), lags=[5, 10], return_df=True)
        lb.assign(cp=cp).to_csv(out / f"ljungbox_{cp}.csv")
        b = dg.buckets(fr.loc[d.index])
        for col in ("delta_b", "tau_b"):
            bg = d.groupby(b[col])[RULES].apply(lambda x: (x**2).sum())
            pd.DataFrame({"cp": cp, "bucket": bg.index, "pairs": d.groupby(b[col]).size().values, "G_R2_R1": 1 - bg.R2 / bg.R1,
                          "G_R4_R1": 1 - bg.R4 / bg.R1, "G_R3_R1": 1 - bg.R3 / bg.R1}).to_csv(out / f"buckets_{col}_{cp}.csv", index=False)
    pd.DataFrame(rows).to_csv(out / "descriptives.csv", index=False)


def stability(R: Run) -> None:
    """R2's and R4's coefficients at each monthly refit, with session-clustered standard errors."""
    P, fr = R.P, R.fr
    rows = []
    for m in R.months:
        s0 = P.quote_date[P.quote_date.dt.to_period("M") == m].min()
        tr = fr.avail & h.training_mask(P.quote_date, P.next_session, s0, 12)
        for cp in "CP":
            d = fr[tr & (fr.cp == cp)]
            for rule in ("R2", "R4"):
                X, y = h.design(rule, d)
                A = np.linalg.inv(X.T @ X)
                b = A @ X.T @ y
                u = y - X @ b
                sc = pd.DataFrame(X * u[:, None]).groupby(d.session.to_numpy()).sum().to_numpy()
                se = np.sqrt(np.diag(A @ (sc.T @ sc) @ A))
                for k in range(len(b)):
                    rows.append({"month": str(m), "cp": cp, "rule": rule, "k": k, "coef": b[k], "se_clustered": se[k]})
    pd.DataFrame(rows).to_csv(R.out / "stability.csv", index=False)


def ceiling_and_monitoring(R: Run, err):
    fr, out = R.fr, R.out
    rows = []
    for (m, cp), d in err.join(fr[["cp"]]).groupby(["month", "cp"]):
        te = fr.loc[d.index]
        X, y = h.design("R2", te)
        e = y - X @ h.ols(X, y)
        rows.append({"month": m, "cp": cp, "G_ceiling": 1 - (e**2).sum() / (te.y**2).sum(), "G_R2": 1 - (d.R2**2).sum() / (d.R1**2).sum()})
    pd.DataFrame(rows).to_csv(out / "ceiling.csv", index=False)
    s = h.session_sse(err, fr, ["R1", "R2"]).reset_index()
    mon = []
    for cp in "CP":
        x = s[s.cp == cp].set_index("session").sort_index()
        roll = 1 - x.R2.rolling(20).sum() / x.R1.rolling(20).sum()
        # a hedge set on session t is complete at t+1, so the trailing Gain known at t uses sessions up to t − 1
        mon.append(pd.DataFrame({"cp": cp, "session": x.index, "trailing20_gain_known": roll.shift(1).values}))
    pd.concat(mon).to_csv(out / "monitoring.csv", index=False)


def attribution(R: Run, err):
    P, fr = R.P, R.fr
    sub = fr.loc[err.index]
    t = dg.attribution(sub, P)
    stress = P.loc[t.index].quote_date.between(*h.STRESS)
    parts = [dg.attribution_summary(t, sub, ["cp"]).assign(group="all"),
             dg.attribution_summary(t, sub, ["cp", "delta_b"]).assign(group="delta"),
             dg.attribution_summary(t, sub, ["cp", "tau_b"]).assign(group="maturity")]
    if stress.any():
        parts += [dg.attribution_summary(t[stress], sub, ["cp"]).assign(group="stress"),
                  dg.attribution_summary(t[~stress], sub, ["cp"]).assign(group="rest")]
    pd.concat(parts).to_csv(R.out / "attribution.csv", index=False)
    pd.Series({"pairs": len(t), "without_day_two_iv": int((~t.ok).sum())}).to_csv(R.out / "attribution_counts.csv")


if __name__ == "__main__":
    y = int(sys.argv[1])
    main(y, sys.argv[2], Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "results" / str(y))
