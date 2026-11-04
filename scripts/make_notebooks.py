"""Build and execute the numbered notebooks (analysis_plan.md §12) from the results files.

Each notebook is a list of (markdown | code) cells defined here, so the narrative and the code that
reads results/ live together under version control; executing them stores the outputs.

Usage: uv run python -I scripts/make_notebooks.py 01 02 ...   (no argument: all)
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NB = ROOT / "notebooks"
SETUP = """import sys, json
from pathlib import Path
import numpy as np, pandas as pd, matplotlib.pyplot as plt
ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
R = ROOT / "results"
pd.set_option("display.width", 160); pd.set_option("display.max_columns", 30)
plt.rcParams.update({"figure.figsize": (9, 4), "axes.grid": True, "grid.alpha": 0.3})"""


def md(s):
    return nbformat.v4.new_markdown_cell(s.strip())


def code(s):
    return nbformat.v4.new_code_cell(s.strip())


NOTEBOOKS: dict[str, tuple[str, list]] = {}

NOTEBOOKS["01"] = ("01_audit_and_attrition", [
    md("""
# 01 · Data audit and attrition

**What this notebook establishes.** The data are OptionsDX's end-of-day SPX option quotes. Before any hedging number, it checks four things:
- whether the quotes are fit for a one-day hedging study;
- which option-days enter the analysis (rules E1–E8 of `analysis_plan.md` §5);
- how many are lost because the next session's quote is missing (*attrition*);
- what the sample is made of.

Every number here is data quality only; no hedging error is computed. The processing rules are in `DATA.md`.

**The unit of observation.** A *pair* is one contract on NYSE session *t* (day one), followed to the same contract on the next NYSE session (day two). A hedge set at day one's close is judged by the option's and the index's moves to day two's close. That is Lecture 7's discrete delta-hedging P&L, cut to one period.
"""),
    code(SETUP),
    md("""
## Eligibility and the vendor's volume coding

Ruf and Wang (2022) keep an option-day only if it traded that day (positive volume), since an untraded quote may be stale.

**Our data needed one correction.** Through 2021, OptionsDX never records a volume above 999. On the evidence of day-to-day transitions, it leaves the field *empty* when 1,000 or more contracts trade. It also leaves it empty for contracts that have not traded, and the last-trade price separates the two cases:
- **"empty" with a positive last price** means a heavily traded day;
- **"empty" with a last price of 0** means no trade.

So rule E7 is: positive volume, or empty volume with a positive last price. The table shows how many pairs each clause admits.
"""),
    code("""
e7 = pd.read_csv(R / "attrition/e7_clause.csv")
e7"""),
    md("""
## Attrition: eligible pairs without a usable next-session quote

A pair needs a two-sided quote (a bid and an ask) for the same contract on the next session.
- **When the vendor lacks the whole session,** the pair is lost (`vendor_missing_session`); it never turns into a two-day hedge.
- **When the bid vanishes** (`one_sided_next`), the value is unknown. The plan stress-tests those pairs with endpoint scenarios (§5).
"""),
    code("""
st = pd.read_csv(R / "attrition/by_status.csv")
st["lost_share"] = 1 - st.ok / st[["ok", "one_sided_next", "vendor_missing_session"]].sum(axis=1)
st"""),
    code("""
m = pd.read_csv(R / "attrition/by_month.csv")
m["quote_date"] = m.iloc[:, 0].astype(str)
pv = m.pivot(index="quote_date", columns="cp", values="lost_share")
ax = pv.plot(marker="o", title="Share of eligible pairs without a usable next-session quote, by month")
ax.set_ylabel("share lost"); plt.xticks(rotation=60); plt.tight_layout()"""),
    md("""
**Reading.**
- **Attrition is small and has a known cause.** It comes almost entirely from whole sessions missing at the vendor: ordinary days, and none in the March 2020 crash.
- **Vanished bids** are under 0.1% of pairs, concentrated in the stress period (2020-02-24 to 04-30), mostly far out-of-the-money and long-dated options.
- **Results are therefore stated conditional on a usable day-two quote,** with this table beside them.
"""),
    md("""
## What the sample is made of

Moneyness is measured by the Black–Scholes delta, which puts all maturities on one scale (Lecture 6).
- **The band.** Hull and White's band keeps 0.05 ≤ |δ| ≤ 0.95: both in- and out-of-the-money options.
- **SPX lists far more strikes below the index than above,** and the volatility skew stretches the band further down.
- **So calls are about half in the money, and puts mostly out of the money.**
"""),
    code("""
itm = pd.read_csv(R / "attrition/itm_share.csv"); itm"""),
    code("""
