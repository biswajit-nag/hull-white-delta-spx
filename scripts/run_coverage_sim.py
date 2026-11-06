"""Interval coverage and power under a known truth (analysis_plan.md section 16.12).

A regression-level market: GARCH(1,1)-t index returns, a cross-section copied from real 2019 SPX
sessions, a Black-Scholes error with a known R2-type effect (kappa), session-block bootstrap intervals
for the Gain of R2 over R1, compared with the true Gain of the fitted coefficients.

Revision 2 (2026-11-06), at the coordinator's request after the first run (kept as *_v1 files):
  * the main target is the Gain conditional on the test year's sigma path and cross-sections, in closed
    form per replication (G_cond); the stationary 200-year truth is secondary;
  * three scenarios: "stationary" (GARCH simulated), "path2020" (train on 2019's GARCH-filtered sigma
    path, test on 2020's) and "calm" (train 2018, test 2019); z, w, eps and cross-sections redrawn;
  * calibration v2: SSE-weighted moments, a gamma-term scale lam_g, and a per-type rescale of s_eps so
    that a replayed 2019 reproduces the real in-sample 2019 Gains. v1 (the plan's moments) is reported.
Choices added beyond the plan are listed in NOTES (also in calibration.json["choices"]).

Usage: uv run python -I scripts/run_coverage_sim.py [--reps N] [--out DIR] [--workers W]
Writes coverage.csv, replications.csv, calibration.json under the output directory
(default results/simulation/).
"""

from __future__ import annotations

import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, special

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from erdos_quant_finance_project import hedging as h  # noqa: E402
from erdos_quant_finance_project.runlog import timed  # noqa: E402

SEED = 20261106
KAPPAS = [0.0, 0.5, 1.0, 1.5, 2.0]
TYPES = ("C", "P")
SCENARIOS = ["stationary", "path2020", "calm"]
MAXOPT = 300
BURN, NTRAIN, NTEST = 500, 252, 252
B, BLOCK = 2000, 10
LONG_YEARS = 200


def arg(name, default, cast):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default


# --------------------------------------------------------------------------------------------------
# GARCH(1,1) with standardized Student-t innovations

def garch_sigma2(r, omega, alpha, beta, s2_0):
    s2 = np.empty(len(r))
    s2[0] = s2_0
    for t in range(1, len(r)):
        s2[t] = omega + alpha * r[t - 1] ** 2 + beta * s2[t - 1]
    return s2


def neg_loglik(theta, r):
    omega, alpha, beta = np.exp(theta[0]), theta[1], theta[2]
    nu = 2.0 + np.exp(theta[3])
    if alpha < 0 or beta < 0 or alpha + beta >= 0.9999:
        return 1e10
    s2 = garch_sigma2(r, omega, alpha, beta, r.var())
    z = r / np.sqrt(s2)
    c = special.gammaln((nu + 1) / 2) - special.gammaln(nu / 2) - 0.5 * np.log(np.pi * (nu - 2))
    ll = c - 0.5 * np.log(s2) - (nu + 1) / 2 * np.log1p(z ** 2 / (nu - 2))
    return -ll.sum()


def fit_garch(r):
    scale = 100.0  # optimise in percent, return to decimal units afterwards
    rs = r * scale
    best = None
    for a0, b0, nu0 in [(0.1, 0.85, 6.0), (0.05, 0.93, 10.0), (0.15, 0.8, 5.0)]:
        th0 = np.array([np.log(rs.var() * (1 - a0 - b0)), a0, b0, np.log(nu0 - 2)])
        res = optimize.minimize(neg_loglik, th0, args=(rs,), method="Nelder-Mead",
                                options={"xatol": 1e-9, "fatol": 1e-9, "maxiter": 20000, "maxfev": 40000})
        res = optimize.minimize(neg_loglik, res.x, args=(rs,), method="Nelder-Mead",
                                options={"xatol": 1e-10, "fatol": 1e-10, "maxiter": 20000, "maxfev": 40000})
        if best is None or res.fun < best.fun:
            best = res
    omega_pct, alpha, beta, nu = np.exp(best.x[0]), best.x[1], best.x[2], 2 + np.exp(best.x[3])
    return {"omega": omega_pct / scale ** 2, "alpha": alpha, "beta": beta, "nu": nu,
            "loglik_decimal_units": -best.fun + len(r) * np.log(scale),
            "n_returns": len(r), "converged": bool(best.success)}


