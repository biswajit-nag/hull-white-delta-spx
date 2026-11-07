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
- the exploratory challenger;
- the first SPY extension (§16.1).

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
## Exploratory challenger: gradient boosting (R8)
"""),
    code("""
g[g.variant.str.startswith("learners") & (g.rule == "R8")][["cp", "rule", "base", "gain", "lo", "hi"]].round(3)"""),
    code("""pd.read_csv(R / "2020/smoothness.csv").round(4)"""),
    md("""
**Reading.**
- **The boosted correction (R8) failed badly for puts.** It was tuned on 2019, when the trailing 20-day realized volatility never exceeded 31% and the worst 5-day return was −6%. In March 2020 those features reached 98% and −20%, far outside what the trees had seen, and their extreme leaves pushed the median put hedge ratio from −0.57 to −1.07. March's squared error was 13 times R2's; in every other month R8 tracked R2.
- **It is also rougher.** It has more out-of-order hedge ratios across adjacent strikes (2.8% against 1.8%) and 48% more daily turnover.

That is the failure mode the non-smooth-hedge argument predicts: a flexible learner extrapolates arbitrarily outside its training data.
"""),
    md("""
## SPY (§16.1)

*Superseded on 2026-11-05 by the full replication of plan §16.3: see notebook 07. The numbers below are the 2026-11-04 exploratory run, kept as the record.*

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


NOTEBOOKS["07"] = ("07_spy_replication", [
    md("""
# 07 · SPY: a full replication of the SPX protocol (plan §16.3)

**What changes for SPY.**
- **The options are American** and settle into shares. Puts are priced on Lecture 12's tree (150 steps, control variate), with δ, ν, vanna and theta from finite differences on the same tree. Calls are priced as European, as the lecture does.
- **SPY pays quarterly dividends.** The distribution enters the hedge leg on ex-dates.
- **The index level is SPY's close:** Nasdaq's from 2016-11-03, and before that Stooq's, with its dividend adjustment reversed (checked against Nasdaq on 1,821 sessions: median 0.43 bp in level, 0.14 bp in return).
- **The dividend yield** comes from SPX's implied carry, using the SPX close on the few sessions without SPX's options-implied level (plan §15).

**What is the same:** every SPX procedure that applies.
- the rehearsal and its specification checks on 2018–2019;
- R8's tuning on 2019, and the dry run;
- 2020 with every Table 8.1 variant except A (American parity gives no options-implied level), and the verdict table;
- the 2011–2023 walk-forward.

**Status.** SPY's 2020 Gains for R0–R5 were first computed on 2026-11-04, so this 2020 verdict is post hoc. The clean evidence is the untouched SPY years: 2011–2014, 2017 and 2021–2023 (`results/spy/year_ledger_spy.csv`).
"""),
    code(SETUP),
    code("""pd.read_csv(R / "spy/year_ledger_spy.csv")"""),
    md("## The rehearsal's specification checks (2018 and 2019)"),
    code("""
pd.concat([pd.read_csv(R / f"spy/rehearsal/spec_checks_{y}.csv").assign(year=y) for y in (2018, 2019)]).round(4)"""),
    md("""
**Reading.** 2018 contradicts nothing. In 2019 the cubic beats the quadratic for both types, and τ^−0.75 and τ^−1 beat 1/√τ for calls, all by small margins. Those variants were carried to 2020 as exploratory rules.
"""),
    md("## 2020: the verdict and its robustness"),
    code("""pd.read_csv(R / "spy/2020/verdict.csv").round(3)"""),
    code("""
g = pd.read_csv(R / "spy/2020/gains.csv")
g[(g.variant == "primary")][["cp", "rule", "base", "gain", "lo", "hi", "pairs"]].round(3)"""),
    code("""
pd.read_csv(R / "spy/2020/descriptives.csv").query("rule in ['R0','R1','R2','R3','R4']")[["cp", "rule", "rms_dollars_per_contract", "effectiveness_vs_R0", "stress_share_R1"]].round(3)"""),
    code("""
pd.concat([g[g.variant.isin(["learners (feature-complete)", "carried variants"])],
           pd.read_csv(R / "spy/2020/r9_r11.csv").query("variant == 'primary'").assign(variant="R9-R11 (primary)")])[["variant", "cp", "rule", "base", "gain", "lo", "hi"]].round(3)"""),
    md("""
**Reading.**
- **Inconclusive, like SPX.** G is 0.104 [−0.30, 0.40] for calls and 0.238 [−0.25, 0.48] for puts. R2 is not distinguished from R3 or R4, and every robustness variant is Inconclusive too.
- **R8 and R10 collapse for puts** in the crash (Gains of about −52 against R2).
- **The δ-only learners R9 and R11 and the carried cubic** beat R2 by a significant but tiny +0.003 to +0.005.
- **The carried τ-scalings are worse than R2.**
"""),
    md("## The 2011–2023 walk-forward"),
    code("""
w = pd.read_csv(R / "spy/walkforward/gains_by_year.csv")
t = w[(w.rule == "R2") & (w.base == "R1")].pivot_table(index=["year", "status"], columns=["window", "cp"], values="gain")
t.round(3)"""),
    code("""
fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for ax, cp, nm in zip(axes, "CP", ("calls", "puts")):
    for W in (12, 36, 60):
        x = w[(w.rule == "R2") & (w.base == "R1") & (w.cp == cp) & (w.window == W)].sort_values("year")
        ax.plot(x.year, x.gain, marker="o", label=f"W{W}")
        if W == 12:
            ax.fill_between(x.year, x.lo, x.hi, alpha=0.15)
    ax.axhline(0, color="k", lw=0.8); ax.set_title(f"SPY {nm}: Gain of R2 over Black–Scholes"); ax.legend()
plt.tight_layout()"""),
    code("""
med = pd.concat([pd.read_csv(R / f"spy/walkforward/{f}.csv").assign(source=f) for f in
                 ("median_yearly_gain", "r5_r8_median_yearly_gain", "r9_r11_median_yearly_gain", "degrees_median_yearly_gain")])
med[med.window == 12].pivot_table(index="rule", columns=["base", "cp"], values="median_yearly_gain").round(3)"""),
    code("""pd.read_csv(R / "spy/walkforward/exdate_by_year.csv").query("pairs == 'ex-date'").round(3)"""),
    md("""
**Reading.**
- **The same pattern as SPX, clearer for puts.** In the clean years 2011–2014 and 2021, R2's put Gain over Black–Scholes is 0.21–0.28, with intervals above 0. The advantage is gone in 2022–2023, and with the long windows puts go strongly negative in 2022.
- **For SPY calls the fixed 0.9 scaling is worse than Black–Scholes** in most years; R2 and the fitted scaling stay positive.
- **The δ-shape rules (R5, R9, R11, P3 and above) add +0.002 to +0.007 a year** over R2.
- **Ex-date pairs** hold 0.3–9% of a year's squared error, with no systematic loss.
"""),
])