comp = pd.read_csv(R / "attrition/composition.csv")
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
for ax, cp in zip(axes, ["C", "P"]):
    t = comp[comp.cp == cp].pivot_table(index="delta_b", columns="year", values="pairs", aggfunc="sum")
    t.plot.bar(ax=ax, title=f"{'Calls' if cp == 'C' else 'Puts'}: usable pairs by |delta| bucket")
plt.tight_layout()"""),
    md("""
## The extra training years (2015–2018)

The 36- and 60-month windows (sensitivities W36 and W60) fit on 2015–2018 as well. A light audit by month found no stamp or settlement anomaly beyond the known ones. The empty-volume share swings by month, from 37% to 77%, but near the money the swing is in untraded new strikes (last price 0), which E7 already excludes.
"""),
    code("""
a = pd.read_csv(R / "audit_light.csv")
a[["month", "sessions", "expiries_per_session", "volume_max", "volume_empty", "empty_last_pos", "iv_converged", "next_ok", "eligible_pairs"]].round(3)"""),
])

NOTEBOOKS["02"] = ("02_forwards_iv_greeks", [
    md("""
# 02 · Forwards, implied volatilities, Greeks, and verification

**Why not a rate and a dividend yield.** Lecture 9 prices with a continuous dividend yield q. The S&P 500's dividends come from 500 companies on scattered dates, so no single q is observable. Instead, every expiry is priced on its own *forward* F and discount factor D, both read from put–call parity at the mids (Lectures 6 and 9):

  C − P = D·(F − K).

**The three stages** (`analysis_plan.md` §4):
1. A weighted least-squares line of C − P on K, per expiry, on strikes within 10% of the index where both legs are quoted.
2. A smooth zero-rate curve r(τ) per session, from the expiries at least 30 days out, because a short expiry pins down D poorly.
3. Each expiry's forward, given D.

**The price** is Black's formula C = D·[F·N(d₁) − K·N(d₂)]. It equals Lecture 9's formula with r = −ln(D)/τ and q = r − ln(F/S)/τ. Implied volatilities come from Lecture 12's solver, `option_pricing.bs_euro_iv`.
"""),
    code(SETUP),
    code("""
s = pd.read_csv(R / "attrition/parity_sessions.csv", parse_dates=["quote_date"])
fig, ax = plt.subplots()
ax.plot(s.quote_date, 100 * (s.c0 + s.c1 * 0.25), label="3-month zero rate from SPX parity (%)")
ax.set_ylabel("%"); ax.legend(); ax.set_title("The options' own discount rate, 2019–2020")"""),
    md("""
**Reading.** The parity rate follows the policy cuts of 2019 and the March 2020 emergency cuts to near zero. It sits a little above Treasury bill yields, which is typical of rates implied by SPX options: they are a funding rate, not a government rate.
"""),
    code("""
s[["n_fits", "stage1_fits", "stage3_forwards", "expiries", "A_days"]].describe().round(2)"""),
    md("""
## Implied-volatility solver statuses

Only a converged solve gives an implied volatility. Mids outside the no-arbitrage bounds are nearly all deep-in-the-money quotes, outside the delta band.
"""),
    code("""pd.read_csv(R / "attrition/iv_status.csv", index_col=0)"""),
    md("""
## A parity-consistency check

If the mids satisfy parity at the fitted D and F, a single σ prices both the call and the put at a strike. The gap between their implied volatilities, by log-moneyness ln(K/F), measures how well that holds.
"""),
    code("""pd.read_csv(R / "attrition/cp_iv_gap.csv").round(4)"""),
    md("""
## Sensitivity A's index level

The audit found the option quotes are synchronous with neither the official close nor the vendor's snapshot. Sensitivity A therefore uses the level implied by the options themselves: the parity forward of the nearest P.M. expiry 0.5–5 days out.
"""),
    code("""
s["gap_bp"] = 1e4 * np.log(s.S_A / s.S_close)
ax = s.set_index("quote_date").gap_bp.plot(title="Options-implied index level against the official close (bp)")
ax.axhline(0, color="k", lw=0.8)
s.gap_bp.abs().describe().round(2)"""),
    md("""
## Verification (`analysis_plan.md` §11)

The pytest suite checks:
- the forward-form Greeks against central finite differences;
- agreement with Lecture 12's `bs_euro_greeks` and `bs_euro_iv`;
- implied-volatility round trips and bound failures;
- recovery of a known D and F by the parity fit;
- recovery of known Hull–White coefficients;
- Gain invariance;
- the no-look-ahead boundary;
- the bootstrap identity;
- the learners' objective;
- the mark formulas.
"""),
    code("""