def std_t(rng, nu, size):
    return rng.standard_t(nu, size=size) * np.sqrt((nu - 2) / nu)


def sim_garch(rng, n, g):
    """n sessions of the stationary GARCH after BURN burn-in sessions; returns (r, sigma2, w)."""
    omega, alpha, beta, nu = g["omega"], g["alpha"], g["beta"], g["nu"]
    tot = n + BURN
    z = std_t(rng, nu, tot)
    w = std_t(rng, nu, tot)
    s2 = np.empty(tot)
    r = np.empty(tot)
    s2[0] = omega / (1 - alpha - beta)
    for t in range(tot):
        if t:
            s2[t] = omega + alpha * r[t - 1] ** 2 + beta * s2[t - 1]
        r[t] = np.sqrt(s2[t]) * z[t]
    return r[BURN:], s2[BURN:], w[BURN:]


# --------------------------------------------------------------------------------------------------
# Data and calibration

def load_closes():
    fred = pd.read_csv(ROOT / "data/external/fred_SP500.csv", parse_dates=["observation_date"]).rename(
        columns={"observation_date": "date", "SP500": "close"}).dropna()
    cboe = pd.read_csv(ROOT / "data/external/cboe_SPX_History.csv").rename(columns={"DATE": "date", "SPX": "close"})
    cboe["date"] = pd.to_datetime(cboe["date"], format="%m/%d/%Y")
    cboe = cboe[cboe.date < fred.date.min()]
    c = pd.concat([cboe, fred]).sort_values("date").drop_duplicates("date").set_index("date").close
    return c.astype(float)


class Cross:
    """2019 cross-section, per type: arrays plus per-session slices (session index 0..S-1)."""

    def __init__(self, fr, g_col, sessions):
        self.sessions = sessions
        self.d = {}
        for cp in TYPES:
            m = (fr.cp == cp).to_numpy()
            sid = np.searchsorted(sessions, fr.session.to_numpy()[m])
            o = np.argsort(sid, kind="stable")
            sid = sid[o]
            arr = {k: fr[k].to_numpy()[m][o] for k in ("delta", "v", "tau")}
            arr["g"] = g_col[m][o]
            bounds = np.searchsorted(sid, np.arange(len(sessions) + 1))
            self.d[cp] = (arr, bounds)

    def draw(self, rng, cp, sess_idx):
        arr, bounds = self.d[cp]
        parts, cnt = [], np.empty(len(sess_idx), int)
        for k, s in enumerate(sess_idx):
            lo, hi = bounds[s], bounds[s + 1]
            n = hi - lo
            if n > MAXOPT:
                parts.append(lo + rng.choice(n, MAXOPT, replace=False))
                cnt[k] = MAXOPT
            else:
                parts.append(np.arange(lo, hi))
                cnt[k] = n
        return np.concatenate(parts), cnt


def kz_of(nu):
    """E z^4 of a standardized Student-t."""
    return 3 + 6 / (nu - 4)


def exp_sse(d, kappa, beta, lam_g, s_eta, s_eps_cp, kz, sig):
    """Closed-form E[e^2] per option given sigma (array per option). beta=None is R1, else R2.
    Cross terms vanish: E[z(z^2-1)] = 0 (E z^3 = 0), eta and eps independent with mean 0."""
    pbeta = 0.0 if beta is None else (beta[0] + beta[1] * d["delta"] + beta[2] * d["delta"] ** 2)
    c = (kappa * d["q"] - pbeta) * d["v"]
    s2 = sig ** 2
    return (c ** 2 * s2 + d["v"] ** 2 * s_eta ** 2 * s2 + (lam_g * d["g"]) ** 2 * s2 ** 2 * (kz - 1)
            + d["v"] ** 2 * d["tau"] * s2 * s_eps_cp ** 2)


