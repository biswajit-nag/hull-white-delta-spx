"""Tune R8 on 2019 only (analysis_plan.md §7), and evaluate R7 and R8 in the rehearsal design.

One Optuna study per option type: TPE sampler (seed 2026), 60 serial trials, no pruning. The objective
is the pooled normalized hedging SSE over the rehearsal folds: trailing 6-month windows, test months
2019-07 to 12, pairs with x = 0 included. Writes results/rehearsal/r8_params.json, r8_trials_{C,P}.csv,
and learners_2019.csv (R7, R8 and R2 on the feature-complete test pairs).

Usage: uv run python -I scripts/tune_r8.py [--spy] [YEAR ...]   (2019 for the plan; 2015 2016 and 2010 for the
walk-forward, §16.4; --spy for SPY, §16.3, writing to results/spy/rehearsal/). --rule R9|R10|R11 tunes those rules
(plan §16.7) with the same design, writing r9_params_*.json etc.; R8 is the default.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import optuna
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project import learners as L  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

U = "spy" if "--spy" in sys.argv else "spx"
RULE = sys.argv[sys.argv.index("--rule") + 1] if "--rule" in sys.argv else "R8"
TAG = RULE.lower()
OUT = ROOT / ("results/spy/rehearsal" if U == "spy" else "results/rehearsal")


def folds(fr, P, z, ok, months, cp):
    """(train, test) frames per rehearsal month: 6-month trailing window, day two before the test month."""
    day1, day2 = P.quote_date, P.next_session
    out = []
    for m in months:
        s0 = day1[day1.dt.to_period("M") == m].min()
        lo = (m - 6).to_timestamp()
        tr = ok & (fr.cp == cp) & (day1 >= lo) & (day1 < s0) & (day2 < s0)
        te = ok & (fr.cp == cp) & (day1.dt.to_period("M") == m)
        out.append((fr[tr], z[tr], fr[te], z[te]))
    return out


def main(years: list[int]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    have = [y for y in sorted({y - 1 for y in years} | set(years)) if (h.PAIRS_ROOT / f"underlying={U}" / f"year={y}").exists()]
    P = h.load_pairs(have, underlying=U)
    # validation pairs end before the first session after the tuning years (2020-01-02 for 2019: no 2020 outcome)
    P = P[P.next_session.dt.year <= max(years)]
    fr = h.ingredients(P)
    z = L.features(fr, P)
    ok = L.complete(fr, z)
    months = [m for y in years for m in pd.period_range(f"{y}-07" if y == years[0] else f"{y}-01", f"{y}-12", freq="M")]
    tag = "_".join(map(str, years))
    best, rows = {}, []
    for cp in ("C", "P"):
        F = folds(fr, P, z, ok, months, cp)

        def objective(trial):
            prm = L.suggest(trial)
            return float(sum((L.lgb_error(RULE, tr, ztr, te, zte, prm) ** 2).sum() for tr, ztr, te, zte in F))

        with timed(f"tune_{TAG}", inputs=f"{U} {tag} {cp}", notes="60 trials, TPE seed 2026") as run:
            study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=L.SEED))
            optuna.logging.set_verbosity(optuna.logging.WARNING)
            study.optimize(objective, n_trials=60, n_jobs=1)
            run["notes"] = f"60 trials, TPE seed 2026; best {study.best_value:.6g}"
        best[cp] = study.best_params
        study.trials_dataframe().to_csv(OUT / f"{TAG}_trials_{tag}_{cp}.csv", index=False)
        if RULE != "R8":
            continue
        # R7 and the tuned R8 against R2 on the same folds (2019 is the tuning year: in-sample for R8)
        for tr, ztr, te, zte in F:
            beta = h.ols(*h.design("R2", tr))
            e2 = te.y - h.design("R2", te)[0] @ beta
            e7 = L.tree_error(L.fit_tree(tr, ztr), te, zte)
            e8 = L.boost_error(L.fit_boost(tr, ztr, study.best_params), te, zte)
            rows.append({"cp": cp, "month": str(te.session.min())[:7], "pairs": len(te),
                         "sse_R1": (te.y**2).sum(), "sse_R2": (e2**2).sum(), "sse_R7": (e7**2).sum(), "sse_R8": (e8**2).sum()})
    (OUT / f"{TAG}_params_{tag}.json").write_text(json.dumps(best, indent=2))
    if RULE == "R8":
        pd.DataFrame(rows).to_csv(OUT / f"learners_{tag}.csv", index=False)
    print(json.dumps(best, indent=2))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a not in ("--spy", "--rule", RULE)]
    main([int(a) for a in args] or [2019])