import subprocess
r = subprocess.run([sys.executable, "-m", "pytest", "-q", str(ROOT / "tests")], capture_output=True, text=True, cwd=ROOT)
print(r.stdout[-1500:])"""),
])


NOTEBOOKS["03"] = ("03_rehearsal_2019", [
    md("""
# 03 · The rehearsal on training data (2019, and 2018)

**Why a rehearsal.** The plan (`analysis_plan.md` §10) runs the whole pipeline on training years before the 2020 test year is opened, so that:
- the code is checked end to end;
- the width of the confidence intervals is previewed;
- every question about the *form* of Hull and White's rule is answered without touching 2020. The rule's polynomial degree in δ and its 1/√T maturity scaling are those questions.

**The design.** A 6-month trailing window, refitted monthly, tested on July–December. 2019 is the main rehearsal year and 2018 a second. The 2019-12-31 pairs end on 2020-01-02, so they are excluded.

**The hedging error,** on Hull and White's normalized scale, is e = (Δf − h·ΔS)/S_t:
- Δf is the option's mid-price change;
- ΔS is the index's change;
- h is the rule's hedge ratio.

**The Gain** of rule X over rule Y is 1 − Σe²_X / Σe²_Y. Intervals come from a circular block bootstrap over sessions, not options, because every option on a day shares that day's index move (§9).
"""),
    code(SETUP),
    code("""
g = pd.concat([pd.read_csv(R / f"rehearsal/gains_{y}.csv").assign(year=y) for y in (2019, 2018)])
show = g[g.rule.isin(["R1", "R2", "R3", "R4", "R5", "R6"]) & g.base.isin(["R0", "R1", "R3", "R4"])]
show[["year", "cp", "rule", "base", "gain", "lo", "hi", "pairs"]].round(4)"""),
    md("""
**Reading.**
- **The Black–Scholes delta already removes about 95% of the unhedged variance** (R1 against R0).
- **In 2019 H2,** Hull and White's correction (R2) removes a further 28% (calls) and 34% (puts) of what is left, and beats the fitted scaling rule (R4) by about 11% for both types.
- **In 2018 H2,** which contains the Q4 2018 sell-off, the call Gain is about zero and the intervals are 0.4–0.5 wide.

That is the preview for 2020: a crash year will give wide intervals, and a correction fitted in calm months may not carry over.
"""),
    md("""
## Specification check 1: the polynomial degree

**The test.** Hull and White's adjustment is a quadratic in δ. Here degrees 0–3 are compared out of sample, on an orthogonal (Legendre) basis.

**The criterion, fixed before running:** the quadratic is *not contradicted* unless the cubic beats it, with a 95% bootstrap lower bound above 0.
"""),
    code("""
s = pd.concat([pd.read_csv(R / f"rehearsal/spec_checks_{y}.csv").assign(year=y) for y in (2019, 2018)])
s[s.check.str.startswith("degree")].round(5)"""),
    code("""
g[g.base == "deg:2"][["year", "cp", "rule", "gain", "lo", "hi"]].round(4)"""),
    md("""
**Reading.**
- **In 2019 the cubic beats the quadratic,** for both types, by about 0.2% of the squared error: statistically detectable with hundreds of thousands of pairs, but economically negligible. In 2018 it does not.
- **Under the plan's rule,** the cubic is carried to 2020 as a labelled exploratory rule; Hull and White's quadratic stays the rule under test.
- **A constant adjustment (degree 0)** also beats the quadratic for calls in 2019, by 1.4%. The plan's criterion does not cover a lower degree winning, so this is reported, not acted on. It suggests the quadratic's extra coefficients add estimation noise on 6-month windows.
"""),
    md("""
## Specification check 2: the 1/√T scaling

**The test.** τ^(−α) replaces τ^(−1/2), for α ∈ {0, 0.25, 0.75, 1}, each compared with α = ½. Holm's adjustment is applied across the four, per option type.
"""),
    code("""s[~s.check.str.startswith("degree")].round(4)"""),
    md("""
**Reading.**
- **1/√T is not contradicted in either year.**
- **No scaling at all** (α = 0) is clearly worse.
- **For calls,** α = ¾ (2019) and α = 1 (2018) look slightly better, but neither survives the adjustment. If anything, the call adjustment decays a little faster with maturity than 1/√T.
"""),
    code("""
b = pd.read_csv(R / "rehearsal/buckets_2019.csv")
order = ["14-30", "31-60", "61-91", "92-122", "123-182", "183-365", "366+"]
t = b[b.pairs > 500].pivot_table(index=["cp", "delta_b"], columns="tau_b", values="sqrt_tau_kappa")[order]
t.round(3)"""),
    md("""