NOTEBOOKS["08"] = ("08_more_rules_and_short_dated", [
    md("""
# 08 · More rules: the learners decomposed, the polynomial degree, and short-dated options

Three sets of rules were added on 2026-11-05, each specified and committed before its run:
- **R5–R8 under every protocol** (plan §16.4).
- **R9–R11** (§16.7). With R8 they form a 2×2 design: a LightGBM correction learned from scratch (R9, R10) or boosted from R2 (R11, R8), on δ alone (R9, R11) or on six features (R10, R8).
- **P0–P8 and PCV** (§16.8): R2's quadratic replaced by a polynomial of degree 0–8, and a degree chosen by validation inside each training window.

Plus **short-dated options** (§16.6): under 14 days, each pair ending before settlement. All of this is exploratory: it was specified after the 2020 test had been seen.
"""),
    code(SETUP),
    md("## 2020: the learners under the Table 8.1 variants (Gain over R2)"),
    code("""
lv = pd.read_csv(R / "2020/learners_variants.csv"); r9 = pd.read_csv(R / "2020/r9_r11.csv")
both = pd.concat([lv[lv.base == "R2"], r9[(r9.base == "R2") & r9.rule.isin(["R9", "R10", "R11"])]])
both.pivot_table(index="variant", columns=["rule", "cp"], values="gain").round(3)"""),
    md("""
**Reading.** Both learners that use the six features (R8, R10) collapse for puts in most variants: the March 2020 crash pushed volatility and returns far outside their calm training range. Both δ-only learners (R9, R11) stay within ±0.02 of R2 everywhere. The features broke R8, not the boosting.
"""),
    md("## The walk-forward, 2011–2023: median yearly Gains over 2015–2023"),
    code("""
med = pd.concat([pd.read_csv(R / f"walkforward/{f}.csv") for f in
                 ("median_yearly_gain", "r5_r8_median_yearly_gain", "r9_r11_median_yearly_gain", "degrees_median_yearly_gain")])
med = med.drop(columns=[c for c in ("sample",) if c in med]).drop_duplicates(["window", "cp", "rule", "base"])
med.pivot_table(index="rule", columns=["base", "window", "cp"], values="median_yearly_gain").round(3)"""),
    code("""
d = pd.read_csv(R / "walkforward/degrees_by_year.csv"); r9w = pd.read_csv(R / "walkforward/r9_r11_by_year.csv")
x = pd.concat([d[(d.base == "R2") & d.rule.isin(["P0", "P3", "PCV"])], r9w[(r9w.base == "R2") & r9w.rule.isin(["R9", "R11"])]])
fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
for ax, cp, nm in zip(axes, "CP", ("calls", "puts")):
    for rule, z in x[(x.window == 12) & (x.cp == cp)].groupby("rule"):
        z = z.sort_values("year"); ax.plot(z.year, z.gain, marker="o", label=rule)
    ax.axhline(0, color="k", lw=0.8); ax.set_title(f"SPX {nm}: Gain over R2 (12-month window)"); ax.legend()
plt.tight_layout()"""),
    code("""
c = pd.read_csv(R / "walkforward/degrees_pcv_choice.csv")
c.groupby(["window", "cp"]).degree.value_counts().unstack(fill_value=0)"""),
    md("""
**Reading.**
- **Every rule built on Hull–White's form tracks R2 within a few thousandths a year.** On SPX, R5 equals R2; R9 gains about +0.001 to +0.002; P3–P8 add nothing.
- **The constant P0 is about as good as R2,** and better in 2022–2023 for puts on the long windows.
- **PCV mostly picks degree 0.** It is never significantly worse than R2.
- **The more flexible learner does worse:** R10.
"""),
    md("""
## Why R9's tuned correction is nearly constant

Refit on 2019 (the window that feeds January 2020): R2's quadratic, R9's tuned h(δ) and the constant fit, as corrections g(δ) in the hedge δ + ν/(S√τ)·g(δ). The x² weights that the loss uses peak near the money.
"""),
    code("""
# fitted on the 2019 pairs by scripts/correction_curves.py; the shaded bars are the x²-weighted distribution of δ
cur = pd.read_csv(R / "rehearsal/correction_curves_2019.csv")
wts = pd.read_csv(R / "rehearsal/correction_weights_2019.csv")
fig, axes = plt.subplots(1, 2, figsize=(11, 4))
for ax, cp in zip(axes, "CP"):
    c, w = cur[cur.cp == cp], wts[wts.cp == cp]
    ax.plot(c.delta, c.R2, label="R2 quadratic"); ax.plot(c.delta, c.R9, label="R9 tuned h(δ)")
    ax.axhline(c.P0.iloc[0], ls="--", color="gray", label="constant (P0)")
    edges = np.r_[w.left.to_numpy(), w.right.iloc[-1]]
    ax2 = ax.twinx(); ax2.hist(w.left, bins=edges, weights=w.weight, alpha=0.15, color="k"); ax2.set_yticks([])
    ax.set_title({"C": "calls", "P": "puts"}[cp] + ": correction g(δ), SPX 2019"); ax.set_xlabel("δ"); ax.legend()
plt.tight_layout()"""),
    md("""
**Reading.** R9 follows R2's shape where the weight lies and flattens toward the constant in the tails. R2's own curve is nearly flat there too. Out of sample on its 2019 tuning folds, the constant matched R2 (+0.014 for calls, +0.000 for puts). Validation therefore shrinks R9 toward a constant: with all options on a session sharing one index move, about 125 independent shocks per fold cannot support much δ-shape. Details: `notes/unified-results.md` §3.2.
"""),
    md("## Short-dated options (under 14 days)"),
    code("""
s = pd.read_csv(R / "short_dated/gains_by_year.csv")
s[s.rule.isin(["R2m", "R2s"])].pivot_table(index="year", columns=["rule", "base", "cp"], values="gain").round(3)"""),
    code("""
b = pd.read_csv(R / "short_dated/buckets.csv")
b.groupby(["cp", "days"])[["G_R2m_R1", "G_R2s_R1", "pairs"]].median().round(3)"""),
    md("""
**Reading.** Close to expiry, vega is small and the correction has little to work with. R2's coefficients from options of 14 days or more (R2m) gain a median 0.06 for calls and 0.005 for puts over Black–Scholes. That comes mainly from the 7–13-day options. Refitting on short-dated options (R2s) does not help.
"""),
])