def calibrate():
    closes = load_closes()
    lr_all = np.log(closes).diff().dropna()
    lr = lr_all[(lr_all.index >= "2010-01-01") & (lr_all.index <= "2019-12-31")]
    g = fit_garch(lr.to_numpy())
    # filter through 2020 with the 2010-2019 parameters (sigma of the return realised on each date)
    lr20 = lr_all[(lr_all.index >= "2010-01-01") & (lr_all.index <= "2020-12-31")]
    s2_all = garch_sigma2(lr20.to_numpy(), g["omega"], g["alpha"], g["beta"], lr.to_numpy().var())
    sig = pd.Series(np.sqrt(s2_all), index=lr20.index)
    paths = {y: sig[sig.index.year == y].to_numpy() for y in (2018, 2019, 2020)}
    kz = kz_of(g["nu"])

    P = h.load_pairs([2019])
    P = P[P.next_session <= pd.Timestamp("2019-12-31")]  # drop pairs ending on or after the unblinding session
    fr = h.ingredients(P)
    assert fr.avail.all()
    fr["v"] = fr.vega_n / fr.sqrt_tau
    fr["gam"] = 0.5 * P.gamma.to_numpy(float) * P.S_close.to_numpy(float)
    fr["sigma"] = sig.reindex(P.next_session).to_numpy()
    assert np.isfinite(fr.sigma).all(), "missing GARCH sigma for some 2019 pair"
    q = {}
    fr["qd"] = 0.0
    for cp in TYPES:
        m = fr.cp == cp
        X, t = h.design("R2", fr[m])
        q[cp] = h.ols(X, t)
        fr.loc[m, "e"] = t - X @ q[cp]
        d = fr[m]
        fr.loc[m, "qd"] = q[cp][0] + q[cp][1] * d.delta + q[cp][2] * d.delta ** 2
    fr["r"] = fr.dSn
    real_gain = {cp: float(1 - (fr.e[fr.cp == cp] ** 2).sum() / (fr.y[fr.cp == cp] ** 2).sum()) for cp in TYPES}
    sessions = pd.DatetimeIndex(np.sort(fr.session.unique()))
    sess_sig = fr.groupby("session").sigma.first()

    # ---- calibration v1: the plan's moments (unweighted)
    fr["ep"] = fr.e - fr.gam * (fr.r ** 2 - fr.sigma ** 2)
    fr["ev"] = fr.ep / fr.v
    eta_hat = fr.groupby("session").ev.mean()
    s_eta1 = float((eta_hat / sess_sig).std(ddof=1))
    fr["eta_hat"] = fr.session.map(eta_hat)
    s_eps1 = {cp: float((((fr.ev - fr.eta_hat) / (fr.sqrt_tau * fr.sigma))[fr.cp == cp]).std(ddof=1)) for cp in TYPES}
    v1 = {"s_eta": s_eta1, "s_eps": s_eps1, "lam_g": 1.0}

    # ---- calibration v2: SSE-weighted moments
    G = fr.gam * (fr.r ** 2 - fr.sigma ** 2)                 # realised gamma term
    expG = fr.gam ** 2 * fr.sigma ** 4 * (kz - 1)            # its model expectation
    lam_g = float(np.sqrt((G ** 2).sum() / expG.sum()))
    fr["ep2"] = fr.e - lam_g * G
    vv = fr.v ** 2
    fr["eta2"] = (fr.v * fr.ep2).groupby(fr.session).transform("sum") / vv.groupby(fr.session).transform("sum")
    s_eta2 = float(np.sqrt(((fr.v * fr.eta2) ** 2).sum() / (vv * fr.sigma ** 2).sum()))
    s_eps2 = {}
    for cp in TYPES:
        m = fr.cp == cp
        res = fr.ep2[m] - fr.v[m] * fr.eta2[m]
        s_eps2[cp] = float(np.sqrt((res ** 2).sum() / (vv[m] * fr.tau[m] * fr.sigma[m] ** 2).sum()))

    cross = Cross(fr, fr.gam.to_numpy(), sessions)
    for cp in TYPES:
        arr, _ = cross.d[cp]
        qq = q[cp]
        arr["q"] = qq[0] + qq[1] * arr["delta"] + qq[2] * arr["delta"] ** 2
    ssig = sess_sig.reindex(sessions).to_numpy()

    def replay_data(cp, full, rng):
        arr, bounds = cross.d[cp]
        if full:
            idx, cnt = np.arange(bounds[-1]), np.diff(bounds)
        else:
            idx, cnt = cross.draw(rng, cp, np.arange(len(sessions)))
        return {k: arr[k][idx] for k in ("delta", "v", "tau", "g", "q")}, np.repeat(ssig, cnt)

    def replay(par, full=False):
        """Expected in-sample Gain (kappa=1, beta=q) of the replayed 2019, per type; subsample seed 0."""
        rng = np.random.default_rng(0)
        out = {}
        for cp in TYPES:
            d, sg = replay_data(cp, full, rng)
            e1 = exp_sse(d, 1.0, None, par["lam_g"], par["s_eta"], par["s_eps"][cp], kz, sg)
            e2 = exp_sse(d, 1.0, q[cp], par["lam_g"], par["s_eta"], par["s_eps"][cp], kz, sg)
            out[cp] = float(1 - e2.sum() / e1.sum())
        return out

    # rescale s_eps per type so the replayed expected Gain equals the real one (linear in s_eps^2)
    v2a = {"s_eta": s_eta2, "s_eps": s_eps2, "lam_g": lam_g}
    v2 = {"s_eta": s_eta2, "s_eps": dict(s_eps2), "lam_g": lam_g}
    rho = {}
    rng = np.random.default_rng(0)
    for cp in TYPES:
        d, sg = replay_data(cp, False, rng)
        s2 = sg ** 2
        S = (d["q"] ** 2 * d["v"] ** 2 * s2).sum()
        N0 = (d["v"] ** 2 * s_eta2 ** 2 * s2 + (lam_g * d["g"]) ** 2 * s2 ** 2 * (kz - 1)).sum()
        Eps = (d["v"] ** 2 * d["tau"] * s2).sum()
        Ntarget = S * (1 - real_gain[cp]) / real_gain[cp]
        eps2 = (Ntarget - N0) / Eps
        if eps2 > 0:
            v2["s_eps"][cp] = float(np.sqrt(eps2))
            rho[cp] = float(np.sqrt(eps2) / s_eps2[cp])
        else:
            v2["s_eps"][cp] = 0.0
            rho[cp] = "infeasible: target noise below common+gamma; s_eps set to 0"
    repl = {"real_in_sample_gain": real_gain,
            "v1_moments": replay(v1), "v1_moments_full_cross_section": replay(v1, full=True),
            "v2_before_rescale": replay(v2a), "v2_final": replay(v2), "v2_final_full_cross_section": replay(v2, full=True)}
    cal = {"garch": g, "kz": kz, "calibration_v1_moments": v1, "calibration_v2_final": v2,
           "calibration_v2_before_rescale": v2a, "v2_s_eps_rescale_factor": rho,
           "replayed_2019_expected_gain": repl,
           "s_eta": v2["s_eta"], "s_eps": v2["s_eps"], "lam_g": v2["lam_g"],
           "q": {cp: q[cp].tolist() for cp in TYPES},
           "n_sessions_2019": int(fr.session.nunique()), "n_pairs_2019": {cp: int((fr.cp == cp).sum()) for cp in TYPES},
           "n_pairs_2019_total": int(len(fr)),
           "sigma_path_lengths": {str(y): len(v) for y, v in paths.items()},
           "sigma_path_mean": {str(y): float(v.mean()) for y, v in paths.items()}}
    return cal, cross, paths