**The bucket analysis Hull and White describe in their §IV.** Each cell is √τ·κ̂, where κ̂ is the per-bucket coefficient of the residual Δf − δΔS on ν·ΔS/S. Under 1/√T, each row should be flat across maturity. For puts it is roughly flat. For calls the magnitude shrinks beyond six months, consistent with the slight preference for α > ½.
"""),
    md("""
## Why the bootstrap is over sessions: naive against clustered standard errors

R2's coefficients, with ordinary OLS standard errors and with standard errors clustered by session.
"""),
    code("""
pd.concat([pd.read_csv(R / f"rehearsal/se_ratio_{y}.csv").assign(year=y) for y in (2019, 2018)])[["year", "cp", "coef", "estimate", "se_naive", "se_clustered", "ratio", "sessions"]].round(4)"""),
    md("""
**Reading.** The clustered standard errors are 4.5 to 34 times the naive ones.
- **Why.** All options on a day share that day's index move and volatility shock, so the information accumulates with sessions (about 250 a year), not with option-days (about 300,000).
- **The consequence.** Significance claims that treat options as independent, such as Hull and White's Appendix B, are far too optimistic.
"""),
])


NOTEBOOKS["04"] = ("04_results_2020", [
    md("""
# 04 · The 2020 test year

**The confirmatory question** (`analysis_plan.md` §1, §8): in 2020, does Hull and White's minimum-variance delta (R2) reduce next-session squared hedging error relative to the Black–Scholes delta (R1)? And does it beat Ruf and Wang's scaling rules: the fixed 0.9·δ for calls and 1.1·δ for puts (R3), and a fitted a·δ (R4)?

**The protocol.**
- Each 2020 month is hedged with coefficients fitted on the 12 months before it. A training pair must end before the test month's first session.
- The plan was committed (77b030e) before any 2020 number existed, and 2020 was opened in one logged run (implementation b661d6a).

**Gain** of rule X over rule Y = 1 − Σe²_X/Σe²_Y on the same pairs; a Gain of 0.10 means 10% less squared error.

**H1** requires the 95% lower bound of the Gain over R1 to exceed 0 for calls *and* puts.
"""),
    code(SETUP),
    code("""
v = pd.read_csv(R / "2020/verdict.csv")
v.round(3)"""),
    code("""
g = pd.read_csv(R / "2020/gains.csv")
prim = g[(g.variant == "primary") & (g.rule == "R2") & g.base.isin(["R1", "R3", "R4"])]
prim[["cp", "rule", "base", "gain", "lo", "hi", "p_plus", "p_minus", "pairs"]].round(3)"""),
    md("""
**The verdict is "Inconclusive".**
- **Point estimates.** The Hull–White delta reduces squared hedging error by 18.5% for calls and 12.0% for puts.
- **Intervals.** The session-block bootstrap intervals are [−0.36, 0.46] and [−0.45, 0.46]. H1 is not supported, and nothing is rejected: the data cannot tell a 20% improvement from none.
- **Against the scaling rules,** all four comparisons are "not distinguished".
- **Every robustness variant gives the same verdict:** the options' own index level, the vendor's level, the frozen 2019 fit, 36- and 60-month windows, the spread screen, bid-only and ask-only marks, the vanished-quote scenarios and the rest of 2020.

**Why the intervals are so wide: concentration.** In March 2020 the index moved by up to 12% a day, so squared errors on those days are about 100 times those of a calm day.
"""),
    code("""
d = pd.read_csv(R / "2020/descriptives.csv")
d[d.rule.isin(["R0", "R1", "R2", "R3", "R4"])][["cp", "rule", "pairs", "effectiveness_vs_R0", "rms_dollars_per_contract", "stress_share_R1"]].round(3)"""),
    code("""
for cp in "CP":
    t = pd.read_csv(R / f"2020/top_sessions_{cp}.csv")
    print(cp, "top-10 sessions' share of Black–Scholes squared error:", round(t.share.sum(), 3))
    print(t.assign(session=t.session.str[:10]).round(3).to_string(index=False))"""),
    md("""
**Reading.**
- **Black–Scholes already does most of the work.** It removes 92% (calls) and 95% (puts) of the unhedged variance; Hull and White's correction adds about one point.
- **In dollars,** it cuts the RMS hedging error per contract from about $825 to $727 for calls, and from $894 to $804 for puts.
- **The stress period** (2020-02-24 to 04-30) holds 80% (calls) and 86% (puts) of the year's Black–Scholes squared error, and ten sessions hold 65–73%.