NOTEBOOKS["09"] = ("09_stress_stability_and_interpretation", [
    md("""
# 09 · Stress periods, parameter stability, the level of the correction, and the published Gains

The brief's model-validation direction asks to "stress-test assumptions" and "study parameter stability". This notebook collects the analyses of plan §16.9–§16.10, all descriptive and post hoc:
- **stress episodes 2011–2023,** defined from the S&P 500 close alone;
- **parameter stability** at every monthly refit, with session-clustered standard errors;
- **the maturity assumption** (1/√τ), tested by year;
- **the split of the Gain into the correction's level and its shape;**
- **our Gains under the published aggregations.**
"""),
    code(SETUP),
    md("## Stress episodes (SPX, out-of-sample, 12-month window)"),
    code("""
E = pd.read_csv(R / "walkforward/stress_episodes.csv"); E"""),
    code("""
G = pd.read_csv(R / "walkforward/stress_gains.csv")
x = G[(G.window == 12) & (G.rule == "R2") & (G.base == "R1")]
x[["definition", "start", "end", "cp", "gain", "lo", "hi", "sessions", "share_of_year_R1_sse", "c_fit_mean", "c_post"]].round(3)"""),
    code("""
fig, ax = plt.subplots(figsize=(10, 4))
for cp, mk in (("C", "o"), ("P", "s")):
    z = x[x.cp == cp]
    ax.scatter(z.c_post - z.c_fit_mean, z.gain, marker=mk, label={"C": "calls", "P": "puts"}[cp])
ax.axhline(0, color="k", lw=0.8); ax.axvline(0, color="k", lw=0.8)
ax.set_xlabel("best level afterwards − fitted level (positive: the fit over-corrected)"); ax.set_ylabel("Gain of R2 over R1")
ax.set_title("Stress episodes: the Gain falls when the fitted level overstates the realized one"); ax.legend()"""),
    code("""
Y = pd.read_csv(R / "walkforward/stress_by_year.csv")
Y[(Y.window == 12) & (Y.rule == "R2") & (Y.base == "R1")].pivot_table(index="year", columns=["regime", "cp"], values="gain").round(3)"""),
    md("""
**Reading.**
- **R2 gains in sell-offs:** every peak-to-trough drawdown, significantly in 2011, 2015–2016 and the February 2018 drop.
- **It loses in rebounds and post-trough volatility,** significantly in September–December 2022. There, implied volatility no longer rose as the index fell, and the fitted level over-corrected.
- **The stable spot–volatility assumption** therefore fails in one direction of stress, not the other.

SPY's episodes, in `results/spy/walkforward/stress_gains.csv`, show the same pattern.
"""),
    md("## Parameter stability"),
    code("""
pp = pd.read_csv(R / "walkforward/parameter_paths.csv")
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
for ax, cp, nm in zip(axes, "CP", ("calls", "puts")):
    for rule, coef, lab in (("P0", "c0", "level c (P0)"), ("R2", "b", "R2's b"), ("R2", "c", "R2's c")):
        z = pp[(pp.window == 12) & (pp.cp == cp) & (pp.rule == rule) & (pp.coef == coef)]
        t = pd.PeriodIndex(z.month, freq="M").to_timestamp()
        ax.plot(t, z.value, label=lab); ax.fill_between(t, z.value - 2 * z.se, z.value + 2 * z.se, alpha=0.15)
    ax.axhline(0, color="k", lw=0.8); ax.set_title(f"SPX {nm}: coefficients at each 12-month refit (±2 clustered SE)"); ax.legend()
plt.tight_layout()"""),
    code("""
S = pd.read_csv(R / "walkforward/parameter_stability_summary.csv")
S[S.window == 12][["cp", "rule", "coef", "min", "median", "max", "median_se", "median_abs_change_over_se", "share_abs_z12_gt_2", "median_corr_bc"]].round(3)"""),
    md("""
**Reading.**
- **R2's three coefficients are poorly identified one by one:** b and c are nearly collinear (|correlation| about 0.9). The level they imply is well identified.
- **That level drifts beyond sampling error** between non-overlapping years (|z| > 2 in 10–19% of comparisons), from about −0.34 to near zero.
- **Longer windows are smoother but staler.**
"""),
    md("## The maturity assumption (1/√τ), by year"),
    code("""
M = pd.read_csv(R / "walkforward/maturity_by_year.csv")
M[M.regime == "all"].pivot_table(index="year", columns=["rule", "cp"], values="gain").round(3)"""),
    md("**Reading.** No alternative exponent beats 1/√τ consistently, in any year or regime; α = 0 and α = 1 are worse in most years."),
    md("## The level and the shape of the correction"),
    code("""
L = pd.read_csv(R / "walkforward/level_shape_by_year.csv")
L[["year", "cp", "c_fit", "c_post", "G_level_P0_R1", "G_shape_R2_P0", "G_R2_R1", "G_ceiling_P0post_R1", "vol_points_per_1pct_fall"]].round(3)"""),
    md("""
**Reading.**
- **The level of R2's correction equals P0's constant exactly:** the first normal equation of R2's least-squares fit.
- **The level supplies the Gain;** the shape adds at most about ±0.015 a year on SPX.
- **For a constant correction c, the Gain over R1 is G* · [1 − ((c − c*)/c*)²],** with c* the best constant afterwards and G* the ceiling it would give. An error in the level therefore costs quadratically, and overshooting by more than a factor of two loses to Black–Scholes. That is what happened in 2022.

Derivation: `notes/level-and-shape-of-the-correction.md`.
"""),
    md("## Our Gains under the published aggregations"),
    code("""
P = pd.read_csv(R / "walkforward/published_comparison.csv")
P[P.rule == "R2"].pivot_table(index=["window", "period", "sample"], columns="cp", values=["pooled", "mean_of_monthly"]).round(3)"""),
    md("""
**Reading.**
- **On the same years and a comparable window, our pooled Gains match Hull and White's:** 0.22 / 0.25 on their 2013–2015 overlap with 36 months, against their 0.26 / 0.23 for 2007–2015.
- **Against Ruf and Wang** (their period, out of the money), our puts match theirs and our calls fall short.
- **Our headline numbers are lower** because of the later years, the 12-month primary window, and in-the-money calls.
- **Hull and White's monthly averaging** makes our Gains look lower still.
"""),
])