# --------------------------------------------------------------------------------------------------
# Simulation

CAL = CROSS = PATHS = None  # set in the worker initializer


def init_worker(cal, cross, paths):
    global CAL, CROSS, PATHS
    CAL, CROSS, PATHS = cal, cross, paths


def sim_block(rng, nsess, sig_path=None):
    """Simulate nsess sessions (stationary GARCH, or returns r = sig_path*z on a fixed sigma path).
    Per type: pos, x, delta, v, tau, g (scaled), q, sig (per option) and y0, m with y(kappa) = y0 + kappa*m."""
    g = CAL["garch"]
    if sig_path is None:
        r, s2, w = sim_garch(rng, nsess, g)
        sig = np.sqrt(s2)
    else:
        sig = sig_path
        z = std_t(rng, g["nu"], nsess)
        w = std_t(rng, g["nu"], nsess)
        r = sig * z
        s2 = sig ** 2
    eta = CAL["s_eta"] * sig * w
    S = len(CROSS.sessions)
    draw = rng.integers(0, S, size=nsess)
    lam = CAL["lam_g"]
    out = {}
    for cp in TYPES:
        arr, _ = CROSS.d[cp]
        idx, cnt = CROSS.draw(rng, cp, draw)
        pos = np.repeat(np.arange(nsess), cnt)
        dl, v, tau, gg, q = arr["delta"][idx], arr["v"][idx], arr["tau"][idx], lam * arr["g"][idx], arr["q"][idx]
        eps = rng.standard_normal(len(idx))
        rr = r[pos]
        x = v * rr
        y0 = v * eta[pos] + gg * (rr ** 2 - s2[pos]) + v * np.sqrt(tau) * sig[pos] * CAL["s_eps"][cp] * eps
        out[cp] = {"pos": pos, "x": x, "delta": dl, "v": v, "tau": tau, "g": arr["g"][idx], "q": q,
                   "sig": sig[pos], "y0": y0, "m": q * x}
    return out