So the pooled Gain is essentially a statement about March 2020, and a few days decide it.
"""),
    md("""
## The month-by-month picture

Hull and White report the average of monthly Gains; the plan reports both.
"""),
    code("""
fig, ax = plt.subplots()
for cp, c in (("C", "tab:blue"), ("P", "tab:orange")):
    m = pd.read_csv(R / f"2020/monthly_{cp}.csv")
    ax.plot(m.month, m.G_R2_R1, marker="o", color=c, label=f"{'calls' if cp == 'C' else 'puts'}: R2 over R1 (mean {m.G_R2_R1.mean():.3f})")
ax.axhline(0, color="k", lw=0.8); ax.set_ylabel("monthly Gain"); ax.legend(); plt.xticks(rotation=60)
ax.set_title("Hull–White over Black–Scholes, month by month, 2020"); plt.tight_layout()"""),
    md("""
**Reading.**
- **The good months.** The correction helps in January–March (Gains of +0.15 to +0.40), June and October.
- **The bad months.** It hurts badly in April (−0.80 for calls), September and November.
- **The average of monthly Gains is about zero for both types.** The pooled +18%/+12% comes from March outweighing the bad months.
"""),
    md("""
## Why April went wrong: the coefficients learn the crash too late

The April fit is the first whose 12-month window contains March 2020. The put coefficients jump (a from −0.34 to −0.45, b from −0.35 to −0.64), so April's hedges apply a crash-sized correction to a market that had calmed.
"""),
    code("""
s = pd.read_csv(R / "2020/stability.csv")
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
for ax, cp in zip(axes, "CP"):
    x = s[(s.rule == "R2") & (s.cp == cp)]
    for k, name in enumerate("abc"):
        y = x[x.k == k]
        ax.errorbar(y.month, y.coef, yerr=2 * y.se_clustered, marker="o", capsize=2, label=name)
    ax.set_title(f"{'Calls' if cp == 'C' else 'Puts'}: R2 coefficients at each monthly refit (±2 clustered s.e.)")
    ax.legend(); ax.tick_params(axis="x", rotation=60)
plt.tight_layout()"""),
    code("""
c = pd.read_csv(R / "2020/ceiling.csv").pivot_table(index="month", columns="cp", values=["G_R2", "G_ceiling"])
c.round(3)"""),
    md("""
**The in-sample ceiling** refits R2 on each test month's own pairs: the best a quadratic correction could have done with hindsight.
- **In the months where R2 failed** (April, August, September, November), even the ceiling is near zero. There was little linear relation between the index move and the volatility move left to exploit, so any correction learned earlier could only add error.
- **That is a model-risk finding.** The rule's value depends on the spot–volatility relation being stable, and in 2020 it was not.
"""),
    md("""
## The crash itself, and the rest of the year

The stress period and the rest of 2020 are bootstrapped in separate strata, so no block crosses between them.
"""),
    code("""
g[g.variant.isin(["stress", "rest of 2020"]) & (g.rule == "R2") & g.base.isin(["R1", "R3", "R4"])][["variant", "cp", "base", "gain", "lo", "hi"]].round(3)"""),
    md("""
**Outside the crash the picture is calmer and clearer for calls.** R2 beats the fitted scaling rule for calls by 5.3%, with an interval of [0.032, 0.077]. The secondary tests use the full-year family, so this is descriptive.
"""),
])

NOTEBOOKS["05"] = ("05_breakdown_and_sensitivities", [
    md("""
# 05 · Breakdown, sensitivities and extensions

This notebook reports everything the plan declares beyond the confirmatory endpoints:
- the bucket Gains;
- the measurement variants of Table 8.1 (`analysis_plan.md` §8);
- the attribution of the hedging error;
- the exploratory challengers;
- the SPY and Heston extensions (§16).

None of these changes the verdict of notebook 04.
"""),
    code(SETUP),
    code("""
g = pd.read_csv(R / "2020/gains.csv")
show = lambda variants: g[g.variant.isin(variants) & (g.rule == "R2") & g.base.isin(["R1", "R3", "R4"])][["variant", "cp", "base", "gain", "lo", "hi"]].round(3)
show(["primary", "A", "B", "F", "W36", "W60", "T"])"""),
    md("""
**The index level and the window.** Neither moves the picture.
- **A and B** are the options' own level and the vendor's snapshot.
- **W36 and W60** are the longer windows. They give the same point Gains (about 0.18 for calls and 0.14 for puts) with somewhat narrower intervals.
- **The frozen fit F**, fitted once on 2019, does about as well as monthly refitting (calls 0.178 against 0.185; puts 0.145 against 0.120). It is the one variant in which R2 beats both scaling rules for puts. In 2020, refitting monthly did not help: the refits learned March too late.
"""),
    code("""show(["P-bid", "P-ask", "P-WM", "P-SW", "S3", "V", "OTM", "OTM-refit"])"""),
    md("""