NOTEBOOKS["10"] = ("10_books_starvation_held_positions", [
    md("""
# 10 · Books, data starvation and held positions

Plan §16.11, §16.13 and §16.14, specified 2026-11-05 and revised 2026-11-06 before any of them ran. All are descriptive and exploratory; only SPX 2020's verdict is a pre-registered test. The rules are those of the preamble to §16.11:
R1 (Black–Scholes), R2 (Hull–White), R3 (Ruf–Wang fixed), R4 (Ruf–Wang fitted), R6 (delta–vega–vanna), R9 (LightGBM on δ) and P0 (a constant correction).

Each is refitted monthly on the trailing 12 months unless stated. The intervals are session-block bootstraps, as everywhere in the project.
"""),
    code(SETUP + """
U = [u for u in ("spx", "spy") if (R / "extensions" / u).exists()]
U"""),
    md("""
## 1. Books (§16.14)

The Gain pools each option's squared error as if each were hedged alone. A dealer hedges the net delta of a book, where option-specific errors diversify away and the day's shared move adds up.

Four books are formed each session from day-one information: all calls; all puts; out-of-the-money puts and calls (long volatility); and a risk reversal, long OTM calls and short OTM puts, as the control. A book's error is the mean of its options' errors.
"""),
    code("""
for u in U:
    m = pd.read_csv(R / "extensions" / u / "books_median_yearly_gain.csv")
    m = m[(m.base == "R1") & m.rule.isin(["R2", "P0", "R3", "R4", "R9"])]
    print(u.upper(), "median yearly Gain over Black-Scholes, 2011-2023")
    display(m.pivot_table(index=["book", "rule"], columns="measure", values="median_yearly_gain").round(3))"""),
    code("""
for u in U:
    s = pd.read_csv(R / "extensions" / u / "books_common_share.csv")
    print(u.upper(), "share of the per-option squared error that survives averaging (median over years)")
    display(s.groupby("book").common_share_R1.median().round(3))"""),
    code("""
for u in U:
    b = pd.read_csv(R / "extensions" / u / "books_by_year.csv")
    x = b[(b.rule == "R2") & (b.base == "R1") & b.year.isin([2020, 2022])]
    print(u.upper(), "R2 over R1 in 2020 and 2022")
    display(x.pivot_table(index=["year", "book"], columns="measure", values=["gain", "lo", "hi"]).round(3))"""),
    md("""
**Reading (SPX; SPY is the same in direction).**
- **A dealer hedging a book sees more of the Gain than the per-option numbers suggest.** SPX's median yearly Gain of R2 over Black–Scholes is 0.22 on the call book against 0.15 per option, and 0.17 against 0.12 for puts.
- **The reason:** about 70% of an option's squared error survives averaging across a book. That is the day's shared move, which the correction targets; option-specific noise diversifies away.
- **The amplification works both ways:** in 2022 the SPX put book lost 0.14, against 0.06 per option.
- **The risk reversal is the control.** Its volatility exposures cancel, so it keeps 12% of the error, and the corrections gain 0.04.
"""),
    md("""
## 2. Data starvation (§16.13)

**Fewer sessions:** 1-, 2-, 3- and 6-month windows. **Fewer options per session:** 12-month fits on 25%, 5% or 1% of each training session's options, or on 10 or 3 per session and type, with five seeds.

The plan stated the expectation in advance: the information is in the number of sessions, because every option on a day shares that day's index move.
"""),
    code("""
for u in U:
    sp = pd.read_csv(R / "extensions" / u / "starve_seed_spread.csv")
    first = sp.span.iloc[0]
    x = sp[(sp.base == "R1") & sp.rule.isin(["R2", "P0", "R9"]) & (sp.span == first)]
    print(u.upper(), "median yearly Gain over R1,", first, "(median over seeds; min and max for thinning)")
    display(x.pivot_table(index="config", columns=["rule", "cp"], values="median").round(3))
    display(x[x.config.str.startswith(("frac", "k"))].pivot_table(index=["config", "rule"], columns="cp", values=["min", "max"]).round(3))"""),
    code("""
for u in U:
    G = pd.read_csv(R / "extensions" / u / "starve_by_year.csv")
    w = G[(G.rule == "R2") & (G.base == "R1") & G.config.isin(["W1", "W2", "W3", "W6", "W12"])]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), sharey=True)
    for ax, cp in zip(axes, "CP"):
        p = w[w.cp == cp].pivot_table(index="year", columns="config", values="gain")[["W1", "W2", "W3", "W6", "W12"]]
        p.plot(ax=ax, marker="o", ms=3)
        ax.axhline(0, color="k", lw=0.8); ax.set_title(f"{u.upper()} {'calls' if cp == 'C' else 'puts'}: R2 over R1 by training window")
    plt.tight_layout()"""),
    md("""
**Reading.**
- **The plan's expectation holds: the information is in the number of sessions, not options.**
  - On SPX, three options per session and type keep a median yearly Gain of 0.138 (calls) and 0.124 (puts), against 0.151 and 0.120 with every option. Over five seeds the range is 0.130–0.140 and 0.120–0.131.
  - Windows of one or two months cut the Gain to about 0.09 and 0.03–0.05.
- **Short windows adapt faster to a regime change.** In 2022 a 3-month window gave +0.071 and +0.047, against +0.002 and −0.058 on 12 months. In 2020 the 12-month window was best.
- **No window is best every year:** a long window estimates the level precisely but goes stale; a short one tracks it but is noisy.
- **SPY shows the same.** R9, a tree learner, loses more than R2 when thinned: it needs more data than three linear coefficients.
"""),
    md("""
## 3. Held positions (§16.11)

A path is H one-session hedges in a row on one contract (H = 5 or 10 sessions), re-hedged at every close with that day's ratio, as a desk would do. After the start, the contract is followed whatever its delta, maturity or volume, because dropping it when it leaves the band would select on the outcome.

The path error is the sum of the daily dollar errors, in units of the index level on the start day. The one-session Gain on exactly the same pairs is reported beside it.
"""),
    code("""
for u in U:
    f = R / "extensions" / u / "paths_gains.csv"
    if not f.exists():
        continue
    G = pd.read_csv(f)
    x = G[(G.subset == "all") & (G.base == "R1") & G.rule.isin(["R2", "P0", "R3", "R4", "R9"]) & ~G.period.str.fullmatch(r"\\d{4}")]
    print(u.upper(), "pooled periods: path Gain against the one-session Gain on the same pairs")
    display(x.pivot_table(index=["H", "period", "rule"], columns=["measure", "cp"], values="gain").round(3))"""),
    code("""
for u in U:
    f = R / "extensions" / u / "paths_gains.csv"
    if not f.exists():
        continue
    G = pd.read_csv(f)
    y = G[(G.subset == "all") & (G.base == "R1") & (G.rule == "R2") & G.period.str.fullmatch(r"\\d{4}")]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), sharey=True)
    for ax, cp in zip(axes, "CP"):
        p = y[y.cp == cp].pivot_table(index="period", columns=["H", "measure"], values="gain")
        p.plot(ax=ax, marker="o", ms=3)
        ax.axhline(0, color="k", lw=0.8); ax.set_title(f"{u.upper()} {'calls' if cp == 'C' else 'puts'}: R2 over R1, paths and one session")
    plt.tight_layout()"""),
    code("""
for u in U:
    f = R / "extensions" / u / "paths_mean_error.csv"
    if not f.exists():
        continue
    M = pd.read_csv(f)
    print(u.upper(), "mean path error and its difference from Black-Scholes (units of the start-day index level)")
    display(M[(M.subset == "all") & M.rule.isin(["R2", "P0", "R3", "R4"]) & ~M.period.str.fullmatch(r"\\d{4}")]
            .pivot_table(index=["H", "period", "rule"], columns="cp", values=["diff_vs_R1", "diff_lo", "diff_hi"]).round(6))
    display(pd.read_csv(R / "extensions" / u / "paths_attrition.csv").groupby("H")[["eligible", "complete", "left_band"]].sum())
    display(pd.read_csv(R / "extensions" / u / "paths_day0_check.csv").max_abs_diff.max())"""),
    md("""
**Reading (SPX).**
- **Checks.**
  - On 2,271,477 first days the path code's error equals the walk-forward's exactly.
  - 94% (5 sessions) and 89% (10 sessions) of eligible paths complete.
  - 15% and 25% of completed paths leave the band at least once. They would have been lost had positions been dropped there, and on the in-band-only subset the Gain is smaller.
- **On real SPX quotes the Gain grows with the holding period.** In 2011–2019, R2 removes 0.185 / 0.200 of a 5-session position's squared error and 0.241 / 0.338 of a 10-session one's, against 0.133 / 0.118 one session at a time.
  - In 2020: 0.256 / 0.277 (5 sessions) and 0.313 / 0.385 (10).
  - Two reasons: quote noise in the mids telescopes away in a path's sum, and the spot–volatility move accumulates over a multi-day sell-off.
- **Losses grow too:** 2021–2023 puts −0.108 over 5 sessions.
- **The expected-P&L cost of the correction is about 1 bp of the index over 5 sessions, and not significant,** so the Sharpe-ratio argument's assumption roughly holds.
- **SPY** shows the same growth in 2011–2019. But its Greeks exist only for first-day candidates, so its paths are restricted to traded days with at least 14 days to expiry (§15).
"""),
])