def design_mat(x, dl):
    return x[:, None] * np.column_stack([np.ones_like(dl), dl, dl ** 2])


def moments_chunks(seed_seq, years):
    acc = {cp: {k: {"n": 0, "yy": 0.0, "Xy": np.zeros(3), "XX": np.zeros((3, 3))} for k in KAPPAS} for cp in TYPES}
    rng = np.random.default_rng(seed_seq)
    for _ in range(years):
        o = sim_block(rng, 252)
        for cp in TYPES:
            X = design_mat(o[cp]["x"], o[cp]["delta"])
            XX = X.T @ X
            for k in KAPPAS:
                y = o[cp]["y0"] + k * o[cp]["m"]
                a = acc[cp][k]
                a["n"] += len(y)
                a["yy"] += float(y @ y)
                a["Xy"] += X.T @ y
                a["XX"] += XX
    return acc


def long_moments(workers, cal):
    chunks = [LONG_YEARS // workers] * workers
    seeds = np.random.SeedSequence([SEED, 777]).spawn(workers)
    with Pool(workers, initializer=init_worker, initargs=(cal, CROSS, PATHS)) as pool:
        parts = pool.starmap(moments_chunks, list(zip(seeds, chunks)))
    tot = parts[0]
    for p in parts[1:]:
        for cp in TYPES:
            for k in KAPPAS:
                for f in ("n", "yy", "Xy", "XX"):
                    tot[cp][k][f] = tot[cp][k][f] + p[cp][k][f]
    return {(cp, k): (tot[cp][k]["yy"] / tot[cp][k]["n"], tot[cp][k]["Xy"] / tot[cp][k]["n"],
                      tot[cp][k]["XX"] / tot[cp][k]["n"]) for cp in TYPES for k in KAPPAS}


def true_gain(beta, m):
    eyy, exy, exx = m
    return 1.0 - (eyy - 2 * beta @ exy + beta @ exx @ beta) / eyy


def one_rep(args):
    rep, mom = args
    kz, lam = CAL["kz"], CAL["lam_g"]
    rows = []
    for si, scen in enumerate(SCENARIOS):
        rng = np.random.default_rng(np.random.SeedSequence([SEED, 1, rep, si]))
        if scen == "stationary":
            ntr, nte, path = NTRAIN, NTEST, None
        elif scen == "path2020":
            path = np.concatenate([PATHS[2019], PATHS[2020]]); ntr, nte = len(PATHS[2019]), len(PATHS[2020])
        else:
            path = np.concatenate([PATHS[2018], PATHS[2019]]); ntr, nte = len(PATHS[2018]), len(PATHS[2019])
        o = sim_block(rng, ntr + nte, path)
        counts = h.bootstrap_counts(pd.RangeIndex(nte), B=B, block=BLOCK, seed=10_000 + rep)
        for k in KAPPAS:
            sse, betas = {}, {}
            gcond = {}
            for cp in TYPES:
                d = o[cp]
                tr = d["pos"] < ntr
                te = ~tr
                X = design_mat(d["x"], d["delta"])
                y = d["y0"] + k * d["m"]
                beta = h.ols(X[tr], y[tr])
                e1 = y[te]
                e2 = e1 - X[te] @ beta
                p = d["pos"][te] - ntr
                sse[cp] = (np.bincount(p, weights=e1 ** 2, minlength=nte), np.bincount(p, weights=e2 ** 2, minlength=nte),
                           np.bincount(p, minlength=nte))
                betas[cp] = beta
                dt = {kk: d[kk][te] for kk in ("delta", "v", "tau", "g", "q")}
                sg = d["sig"][te]
                E1 = exp_sse(dt, k, None, lam, CAL["s_eta"], CAL["s_eps"][cp], kz, sg).sum()
                E2 = exp_sse(dt, k, beta, lam, CAL["s_eta"], CAL["s_eps"][cp], kz, sg).sum()
                gcond[cp] = float(1 - E2 / E1)
            idx = pd.MultiIndex.from_product([range(nte), ["C", "P"]], names=["session", "cp"])
            df = pd.DataFrame({"R1": np.column_stack([sse["C"][0], sse["P"][0]]).ravel(),
                               "R2": np.column_stack([sse["C"][1], sse["P"][1]]).ravel(),
                               "n": np.column_stack([sse["C"][2], sse["P"][2]]).ravel()}, index=idx)
            gt = h.gain_table(df, [("R2", "R1")], counts).set_index("cp")
            tot1 = sse["C"][0] + sse["P"][0]
            top10 = float(np.sort(tot1)[-10:].sum() / tot1.sum())
            for cp in TYPES:
                rows.append({"scenario": scen, "kappa": k, "rep": rep, "cp": cp,
                             "truth_cond": gcond[cp], "truth_stat": true_gain(betas[cp], mom[(cp, k)]),
                             "estimate": gt.loc[cp, "gain"], "lo": gt.loc[cp, "lo"], "hi": gt.loc[cp, "hi"],
                             "top10_share": top10})
    return rows


# --------------------------------------------------------------------------------------------------

def summarise(rep_df):
    d0 = rep_df.copy()
    d0["cov_cond"] = (d0.lo <= d0.truth_cond) & (d0.truth_cond <= d0.hi)
    d0["cov_stat"] = (d0.lo <= d0.truth_stat) & (d0.truth_stat <= d0.hi)
    d0["width"] = d0.hi - d0.lo
    d0["like2020"] = d0.top10_share >= 0.5
    rows, h1 = [], []
    for subset in ("all", "2020-like"):
        d = d0 if subset == "all" else d0[d0.like2020]
        for (sc, k, cp), g in d.groupby(["scenario", "kappa", "cp"]):
            rows.append({"scenario": sc, "kappa": k, "cp": cp, "subset": subset, "replications": len(g),
                         "coverage_cond": g.cov_cond.mean(), "coverage_stat": g.cov_stat.mean(),
                         "median_width": g.width.median(), "mean_G_cond": g.truth_cond.mean(),
                         "mean_G_stat": g.truth_stat.mean(), "mean_estimate": g.estimate.mean(),
                         "bias_cond": (g.estimate - g.truth_cond).mean(), "bias_stat": (g.estimate - g.truth_stat).mean(),
                         "median_top10_share": g.top10_share.median()})
        w = d.pivot_table(index=["scenario", "kappa", "rep"], columns="cp", values=["lo", "truth_cond", "top10_share"])
        pas = (w["lo"]["C"] > 0) & (w["lo"]["P"] > 0)
        for (sc, k), g in pas.groupby(level=[0, 1]):
            tt = w["truth_cond"].loc[g.index]
            h1.append({"scenario": sc, "kappa": k, "cp": "H1_both", "subset": subset, "replications": len(g),
                       "h1_pass_rate": g.mean(), "mean_G_cond": float(tt.mean(axis=1).mean()),
                       "share_both_G_cond_pos": float(((tt["C"] > 0) & (tt["P"] > 0)).mean()),
                       "median_top10_share": float(w["top10_share"]["C"].loc[g.index].median())})
    return pd.DataFrame(rows), pd.DataFrame(h1)


NOTES = [
    "Optimisation in percent units, results converted to decimal daily units; omega scaled by 1e-4.",
    "GARCH fitted on log returns dated 2010-01-04..2019-12-31 (first return uses the last 2009 close); variance recursion started at the sample variance; Nelder-Mead from 3 starts, best kept; alpha+beta<0.9999 enforced.",
    "Closes: Cboe before 2016-10-28, FRED from then on (FRED NaN holidays dropped).",
    "Stationary scenario: GARCH starts at the unconditional variance, then 500 burn-in sessions; training year immediately precedes the test year on one path.",
    "2019 pairs ending after 2019-12-31 (the 2019-12-31 starts) are dropped from the q fit, calibration and cross-section (unblinding rule).",
    "sigma_t for a pair = GARCH conditional sd of the return realised on its next_session date; r = pair's dSn (simple return). Filter run through 2020 with the 2010-2019 parameters; path2020 = 2019 train / 2020 test return dates (252 / 253 sessions), calm = 2018 / 2019.",
    "Calibration v1 = plan's moments (unweighted: eta_hat = session mean of e'/v, s_eta = sd of eta_hat/sigma; s_eps = sd of (e'/v - eta_hat)/(sqrt(tau) sigma), ddof=1).",
    "Calibration v2 (used): (i) gamma scale lam_g with lam_g^2 = realised sum of squared gamma terms / model-expected sum (pooled over types), because the t(nu) kurtosis alone makes the expected gamma SSE exceed the whole real R2 SSE; y uses lam_g*g everywhere; (ii) eta_hat_t = sum(v e')/sum(v^2) per session with e' = e - lam_g g (r^2 - sigma^2); s_eta^2 = sum (v eta_hat)^2 / sum v^2 sigma^2 (SSE-weighted, pooled); s_eps^2 per type = sum (e' - v eta_hat)^2 / sum v^2 tau sigma^2; (iii) s_eps per type then rescaled exactly so the replayed-2019 expected in-sample Gain (kappa=1, beta=q, <=300 options/type/session, subsample seed 0) equals the real in-sample Gain.",
    "Conditional truth G_cond = 1 - sum E[e_R2^2] / sum E[e_R1^2] over the test year's options, E[e^2] = c^2 s^2 + v^2 s_eta^2 s^2 + (lam_g g)^2 s^4 (E z^4 - 1) + v^2 tau s^2 s_eps^2, c = (kappa q - beta'p) v, E z^4 = 3 + 6/(nu-4); beta = 0 for R1.",
    "Stationary truth: 200 years as 4 independent chunks of 50 years (fresh GARCH path each), pair-weighted moments; also reported for the fixed-path scenarios (secondary).",
    "Random draws are common across the five kappas within a replication and scenario; scenario streams SeedSequence([20261106, 1, rep, scenario_index]); long simulation SeedSequence([20261106, 777]); bootstrap seed 10000+rep shared by C and P and scenarios.",
    "2020-like flag: test-year top-10 session share of R1 squared error, calls and puts summed, >= 0.5; same flag for both types.",
]


def main():
    reps = arg("--reps", 1000, int)
    out = Path(arg("--out", str(ROOT / "results/simulation"), str))
    workers = arg("--workers", 4, int)
    out.mkdir(parents=True, exist_ok=True)
    with timed("coverage_sim_v2", inputs=f"spx 2019 cross-section, GARCH 2010-2019, {reps} reps x {len(KAPPAS)} kappas x {len(SCENARIOS)} scenarios, B={B}") as log:
        global CROSS, PATHS
        cal, CROSS, PATHS = calibrate()
        print("calibration:", json.dumps(cal, indent=1), flush=True)
        mom = long_moments(workers, cal)
        print("long-run moments done", flush=True)
        with Pool(workers, initializer=init_worker, initargs=(cal, CROSS, PATHS)) as pool:
            res = []
            for i, rows in enumerate(pool.imap(one_rep, [(r, mom) for r in range(reps)], chunksize=2)):
                res.extend(rows)
                if (i + 1) % 50 == 0:
                    print(f"rep {i + 1}/{reps}", flush=True)
        rep_df = pd.DataFrame(res)
        rep_df.to_csv(out / "replications.csv", index=False)
        cov, h1 = summarise(rep_df)
        pd.concat([cov, h1], ignore_index=True).to_csv(out / "coverage.csv", index=False)
        cal["truth_moments_years"] = LONG_YEARS
        cal["seed"] = SEED
        cal["choices"] = NOTES
        (out / "calibration.json").write_text(json.dumps(cal, indent=1))
        log["rows_out"] = len(rep_df)


if __name__ == "__main__":
    main()