**Marks and populations.**
- **Marks.** Marking at the bid, the ask, the imbalance-weighted mid or Lecture 12's size-weighted price leaves the comparison where it was.
- **Populations.**
  - The spread screen (S3) lowers the point Gains, especially for puts.
  - On the out-of-the-money subsample, Ruf and Wang's home domain, the comparison with the scaling rules stays "not distinguished".
  - Refitting R4 on out-of-the-money pairs makes it almost exactly as good as R2 there (relative Gain about 0).
"""),
    code("""
for col in ("delta_b", "tau_b"):
    t = pd.concat([pd.read_csv(R / f"2020/buckets_{col}_{cp}.csv") for cp in "CP"])
    print(t.round(3).to_string(index=False)); print()"""),
    md("""
## Where the error comes from: the attribution

Each pair's Black–Scholes hedging error is split into vega (ν·Δσ), gamma (½Γ·ΔS²), theta, vanna, volga, carry (rate, dividend and index-timing changes) and a remainder, all divided by S_t. The table shows each term's mean square relative to the mean squared error. `xmom_*` is each term's contribution to the best scalar delta correction.
"""),
    code("""
a = pd.read_csv(R / "2020/attribution.csv")
a[a.group.isin(["all", "stress", "rest"])][["group", "cp", "pairs", "ms_vega", "ms_gamma", "ms_theta", "ms_carry", "ms_vanna", "ms_remainder", "xmom_vega", "xmom_gamma", "xmom_carry"]].round(4)"""),
    md("""
**Reading.**
- **The vega term is about 60% of the squared error, and the gamma term 27–34%.** The minimum-variance delta works on the vega term: the part of the volatility move that comes with the index move.
- **That part is small, a delta correction of about −0.04** (`xmom_vega`). Most of the vega risk is volatility moving on its own, which no delta can hedge. That caps what any delta rule can gain.
- **The remainder is about 1%,** so the second-order expansion holds even in March 2020: a check on the Greeks.
"""),
    md("""
## Other declared diagnostics
"""),
    code("""pd.read_csv(R / "2020/extra_diagnostics.csv")"""),
    md("""
**Reading.**
- **The size-weighted marks.** Under the Black–Scholes hedge (R1), the imbalance-weighted mid (WM) has about 2% less squared error than Lecture 12's size-weighted price (SW). Its changes covary negatively with the mid's hedging error, so the 16:00 size imbalance carries a little information, in the direction microstructure theory predicts.
- **Sensitivity A's level never reuses a hedged contract's quotes.** 363 pairs had ten days or less left on day two, and none of their expiries fed that day's fallback level fit.
"""),
    code("""
g[g.variant.isin(["day-two volume > 0", "day-two volume 0 or empty", "primary, block 5", "primary, block 20"]) & (g.rule == "R2") & g.base.isin(["R1", "R4"])][["variant", "cp", "base", "gain", "lo", "hi", "pairs"]].round(3)"""),
    code("""
g[(g.variant == "primary") & g.rule.isin(["R5", "R6"])][["cp", "rule", "base", "gain", "lo", "hi"]].round(3)"""),
    code("""
print(pd.read_csv(R / "2020/mean_error_by_gap.csv").round(6).to_string(index=False))
for cp in "CP":
    print(cp, pd.read_csv(R / f"2020/ljungbox_{cp}.csv").round(4).to_string(index=False))"""),
    code("""
mon = pd.read_csv(R / "2020/monitoring.csv", parse_dates=["session"])
fig, ax = plt.subplots()
for cp in "CP":
    x = mon[mon.cp == cp]
    ax.plot(x.session, x.trailing20_gain_known, label=f"{'calls' if cp == 'C' else 'puts'}")
ax.axhline(0, color="k", lw=0.8); ax.set_ylim(-2, 1)
ax.set_title("Monitoring illustration: trailing 20-session Gain of R2 over R1, as known on each day")
ax.legend()"""),
    md("""
**The monitoring illustration** shows what a desk would have seen: the trailing 20-session Gain, computed only from completed hedges. It first turns negative on 9 April (puts) and 14 April (calls), about four weeks after the worst days of mid-March, so it would have flagged the problem only partway through April. Per the plan, no switching rule is evaluated.
"""),
    md("""
## Exploratory challengers: a regression tree (R7) and gradient boosting (R8)
"""),
    code("""
