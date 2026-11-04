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
