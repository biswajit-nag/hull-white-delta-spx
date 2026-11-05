"""R7 and R8 under the Table 8.1 variants of a test year (analysis_plan.md §16.4; SPY under §16.3).

Variants that refit (A, B, P-bid, P-ask, P-WM, P-SW, T, F, W36, W60; A not for SPY): R7 and R8 refitted on
the variant's training data with R8's frozen hyperparameters, compared with that variant's R2 on its
feature-complete pairs. Subsample variants (S3, V, OTM, stress, rest of the year, day-two volume, block
lengths 5 and 20) use the primary R7/R8 hedges (learner_hedges.parquet); OTM-refit compares them with the
OTM-refitted R2. The endpoint scenarios are not run for R7/R8 (plan §16.4).
Writes <outdir>/learners_variants.csv. Run after run_test_year.py for the same year.

Usage: uv run python -I scripts/run_learners_variants.py YEAR [OUTDIR] [--spy]
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

import run_test_year as T  # noqa: E402
from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project import learners as L  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

COMPS = [("R7", "R2"), ("R8", "R2"), ("R7", "R1"), ("R8", "R1"), ("R2", "R1")]


def learner_errors(R, frame, variant_err, params, months_back=12, frozen=None) -> pd.DataFrame:
    """R7 and R8 fitted on `frame`'s training pairs, beside the variant's own R1 and R2, on feature-complete test pairs."""
    P = R.P
    z = L.features(frame, P)
    ok = L.complete(frame, z)
    out = []
    for m in R.months:
        s0 = P.quote_date[P.quote_date.dt.to_period("M") == m].min()
        tr_all = ok & h.training_mask(P.quote_date, P.next_session, s0, months_back, frozen)
        assert (P.next_session[tr_all] < (s0 if frozen is None else frozen)).all(), "look-ahead"
        te_all = ok & (P.quote_date.dt.to_period("M") == m) & frame.index.isin(variant_err.index)
        for cp in "CP":
            tr, te = tr_all & (frame.cp == cp), te_all & (frame.cp == cp)
            if not te.any():
                continue
            d, dt = frame[tr], frame[te]
            e = variant_err.loc[dt.index, ["R1", "R2", "month"]].copy()
            e["R7"] = L.tree_error(L.fit_tree(d, z[tr]), dt, z[te])
            e["R8"] = L.boost_error(L.fit_boost(d, z[tr], params[cp]), dt, z[te])
            out.append(e)
    return pd.concat(out)


def main(year: int, out: Path) -> None:
    R = T.Run(year, out)
    P, fr = R.P, R.fr
    params = json.loads((T.BASE / "rehearsal/r8_params_2019.json").read_text())
    rows = []

    def add(label, E, frame, counts=None):
        index = R.index
        g = h.gain_table(h.aligned_sse(E, frame, ["R1", "R2", "R7", "R8"], index), COMPS, R.counts if counts is None else counts)
        rows.append(g.assign(variant=label))
        print(label, "done", flush=True)

    with timed("learners_variants", inputs=f"{T.U} {year}, R7 R8 under Table 8.1") as log:
        # variants that refit: the variant's own walk-forward gives its R1 and R2
        for label, kw in [("A", {"level": "A"}), ("B", {"level": "B"}), ("P-bid", {"mark": "bid"}), ("P-ask", {"mark": "ask"}),
                          ("P-WM", {"mark": "wm"}), ("P-SW", {"mark": "sw"}), ("T", {"theta": True})]:
            if T.U == "spy" and label == "A":
                continue
            f2 = h.ingredients(P, **kw)
            f2["avail"] &= fr.avail
            e2 = R.fit(f2, rules=["R2", "R4"], label=label)
            add(label, learner_errors(R, f2, e2, params), f2)
        unblind = pd.Timestamp(f"{year}-01-02") if year != 2020 else h.UNBLIND
        eF = R.fit(fr, frozen=unblind, rules=["R2", "R4"], label="F")
        add("F", learner_errors(R, fr, eF, params, frozen=unblind), fr)
        for W in (36, 60):
            eW = R.fit(fr, window=h.Window(W), rules=["R2", "R4"], label=f"W{W}")
            add(f"W{W}", learner_errors(R, fr, eW, params, months_back=W), fr)

        # subsample variants: the primary R7/R8 hedges
        H = pd.read_parquet(out / "learner_hedges.parquet")
        q = P.loc[H.index]
        otm = ((q.cp == "C") & (q.strike >= q.F)) | ((q.cp == "P") & (q.strike <= q.F))
        subsets = {"S3": q.rel_spread <= 0.05, "V": q.E7_strict.astype(bool), "OTM": otm,
                   "day-two volume > 0": q.volume_next > 0, "day-two volume 0 or empty": ~(q.volume_next > 0)}
        for label, m in subsets.items():
            add(label, H[m.to_numpy()], fr)
        if year == 2020:
            strata = [(pd.Timestamp("2020-01-01"), pd.Timestamp("2020-02-21")), h.STRESS, (pd.Timestamp("2020-05-01"), pd.Timestamp("2020-12-31"))]
            sc = h.bootstrap_counts(R.index, B=10_000, block=10, seed=2026, strata=strata)
            stress = q.quote_date.between(*h.STRESS).to_numpy()
            add("stress", H[stress], fr, sc)
            add(f"rest of {year}", H[~stress], fr, sc)
        for b in (5, 20):
            add(f"primary, block {b}", H, fr, h.bootstrap_counts(R.index, B=10_000, block=b, seed=2026))
        # OTM-refit: R2 refitted on out-of-the-money training pairs, R7/R8 keep the primary fits
        Potm = ((P.cp == "C") & (P.strike >= P.F)) | ((P.cp == "P") & (P.strike <= P.F))
        fo = fr.copy()
        fo["avail"] &= Potm
        eo = R.fit(fo, rules=["R2", "R4"], label="OTM-refit")
        Ho = H[otm.to_numpy()].copy()
        Ho["R2"] = eo.R2.reindex(Ho.index)
        add("OTM-refit", Ho[Ho.R2.notna()], fr)

        G = pd.concat(rows, ignore_index=True)
        G.to_csv(out / "learners_variants.csv", index=False)
        log["rows_out"] = len(G)
        print(G[G.base == "R2"].pivot_table(index="variant", columns=["rule", "cp"], values="gain").round(3).to_string())


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--spy"]
    y = int(args[0])
    main(y, Path(args[1]) if len(args) > 1 else T.BASE / str(y))