NOTEBOOKS["11"] = ("11_single_stocks_and_etfs", [
    md("""
# 11 · Single stocks and ETFs: AAPL, NVDA, TSLA, QQQ and SLV, 2016–2023

Plan §16.15: the SPY protocol on five more underlyings, specified before any of their outcomes was computed. Exploratory; no verdict.

**Data and method.**
- OptionsDX end-of-day files, the same format as SPX and SPY, with our own implied volatilities and Greeks:
  - puts from Lecture 12's American tree;
  - calls from European Black–Scholes with the dividend yield;
  - rates from SPX's parity curve;
  - dividends from Nasdaq's history (TSLA and SLV pay none).
- The level is the vendor's snapshot. Pairs straddling a stock split are excluded.
- The rules are R1–R4, R6, R9 and P0.

**Context.** Hull and White's Table 3 (2004–2015, 36-month window) gives an average Gain over the 30 Dow stocks of 10.3% for calls and 2.5% for puts, and 7.7% and 2.5% for three commodity ETFs, one of them SLV.
"""),
    code(SETUP + """
U = [u for u in ("aapl", "nvda", "tsla", "qqq", "slv") if (R / "stocks" / u / "walkforward_gains_by_year.csv").exists()]
U"""),
    md("## Data audit and attrition"),
    code("""
for u in U:
    for f in sorted((R / "stocks" / u).glob("audit*.csv")) + sorted((R / "stocks" / u).glob("attrition*.csv")):
        print(u.upper(), f.name); display(pd.read_csv(f).head(20))
    s = R / "stocks" / u / "splits.csv"
    if s.exists():
        print(u.upper(), "splits detected"); display(pd.read_csv(s))"""),
    md("## 2020 as the test year (2019 training, 12-month window), under the verdict procedure of §8"),
    code("""
rows = []
for u in U:
    v = pd.read_csv(R / "stocks" / u / "test2020_verdict.csv").assign(underlying=u.upper())
    rows.append(v)
pd.concat(rows)[["underlying", "variant", "verdict", "G_C", "G_C_lo", "G_C_hi", "G_P", "G_P_lo", "G_P_hi", "C_vs_R3", "C_vs_R4", "P_vs_R3", "P_vs_R4"]].round(3)"""),
    md("""
**Reading.** None of the five passes H1 in 2020.
- **AAPL, TSLA and QQQ are Inconclusive.**
- **NVDA is Reject (b):** both upper bounds are below the 0.05 the plan calls material.
- **SLV is Reject (a):** its put interval lies below zero, so R2 is significantly worse than Black–Scholes.
- **Outside the stress period, AAPL's, NVDA's and QQQ's calls lose significantly.** It is SPX's April 2020 lesson again: the crash entered the training window and the fits over-corrected.
"""),
    md("## The walk-forward: Gain over Black–Scholes by year"),
    code("""
for u in U:
    G = pd.read_csv(R / "stocks" / u / "walkforward_gains_by_year.csv")
    x = G[(G.window == 12) & (G.base == "R1") & G.rule.isin(["R2", "R3", "R4", "R6", "R9", "P0"])]
    print(u.upper(), "W12, Gain over R1")
    display(x.pivot_table(index="year", columns=["rule", "cp"], values="gain").round(3))"""),
    code("""
med = []
for u in U:
    m = pd.read_csv(R / "stocks" / u / "walkforward_median_yearly_gain.csv").assign(underlying=u.upper())
    med.append(m[(m.base == "R1") & m.rule.isin(["R2", "R3", "R4", "R9", "P0"])])
pd.concat(med).pivot_table(index=["underlying", "window"], columns=["rule", "cp"], values="median_yearly_gain").round(3)"""),
    md("""
**Reading.**
- **The single stocks gain little or lose.** AAPL's median yearly Gain of R2 is 0.04–0.06 for calls and at most 0.02 for puts. NVDA and TSLA are near zero or negative.
- **QQQ, an index ETF, behaves like SPX:** 0.06–0.08 on the 12- and 36-month windows.
- **SLV gains nothing.**
- **Ruf and Wang's fixed 0.9/1.1 scaling (R3), calibrated to S&P 500 options, is harmful off the index:** −0.05 to −0.37 for calls on the stocks.
"""),
    md("## Beside Hull and White's Table 3 (mean of monthly Gains, 36-month window)"),
    code("""
hw = {"C": {"Stocks": 0.103, "Commodity ETFs": 0.077}, "P": {"Stocks": 0.025, "Commodity ETFs": 0.025}}
rows = []
for u in U:
    t = pd.read_csv(R / "stocks" / u / "hw_table3_comparison.csv")
    a = t[t.bucket.astype(str) == "all"].set_index("cp").gain
    rows.append({"underlying": u.upper(), "calls (ours)": a.get("C"), "puts (ours)": a.get("P")})
display(pd.DataFrame(rows).round(3)); hw"""),
    md("""
**Reading.**
- **Our aggregation of Hull and White's kind gives the stocks far less** than their Dow-stock average of 0.103 (calls) and 0.025 (puts). The direction matches theirs: much less than for indices, and almost nothing for puts.
- **Their explanation fits.** Noise inserts a wedge between the parameters estimated in one period and those that would hedge best in the next.
- **A caution on reading QQQ's row.** The monthly average can be negative even when the pooled yearly Gains are positive, because single months with large losses weigh as much as calm months.
"""),
    md("## Stress episodes, parameter stability, level and shape, maturity"),
    code("""
for u in U:
    S = pd.read_csv(R / "stocks" / u / "stress_gains.csv")
    x = S[(S.window == 12) & (S.rule == "R2") & (S.base == "R1")]
    print(u.upper(), "stress episodes, R2 over R1 (W12)")
    display(x[["definition", "start", "end", "cp", "gain", "lo", "hi", "sessions", "best_constant", "fitted_constant"]].round(3))"""),
    code("""
for u in U:
    L = pd.read_csv(R / "stocks" / u / "level_shape_by_year.csv")
    print(u.upper(), "level (P0 over R1), shape (R2 over P0) and the ceiling, by year")
    display(L.pivot_table(index="year", columns="cp", values=["level_P0_over_R1", "shape_R2_over_P0", "ceiling_best_over_R1"]).round(3))
    P = pd.read_csv(R / "stocks" / u / "parameter_stability_summary.csv")
    display(P[(P.rule == "P0")].round(3))"""),
    code("""
for u in U:
    M = pd.read_csv(R / "stocks" / u / "maturity_by_year.csv")
    print(u.upper(), "tau^(-alpha) against alpha = 0.5 (R2)")
    display(M.pivot_table(index=["sessions_kind", "year"], columns=["rule", "cp"], values="gain").round(3))"""),
    md("""
**Reading.**
- **The spot–volatility relation exists within each period but does not carry forward.**
  - The level that fits each month best, after the fact, would have removed 11–22% of the three stocks' error: the ceiling column.
  - The level fitted on the previous 12 months gains nothing or loses: the level column is negative for NVDA and TSLA.
  - A stock's relation is too unstable to be estimated from its own history. For comparison, SPX's trailing level reached at least half of its ceiling in 15 of 26 type-years (2011–2023); it fell short in 2017–2019, 2022–2023 and for 2012's calls.
"""),
    md("## Books, data starvation and held positions on the five (§16.11, §16.13, §16.14)"),
    code("""
for u in U:
    d = R / "extensions" / u
    if (d / "books_median_yearly_gain.csv").exists():
        m = pd.read_csv(d / "books_median_yearly_gain.csv")
        print(u.upper(), "books, median yearly Gain over R1")
        display(m[(m.base == "R1") & m.rule.isin(["R2", "P0", "R4"])].pivot_table(index=["book", "rule"], columns="measure", values="median_yearly_gain").round(3))
    if (d / "starve_seed_spread.csv").exists():
        sp = pd.read_csv(d / "starve_seed_spread.csv")
        print(u.upper(), "starvation, median yearly Gain of R2 over R1")
        display(sp[(sp.base == "R1") & (sp.rule == "R2")].pivot_table(index="config", columns="cp", values="median").round(3))
    if (d / "paths_gains.csv").exists():
        G = pd.read_csv(d / "paths_gains.csv")
        print(u.upper(), "held positions, R2 over R1, pooled periods")
        display(G[(G.subset == "all") & (G.base == "R1") & (G.rule == "R2") & ~G.period.str.fullmatch(r"\\d{4}")]
                .pivot_table(index=["H", "period"], columns=["measure", "cp"], values="gain").round(3))"""),
    md("""
**Reading.**
- **Books amplify whatever the sign:** gains for QQQ (calls 0.162 on the book, against 0.083 per option) and AAPL, losses for NVDA and TSLA.
- **The risk-reversal book gains 0.22–0.24 for AAPL, TSLA and SLV.** That is unlike the indices, where it is the control. One possible reason, not investigated: out-of-the-money calls and puts on these underlyings may not share one volatility move.
- **Held positions:**
  - QQQ's Gain grows with the holding period in 2017–2019 (10 sessions: 0.333 / 0.275, against 0.122 / 0.102 one session), as SPX's does.
  - The stocks are mixed.
  - Most of the five lose on paths in 2020 and 2021–2023.
- **Checks:** on every underlying, the path code's first-day errors equal the walk-forward's exactly, and 79–94% of eligible paths complete.
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