g[g.variant.str.startswith("learners")][["cp", "rule", "base", "gain", "lo", "hi"]].round(3)"""),
    code("""pd.read_csv(R / "2020/smoothness.csv").round(4)"""),
    md("""
**Reading.**
- **The depth-3 tree (R7)** is not distinguished from Hull–White.
- **The boosted correction (R8) failed badly for puts.** It was tuned on 2019, when the trailing 20-day realized volatility never exceeded 31% and the worst 5-day return was −6%. In March 2020 those features reached 98% and −20%, far outside what the trees had seen, and their extreme leaves pushed the median put hedge ratio from −0.57 to −1.07. March's squared error was 13 times R2's; in every other month R8 tracked R2.
- **It is also rougher.** It has more out-of-order hedge ratios across adjacent strikes (2.8% against 1.8%) and 48% more daily turnover.

That is the failure mode the non-smooth-hedge argument predicts: a flexible learner extrapolates arbitrarily outside its training data.
"""),
    md("""
## SPY (§16.1)

The same protocol on SPY: American options (Lecture 12's tree for puts), SPY's own close, and distributions added to the hedge leg on ex-dates.
"""),
    code("""
s = pd.read_csv(R / "spy/gains.csv")
s[(s.rule == "R2") & s.base.isin(["R1", "R3", "R4"])][["variant", "cp", "base", "gain", "lo", "hi", "pairs"]].round(3)"""),
    md("""
**Reading.**
- **SPY tells the same story.** The point Gains are positive (0.10 for calls, 0.25 for puts), the intervals span zero, and the scaling rules are not distinguished.
- **The ex-date-only rows are too thin to read.** 2020 has three ex-dates with pairs, so most bootstrap draws contain none and the interval is undefined.
- **On ex-date pairs, adding the distribution to the hedge leg helps puts but not calls.** That is the limitation stated in advance: calls are priced as European. A deep in-the-money American call carries an early-exercise premium before the ex-date, which vanishes on it.
"""),
    md("""
## Heston (§16.2), in the style of Lecture 12

Heston's model makes the variance v a second random factor, correlated (ρ) with the index (Lecture 12).
- **Calibration.** Each session is calibrated with `scipy.optimize.least_squares`, as in the lecture. **L** fits the lecture's own sample (calls 50–100 days, sizes above 10, the size-weighted price), to price errors and to implied-volatility errors. **B** is a broader fit to out-of-the-money calls and puts, 14 days to a year.
- **Hedging.** The Heston minimum-variance delta, C_S + (ρξ/S)·C_v, is the model's own version of Hull and White's correction. It is compared with the Black–Scholes and Hull–White deltas on the 2020 pairs.
"""),
    code("""
p = pd.read_csv(R / "heston/params.csv", parse_dates=["session"])
p.groupby("fit").agg(sessions=("session", "size"), ok=("ok", "mean"), iv_rmse_median=("iv_rmse", "median"),
                     rho_median=("rho", "median"), xi_median=("xi", "median"), kappa_median=("kappa", "median")).round(4)"""),
    code("""
b = p[(p.fit == "B-iv") & p.ok.fillna(False).astype(bool)].set_index("session")
fig, axes = plt.subplots(1, 3, figsize=(14, 3.5))
for ax, c in zip(axes, ["v0", "rho", "xi"]):
    b[c].plot(ax=ax, title=f"calibration B: {c}")
plt.tight_layout()"""),
    code("""pd.read_csv(R / "heston/gains.csv").round(3)"""),
    md("""
**Reading** (`H_model`: the Heston model delta C_S; `H_mv`: the Heston minimum-variance delta):
- **The calibrations.**
  - The lecture's fit (L, 50–100-day calls) converges on 99.8% of sessions, with errors of 0.35–0.41 vol points.
  - The broad fit (B, out-of-the-money calls and puts, 14 days to a year) converges on 90%, with a median error of 1.9 vol points. Three-quarters of its fits put κ at the bound of 10: Heston strains to fit SPX's skew across maturities.
  - Through March 2020, v₀ rises to 0.3–0.9 (55–95% volatility) and ρ stays near −0.8.
- **The Heston model delta is far worse than Black–Scholes,** roughly doubling the squared error (Gains −1.30 and −1.11). As calibrated, Heston implies a smile that moves with the index (close to sticky delta), so its delta over-hedges calls and under-hedges puts.
- **Heston's minimum-variance delta repairs most of that,** through its ρξ·C_v/S term, and ends level with Black–Scholes (Gains +0.04 and +0.02, intervals spanning zero).
- **It is significantly worse than Hull and White's empirical rule:** −0.20 [−0.46, −0.13] for calls and −0.12 [−0.39, −0.01] for puts. This matches Hull and White's comparison with SABR: a correction estimated from historical co-movement beats one read off each day's smile.
- **The 57 sessions whose fits hit no bound.** For calls the ordering is the same: the Heston minimum-variance delta is worse than R2, −0.05 [−0.35, −0.01]. For puts, the model delta, the minimum-variance delta and R2 cannot be told apart, and all are below Black–Scholes on those days. Those sessions are not a random subset: a fit without bound hits is a day on which Heston happens to fit well.
"""),
])


NOTEBOOKS["06"] = ("06_walkforward_2011_2023", [
    md("""
# 06 · Stability across years: the 2011–2023 walk-forward

**The project question asks** how stable the minimum-variance delta's advantage is across years. The pre-declared walk-forward (`analysis_plan.md` §14, item 2) answers it.
- **The design.** Coefficients are refitted monthly on trailing 12-, 36- and 60-month windows. The windows are compared on their common test months, 2015-01 to 2023-12; the 12- and 36-month windows also start earlier.
- **Intervals.** Each year gets its own session-block bootstrap.
- **Which years count as clean.** 2015–2020 had already been used for fitting or evaluation, so the clean held-out years are 2011–2013 and 2021–2023 (`results/year_ledger.csv`).
"""),
    code(SETUP),
    code("""
g = pd.read_csv(R / "walkforward/gains_by_year.csv")
t = g[(g.rule == "R2") & (g.base == "R1")].pivot_table(index=["year", "status"], columns=["window", "cp"], values="gain")
t.round(3)"""),
    code("""
from IPython.display import Image
Image(filename=str(R / "figures/walkforward_by_year.png"))"""),
    code("""pd.read_csv(R / "walkforward/median_yearly_gain.csv").round(3)"""),
    code("""
g[(g.rule == "R2") & g.base.isin(["R1", "R4"]) & (g.year >= 2021)][["window", "year", "cp", "base", "gain", "lo", "hi"]].round(3)"""),
    md("""
**Reading.**
- **Through 2021 the advantage is real and fairly steady.** With the 12-month window the Gain over Black–Scholes is positive every year, mostly 0.10–0.25. In 2021, a clean year, it is significant for both calls and puts, and R2 also beats the fitted scaling rule.
- **In 2022–2023 it disappears.** With the 12-month window it is about 0, with tight intervals in 2023. With the longer windows it turns negative in 2022: for puts, R2 is significantly worse than the fitted scaling rule.
"""),
    code("""pd.read_csv(R / "walkforward/spot_vol_slope.csv").round(3)"""),
    md("""
**Why.** The minimum-variance correction works through the co-movement of implied volatility and the index.
- **The slope collapsed.** Near the money, that slope was 0.25–0.55 vol points per 1% fall in 2011–2021, and 0.13 in both 2022 and 2023.
- **So the fitted coefficients were too large.** They had learned a stronger relation than the market then delivered. Longer windows remember more of it, and suffered more.
- **The earlier analogue.** 2017, the earlier low-slope year, also had the smallest earlier Gains.

This is a descriptive reading. A model validator would take it as the case for monitoring the spot–volatility slope alongside the hedge.
"""),
    md("""
## The boosted challenger in the walk-forward

R8 is retuned once on 2015–2016, with validation pairs ending before 2017, then refitted monthly on the 12-month window from 2017 on. Each row is its relative Gain over R2.
"""),
    code("""
w = pd.read_csv(R / "walkforward/r8_by_year.csv")
w[w.rule == "R8"][["year", "cp", "gain", "lo", "hi"]].round(3)"""),
    md("""
**Reading.**
- **The tuning chose a minimal model:** 51 trees, a learning rate of 0.01, 4 leaves.
- **In most years R8 is within a few percent of R2.**
- **2020 puts are the exception.** The crash pushed the features far outside their training range, and even this small correction more than doubled R2's squared error (relative Gain −1.98). The same failure appears in the 2020 test (notebook 05).
"""),
])


def build(key: str) -> None:
    name, cells = NOTEBOOKS[key]
    nb = nbformat.v4.new_notebook()
    nb.cells = cells
    nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    NB.mkdir(exist_ok=True)
    NotebookClient(nb, timeout=1800, kernel_name="python3", resources={"metadata": {"path": str(NB)}}).execute()
    nbformat.write(nb, NB / f"{name}.ipynb")
    print("wrote", NB / f"{name}.ipynb", flush=True)


if __name__ == "__main__":
    for k in sys.argv[1:] or sorted(NOTEBOOKS):
        build(k)
