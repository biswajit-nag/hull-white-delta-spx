"""Exploratory challengers R7 (a regression tree) and R8 (LightGBM boosted from R2), plan §6–§7.

Both learn g in the hedge δ + ν/(S√τ)·g(z) by minimizing the hedging loss Σ(y − x·g)², written for
x ≠ 0 as a weighted regression of y/x on z with weights x², rescaled to mean 1.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeRegressor

from .hedging import ols, poly

FEATURES = ["delta", "log_tau", "smile_pos", "sigma_atm", "rv20", "ret5"]
SEED = 2026


def features(frame: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    z = pd.DataFrame({"delta": frame.delta, "log_tau": np.log(frame.tau)}, index=frame.index)
    for c in ("smile_pos", "sigma_atm", "rv20", "ret5"):
        z[c] = p.loc[frame.index, c].to_numpy(float)
    return z


def complete(frame: pd.DataFrame, z: pd.DataFrame) -> pd.Series:
    """Pairs a learner can use: all features present (missing ones leave the pair out of R7/R8 only)."""
    return frame.avail & np.isfinite(z.to_numpy()).all(axis=1)


def _target(d: pd.DataFrame):
    keep = d.x.to_numpy() != 0
    x, y = d.x.to_numpy()[keep], d.y.to_numpy()[keep]
    w = x**2
    return keep, y / x, w / w.mean()


def fit_tree(d: pd.DataFrame, z: pd.DataFrame) -> DecisionTreeRegressor:
    keep, t, w = _target(d)
    m = DecisionTreeRegressor(max_depth=3, min_weight_fraction_leaf=0.05, random_state=SEED)
    return m.fit(z.to_numpy()[keep], t, sample_weight=w)


def tree_error(m, d, z) -> np.ndarray:
    return (d.y - d.x * m.predict(z.to_numpy())).to_numpy()


def fit_boost(d: pd.DataFrame, z: pd.DataFrame, params: dict) -> tuple[lgb.Booster, np.ndarray]:
    """LightGBM on the residual of R2: initial score = R2's fitted polynomial on the same window."""
    beta = ols(d.x.to_numpy()[:, None] * poly(d.delta.to_numpy()), d.y.to_numpy())
    keep, t, w = _target(d)
    base = (poly(d.delta.to_numpy()) @ beta)[keep]
    n = int(keep.sum())
    prm = {"objective": "regression", "learning_rate": params["learning_rate"], "num_leaves": params["num_leaves"],
           "lambda_l2": params["lambda_l2"], "min_sum_hessian_in_leaf": params["min_hess_frac"] * n,
           "min_data_in_leaf": 20, "boost_from_average": False, "feature_fraction": 1.0, "bagging_fraction": 1.0, "bagging_freq": 0,
           "deterministic": True, "seed": SEED, "num_threads": 8, "verbose": -1, "force_col_wise": True}
    ds = lgb.Dataset(z.to_numpy()[keep], label=t, weight=w, init_score=base, free_raw_data=False)
    return lgb.train(prm, ds, num_boost_round=params["n_estimators"]), beta


def boost_error(model_beta, d, z) -> np.ndarray:
    model, beta = model_beta
    # the prediction is R2's polynomial plus the trees' correction, added explicitly
    g = poly(d.delta.to_numpy()) @ beta + model.predict(z.to_numpy(), raw_score=True)
    return (d.y - d.x * g).to_numpy()


def suggest(trial) -> dict:
    return {"num_leaves": trial.suggest_int("num_leaves", 4, 64, log=True),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 50, 1000, log=True),
            "lambda_l2": trial.suggest_float("lambda_l2", 1e-3, 100, log=True),
            "min_hess_frac": trial.suggest_float("min_hess_frac", 1e-4, 1e-2, log=True)}
