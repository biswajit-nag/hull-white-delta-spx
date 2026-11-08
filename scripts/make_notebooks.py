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

NOTEBOOKS["00"] = ("00_the_story", [
    md(r"""
# 00 · The story: does Hull and White's minimum-variance delta hedge SPX options better?

*A pre-registered model validation on SPX option quotes, 2011–2023.*

This notebook tells the project's whole story, in the order of the executive summary ([`EXECUTIVE_SUMMARY.md`](../EXECUTIVE_SUMMARY.md)), with more detail. It recomputes the principal results from the committed tables in `results/`, and points to the detail notebooks or sources for the other numbers. Hull and White's published Gains, for example, are quotations, and the out-of-the-money comparison comes from notebook 09. Each section names the notebooks that hold the detail:

| Section | Detail in |
|---|---|
| Bottom line | this notebook |
| 1. The problem | this notebook; `analysis_plan.md` §6 |
| 2. Data | 01 (audit and attrition), 02 (forwards, implied volatilities, Greeks); `DATA.md` |
| 3. Methodology | 02 (the inputs: forwards, implied volatilities, Greeks), 03 (the rehearsal and the dry run); `analysis_plan.md` §§5–10 |
| 4.1 The confirmatory test | 04 (the 2020 verdict), 05 (its robustness and breakdown) |
| 4.2 Years and stress episodes | 06 (the 2011–2023 walk-forward), 09 (stress episodes), 07 (SPY) |
| 4.3 Complex against simple rules | 06 (the scaling rules), 08 (the challengers), 05 (the boosted learner's failure in 2020) |
| 4.4 The level and the assumption checks | 09 (level, shape, stability, maturity), 08 (polynomial degree), 03 (the checks made before 2020) |
| 4.5 Extensions and published benchmarks | 10 (books, held positions, data starvation), 11 (stocks and ETFs), 08 (short-dated options), 09 (the published Gains) |
| 5. Financial interpretation | 05 (where the error comes from), 06, 09, 10 |
| 6. Assumptions, limitations and failure modes | the failure modes in 04, 05, 06, 07, 08 and 11; the assumption checks in 02, 03, 04, 05, 08, 09 and 10 (the table's last column names them per assumption) |
| 7. Reproducibility | `REPRODUCING.md` |

The finance is explained where it first appears, with the boot camp's lectures cited where they cover it.
"""),
    code(SETUP + r"""
from IPython.display import Image, display
CP = {"C": "calls", "P": "puts"}


def fmt(r, d=3):
    # A Gain with its 95% session-block bootstrap interval; * marks an interval that excludes 0
    star = " *" if (r.lo > 0 or r.hi < 0) else ""
    return f"{r.gain:+.{d}f} [{r.lo:+.2f}, {r.hi:+.2f}]{star}"


# The SPX walk-forward, 2011-2023: every rule's yearly Gain with 12-, 36- and 60-month fits
G = pd.read_csv(R / "walkforward/gains_by_year.csv")  # R1-R4
WF = pd.concat([G,
                pd.read_csv(R / "walkforward/degrees_by_year.csv"),  # P0-P8 and PCV
                pd.read_csv(R / "walkforward/r9_r11_by_year.csv").query("rule != 'R2'"),  # LightGBM R9-R11
                pd.read_csv(R / "walkforward/r5_r8_by_year.csv").query("rule != 'R2'").drop(columns="sample")],  # R5, R6, R8
               ignore_index=True)


def wf(rule, base, window=12):
    return WF[(WF.rule == rule) & (WF.base == base) & (WF.window == window)].sort_values(["year", "cp"])


def median_1523(rule, base, window=12):
    # The median yearly Gain over 2015-2023, the span common to all three windows
    x = wf(rule, base, window)
    return x[x.year.between(2015, 2023)].groupby("cp").gain.median()"""),
    md(r"""
## Bottom line

Does adjusting the Black–Scholes delta for changing volatility improve daily SPX option hedges? A dealer hedges each option by holding delta units of the index. The Black–Scholes delta treats volatility as fixed, although implied volatility, the volatility consistent with an option's price, tends to rise when the index falls. Hull and White's minimum-variance delta corrects for this response, using monthly regressions on past prices. Its Gain is the fraction of the Black–Scholes delta's squared one-day hedging error that it removes.

The pre-registered SPX 2020 test is inconclusive. The minimum-variance delta removed 18.5% of the squared error for calls and 12.0% for puts. But the March 2020 crash leaves 95% intervals spanning about −0.4 to +0.46, so neither an improvement nor a loss is established. The verdict rule was committed before any 2020 hedging outcome was computed. All 11 pre-specified robustness variants preserve the verdict.

Repeated out of sample over 2011–2023, with monthly fits on the preceding 12 months, the correction usually helps. Its median yearly Gain over 2015–2023, the span common to all fitting windows, is 0.12 for calls and 0.10 for puts. In no year is it significantly worse than Black–Scholes. Its advantage disappears in 2022–2023, as implied volatility became less responsive to index moves.

Simpler rules do almost as well. One fitted constant correction gives essentially the same Gain as the three-coefficient form. Machine-learning corrections add no material improvement, and two fail badly in the crash. Ruf and Wang's fixed 0.9/1.1 scaling, an unfitted rule of thumb read off their results, matches the minimum-variance delta's median Gain but fails in 2022–2023.

Figure 1 below shows the stability evidence: the yearly Gain of the minimum-variance delta over the Black–Scholes delta, for calls and puts, with 12-, 36- and 60-month fits and 95% session-block bootstrap intervals. Grey marks the clean held-out years (2011–2013 and 2021–2023), which no earlier step had touched; orange marks the pre-registered test year, 2020.
"""),
    code(r"""
x = G[(G.rule == "R2") & (G.base == "R1")]
fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
for ax, cp in zip(axes, "CP"):
    for yr in (2011, 2012, 2013, 2021, 2022, 2023):  # the clean held-out years
        ax.axvspan(yr - 0.45, yr + 0.45, color="0.93", zorder=0, lw=0)
    ax.axvspan(2019.55, 2020.45, color="#fde2c8", zorder=0, lw=0)  # the pre-registered test year
    for W, c, off in ((12, "#1f77b4", -0.2), (36, "#ff7f0e", 0.0), (60, "#2ca02c", 0.2)):
        z = x[(x.cp == cp) & (x.window == W)]
        ax.errorbar(z.year + off, z.gain, yerr=[z.gain - z.lo, z.hi - z.gain], fmt="o", ms=4, color=c, capsize=2, lw=1, label=f"{W}-month fits")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_title(CP[cp].capitalize()); ax.set_xticks(range(2011, 2024, 2))
axes[0].set_ylabel("Gain over the Black–Scholes delta"); axes[0].legend(fontsize=8, loc="lower left")
plt.suptitle("Figure 1. Yearly Gain of the minimum-variance delta over the Black–Scholes delta, SPX, 2011–2023", fontsize=10)
plt.tight_layout(); plt.show()"""),
    md(r"""
## 1. The problem

A delta hedge (Lectures 6–8) offsets an option's index exposure. A dealer who holds one option and shorts h units of the index from one close to the next earns Δf − h·ΔS, where Δf is the option's price change and ΔS the index's. The Black–Scholes delta, δ_BS = ∂f/∂S, offsets the index move to first order if volatility does not move. Lecture 7 builds this hedge and Lecture 8 backtests it.

Implied volatility moves with the index: on average, it tends to rise when the index falls. Lecture 11's SPY smiles show the related skew across strikes. An option's sensitivity to volatility is its vega, ν = ∂f/∂σ (Lecture 6). If a 1% fall in the index raises implied volatility by a predictable amount, part of the option's vega exposure is really index exposure, and a hedge can neutralize it.

Hull and White's minimum-variance delta does that. It is the right-hand side of their equation (2):

$$
\delta_{\mathrm{MV}}\approx\delta_{\mathrm{BS}}+\nu_{\mathrm{BS}}\frac{\partial E[\sigma_{\mathrm{imp}}]}{\partial S}.
$$

Here $S$ is the index level and $\sigma_{\mathrm{imp}}$ is implied volatility. To first order, Δf ≈ δ_BS·ΔS + ν·Δσ. The h that minimizes the variance of Δf − h·ΔS is therefore δ_BS plus ν times the regression slope of Δσ on ΔS. The correction hedges the expected volatility response to an index move. The part of the volatility move unrelated to the index stays unhedged, as it must for any delta.

The main rules, simplest first, are:

1. the Black–Scholes delta, the benchmark;
2. the fixed 0.9/1.1 scaling: 0.9 times delta for calls, 1.1 times delta for puts;
3. the fitted scaling, $a\delta$, with $a$ fitted monthly;
4. the minimum-variance delta, with three coefficients fitted monthly.

The exploratory challengers are a constant correction; polynomials in delta of degrees 0–8, and a separate rule whose degree is selected by validation; a relaxed Hull–White rule with a free delta multiplier; Ruf and Wang's delta–vega–vanna regression; and LightGBM corrections using delta alone or market features. Vanna is delta's sensitivity to implied volatility. LightGBM fits the correction with a sum of decision trees.

The tables in `results/` and the other notebooks name the rules by code. Here δ means δ_BS and T is time to expiry in years. In the LightGBM rows, h denotes the complete fitted correction function; for the rules boosted from R2, it includes R2's fitted quadratic plus the learned tree correction:

| Rule in the story | Code | Hedge ratio | Coefficients fitted per option type |
|---|---|---|---|
| No hedge (reference for effectiveness) | R0 | 0 | — |
| Black–Scholes delta | R1 | δ, at the option's own implied volatility | 0 |
| Fixed 0.9/1.1 scaling (Ruf and Wang's rule of thumb) | R3 | 0.9·δ for calls, 1.1·δ for puts | 0 |
| Fitted scaling | R4 | a·δ | 1 |
| Constant correction | P0 | δ + c·ν/(S√T) | 1 |
| Minimum-variance delta (Hull and White) | R2 | δ + ν/(S√T)·(a + bδ + cδ²) | 3 |
| Polynomial of degree k in delta | P0–P8 | δ + ν/(S√T)·p_k(δ); P2 spans the same functions as R2 | k + 1 |
| Degree chosen by validation | PCV | P_k, with k chosen inside each training window | — |
| Relaxed Hull–White | R5 | a₀·δ + ν/(S√T)·(a + bδ + cδ²) | 4 |
| Ruf and Wang's delta–vega–vanna regression | R6 | a·δ + b·ν/S + c·vanna | 3 |
| LightGBM on delta alone | R9 (from scratch), R11 (boosted from R2) | δ + ν/(S√T)·h(δ) | tuned |
| LightGBM on market features | R10 (from scratch), R8 (boosted from R2) | δ + ν/(S√T)·h(z) | tuned |

The market features z are delta, log maturity, the option's position on its smile, the at-the-money implied volatility, 20-day realized volatility and the 5-day index return (`analysis_plan.md` §6). R7, a regression tree, was specified but withdrawn from the submission (`analysis_plan.md` §15, 2026-11-06), which is why the codes skip it.

The question matters to dealers who hedge daily, and to the teams that validate their models. Black–Scholes leaves the volatility response unhedged. Why implied volatility rises when the index falls is debated. The leverage explanation is that a falling stock price raises a firm's debt-to-equity ratio and so its volatility. Volatility feedback runs the other way: higher volatility raises the returns investors require, which lowers prices. Hull and White read the evidence as favouring volatility feedback. For hedging, what matters is how large and how stable the response is. That is what this study measures.
"""),
    md(r"""
## 2. Data

| Data | Source | Used for |
|---|---|---|
| SPX and SPY end-of-day option quotes, 2010–2023 | OptionsDX | One row per quote date, expiry and strike, with the call and the put side by side |
| AAPL, NVDA, TSLA, QQQ and SLV option quotes, 2016–2023 | OptionsDX | The extension to stocks and ETFs (§4.5) |
| S&P 500 closes | FRED (Cboe before 2016-10) | The index level for SPX |
| SPY closes | Nasdaq (Stooq before 2016-11, with its dividend adjustment reversed) | SPY's level |
| The five stocks' and ETFs' levels | the vendor's near-close snapshot | No official close was in hand |
| Dividends | SSGA for SPY; Nasdaq for AAPL, NVDA and QQQ | TSLA and SLV pay none |
| Rates and the S&P 500's dividend yield | none: each expiry's forward and discount factor are read from put–call parity on the SPX quotes (notebook 02) | Pricing, implied volatilities and Greeks |

The unit of observation is a pair: one contract at one NYSE session's close (day one), and the same contract at the next session's close (day two). The hedge is set on day one and judged on day two. This is Lecture 7's discrete hedge cut to one period.

The sample requires at least 14 days to expiry, an absolute delta of 0.05–0.95, and trading on day one. The expiry and delta filters come from Hull and White and keep both in- and out-of-the-money options. The trading filter comes from Ruf and Wang, since an untraded quote may be stale.

The vendor's data needed care (notebook 01; every rule is in `DATA.md`):

- **Volume.** Through 2021 the vendor never records a volume above 999, and an empty volume can mean 1,000 or more contracts traded. An empty volume with a positive last-trade price is read as traded. A naive "volume > 0" filter would drop the busiest contracts.
- **Timing.** The option quotes are synchronous with neither the official close nor the vendor's own index snapshot. Their parity-implied index level sits a median 3.3 basis points (bp) from the close in 2019–2020. Two sensitivities use the other levels (§4.1).
- **Calendar.** Pairs are formed across NYSE sessions, not the vendor's dates: 35 SPX sessions are missing from the files, and 12 holiday rows are after-close snapshots of the previous session.
- **April 2019.** On 2019-04-04 to 04-16 the vendor's expiry stamps shift by a day; pairs touching the window are excluded, without repair.
"""),
    code(r"""
d20 = pd.read_csv(R / "2020/descriptives.csv").query("rule == 'R1'").set_index("cp").pairs
print(f"SPX 2020 pairs: {d20.sum():,} ({d20['C']:,} calls, {d20['P']:,} puts)")
print(f"SPX 2011-2023 pairs in the 12-month walk-forward: {wf('R2', 'R1').pairs.sum():,}")
cols = ["ok", "one_sided_next", "vendor_missing_session"]
st = pd.read_csv(R / "attrition/by_status.csv")  # its "2020" rows exclude the stress period, which has its own rows
st["period"] = st.period.replace({"2020": "2020, outside the stress period", "stress": "2020, stress period"})
whole = st[st.period.str.startswith("2020")].groupby("cp", as_index=False)[cols].sum().assign(period="2020, whole year")
st = pd.concat([st, whole]).set_index(["period", "cp"])
st["usable share"] = st.ok / st[cols].sum(axis=1)
st.round(4)"""),
    md(r"""
**Reading.** In 2020, 98.7% of eligible pairs have a usable day-two quote (98.5% in 2019). Nearly all the rest fall on ordinary sessions that the vendor lacks entirely. Within the stress period no session is missing, and vanished bids (`one_sided_next`) are 0.3% of pairs. Results are conditional on a usable day-two quote, and the vanished quotes are stress-tested in §4.1. Detail: notebook 01.
"""),
    md(r"""
## 3. Methodology

The fitted rule is Hull and White's equation (5):

$$
\delta_{\mathrm{MV}}=\delta_{\mathrm{BS}}+\frac{\nu_{\mathrm{BS}}}{S\sqrt{T}}\left(a+b\delta_{\mathrm{BS}}+c\delta_{\mathrm{BS}}^2\right).
$$

Here $T$ is the time to expiry in years. The $1/S$ factor makes volatility respond to index returns rather than to point moves. The $1/\sqrt{T}$ factor is Hull and White's empirical maturity scaling: short-dated implied volatilities move more. The quadratic lets the correction vary across strikes. Least squares fits the coefficients separately for calls and puts.

Each expiry's forward and discount factor come from put–call parity at the mid quotes, so no rate or dividend yield is assumed. Implied volatilities come from the boot camp's Lecture 12 solver, and the Greeks are Black–Scholes at each option's own implied volatility (notebook 02).

For a hedge ratio $h$, the error is $e=(\Delta f-h\Delta S)/S$, where $\Delta f$ is the option's price change and $S$ the day-one index level. The Gain of a rule is $1-\mathrm{SSE}(\mathrm{rule})/\mathrm{SSE}(\mathrm{Black\text{–}Scholes})$, using sums of squared errors on identical pairs. Since the root-mean-square (RMS) error scales as $\sqrt{1-\text{Gain}}$, a Gain of 0.10 means 10% less squared error, or about 5% lower RMS error (computed below).

Monthly fits use trailing 12-month windows, with 36- and 60-month alternatives. Each fit hedges only the following month, and training pairs must end before the test month starts. No fit sees its own outcomes.

Before 2020 was opened, a rehearsal on 2018–2019 and a dry run of the test script on 2019 checked the code and the model's form (notebook 03). The analysis plan, `analysis_plan.md`, was committed (77b030e) before any 2020 hedging outcome was computed. It fixed the endpoints, the verdict table and the thresholds ("material" means a Gain of at least 0.05).

The walk-forward repeats this chronological protocol over 2011–2023. Its untouched years, 2011–2013 and 2021–2023, are the clean held-out evidence. The other years had been used for fitting, rehearsal or the test before the walk-forward ran, as the ledger below records.

Bootstrap intervals resample trading days rather than options, because all options on a day share that day's index move. We use a circular block bootstrap of sessions, blocks of 10, 10,000 draws (plan §9). For the rehearsal's coefficients, standard errors clustered by session are 4.5–34 times the ordinary estimates that treat options as independent (notebook 03). Yearly and episode significance is pointwise and not adjusted for multiple comparisons.

The exploratory analyses are all descriptive, and most were specified after 2020 had been seen. They cover the additional rules, an SPY replication, parameter stability, the polynomial degree and the maturity scaling, the correction's level and shape, the published benchmarks, books, 5- and 10-day held positions, reduced training data, short-dated options, and five stocks and ETFs. Stress episodes are defined from the S&P 500 close alone: 20-day realized volatility above 25%, or a peak-to-trough drawdown of at least 10%. Episode Gains use the walk-forward's fits, and stress and calm sessions are compared by year.
"""),
    code(r"""
for g in (0.05, 0.10, 0.15, 0.25):
    print(f"Gain {g:.2f}: RMS error lower by {1 - np.sqrt(1 - g):.1%}")
with pd.option_context("display.max_colwidth", 140):
    display(pd.read_csv(R / "year_ledger.csv").head(8)[["years", "actual_exposure", "date"]])  # the core runs; later rows log the extensions"""),
    md(r"""
## 4. Principal findings

### 4.1 The confirmatory test (detail: notebooks 04 and 05)

The pre-registered verdict for 2020 is Inconclusive: neither option type's 95% lower bound is above zero. The plan's hypothesis H1 needed both lower bounds of the Gain over Black–Scholes above zero. The minimum-variance delta is not distinguished from either scaling rule. The first row of the table is the primary analysis; the other 11 are the pre-specified robustness variants.
"""),
    code(r"""
v = pd.read_csv(R / "2020/verdict.csv")
iv = lambda g, l, h: [f"{a:+.3f} [{b:+.2f}, {c:+.2f}]" for a, b, c in zip(g, l, h)]
t = pd.DataFrame({"variant": v.variant, "verdict": v.verdict,
                  "calls: Gain [95%]": iv(v.G_C, v.G_C_lo, v.G_C_hi), "puts: Gain [95%]": iv(v.G_P, v.G_P_lo, v.G_P_hi),
                  "calls against R3 / R4": v.C_vs_R3 + " / " + v.C_vs_R4, "puts against R3 / R4": v.P_vs_R3 + " / " + v.P_vs_R4})
print(f"primary: {v.verdict[0]}; the {len(v) - 1} robustness variants: {v.verdict[1:].value_counts().to_dict()}")
t"""),
    md(r"""
The variants are:

- A: the index level implied by the options themselves, using the parity forward of the nearest expiry.
- B: the vendor's 16:00 index snapshot.
- P-bid, P-ask: options marked at the bid or the ask instead of the mid.
- F: coefficients frozen at one 2019 fit.
- W36, W60: 36- and 60-month windows.
- S3: only quotes with a relative spread of at most 5%.
- Rest of 2020: leaving out the stress period, 24 February to 30 April.
- Endpoint low and high: the pairs whose day-two bid vanished, valued at the low and the high end of their no-arbitrage band.

"R2 beats" in a comparison column means the minimum-variance delta passed the plan's statistical superiority test against that scaling rule, with adjustment for the four scaling-rule comparisons. It happens three times, never in the primary.

All tested variants remain inconclusive; wide intervals limit what that agreement establishes. The point Gains move more: the spread screen gives 0.095 / −0.028, the options' own index level 0.147 / 0.219, and bid or ask marks about 0.15 / 0.10.

The pre-registered timing diagnostic (plan §8) compares the primary with sensitivity A: the call Gain falls by 0.038 and the put Gain rises by 0.099. Changes in opposite directions are consistent with the timing mismatch between the option quotes and the close, though they do not identify it.

The next table compares four alternatives to Black–Scholes in 2020 and across years. Gains are over the Black–Scholes delta. The constant correction was not a 2020 test-year rule; its 2020 values come from the walk-forward, which uses the same 12-month fits as the 2020 test.
"""),
    code(r"""
g20 = pd.read_csv(R / "2020/gains.csv").query("variant == 'primary' and base == 'R1'")
rows = []
for name, rule, k in [("Fixed 0.9/1.1 scaling (Ruf and Wang's rule of thumb)", "R3", 0), ("Fitted scaling a·δ", "R4", 1),
                      ("Constant correction", "P0", 1), ("Minimum-variance delta (Hull and White)", "R2", 3)]:
    src = wf(rule, "R1").query("year == 2020") if rule == "P0" else g20[g20.rule == rule]
    m = median_1523(rule, "R1")
    rows.append({"hedge rule": name, "code": rule, "coefficients fitted": k,
                 "SPX 2020, calls": fmt(src[src.cp == "C"].iloc[0]), "SPX 2020, puts": fmt(src[src.cp == "P"].iloc[0]),
                 "median yearly Gain 2015-2023, calls / puts (12-month fits)": f"{m['C']:.3f} / {m['P']:.3f}"})
pd.DataFrame(rows)"""),
    md(r"""
The numbers below put the 2020 Gains in context: how much Black–Scholes already does, what the improvement is worth in dollars, and how concentrated the year's error is.
"""),
    code(r"""
d = pd.read_csv(R / "2020/descriptives.csv").set_index(["cp", "rule"])
for cp in "CP":
    r1, r2 = d.loc[(cp, "R1")], d.loc[(cp, "R2")]
    top10 = pd.read_csv(R / f"2020/top_sessions_{cp}.csv").share.sum()
    p = g20[(g20.rule == "R2") & (g20.cp == cp)].iloc[0]
    print(f"{CP[cp]}:")
    print(f"  Black-Scholes removes {r1.effectiveness_vs_R0:.1%} of the unhedged squared error")
    print(f"  RMS error per contract: ${r1.rms_dollars_per_contract:,.0f} (Black-Scholes) -> ${r2.rms_dollars_per_contract:,.0f} (minimum-variance)")
    print(f"  share of the year's Black-Scholes squared error: stress period {r1.stress_share_R1:.0%}, ten largest sessions {top10:.0%}")
    print(f"  the lower bound sits {p.gain - p.lo:.2f} below the point Gain")"""),
    md(r"""
**Reading.** Black–Scholes alone removes 92–95% of the unhedged squared error. The minimum-variance correction works on what is left.

The minimum-variance delta lowers the calls' RMS error per contract from \$825 to \$727 (SPX options are \$100 per index point). The dollar figure weights each pair by its index level squared, so the reduction it implies (22% of the squared error for calls, 19% for puts) is not the Gain.

The stress period, 24 February to 30 April, contains 80–86% of the year's normalized Black–Scholes squared error, and the ten largest sessions contain 65–73%. The call hedges set on 13 March 2020 and closed on 16 March, when the index fell 12%, together account for 30% of that year's total for calls.

The lower bounds sit 0.54 and 0.57 below the point Gains. Given these interval widths, only a Gain above roughly 0.5 could have cleared zero: about twice the 0.23–0.26 Hull and White report. That is why the verdict is Inconclusive rather than negative, and why the walk-forward carries the stability evidence.

The cumulative squared error through 2020 shows the concentration. The figure is drawn by `scripts/make_figures.py` from the per-pair errors, which are regenerable but not committed.
"""),
    code(r"""
display(Image(filename=str(R / "figures/cumulative_sse_2020.png"), width=900))
m = pd.concat([pd.read_csv(R / f"2020/monthly_{cp}.csv") for cp in "CP"]).pivot(index="month", columns="cp", values="G_R2_R1")
print("Gain of the minimum-variance delta over Black-Scholes, month by month; mean of the monthly Gains:", m.mean().round(3).rename(CP).to_dict())
m.rename(columns=CP).round(3).T"""),
    md(r"""
Month by month, the Gain swings from about +0.4 to −0.8. The average of the monthly Gains, Hull and White's aggregation, is about zero. The correction helped from January to March and hurt badly in April.

April's fit was the first whose 12-month window contained March 2020, and its put coefficients jumped. But in April, as in August, September and November, even refitting the quadratic correction on that month's own data removed little: 5–8% of the Black–Scholes squared error in April, and under 2% in the other three. These low ceilings are consistent with a weaker spot–volatility relation; the correction fitted on earlier data added error instead (notebook 04). The crash in the window is not the whole story: May and June, with the same crash in their windows, gained, and September and November lost without a new one.
"""),
    md(r"""
### 4.2 Years and stress episodes (detail: notebooks 06, 09 and 07)

Yearly Gains are mostly 0.10–0.25 through 2021, and about zero in 2022–2023. The table gives each year's Gain over Black–Scholes with its interval (12-month fits) and the point Gains with 36- and 60-month fits. The status column says whether the year was clean.
"""),
    code(r"""
x = G[(G.rule == "R2") & (G.base == "R1")]
t = pd.DataFrame(index=sorted(x.year.unique()))
for cp in "CP":
    for W in (12, 36, 60):
        z = x[(x.cp == cp) & (x.window == W)].set_index("year")
        t[f"{CP[cp]}, {W}-month"] = z.apply(fmt, axis=1) if W == 12 else z.gain.map(lambda v: f"{v:+.3f}")
t = t.fillna("")
t["status"] = x[(x.cp == "C") & (x.window == 12)].set_index("year").status
x12 = x[x.window == 12]
print(f"12-month fits: significantly positive in {(x12.lo > 0).sum()} of {len(x12)} call-or-put years, significantly negative in {(x12.hi < 0).sum()}")
print("median yearly Gain, 2015-2023:", {f"{W}-month": median_1523("R2", "R1", W).round(3).rename(CP).to_dict() for W in (12, 36, 60)})
t"""),
    md(r"""
**Reading.** With 12-month fits, the Gain is significantly positive in 7 of 26 call-or-put years and significantly negative in none. It is positive in every year through 2021.

The clean years agree. 2011–2013 gain 0.03–0.24, and in 2021, a year nobody had looked at, both types gain significantly (0.15 and 0.16).

The advantage disappears in 2022–2023. With 12-month fits the Gain is about zero, with tight intervals in 2023. Longer windows, which remember more of the earlier, stronger relation, lose in 2022 (−0.16 to −0.23). They gain more in the typical year (median 0.16 with 36- or 60-month fits, against 0.12 / 0.10), but pay more when the relation changes.

The stress episodes below are defined from the S&P 500 close alone: RV is 20-day realized volatility above 25%; DD is a peak-to-trough drawdown of at least 10%. They are scored with the walk-forward's 12-month fits.
"""),
    code(r"""
S = pd.read_csv(R / "walkforward/stress_gains.csv")
s = S[(S.window == 12) & (S.rule == "R2") & (S.base == "R1")].copy()
s["episode"] = s.start + " to " + s.end + " (" + s.definition + ")"
s["g"] = s.apply(fmt, axis=1)
s.pivot_table(index=["episode", "sessions"], columns="cp", values="g", aggfunc="first").rename(columns=CP)"""),
    md(r"""
**Reading.** Sell-offs gain, significantly in 2011, 2015–2016 and February 2018. Every drawdown gains for both types in its point estimate.

Rebounds and post-crash periods lose. September–December 2022 loses significantly: −0.52 for calls and −0.56 for puts. Late 2018 (the rebound from the December 2018 low) and March 2022 lose too, without significance. A three-session episode at the end of September 2020 is also significantly negative for puts, but three sessions are too few for its interval to mean much.

Significance here is pointwise, over 17 episodes and two types, with no adjustment for multiplicity. Episode bootstraps shorten the block for short episodes. The stable-relation assumption therefore fails in one direction of stress more than the other (§5, notebook 09).

SPY replicates the picture. SPY options are American and settle into shares, and SPY pays quarterly dividends, so the replication reruns every applicable SPX procedure with Lecture 12's American tree (notebook 07). Its 2020 is also Inconclusive, as are all 10 of its robustness variants (SPX's set without A). That verdict is post hoc, because SPY's 2020 Gains were seen before the replication was specified. Puts typically gain 16–28% a year through 2021:
"""),
    code(r"""
sv = pd.read_csv(R / "spy/2020/verdict.csv")
print(f"SPY 2020: {sv.verdict[0]}; calls {sv.G_C[0]:+.3f} [{sv.G_C_lo[0]:+.2f}, {sv.G_C_hi[0]:+.2f}], puts {sv.G_P[0]:+.3f} [{sv.G_P_lo[0]:+.2f}, {sv.G_P_hi[0]:+.2f}]")
print("robustness variants:", sv.verdict[1:].value_counts().to_dict())
sg = pd.read_csv(R / "spy/walkforward/gains_by_year.csv")
z = sg[(sg.rule == "R2") & (sg.base == "R1") & (sg.window == 12)]
z.assign(g=z.apply(fmt, axis=1)).pivot(index="year", columns="cp", values="g").rename(columns=CP)"""),
    md(r"""
### 4.3 Complex against simple rules (detail: notebooks 06, 08 and 05)

The comparison below gives the Gain of the minimum-variance delta over each scaling rule, year by year, with 12-month fits.
"""),
    code(r"""
for base, name in (("R3", "the fixed 0.9/1.1 scaling"), ("R4", "the fitted scaling")):
    z = wf("R2", base)
    win, lose = z[z.lo > 0], z[z.hi < 0]
    print(f"Against {name}: significantly better in {len(win)} of {len(z)} call-or-put years, significantly worse in {len(lose)}"
          + (" (" + ", ".join(f"{y} {CP[c]}" for y, c in zip(lose.year, lose.cp)) + ")" if len(lose) else ""))
print("median yearly Gain over Black-Scholes, 2015-2023 (calls / puts):",
      {r: median_1523(r, "R1").round(3).tolist() for r in ("R2", "R3", "R4", "P0")})"""),
    md(r"""
**Reading.** The minimum-variance delta beats the fixed scaling significantly in 14 of 26 call-or-put years, and loses in two, both in 2018. The fitted scaling is significantly worse in 12 of 26, and never significantly better. Yet the fixed scaling's median Gain over Black–Scholes (0.125 / 0.099) matches the minimum-variance delta's. It is better in some years (2018) and much worse in others (−0.14 to −0.18 in 2022, −0.06 to −0.14 in 2023).

The next table compares the challengers. Each row summarizes a rule's yearly Gain over the minimum-variance delta (12-month fits, SPX). The last column is the largest gap, in any year, between the rule's Gain over Black–Scholes and the minimum-variance delta's.
"""),
    code(r"""
names = {"P0": "constant correction", "P1": "linear in delta", "P2": "quadratic (spans R2: a check)", "P3": "cubic",
         "P4": "degree 4", "P5": "degree 5", "P6": "degree 6", "P7": "degree 7", "P8": "degree 8", "PCV": "degree chosen by validation",
         "R5": "relaxed Hull-White", "R6": "delta-vega-vanna regression", "R9": "LightGBM on delta, from scratch",
         "R11": "LightGBM on delta, boosted from R2", "R10": "LightGBM on features, from scratch", "R8": "LightGBM on features, boosted from R2"}
r2 = wf("R2", "R1").set_index(["year", "cp"]).gain
rows = []
for rule, name in names.items():
    z, m = wf(rule, "R2"), median_1523(rule, "R2")
    rows.append({"code": rule, "rule": name, "median over R2, 2015-2023 (calls / puts)": f"{m['C']:+.3f} / {m['P']:+.3f}",
                 "lowest year": z.gain.min(), "highest year": z.gain.max(),
                 "significantly better / worse (of 26)": f"{(z.lo > 0).sum()} / {(z.hi < 0).sum()}",
                 "largest gap from R2 over Black-Scholes": (wf(rule, "R1").set_index(["year", "cp"]).gain - r2).abs().max()})
pd.DataFrame(rows).round(3)"""),
    md(r"""
**Reading.** For SPX with 12-month fits, the constant correction, every polynomial degree and the delta-only LightGBM corrections all stay within about 0.015 a year of the minimum-variance delta. That is under a third of the 0.05 the plan calls material. In a typical year the gap is a few thousandths.

The significance counts need care for these close rules. P2 spans exactly the same functions as the minimum-variance delta (its gap is about 10⁻¹⁵), yet it shows "significant" differences in 6 of 26 call-or-put years. At gaps this small, the bootstrap's marks are rounding noise.

The relaxed Hull–White rule equals the minimum-variance delta to within 0.006 a year. Ruf and Wang's delta–vega–vanna regression is slightly worse: median Gains of −0.011 / −0.004 relative to the minimum-variance delta, and −0.18 for 2020 puts.

The LightGBM corrections that use market features fail in the crash, as shown below, and otherwise track the minimum-variance delta.
"""),
    code(r"""
g = pd.read_csv(R / "2020/gains.csv").query("variant == 'learners (feature-complete)'").set_index(["rule", "base", "cp"]).gain
r9 = pd.read_csv(R / "2020/r9_r11.csv").query("variant == 'primary' and base == 'R1'").set_index(["rule", "cp"]).gain
for cp in "CP":
    r8 = (1 - g[("R8", "R2", cp)]) * (1 - g[("R2", "R1", cp)])  # SSE(R8)/SSE(R1), via R2 on the same pairs
    print(f"2020 {CP[cp]}: squared error relative to Black-Scholes: R8 {r8:.2f}, R10 {1 - r9[('R10', cp)]:.2f}, "
          f"R9 {1 - r9[('R9', cp)]:.2f}, R11 {1 - r9[('R11', cp)]:.2f}")"""),
    md(r"""
**Reading.** In 2020 the market-feature corrections' squared error for puts was 9–11 times Black–Scholes', after the crash took their features outside the training range. The trees used in March were fitted on March 2019 to February 2020, whose 20-day realized volatility never exceeded 25% and whose worst 5-day index return was −12%. March 2020 brought 98% and −20%.

Trees extrapolate a constant from the edge of their training data. Calls were unaffected, and the delta-only learners, with no such features, stayed with the minimum-variance delta. The 2×2 design (from scratch or boosted, on delta or on features) therefore points to the features, not the boosting, as what broke.
"""),
    md(r"""
### 4.4 The level and the assumption checks (detail: notebooks 09, 08 and 03)

The level replaces the quadratic with one constant: the hedge's assumed sensitivity of implied volatility to the index. With a constant correction c, the hedge is δ + c·ν/(S√T), so the assumed response is ∂σ/∂S = c/(S√T). A 1% index fall (ΔS = −0.01·S) raises implied volatility by −0.01·c/√T, or −c/√T volatility points. A level of −0.13 therefore means a 1% index fall raises implied volatility by 0.13 volatility points at one year to expiry, or 0.26 at three months:
"""),
    code(r"""
c = -0.13
for T, label in ((1.0, "one year"), (0.25, "three months")):
    print(f"level {c}: a 1% index fall raises implied volatility by {-c / np.sqrt(T):.2f} vol points at {label} to expiry")
L = pd.read_csv(R / "walkforward/level_shape_by_year.csv")
print(f"\nlargest |R2's weighted mean correction - the constant's c|, over all years: {(L.R2_mean_correction - L.c_fit).abs().max():.1e}")
print(f"the shape (R2 over the constant) adds {L.G_shape_R2_P0.min():+.3f} to {L.G_shape_R2_P0.max():+.3f} a year")
cols = ["c_fit", "c_post", "G_level_P0_R1", "G_shape_R2_P0", "G_ceiling_P0post_R1"]
L.pivot_table(index="year", columns="cp", values=cols)[cols].rename(columns=CP, level=1).round(3)"""),
    md(r"""
**Reading.** In the table, `c_fit` is the median of the year's twelve fitted levels, each estimated on the preceding 12 months, and `c_post` is the median of the twelve constants fitted separately to each month's own pairs, after the fact. `G_level_P0_R1` is the constant correction's Gain over Black–Scholes, `G_shape_R2_P0` is the quadratic's Gain over the constant correction, and `G_ceiling_P0post_R1` is the yearly Gain from using a separate best constant for each month.

The fitted quadratic, averaged over the training pairs with weights [ν·ΔS/(S²√T)]², equals the constant exactly. That is the first normal equation of the least-squares fit: the first regressor is ν·ΔS/(S²√T), and the sum of residuals multiplied by that regressor is zero. The match above is to rounding error. The level supplies the Gain; variation across strikes adds only −0.014 to +0.015 a year.

A mis-estimated level costs quadratically. With y the Black–Scholes error and x the regressor ν·ΔS/(S²√T), the squared error of a constant c is Σy² − 2cΣxy + c²Σx², and the best constant is c* = Σxy/Σx². The Gain of c over Black–Scholes is therefore exactly G(c) = G*·[1 − ((c − c*)/c*)²], where G* is the ceiling. A level twice too large gives zero, and more than that loses to Black–Scholes.

The identity holds for each monthly fit and its own test month, where c is a single number. The yearly columns combine twelve monthly fits, using medians for the levels and summed squared errors for the Gains, and need not satisfy the identity. The check below covers every monthly fit of 2011–2023:
"""),
    code(r"""
lm = pd.read_csv(R / "walkforward/level_shape_by_month.csv")  # one row per test month and type: the fitted c, the best c*, the sums of squares
G_c = 1 - lm.sse_P0 / lm.sse_R1
G_star = 1 - lm.sse_P0_post / lm.sse_R1
ratio = lm.c_fit / lm.c_post
print(f"{len(lm)} monthly fits; largest |G(c) - G*[1 - (1 - c/c*)^2]|: {(G_c - G_star * (1 - (1 - ratio) ** 2)).abs().max():.1e}")
print(f"fits (month x type) whose fitted level overshot the best by more than 2x: {(ratio > 2).sum()}, of which lost to Black-Scholes: {((ratio > 2) & (G_c < 0)).sum()}")
print(f"months that lost to Black-Scholes: {(G_c < 0).sum()}, of which the fitted level was more than 2x the best or of the wrong sign: {((G_c < 0) & ((ratio > 2) | (ratio < 0))).sum()}")"""),
    md(r"""
**Reading.** Every month in which the fitted level overshot the month's best level by more than a factor of two lost to Black–Scholes, and every losing month either overshot that much or had the wrong sign. In market terms, the rule loses whenever the spot–volatility relation weakens by more than half between the fitting window and the hedging month.

The individual coefficients are poorly identified, but the level is well identified, and it varies over time:
"""),
    code(r"""
P = pd.read_csv(R / "walkforward/parameter_stability_summary.csv")
P[P.window == 12][["cp", "rule", "coef", "refits", "min", "median", "max", "median_se", "share_abs_z12_gt_2", "median_corr_bc"]].round(3)"""),
    md(r"""
**Reading.** Each row summarizes a coefficient over the 156 monthly refits of 2011–2023, with session-clustered standard errors. R2's b and c have strongly correlated estimation errors (|correlation| about 0.9), so they trade off against each other. The constant's c (P0, the level) has a median standard error of about 0.03–0.04.

The level drifts from about −0.34 to near zero. Fits 12 months apart, on non-overlapping data, differ by more than two reported standard errors in 19% of call and 10% of put comparisons (`share_abs_z12_gt_2`). These standard errors are clustered by session but omit serial dependence across sessions, so the counts may overstate the instability; the effect is not quantified here.

With 12-month fits, degrees 0–8 give essentially the same Gain (§4.3). Maturity powers $T^{-\alpha}$ for $\alpha=0,0.25,0.75,1$ never consistently beat $1/\sqrt{T}$. The table counts significant years against $1/\sqrt{T}$:
"""),
    code(r"""
M = pd.read_csv(R / "walkforward/maturity_by_year.csv").query("regime == 'all'")
M.assign(better=M.lo > 0, worse=M.hi < 0).groupby("rule").agg(
    better=("better", "sum"), worse=("worse", "sum"), type_years=("gain", "size"), median_gain_over_sqrt_T=("gain", "median")).round(3)"""),
    md(r"""
These checks were first made before 2020 was opened, in the rehearsal (notebook 03). There $1/\sqrt{T}$ was not contradicted by any alternative power.

The rehearsal's pre-specified diagnostic (`analysis_plan.md` §10, check 1) contradicted the quadratic in 2019 for both calls and puts: a cubic beat it, with a 95% lower bound above zero. The 2019 improvement was economically small, about 0.2% of the squared error. In 2018 an improvement was not statistically established: the point Gains were positive, but the lower bounds were below zero. The cubic was carried to 2020 as an exploratory rule and was no better there. The note below the table of §6 distinguishes that table's checks from the rehearsal diagnostic.

### 4.5 Extensions and published benchmarks (detail: notebooks 10, 11, 08 and 09)

**Books.** We score each day's average error across all calls, all puts, or long-volatility positions in out-of-the-money options (notebook 10). A risk reversal, long out-of-the-money calls and short out-of-the-money puts, is the control because its volatility exposures partly cancel. The table gives median yearly Gains over Black–Scholes, 2011–2023, on the book and per option, with each book's common share: the part of the per-option squared error that survives averaging.
"""),
    code(r"""
B = pd.read_csv(R / "extensions/spx/books_median_yearly_gain.csv")
t = B[(B.base == "R1") & B.rule.isin(["R2", "R3", "R4", "P0"])].pivot_table(index="book", columns=["rule", "measure"], values="median_yearly_gain")
t[("common share", "")] = pd.read_csv(R / "extensions/spx/books_common_share.csv").groupby("book").common_share_R1.median()
display(t.round(3))
print("The fixed scaling (R3) over the minimum-variance delta, median yearly Gain:")
B[(B.base == "R2") & (B.rule == "R3")].pivot_table(index="book", columns="measure", values="median_yearly_gain").round(3)"""),
    md(r"""
**Reading.** For SPX calls, the median yearly Gain over 2011–2023 is 0.22 on the book against 0.15 per option, about 1.4 times (puts: 0.17 against 0.12). Losses grow too: in 2022 the put book lost 0.14 against 0.06 per option (its interval, [−0.49, +0.13], includes zero). The control gains little (0.04). For the three long-option books, the common share is a median of about 0.7 across years, ranging from 0.32 to 0.82 by book and year.

Only a book's total correction matters. Every option's error on a day is divided by the same index level, so a book's error depends only on the average of its hedge ratios. On books the fixed scaling therefore roughly ties the minimum-variance delta (+0.011 / +0.003), though it trails per option (−0.037 / −0.056).

**Held positions.** These tests accumulate the error over 5 or 10 days, rehedging daily with each day's ratio (notebook 10). After the start, the contract is followed whatever its delta, maturity or volume, because dropping it when it leaves the band would select on the outcome. The table gives Gains over Black–Scholes, on the path and one day at a time on the same pairs:
"""),
    code(r"""
PG = pd.read_csv(R / "extensions/spx/paths_gains.csv")
z = PG[(PG.subset == "all") & (PG.base == "R1") & PG.rule.isin(["R2", "P0", "R3", "R4"]) & PG.period.isin(["2011-2019", "2020", "2021-2023"])]
z.pivot_table(index=["period", "rule"], columns=["H", "measure", "cp"], values="gain").round(3)"""),
    md(r"""
**Reading.** In 2011–2019 the Gain rises from 12–13% one day at a time to 19–20% over 5 days on the same pairs. On the 10-day paths, it rises from 12–15% one day at a time to 24–34% (2020 path Gains: 26–28% over 5 days and 31–39% over 10 days). Two reasons are likely: noise in the mid quotes cancels along a path, entering only at its two ends, and the spot–volatility move accumulates over a multi-day sell-off. Losses also grow, in 2021–2023 (puts −0.11 over 5 days). The fixed scaling gains less than the minimum-variance delta on paths.

**Data starvation.** These tests keep fewer options per training day, or shorten the training window (notebook 10). The table gives the median yearly Gain of the minimum-variance delta, 2011–2023, over Black–Scholes and over the full-data fit (`R2full`) on the same pairs. `frac` keeps a random fraction of each training session's options and `k` a fixed number per session and type (medians over five seeds). `W1`–`W6` are windows of 1–6 months.
"""),
    code(r"""
sp = pd.read_csv(R / "extensions/spx/starve_seed_spread.csv").query("span == '2011-2023' and rule == 'R2'")
order = ["W12", "frac0.25", "frac0.05", "frac0.01", "k10", "k3", "W6", "W3", "W2", "W1"]
display(sp.pivot_table(index="config", columns=["base", "cp"], values="median").loc[order].round(3))
SB = pd.read_csv(R / "extensions/spx/starve_by_year.csv")
print("2022, Gain over Black-Scholes by training window:")
SB[(SB.rule == "R2") & (SB.base == "R1") & (SB.year == 2022)].pivot_table(index="config", columns="cp", values="gain").loc[["W12", "W6", "W3", "W2", "W1"]].rename(columns=CP).round(3)"""),
    md(r"""
**Reading.** With three options of each type a day, the median yearly Gain relative to the full-data fit is about −0.01. Retaining sessions appears more important than retaining many options per session, consistent with all options on a day sharing its index move. Windows below three months have median yearly Gains of −0.02 to −0.07 relative to the full 12-month fit.

Yet a three-month window would have adapted to 2022: puts go from −0.058 to +0.047. That is hindsight on one year. The same window does worse in 2021 (puts 0.104 against 0.161) and 2023 (−0.060 against −0.014). No window is best every year: a long one estimates the level precisely but goes stale; a short one tracks it but is noisy.

**Stocks and ETFs.** Notebook 11 applies the SPY protocol to AAPL, NVDA and TSLA (single stocks), QQQ (a Nasdaq-100 ETF) and SLV (a silver ETF). The table gives median yearly Gains over Black–Scholes of the minimum-variance delta (R2) and the fixed scaling (R3). The 12-, 36- and 60-month medians cover 2017–2023, 2019–2023 and 2021–2023.
"""),
    code(r"""
m = pd.concat([pd.read_csv(R / f"stocks/{u}/walkforward_median_yearly_gain.csv").assign(underlying=u.upper()) for u in ("aapl", "nvda", "tsla", "qqq", "slv")])
m[(m.base == "R1") & m.rule.isin(["R2", "R3"])].pivot_table(index="underlying", columns=["rule", "window", "cp"], values="median_yearly_gain").round(3)"""),
    md(r"""
**Reading.** AAPL gains a little; NVDA, TSLA and SLV gain nothing or lose; and QQQ behaves like SPX on 12- and 36-month fits. Its 60-month median, −0.09 for calls, rests on 2021–2023 alone, the years SPX's Gain faded too. The fixed 0.9/1.1 scaling, read off S&P 500 options, loses 0.05–0.37 for calls on the three stocks with 12-month fits. Hull and White also found much smaller Gains for single stocks (Dow stocks, 2004–2015: 10.3% for calls and 2.5% for puts).

The short-dated options test (notebook 08) covers options under 14 days, with the main study's coefficients.
"""),
    code(r"""
sd = pd.read_csv(R / "short_dated/gains_by_year.csv")
print("median yearly Gain over Black-Scholes, 2015-2023:",
      sd[(sd.rule == "R2m") & (sd.base == "R1") & sd.year.between(2015, 2023)].groupby("cp").gain.median().round(3).rename(CP).to_dict())
print("by days to expiry on day one, median over 2011-2023:")
pd.read_csv(R / "short_dated/buckets.csv").groupby(["days", "cp"]).G_R2m_R1.median().unstack().rename(columns=CP).round(3)"""),
    md(r"""
**Reading.** For options under 14 days, the median yearly Gain over Black–Scholes in 2015–2023 is 0.06 / 0.005 for calls / puts. The maturity-bucket medians cover 2011–2023: the Gain is about zero under three days, and the 7–13-day calls do best (0.087). Why the Gain fades is not tested here. The vega factor in the correction does not vanish at the money near expiry: ν/(S√T) equals the standard normal density at d₁ times D·F/S, where F is the expiry's forward and D its discount factor. The dividend discount factor D·F/S is close to 1, so ν/(S√T) stays near 0.4 at the money. More likely, other parts of the error, gamma's above all, grow as expiry nears, and the coefficients come from options of 14 days or more.

The published-benchmark comparison (notebook 09) uses Hull and White's test months that we also have: 2013–2015 with 36-month fits; 2011–2015 with 12-month fits. It gives our Gains pooled and as a mean of monthly Gains, which is their aggregation:
"""),
    code(r"""
P = pd.read_csv(R / "walkforward/published_comparison.csv")
P[(P.rule == "R2") & (P.period == "HW overlap") & (P["sample"] == "analysis (E7)")].pivot_table(index="window", columns="cp", values=["pooled", "mean_of_monthly", "months"]).rename(columns=CP, level=1).round(3)"""),
    md(r"""
**Reading.** Our pooled 2013–2015 Gains with 36-month fits are 0.22 / 0.25, while Hull and White report mean monthly Gains of 0.26 / 0.23 over 2007–2015. On their aggregation ours are lower still (0.10 / 0.09), so pooling is not what makes ours lower than theirs. The periods differ. Our data begin in 2010, so their 2007–2009 is not in our data; and with 36-month fits our first test month is 2013-01, so their 2007–2012 test months have no counterpart in this comparison.

Our lower headline reflects three things:

- The period: 2017, 2018 and 2022–2023 are weak years.
- The 12-month window: pooled over mid-2012 to mid-2019 it gives about half the 36-month Gain (0.08 against 0.14–0.17), though over the 2015–2023 medians the ratio is 0.6–0.8.
- In-the-money calls, about half of our call sample (55% in 2020; notebook 01): restricting to out-of-the-money options raises the pooled 2011–2019 Gain, but only modestly (calls 0.119 → 0.130, puts 0.112 → 0.132; notebook 09).
"""),
    md(r"""
## 5. Financial interpretation

The correction hedges the expected volatility response. About 70% of an option's squared error is shared by all options on the day and survives averaging across a book (the common share in §4.5), which explains the larger book Gain. The size of the response matters more than its shape across strikes (§4.4).

The table puts the measured response beside the yearly Gain. For near-the-money options (|δ| 0.4–0.6) 20–60 days from expiry, it gives the slope of the daily change in implied volatility on the index return, in volatility points per 1% index fall.
"""),
    code(r"""
sv = pd.read_csv(R / "walkforward/spot_vol_slope.csv").set_index("year")[["vol_points_per_1pct_fall"]]
gy = wf("R2", "R1").pivot(index="year", columns="cp", values="gain").rename(columns=lambda c: f"Gain, {CP[c]}")
cp_ = L.pivot(index="year", columns="cp", values="c_post").rename(columns=lambda c: f"best level, {CP[c]}")
t = sv.join(gy).join(cp_)
print("correlation of the measured response with the yearly Gain:", t.corr().iloc[0, 1:3].round(2).to_dict(),
      "; without 2022-2023:", t.drop([2022, 2023]).corr().iloc[0, 1:3].round(2).to_dict())
print("correlation of the measured response with the best level:", t.corr().iloc[0, 3:].round(2).to_dict())
fig, ax = plt.subplots(figsize=(6, 3.6))
for cp, mk in (("C", "o"), ("P", "s")):
    ax.scatter(t.vol_points_per_1pct_fall, t[f"Gain, {CP[cp]}"], marker=mk, label=CP[cp])
for yr, r in t.iterrows():
    ax.annotate(str(yr), (r.vol_points_per_1pct_fall, r["Gain, calls"]), fontsize=7, xytext=(3, -9 if yr == 2023 else 3), textcoords="offset points")
ax.axhline(0, color="k", lw=0.8); ax.set_xlabel("vol points per 1% index fall (near the money)"); ax.set_ylabel("Gain over Black-Scholes (12-month fits)")
ax.legend(); plt.tight_layout(); plt.show()
t.round(3)"""),
    md(r"""
**Reading.** For near-the-money options 20–60 days from expiry, the measured response fell from 0.55 volatility points per 1% index fall in 2021 to 0.13 in 2022–2023, and the Gain fell with it. The yearly median of the best monthly levels after the fact tracks the measured response (correlation −0.61 for calls, −0.85 for puts). In 2022, the median fitted level, learned from the stronger preceding period, was more negative than the median best monthly level.

This is a descriptive reading, consistent with the identity of §4.4 but not a test. Across years the response and the Gain correlate at 0.56 / 0.64, and at only 0.21 / 0.27 without 2022–2023. 2017, the earlier low-response year (0.20), had the smallest put Gain before 2022 (0.05).

The scatter also shows that a strong response is not enough: what matters is whether the fitted level matches the year's. 2018 had a strong response (0.44) but small Gains. After the February 2018 spike entered the training window, fitted levels increased in magnitude. The year's median fitted level (−0.22 for calls, −0.26 for puts) was more negative than the median of its monthly best levels (−0.06 and −0.11; the table in §4.4).

**Drift.** For one-day hedges, we follow Hull and White's specification, with no intercept and no theta adjustment (theta is the option's time decay, Lecture 6). Subtracting one day's theta changes the 2020 Gains by at most 0.011:
"""),
    code(r"""
g = pd.read_csv(R / "2020/gains.csv")
z = g[g.variant.isin(["primary", "T"]) & (g.rule == "R2") & (g.base == "R1")].pivot(index="cp", columns="variant", values="gain").rename(index=CP)
z["T - primary"] = z["T"] - z["primary"]
display(z.round(3))
ME = pd.read_csv(R / "extensions/spx/paths_mean_error.csv")
q = ME[(ME.subset == "all") & (ME.rule == "R2") & (ME.period == "2011-2019")].set_index(["H", "cp"])[["diff_vs_R1", "diff_lo", "diff_hi"]]
print("Mean held-position error, minimum-variance delta minus Black-Scholes, 2011-2019, in basis points of the start-day index level:")
(q * 1e4).round(2)"""),
    md(r"""
**Reading.** For the long-option position that $e$ represents, the correction leaves the position slightly longer the index, because it under-hedges calls and over-hedges puts (the fitted level is negative). Its five-day mean error exceeds Black–Scholes' by about 0.9 basis points of the index level in 2011–2019. That is consistent with earning some of the index's upward drift, and the difference is not significant (the intervals include zero).

If the mean P&L is unchanged, and the reduction in squared error approximates the reduction in variance, a Gain $g$ multiplies the hedged position's Sharpe ratio (mean P&L over its standard deviation) by about $1/\sqrt{1-g}$:
"""),
    code(r"""
for g in (0.10, 0.15, 0.25):
    print(f"Gain {g:.2f}: Sharpe ratio multiplied by about {1 / np.sqrt(1 - g):.2f}")"""),
    md(r"""
Here the slope is the number of volatility points by which implied volatility rises per 1% fall in the index.

- **Works:** index options (SPX, SPY, QQQ); sell-offs; years in which the slope stays close to the preceding year's; books and held positions.
- **Fails:** after a crash enters the training window (April 2020); in rebounds and post-crash periods (late 2018, losses not significant; late 2022, significant); when the slope weakens (2022–2023); on single stocks and silver; near expiry.

## 6. Assumptions, limitations and failure modes

| Assumption | Check | Result | Notebook |
|---|---|---|---|
| Volatility response is quadratic in delta | Degrees 0–8, a validated degree, LightGBM on delta | Small economic differences; some pointwise significant improvements | 03, 08 |
| Response scales as $1/\sqrt{T}$ | $T^{-\alpha}$, $\alpha\in\{0,0.25,0.75,1\}$, by year | Not beaten consistently | 03, 09 |
| Coefficients remain stable between windows | Coefficient paths; fits 12 months apart | Fails: the level drifts, badly in 2022 | 04, 09 |
| No intercept or theta term is needed | Theta-adjusted 2020 variant; held-position mean error | 2020 Gains change by at most 0.011 with theta adjustment; five-day mean-error difference from Black–Scholes about +0.9 bp in 2011–2019, not significant | 05, 10 |
| One day is the relevant horizon | 5- and 10-day held positions | Gain grows in 2011–2019 and 2020; losses can grow too | 10 |
| Mid quotes are synchronous with the index | Two index-level sensitivities; bid and ask marks | Verdict unchanged | 02, 04, 05 |
| Frictionless index hedging | Turnover only | Not tested with costs; in 2020 the minimum-variance delta's daily change in hedge ratio was 3% smaller than Black–Scholes' | 05 |

The rehearsal's pre-specified diagnostic (`analysis_plan.md` §10, check 1) contradicted the quadratic in 2019 for both calls and puts: a cubic beat it, with a 95% lower bound above zero (notebook 03). The improvement was economically small, about 0.2% of the squared error. In the 2018 rehearsal an improvement was not statistically established. The later 12-month walk-forward also has some positive pointwise 95% lower bounds for higher degrees relative to the quadratic. Those comparisons are exploratory and unadjusted for multiplicity. Economically, the Gain is essentially unchanged across degrees 0–8 with 12-month fits.

There is one confirmatory year, and it contains a crash. The other analyses are exploratory, and clean years are few. The study uses one data vendor, whose quote timing is undocumented, and excludes transaction and financing costs. The intervals omit the training window's estimation error, and a crash strains the bootstrap's assumptions.

SPY's held-position test follows a contract only through days on which it traded with at least 14 days to expiry, because SPY's Greeks were computed only for day-one candidates. The five stocks and ETFs use the vendor's underlying levels.

The observed failure modes are:

- a crash entering the training window, followed by over-correction: April 2020, and the stocks' 2020 (notebooks 04 and 11);
- the LightGBM corrections with market features extrapolating outside their training range in March 2020 (notebooks 05 and 08);
- a fixed scaling of delta applied outside the market and period it was read from. Ruf and Wang's 0.9/1.1 comes from S&P 500 options from 2010 to mid-2019. It fails on SPY calls and single stocks, and on SPX itself in 2022–2023, as the volatility response weakened (notebooks 06, 07 and 11).

## 7. Reproducibility

The repository is [github.com/biswajit-nag/hull-white-delta-spx](https://github.com/biswajit-nag/hull-white-delta-spx). `uv sync --locked`, `uv run pytest` and `uv run python -I scripts/make_notebooks.py` rebuild every notebook, this one included, from the committed tables, without the vendor data. With the vendor's archives, the scripts in `scripts/` rebuild those tables. `REPRODUCING.md` gives every step, and `results/runtime_log.csv` records each run's commit and wall time.

This is an individual project. Claude (Anthropic) assisted with code, analysis and drafting. GPT-6 Astra (OpenAI) reviewed key steps and helped in wording the reports. The author directed the work and takes the responsibility for its correctness.

**References.** Hull, J. and White, A. (2017), Optimal delta hedging for options, *Journal of Banking & Finance* 82, 180–190. Ruf, J. and Wang, W. (2022), Hedging with linear regressions and neural networks, *Journal of Business & Economic Statistics* 40(4), 1442–1454.
"""),
])

NOTEBOOKS["01"] = ("01_audit_and_attrition", [
    md(r"""
# 01 · Data audit and attrition

**In the story** (notebook 00, §2): this notebook shows where the sample comes from. It yields 1.06 million SPX pairs in 2020 and 7.6 million over 2011–2023, with at least 14 days to expiry, an absolute delta of 0.05–0.95 and trading on day one. In 2020, 98.7% of eligible pairs have a usable next-session quote.

The data are OptionsDX's end-of-day SPX option quotes. Before computing any hedging number, this notebook checks four things:
- whether the quotes are fit for a one-day hedging study;
- which option-days enter the analysis (rules E1–E8 of `analysis_plan.md` §5);
- how many are lost because the next session's quote is missing (*attrition*);
- what the sample is made of.

Every number here concerns data quality; no hedging error is computed. The processing rules are in `DATA.md`.

A *pair* is one contract on NYSE session *t* (day one), followed to the same contract on the next NYSE session (day two). A hedge set at day one's close is judged by the option's and the index's moves to day two's close. That is Lecture 7's discrete delta-hedging P&L, cut to one period.
"""),
    code(SETUP),
    md(r"""
## Eligibility and the vendor's volume coding

Ruf and Wang (2022) keep an option-day only if it traded that day (positive volume), since an untraded quote may be stale.

Our data needed one correction. Through 2021, OptionsDX never records a volume above 999. On the evidence of day-to-day transitions, it leaves the field *empty* when 1,000 or more contracts trade. It also leaves it empty for contracts that have not traded. The last-trade price separates the two cases:
- "empty" with a positive last price means a heavily traded day;
- "empty" with a last price of 0 means no trade.

Rule E7 therefore requires positive volume, or empty volume with a positive last price. The table shows how many pairs each clause admits.
"""),
    code("""
e7 = pd.read_csv(R / "attrition/e7_clause.csv")
e7"""),
    md(r"""
## Attrition: eligible pairs without a usable next-session quote

A pair needs a two-sided quote (a bid and an ask) for the same contract on the next session. When the vendor lacks the whole session, the pair is lost (`vendor_missing_session`); it never turns into a two-day hedge. When the bid vanishes (`one_sided_next`), the value is unknown. The plan stress-tests those pairs with endpoint scenarios (§5).

In the table, the `2020` rows exclude the stress period (2020-02-24 to 04-30), which has its own `stress` rows. Together they give 98.7% usable pairs for 2020.
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
    md(r"""
**Reading.** Attrition is small and comes almost entirely from whole sessions missing at the vendor: ordinary days, and none in the March 2020 crash.

Vanished bids are under 0.1% of pairs. They are concentrated in the stress period (2020-02-24 to 04-30), mostly in far out-of-the-money and long-dated options.

Results are therefore stated conditional on a usable day-two quote, with this table beside them.
"""),
    md(r"""
## What the sample is made of

Moneyness is measured by the Black–Scholes delta, which puts all maturities on one scale (Lecture 6). Hull and White's band keeps 0.05 ≤ |δ| ≤ 0.95, including both in- and out-of-the-money options.

SPX lists far more strikes below the index than above, and the volatility skew stretches the band further down. Calls are therefore about half in the money, while puts are mostly out of the money. The in-the-money shares are 55% for calls and 29% for puts in 2020; 48% and 20% in 2019.

This matters for comparisons with published work: in-the-money calls are a large part of our call sample, and one reason our headline Gains are below Hull and White's (notebook 09).
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
    md(r"""
# 02 · Forwards, implied volatilities, Greeks, and verification

**In the story** (notebook 00, §§2–3 and §6): every hedge ratio in the study is built from the quantities made here: each expiry's forward and discount factor, each option's implied volatility, and its Black–Scholes delta, vega and vanna. This notebook also sets up sensitivity A, which checks the synchronous-quotes assumption after finding that the option quotes are synchronous with neither index series. It also runs the test suite.

Lecture 9 prices with a continuous dividend yield q. The S&P 500's dividends come from 500 companies on scattered dates, so no single q is observable. Instead, every expiry is priced on its own *forward* F and discount factor D, both read from put–call parity at the mids (Lectures 6 and 9):

  C − P = D·(F − K).

The three stages (`analysis_plan.md` §4) are:
1. A weighted least-squares line of C − P on K, per expiry, on strikes within 10% of the index where both legs are quoted.
2. A smooth zero-rate curve r(τ) per session, from the expiries at least 30 days out, because a short expiry pins down D poorly.
3. Each expiry's forward, given D.

The price is Black's formula C = D·[F·N(d₁) − K·N(d₂)]. It equals Lecture 9's formula with r = −ln(D)/τ and q = r − ln(F/S)/τ. Implied volatilities come from Lecture 12's solver, `option_pricing.bs_euro_iv`.
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
    md(r"""
## Sensitivity A's index level

The audit found the option quotes are synchronous with neither the official close nor the vendor's snapshot. Sensitivity A therefore uses the level implied by the options themselves: the parity forward of the nearest P.M. expiry with a successful fit 0.5–5 days out, falling back to the nearest successful fit up to 10 days out.
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
    md(r"""
# 03 · The rehearsal on training data (2019, and 2018)

**In the story** (notebook 00, §3, §4.4 and §6): before 2020 was opened, a rehearsal on 2018–2019 and a dry run of the test script on 2019 checked the code and the model's form. The quadratic in delta and the 1/√T maturity scaling were checked here first, and the walk-forward repeated those checks later (notebooks 08 and 09). This notebook also shows why the Gain intervals resample sessions, not options.

The plan (`analysis_plan.md` §10) runs the whole pipeline on training years before the 2020 test year is opened. This checks the code end to end, previews the width of the confidence intervals, and answers every question about the *form* of Hull and White's rule without touching 2020. Those questions concern the rule's polynomial degree in δ and its 1/√T maturity scaling.

The design uses a 6-month trailing window, refitted monthly and tested on July–December. The main rehearsal year is 2019, with 2018 as a second year. The 2019-12-31 pairs end on 2020-01-02, so they are excluded.

The hedging error, on Hull and White's normalized scale, is e = (Δf − h·ΔS)/S_t:
- Δf is the option's mid-price change;
- ΔS is the index's change;
- h is the rule's hedge ratio.

The Gain of rule X over rule Y is 1 − Σe²_X / Σe²_Y. Intervals come from a circular block bootstrap over sessions, not options, because every option on a day shares that day's index move (§9).
"""),
    code(SETUP),
    code("""
g = pd.concat([pd.read_csv(R / f"rehearsal/gains_{y}.csv").assign(year=y) for y in (2019, 2018)])
show = g[g.rule.isin(["R1", "R2", "R3", "R4", "R5", "R6"]) & g.base.isin(["R0", "R1", "R3", "R4"])]
show[["year", "cp", "rule", "base", "gain", "lo", "hi", "pairs"]].round(4)"""),
    md(r"""
**Reading.** The Black–Scholes delta already removes about 95% of the unhedged squared error (R1 against R0).

In 2019 H2, Hull and White's correction (R2) removes a further 28% for calls and 34% for puts of what is left. It beats the fitted scaling rule (R4) by about 11% for both types. In 2018 H2, which contains the Q4 2018 sell-off, the call Gain is about zero and its 95% interval is about 0.48 wide; the put interval is about 0.29 wide.

That is the preview for 2020: a crash year will give wide intervals, and a correction fitted in calm months may not carry over.
"""),
    md(r"""
## Specification check 1: the polynomial degree

Hull and White's adjustment is a quadratic in δ. Here degrees 0–3 are compared out of sample, on an orthogonal (Legendre) basis.

The criterion was fixed before running: the quadratic is *not contradicted* unless the cubic beats it, with a 95% bootstrap lower bound above 0.
"""),
    code("""
s = pd.concat([pd.read_csv(R / f"rehearsal/spec_checks_{y}.csv").assign(year=y) for y in (2019, 2018)])
s[s.check.str.startswith("degree")].round(5)"""),
    code("""
g[g.base == "deg:2"][["year", "cp", "rule", "gain", "lo", "hi"]].round(4)"""),
    md(r"""
**Reading.** In 2019 the cubic beats the quadratic for both types, with a 95% lower bound above zero. Under the pre-specified diagnostic, this contradicts the quadratic. The improvement is statistically detectable with hundreds of thousands of pairs. Its economic size is negligible: about 0.2% of the squared error. In 2018 an improvement was not statistically established: the point Gains are positive, but the lower bounds are below zero.

Under the plan's rule, the cubic is carried to 2020 as a labelled exploratory rule; Hull and White's quadratic stays the rule under test.

A constant adjustment (degree 0) also beats the quadratic for calls in 2019, by 1.4%. The plan's criterion does not cover a lower degree winning, so this is reported, not acted on. It suggests the quadratic's extra coefficients add estimation noise on 6-month windows.

This was the first sign of a central finding: in the 2011–2023 walk-forward, one fitted constant gives essentially the same Gain as Hull and White's three coefficients (notebooks 08 and 09).
"""),
    md(r"""
## Specification check 2: the 1/√T scaling

The test replaces τ^(−1/2) with τ^(−α), for α ∈ {0, 0.25, 0.75, 1}, each compared with α = ½. Holm's adjustment is applied across the four, per option type.
"""),
    code("""s[~s.check.str.startswith("degree")].round(4)"""),
    md(r"""
**Reading.** The 1/√T scaling is not contradicted in either year. No scaling at all (α = 0) has a negative Gain against α = ½ for both types in both years (2019: −0.20 and −0.15; 2018: −0.04 and −0.04). The table shows only lower bounds, so the small 2018 gaps are not established.

For calls, α = ¾ (2019) and α = 1 (2018) look slightly better, but neither survives the adjustment. If anything, the call adjustment decays a little faster with maturity than 1/√T.
"""),
    code("""
b = pd.read_csv(R / "rehearsal/buckets_2019.csv")
order = ["14-30", "31-60", "61-91", "92-122", "123-182", "183-365", "366+"]
t = b[b.pairs > 500].pivot_table(index=["cp", "delta_b"], columns="tau_b", values="sqrt_tau_kappa")[order]
t.round(3)"""),
    md(r"""
This is the bucket analysis Hull and White describe in their §IV. Each cell is √τ_eff·κ̂, where κ̂ is the per-bucket no-intercept OLS coefficient of y = (Δf − δΔS)/S_t on w = (ν/S_t)·(ΔS/S_t), and τ_eff^(−1/2) = Σw²τ^(−1/2)/Σw². Under 1/√T, each row should be flat across maturity. For puts it is roughly flat. For calls the magnitude shrinks beyond six months, consistent with the slight preference for α > ½.
"""),
    md(r"""
## Why the bootstrap is over sessions: naive against clustered standard errors

R2's coefficients are shown with ordinary OLS standard errors and with standard errors clustered by session.
"""),
    code("""
pd.concat([pd.read_csv(R / f"rehearsal/se_ratio_{y}.csv").assign(year=y) for y in (2019, 2018)])[["year", "cp", "coef", "estimate", "se_naive", "se_clustered", "ratio", "sessions"]].round(4)"""),
    md(r"""
**Reading.** The clustered standard errors are 4.5 to 34 times the naive ones. All options on a day share that day's index move and volatility shock, so the information accumulates with sessions (about 250 a year), not with option-days (about 300,000). Significance claims that treat options as independent, such as Hull and White's Appendix B, are therefore far too optimistic.

The same fact recurs later. It is why a fit on three options per session and type loses only about 0.01 in Gain (notebook 10), and why a tuned learner's correction shrinks almost to a constant (notebook 08).
"""),
    md("""
## The dry run of the test script (2019)

After the rehearsal, the full test-year script (`scripts/run_test_year.py`) ran end to end with 2019 as the test year, on 12-month windows, excluding pairs whose day two is in 2020 (plan §15, 2026-11-04). It produces no 2020 number and is not evidence, since 2019 had already been used for the rehearsal. It tested the code, so that nothing would be debugged with 2020 results in view.
"""),
    code("""
pd.read_csv(R / "dryrun_2019/verdict.csv").round(3)"""),
    md("""
**Reading.** The script ran every variant of the verdict table. Even in 2019, a calm year, the procedure returns Inconclusive: calls 0.114 [−0.05, 0.24], puts 0.099 [−0.26, 0.30]. Those intervals are narrower than 2020's turned out to be (widths 0.29 and 0.56, against 0.82 and 0.90), but still too wide to establish a Gain of this size in one year. That is why the stability question is answered by the walk-forward over many years (notebook 06).
"""),
])


NOTEBOOKS["04"] = ("04_results_2020", [
    md(r"""
# 04 · The 2020 test year

**In the story** (notebook 00, §4.1 and §6): the pre-registered SPX 2020 test is inconclusive. The minimum-variance delta removed 18.5% of the squared error for calls and 12.0% for puts, but the March 2020 crash leaves 95% intervals spanning about −0.4 to +0.46. All 11 pre-specified robustness variants agree on the verdict, though wide intervals limit what that agreement establishes. This notebook shows the verdict, why the intervals are so wide, and what went wrong after the crash.

The confirmatory question (`analysis_plan.md` §1, §8) is whether, in 2020, Hull and White's minimum-variance delta (R2) reduces next-session squared hedging error relative to the Black–Scholes delta (R1). Does it also beat Ruf and Wang's scaling rules: the fixed 0.9·δ for calls and 1.1·δ for puts (R3), and a fitted a·δ (R4)?

Each 2020 month is hedged with coefficients fitted on the 12 months before it. A training pair must end before the test month's first session. The plan was committed (77b030e) before any 2020 hedging outcome was computed, and 2020 was opened in one logged run (implementation b661d6a).

Gain of rule X over rule Y = 1 − Σe²_X/Σe²_Y on the same pairs; a Gain of 0.10 means 10% less squared error.

H1 requires the 95% lower bound of the Gain over R1 to exceed 0 for calls *and* puts.
"""),
    code(SETUP),
    code("""
v = pd.read_csv(R / "2020/verdict.csv")
v.round(3)"""),
    code("""
g = pd.read_csv(R / "2020/gains.csv")
prim = g[(g.variant == "primary") & (g.rule == "R2") & g.base.isin(["R1", "R3", "R4"])]
prim[["cp", "rule", "base", "gain", "lo", "hi", "p_plus", "p_minus", "pairs"]].round(3)"""),
    md(r"""
The verdict is "Inconclusive". The minimum-variance delta (R2) reduces squared hedging error by 18.5% for calls and 12.0% for puts, relative to the Black–Scholes delta (R1). The session-block bootstrap intervals are [−0.36, 0.46] and [−0.45, 0.46]. H1 is not supported, and nothing is rejected: the data cannot tell a 20% improvement from none.

Against the scaling rules, all four comparisons are "not distinguished": the fixed 0.9/1.1 scaling (R3) and the fitted scaling a·δ (R4), for calls and puts.

All 11 pre-specified robustness variants give the same verdict:
- the options' own index level (A);
- the vendor's level (B);
- bid-only and ask-only marks;
- the frozen 2019 fit (F);
- 36- and 60-month windows;
- the spread screen (S3);
- the rest of 2020 without the stress period;
- the two vanished-quote scenarios.

Wide intervals limit what that agreement establishes. The variants' point Gains move more; notebook 05 gives the detail. In three variant comparisons the minimum-variance delta does beat a scaling rule (F for puts against both; the rest of 2020 for calls against R4), never in the primary.

The lower bounds sit 0.54 and 0.57 below the point Gains. Given these interval widths, only a Gain above roughly 0.5 could have cleared zero: about twice the 0.23–0.26 that Hull and White report.

The intervals are wide because the error is concentrated. In March 2020 the index moved by up to 12% a day, so squared errors on those days are about 100 times those of a calm day.
"""),
    code("""
d = pd.read_csv(R / "2020/descriptives.csv")
d[d.rule.isin(["R0", "R1", "R2", "R3", "R4"])][["cp", "rule", "pairs", "effectiveness_vs_R0", "rms_dollars_per_contract", "stress_share_R1"]].round(3)"""),
    code("""
for cp in "CP":
    t = pd.read_csv(R / f"2020/top_sessions_{cp}.csv")
    print(cp, "top-10 sessions' share of Black–Scholes squared error:", round(t.share.sum(), 3))
    print(t.assign(session=t.session.str[:10]).round(3).to_string(index=False))"""),
    md(r"""
**Reading.** Black–Scholes already does most of the work. It removes 92% for calls and 95% for puts of the unhedged squared error. The minimum-variance correction adds about 1.5 percentage points of effectiveness for calls and 0.6 for puts by working on what is left.

SPX options are \$100 per index point. In dollars, the correction cuts the RMS hedging error per contract from about \$825 to \$727 for calls, and from \$894 to \$804 for puts.

The stress period (2020-02-24 to 04-30) holds 80% for calls and 86% for puts of the year's Black–Scholes squared error, and ten sessions hold 65–73%. Sessions are dated by day one, so the largest, 2020-03-13 (30% of the calls' error), is the hedge from 13 to 16 March, when the index fell 12%.

The pooled Gain is therefore essentially a statement about March 2020, and a few days decide it.
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
    md(r"""
**Reading.** The correction helps in January–March (Gains of +0.15 to +0.40), June and October. It hurts badly in April (−0.80 for calls), September and November.

The average of monthly Gains is about zero for both types. The pooled +18%/+12% comes from March outweighing the bad months.
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
    md(r"""
The in-sample ceiling refits R2 on each test month's own pairs: the best a quadratic correction could have done with hindsight.

In the months where R2 failed for both types (April, August, September, November), even the ceiling is small: 0.05–0.08 in April, and at most 0.015 in the other three. The R2 specification could remove only that fraction of Black–Scholes squared error even with hindsight, so an earlier fit of the same specification could gain at most that much; R2 lost 0.11 to 0.80 instead.

The crash in the window is not the whole story. May and June, with March 2020 also in their windows, gained (+0.17 and +0.42 for calls), while September and November lost without a new crash. What decides a month is whether the relation the fit expects is there.

That is a model-risk finding. The rule's value depends on the spot–volatility relation being stable, and in 2020 it was not.
"""),
    md("""
## The crash itself, and the rest of the year

The stress period and the rest of 2020 are bootstrapped in separate strata, so no block crosses between them.
"""),
    code("""
g[g.variant.isin(["stress", "rest of 2020"]) & (g.rule == "R2") & g.base.isin(["R1", "R3", "R4"])][["variant", "cp", "base", "gain", "lo", "hi"]].round(3)"""),
    md(r"""
Outside the crash the picture is calmer and clearer for calls. R2 beats the fitted scaling rule for calls by 5.3%, with an interval of [0.032, 0.077]. The secondary tests use the full-year family, so this is descriptive.

One crash year cannot settle the question, so the stability evidence comes from repeating the same protocol over 2011–2023 (notebook 06). There the correction usually helps. Its failure in April 2020—a crash entering the training window followed by over-correction—turns out to be one of three recurring failure modes (notebook 00, §6).
"""),
])

NOTEBOOKS["05"] = ("05_breakdown_and_sensitivities", [
    md(r"""
# 05 · Breakdown, sensitivities and extensions

**In the story** (notebook 00, §§4.1, 4.3, 5 and 6): this notebook examines the robustness of the 2020 verdict, where the hedging error comes from, and the boosted learner's failure in March 2020.

For §4.1, it reports robustness variant by variant. For §5, it shows that the minimum-variance correction works only on the part of the volatility move that comes with the index move. Subtracting one day's theta (sensitivity T) changes the 2020 Gains by at most 0.011. For §4.3 and §6, it documents the first appearance of a failure mode: a LightGBM correction on market features, tuned on calm 2019, broke in March 2020.

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
    md(r"""
Neither the index level nor the fitting window moves the verdict.

A and B use the options' own level and the vendor's snapshot. In the pre-registered timing diagnostic (plan §8), moving from the primary to A lowers the call Gain by 0.038 (0.185 → 0.147) and raises the put Gain by 0.099 (0.120 → 0.219). Changes in opposite directions are consistent with the timing mismatch the audit found between the option quotes and the close, though they do not identify it uniquely.

W36 and W60 use the longer windows. They give the same point Gains (about 0.18 for calls and 0.14 for puts), with somewhat narrower intervals.

The frozen fit F, fitted once on 2019, does about as well as monthly refitting (calls 0.178 against 0.185; puts 0.145 against 0.120). It is the one variant in which the minimum-variance delta (R2) beats both scaling rules for puts. In 2020, refitting monthly did not help: the refits learned March too late.

Hull and White's one-day error has no intercept and no theta term. Subtracting one day's theta (the option's time decay, Lecture 6) from the option's price change in sensitivity T changes the Gains by at most 0.011 (calls 0.174 against 0.185, puts 0.112 against 0.120). The drift a hedge leaves is examined over longer horizons in notebook 10.
"""),
    code("""show(["P-bid", "P-ask", "P-WM", "P-SW", "S3", "V", "OTM", "OTM-refit"])"""),
    md(r"""
**Marks.** Marking at the bid, the ask, the imbalance-weighted mid or Lecture 12's size-weighted price leaves the comparison where it was.

**Populations.** The spread screen (S3) lowers the point Gains, especially for puts. On the out-of-the-money subsample, Ruf and Wang's home domain, the comparison with the scaling rules stays "not distinguished". Refitting the fitted scaling (R4) on out-of-the-money pairs brings it close to R2: R2's relative Gain over it is about 0 for calls and 0.030 for puts, with both intervals including 0.
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
    md(r"""
**Reading.** The vega term is about 60% of the squared error, and the gamma term 27–34%. The minimum-variance delta works on the vega term: the part of the volatility move that comes with the index move.

That part is small, a delta correction of about −0.04 (`xmom_vega`). Most of the vega risk is volatility moving on its own, which no delta can hedge. That caps what any delta rule can gain.

The gamma term (the convexity of the option's value in the index, Lecture 6) is also largely beyond a delta, since it is quadratic in the index move; only a small part is reachable by a delta correction (`xmom_gamma` of about −0.015 to −0.017).

The remainder is about 1%, so the second-order expansion holds even in the stress period (24 February to 30 April 2020): a check on the Greeks.
"""),
    md("""
## Other declared diagnostics
"""),
    code("""pd.read_csv(R / "2020/extra_diagnostics.csv")"""),
    md(r"""
**Reading.** Under the Black–Scholes hedge (R1), the imbalance-weighted mid (WM) has about 2% less squared error than Lecture 12's size-weighted price (SW). Its changes covary negatively with the mid's hedging error, so the 16:00 size imbalance carries a little information, in the direction microstructure theory predicts.

Sensitivity A's level never reuses a hedged contract's quotes. 363 pairs had ten days or less left on day two, and none of their expiries fed that day's fallback level fit.
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
    md(r"""
The monitoring illustration shows what a desk would have seen: the trailing 20-session Gain, computed only from completed hedges. It first turns negative on 9 April (puts) and 14 April (calls), about four weeks after the worst days of mid-March. It would therefore have flagged the problem only partway through April. Per the plan, no switching rule is evaluated.
"""),
    md("""
## Exploratory challenger: gradient boosting (R8)

R8 is a LightGBM correction boosted from the minimum-variance delta on six market features: delta, log maturity, the option's position on its smile, the at-the-money implied volatility, 20-day realized volatility and the 5-day index return. It was tuned with Optuna on 2019 before 2020 was opened.
"""),
    code("""
g[g.variant.str.startswith("learners") & (g.rule == "R8")][["cp", "rule", "base", "gain", "lo", "hi"]].round(3)"""),
    code("""pd.read_csv(R / "2020/smoothness.csv").round(4)"""),
    md(r"""
**Reading.** The boosted correction (R8) failed badly for puts. Its Gain over R2 is −9.25: its squared error for puts was about 10 times R2's, and 9 times Black–Scholes'.

Its hyperparameters were tuned on 2019, and the trees used in March were fitted on March 2019 to February 2020. Over that window, the 20-day realized volatility never exceeded 25% and the worst 5-day index return was −12% (at the very end of February). In March 2020 those features reached 98% and −20%, far outside what the trees had seen. Their extreme leaves pushed the median put hedge ratio from −0.57 to −1.07. March's squared error for puts was 13 times R2's; in the other months it stayed within 0.8–1.6 times R2's.

The boosted correction is also rougher. It has more out-of-order hedge ratios across adjacent strikes (2.8% against 1.8%) and 48% more daily turnover than R2. R2 itself trades 3% less than Black–Scholes (a mean daily change in hedge ratio of 0.0333 against 0.0344), so the correction would not raise proportional trading costs.

That is the failure mode the non-smooth-hedge argument predicts: a flexible learner extrapolates arbitrarily outside its training data. Notebook 08 shows that the features, not the boosting, broke it: a LightGBM correction on delta alone stayed with R2 throughout 2020.
"""),
    md(r"""
## SPY (§16.1)

*Superseded on 2026-11-05 by the full replication of plan §16.3: see notebook 07. The numbers below reproduce the 2026-11-04 exploratory protocol with the corrected inputs, rerun on 2026-11-07.*

The same protocol is applied to SPY: American options (Lecture 12's tree for puts), SPY's own close, and distributions added to the hedge leg on ex-dates.
"""),
    code("""
s = pd.read_csv(R / "spy/gains.csv")
s[(s.rule == "R2") & s.base.isin(["R1", "R3", "R4"])][["variant", "cp", "base", "gain", "lo", "hi", "pairs"]].round(3)"""),
    md(r"""
**Reading.** SPY tells the same story. The point Gains are positive (0.10 for calls, 0.24 for puts), the intervals span zero, and the scaling rules are not distinguished.

The ex-date-only rows are too thin to interpret. 2020 has three ex-dates with pairs, so some bootstrap draws (about 4%) contain none, and any such draw leaves the interval undefined.

On ex-date pairs, adding the distribution to the hedge leg helps puts but not calls. That is the limitation stated in advance: calls are priced as European. A deep in-the-money American call carries an early-exercise premium before the ex-date, which vanishes on it.
"""),
])


NOTEBOOKS["06"] = ("06_walkforward_2011_2023", [
    md(r"""
# 06 · Stability across years: the 2011–2023 walk-forward

**In the story** (notebook 00, §§4.2–4.3, §5, §6 and Figure 1): repeated out of sample over 2011–2023, with monthly fits on the preceding 12 months, the correction usually helps. Its median yearly Gain over 2015–2023 is 0.12 for calls and 0.10 for puts. Its advantage disappears in 2022–2023 as implied volatility became less responsive to index moves. This notebook also examines the spot–volatility slope and the fixed scaling's failure on SPX in 2022–2023.

The project asks how stable the minimum-variance delta's advantage is across years. The pre-declared walk-forward (`analysis_plan.md` §14, item 2) answers that question; its results are exploratory.

Coefficients are refitted monthly on trailing 12-, 36- and 60-month windows. The windows are compared on their common test months, 2015-01 to 2023-12; the 12- and 36-month windows also start earlier. Each year gets its own session-block bootstrap.

2014–2020 had already been used for fitting or evaluation, so the clean held-out years are 2011–2013 and 2021–2023 (`results/year_ledger.csv`).
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
    md(r"""
## Significant years, and the scaling rules year by year

Counts cover the 26 call-or-put years of 2011–2023, with the 12-month window. Significance is pointwise (each year's own 95% interval), not adjusted for multiple comparisons.
"""),
    code("""
w12 = g[g.window == 12]
for base, name in (("R1", "Black–Scholes (R1)"), ("R3", "the fixed 0.9/1.1 scaling (R3)"), ("R4", "the fitted scaling (R4)")):
    z = w12[(w12.rule == "R2") & (w12.base == base)]
    win, lose = z[z.lo > 0], z[z.hi < 0]
    print(f"R2 against {name}: significantly better in {len(win)} of {len(z)}, significantly worse in {len(lose)}",
          list(zip(lose.year, lose.cp)) if len(lose) else "")
med = w12[w12.base == "R1"].query("2015 <= year <= 2023").groupby(["rule", "cp"]).gain.median().unstack()
print("median yearly Gain over Black–Scholes, 2015–2023:"); med.round(3)"""),
    md(r"""
**Reading.** Through 2021 the advantage is consistent. With the 12-month window, the Gain over Black–Scholes is positive every year, mostly 0.10–0.25. It is significantly positive in 7 of 26 call-or-put years and significantly negative in none. In 2021, a clean year, it is significant for both calls and puts, and the minimum-variance delta (R2) also beats the fitted scaling rule.

In 2022–2023 the advantage disappears. With the 12-month window it is about 0, with tight intervals in 2023. With the longer windows it turns negative in 2022 (−0.16 to −0.23): for puts, R2 is significantly worse than the fitted scaling rule.

R2 beats the fixed 0.9/1.1 scaling significantly in 14 of 26 call-or-put years and loses in two, both in 2018; it beats the fitted scaling in 12 and never loses. Yet the fixed scaling's median Gain over Black–Scholes (0.125 / 0.099) matches R2's (0.124 / 0.100). The fixed scaling wins clearly in 2018 and fails in 2022 (−0.14 to −0.18) and 2023 (−0.06 to −0.14), when the volatility response it was read from had weakened. Notebook 08 compares R2 with the other challengers.
"""),
    code("""pd.read_csv(R / "walkforward/spot_vol_slope.csv").round(3)"""),
    md(r"""
The minimum-variance correction works through the co-movement of implied volatility and the index. The table measures it each year for near-the-money options (|δ| 0.4–0.6) 20–60 days from expiry. It reports the slope of each session's median change in implied volatility on the index return, in volatility points per 1% index fall (`scripts/spot_vol_slope.py`).

The slope collapsed. It was 0.20–0.55 vol points per 1% fall in 2011–2021 (0.25–0.55 outside 2017; 0.55 in 2021), and 0.13 in both 2022 and 2023.

The fitted coefficients were therefore too large: they had learned a stronger relation than the market then delivered. Longer windows remember more of it, and suffered more. Notebook 09 gives an exact identity for each monthly fit: the Gain depends on the fitted level of the correction against the level that month rewarded, and a level more than twice too large loses to Black–Scholes.

2017 provides an earlier analogue. That earlier low-slope year (0.20) had the smallest put Gain before 2022 (0.05).

This is a descriptive reading. A model validator would take it as the case for monitoring the spot–volatility slope alongside the hedge.
"""),
    md(r"""
## The boosted challenger in the walk-forward

R8, the LightGBM correction on market features boosted from R2, is retuned once on 2015–2016, with validation pairs ending before 2017. It is then refitted monthly on the 12-month window from 2017 on. Each row is its relative Gain over R2.
"""),
    code("""
w = pd.read_csv(R / "walkforward/r8_by_year.csv")
w[w.rule == "R8"][["year", "cp", "gain", "lo", "hi"]].round(3)"""),
    md(r"""
**Reading.** The tuning chose a minimal model: 51 trees, a learning rate of 0.01, 4 leaves. In most years R8 is within a few percent of R2.

2020 puts are the exception. The crash pushed the features far outside their training range, and even this small correction roughly tripled R2's squared error (relative Gain −1.98). The same failure appears in the 2020 test (notebook 05).
"""),
])


NOTEBOOKS["07"] = ("07_spy_replication", [
    md(r"""
# 07 · SPY: a full replication of the SPX protocol (plan §16.3)

**In the story** (notebook 00, §4.2 and §6): SPY replicates the picture. 2020 is inconclusive, and puts typically gain 16–28% a year through 2021; the advantage fades in 2022–2023 as on SPX. SPY also shows a failure mode of §6: Ruf and Wang's fixed 0.9 scaling for calls, read off S&P 500 index options, is worse than Black–Scholes on SPY calls in 8 of 13 years (significantly only in 2012 and 2023).

Four things change for SPY:

- The options are American and settle into shares. Puts are priced on Lecture 12's tree (150 steps, control variate), with δ, ν, vanna and theta from finite differences on the same tree. Calls are priced as European, as the lecture does.
- SPY pays quarterly dividends. The distribution enters the hedge leg on ex-dates.
- The index level is SPY's close: Nasdaq's from 2016-11-03, and before that Stooq's, with its dividend adjustment reversed (checked against Nasdaq on 1,821 sessions: median 0.43 bp in level, 0.14 bp in return).
- The dividend yield comes from SPX's implied carry, using the SPX close on the few sessions without SPX's options-implied level (plan §15).

Every SPX procedure that applies is retained:

- the rehearsal and its specification checks on 2018–2019;
- tuning the LightGBM correction on market features (R8) on 2019, and the dry run;
- 2020 with every Table 8.1 variant except A (American parity gives no options-implied level), and the verdict table;
- the 2011–2023 walk-forward.

SPY's 2020 Gains for R0–R5 were first computed on 2026-11-04, so this 2020 verdict is post hoc. The clean evidence is the untouched SPY years: 2011–2014, 2017 and 2021–2023 (`results/spy/year_ledger_spy.csv`).
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
    md(r"""
**Reading.** The verdict is Inconclusive, like SPX. Gain G is 0.104 [−0.30, 0.40] for calls and 0.238 [−0.25, 0.48] for puts. The minimum-variance delta (R2) is not distinguished from the fixed scaling (R3) or the fitted scaling (R4), and every robustness variant is Inconclusive too.

The LightGBM corrections on market features (R8 and R10) collapse for puts in the crash (Gains of about −52 against R2). The δ-only learners R9 and R11 and the carried cubic beat R2 by a significant but tiny +0.003 to +0.005. The carried τ-scalings have negative point Gains against R2 (−0.02 to −0.08), with intervals that include 0.
"""),
    md(r"""
## The 2011–2023 walk-forward

Yearly significance is pointwise, using each year's own 95% interval, without adjustment for multiple comparisons.
"""),
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
    md(r"""
**Reading.** The pattern is the same as SPX, and clearer for puts. Through 2021, R2 and the scaling rules typically remove 16–28% of the Black–Scholes error for puts; 2017 and 2019 are lower. In the clean years 2011–2014 and 2021, R2's put Gain over Black–Scholes is 0.21–0.28, with intervals above 0. The advantage is gone in 2022–2023, and with the long windows puts go strongly negative in 2022.

For SPY calls, the fixed 0.9 scaling is worse than Black–Scholes in 8 of 13 years (significantly in 2012 and 2023); R2 and the fitted scaling are positive in most years but not all (R2's call Gain over Black–Scholes is −0.078 in 2018 and −0.004 in 2023 with 12-month fits).

With 12-month fits, the relaxed Hull–White rule (R5), the δ-only learners (R9, R11) and polynomials of degree 3–8 (P3–P8) have median yearly Gains over R2 of about +0.001 to +0.006 over 2015–2023. Ex-date pairs hold 0.3–9% of a year's squared error, with no systematic loss.
"""),
])

NOTEBOOKS["08"] = ("08_more_rules_and_short_dated", [
    md(r"""
# 08 · More rules: the learners decomposed, the polynomial degree, and short-dated options

**In the story** (notebook 00, §4.3, §4.4, §4.5 and §6): this notebook compares simpler and more flexible rules, checks the polynomial degree, documents the LightGBM failure mode, and examines short-dated options. For SPX with 12-month fits, the constant correction, every polynomial degree and the delta-only LightGBM corrections all stay within about 0.015 a year of the minimum-variance delta (R2). The LightGBM corrections that use market features fail in the crash, and options under 14 days gain little.

Three sets of rules were added on 2026-11-05, each specified and committed before its run:

- **R5, R6 and R8** under every protocol (plan §16.4): the relaxed Hull–White rule with a free delta multiplier, Ruf and Wang's delta–vega–vanna regression, and the LightGBM correction on market features. R7, a regression tree, was specified with them but withdrawn from the submission (plan §15, 2026-11-06).
- **R9–R11** (§16.7). With R8 they form a 2×2 design: a LightGBM correction learned from scratch (R9, R10) or boosted from R2 (R11, R8), on δ alone (R9, R11) or on six features (R10, R8).
- **P0–P8 and PCV** (§16.8): R2's quadratic replaced by a polynomial of degree 0–8, and a degree chosen by validation inside each training window.

The short-dated options extension (§16.6) covers options under 14 days, with each pair ending before settlement. All of this is exploratory: it was specified after the 2020 test had been seen.
"""),
    code(SETUP),
    md("## 2020: the learners under the Table 8.1 variants (Gain over R2)"),
    code("""
lv = pd.read_csv(R / "2020/learners_variants.csv"); r9 = pd.read_csv(R / "2020/r9_r11.csv")
both = pd.concat([lv[lv.base == "R2"], r9[(r9.base == "R2") & r9.rule.isin(["R9", "R10", "R11"])]])
both.pivot_table(index="variant", columns=["rule", "cp"], values="gain").round(3)"""),
    md("""
**Reading.** Both learners that use the six features (R8, R10) collapse for puts in most variants: the March 2020 crash pushed volatility and returns far outside their training range. Both δ-only learners (R9, R11) stay within ±0.02 of R2 everywhere. Since the failure appears with or without R2 underneath, and only with the features, the 2×2 design points to the features, not the boosting.
"""),
    md(r"""
## The walk-forward, 2011–2023: median yearly Gains over 2015–2023

Yearly significance is pointwise, using each year's own 95% interval, without adjustment for multiple comparisons.
"""),
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
    md(r"""
**Reading.** The median yearly Gains relative to R2 are within about 0.004 of zero for the constant, the polynomial degrees, PCV, R5 and the delta-only learners (R9 and R11 within about 0.002). On SPX, R5 nearly matches R2; R9 gains about +0.001 to +0.002; P3–P8 add nothing. With 12-month fits, the constant, every degree and the delta-only learners stay within about 0.015 a year of R2, in every year.

The constant P0 is about as good as R2, and better in 2022–2023 for puts on the long windows (+0.011 to +0.049). That is consistent with a quadratic fitted on 3–5 years of history extrapolating worse when the regime changed, though it is not a test of that.

PCV picks degree 0 more often than any other (in 38–50% of refits, depending on window and type). It is never significantly worse than R2.

With 12-month fits, Ruf and Wang's delta–vega–vanna regression (R6) is slightly worse than R2: median yearly Gains relative to R2 of −0.011 / −0.004 over 2015–2023, never significantly better in 2011–2023, and −0.18 for puts in 2020.

The more flexible learner does worse: R10, which learns from scratch on the market features.
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
    md(r"""
**Reading.** R9 follows R2's shape where the weight lies and flattens toward the constant in the tails.

Where the weight is, R2's own curve is nearly flat too. The loss weights are x² = (ν/S)²(ΔS/S)²/τ, which grow with vega² and peak near the money: options with |δ| above 0.85 carry about 2% of the weight. Over |δ| 0.2–0.7, about three-quarters of the weight, R2's call curve stays within about 0.008 of the constant fit (−0.127).

This is consistent with validation favouring a nearly constant correction. All options on a session share one index move, so each 6-month training window holds about 125 sessions, one index move each, however many options are quoted; validation scores the following month. The limited number of distinct index moves may help explain both the small benefit from δ-shape and why a fit on three options per session loses so little (notebook 10).
"""),
    md("## Short-dated options (under 14 days)"),
    code("""
s = pd.read_csv(R / "short_dated/gains_by_year.csv")
s[s.rule.isin(["R2m", "R2s"])].pivot_table(index="year", columns=["rule", "base", "cp"], values="gain").round(3)"""),
    code("""
b = pd.read_csv(R / "short_dated/buckets.csv")
b.groupby(["cp", "days"])[["G_R2m_R1", "G_R2s_R1", "pairs"]].median().round(3)"""),
    md(r"""
**Reading.** R2's coefficients from options of 14 days or more (R2m) gain a median 0.06 for calls and 0.005 for puts over Black–Scholes (2015–2023). That comes mainly from the 7–13-day options; under three days the median Gain is about zero (+0.003 / −0.016 over 2011–2023). Refitting on short-dated options (R2s) does not help. So the study's 14-day floor, Hull and White's, costs little.

Why the Gain fades near expiry is not tested here. The correction itself does not vanish: ν/(S√τ) = (D·F/S)·φ(d₁), where D is the discount factor, F the forward price and φ the standard normal density. The factor D·F/S is the implied dividend discount factor, close to 1. It is about 0.4 at the money at any maturity. More likely, the parts of the error no delta can hedge, gamma's above all, grow as expiry nears, and the coefficients were fitted on longer-dated options.
"""),
])

NOTEBOOKS["09"] = ("09_stress_stability_and_interpretation", [
    md(r"""
# 09 · Stress periods, parameter stability, the level of the correction, and the published Gains

**In the story** (notebook 00, §§4.2, 4.4, 4.5, 5 and 6): this notebook supports the following parts.

- §4.2: sell-offs gain significantly in 2011, 2015–2016 and February 2018, and September–December 2022 loses significantly (−0.52 for calls, −0.56 for puts).
- §4.4: the level of the correction supplies the Gain, the shape across strikes adds only −0.014 to +0.015 a year, and the level drifts.
- §4.5: our Gains beside Hull and White's published ones.
- §5: why the Gain fell in 2022–2023, and what it would take for the rule to lose.
- §6: the level's drift and the maturity check.

The brief's model-validation direction asks to "stress-test assumptions" and "study parameter stability". This notebook collects the analyses of plan §16.9–§16.10, all descriptive and post hoc:

- stress episodes 2011–2023, defined from the S&P 500 close alone;
- parameter stability at every monthly refit, with session-clustered standard errors;
- the maturity assumption (1/√τ), tested by year;
- the split of the Gain into the correction's level and its shape;
- our Gains under the published aggregations.
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
ax.set_title("Stress episodes: Gain against the fitted level's overstatement"); ax.legend()"""),
    code("""
Y = pd.read_csv(R / "walkforward/stress_by_year.csv")
Y[(Y.window == 12) & (Y.rule == "R2") & (Y.base == "R1")].pivot_table(index="year", columns=["regime", "cp"], values="gain").round(3)"""),
    md(r"""
**Reading.** The minimum-variance delta (R2) gains in every peak-to-trough drawdown (DD), significantly for calls in 2011 and for both types in 2015–2016 and the February 2018 drop.

It loses in rebounds and post-trough volatility, significantly in September–December 2022 (−0.52 for calls, −0.56 for puts). There, implied volatility no longer rose as the index fell, and the fitted level over-corrected. Late 2018 and March 2022 lose too, without significance.

One more significant loss is too thin to interpret: puts in the three-session realized-volatility (RV) episode at the end of September 2020 (RV episodes use annualized trailing 20-session realized volatility above 25%, with high-volatility runs within 10 sessions merged). The episode bootstrap shortens its blocks for short episodes (the `block` column), but three sessions are too few for an interval to mean much. Significance is pointwise, over 17 episodes and two types, with no adjustment for multiplicity.

The scatter is consistent with the level mechanism in one direction. Every losing episode lies to the right of zero, where the best level afterwards was weaker than the fitted level. But many episodes to the right still gain, because a fitted level less than twice too large still helps (the identity below).

By year, 2022's stress sessions lost (−0.17 / −0.16) while its calm sessions gained (+0.13 / +0.05). The stable spot–volatility assumption therefore fails in one direction of stress, not the other.

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
    md(r"""
**Reading.** R2's three coefficients are poorly identified individually: b and c are nearly collinear (|correlation| about 0.9), so they trade off against each other. The level they imply is well identified: the constant correction's (P0's) c has a median standard error of about 0.03.

That level varies over time, from about −0.34 to near zero. Fits 12 months apart, on non-overlapping data, differ by more than two reported standard errors in 19% of call and 10% of put comparisons (`share_abs_z12_gt_2`). These standard errors are clustered by session but omit serial dependence across sessions, so the counts may overstate the instability; the effect is not quantified here. Longer windows are smoother but staler.

The fitted scaling's â runs 0.80–1.005 for calls and 0.97–1.19 for puts; Ruf and Wang's fixed 0.9 and 1.1 sit inside both ranges.
"""),
    md("## The maturity assumption (1/√τ), by year"),
    code("""
M = pd.read_csv(R / "walkforward/maturity_by_year.csv")
M[M.regime == "all"].pivot_table(index="year", columns=["rule", "cp"], values="gain").round(3)"""),
    code("""
M[M.regime == "all"].assign(better=lambda q: q.lo > 0, worse=lambda q: q.hi < 0).groupby("rule").agg(
    better=("better", "sum"), worse=("worse", "sum"), type_years=("gain", "size"), median_gain=("gain", "median")).round(3)"""),
    md(r"""
**Reading.** No alternative exponent consistently beats 1/√τ across years and regimes. The significance counts below are pointwise, without multiplicity adjustment. α = 0.25 is significantly better in 3 of 26 type-years and worse in 4; α = 0.75 and α = 1 are significantly worse in 8 and 11, and every alternative has a negative median Gain against 1/√τ.
"""),
    md("## The level and the shape of the correction"),
    code("""
L = pd.read_csv(R / "walkforward/level_shape_by_year.csv")
L[["year", "cp", "c_fit", "c_post", "G_level_P0_R1", "G_shape_R2_P0", "G_R2_R1", "G_ceiling_P0post_R1", "vol_points_per_1pct_fall"]].round(3)"""),
    md(r"""
**The level.** The constant correction's hedge is δ + c·ν/(S√τ), so it assumes implied volatility responds to the index as ∂σ/∂S = c/(S√τ). A 1% index fall then raises implied volatility by −c/√τ volatility points: a level of −0.13 means 0.13 vol points at one year to expiry, or 0.26 at three months.

**Reading.** In the table, `c_fit` is the fitted level (the trailing 12-month constant, the median over the year's twelve monthly refits) and `c_post` the median over the year's months of the best constant for each month's own pairs, after the fact. `G_level_P0_R1` is the constant's Gain over Black–Scholes, `G_shape_R2_P0` what R2's quadratic shape adds, and `G_ceiling_P0post_R1` the Gain a separate best constant for each month would have given.

The level of R2's correction equals P0's constant exactly. Averaged over the training pairs with the regression's weights, R2's fitted quadratic is c. That follows from the normal equation for the regressor x (defined below), corresponding to the constant term of R2's quadratic. The level supplies the Gain; the shape adds only −0.014 to +0.015 a year on SPX.

A mis-estimated level costs quadratically. Write y for a pair's Black–Scholes error and x = ν·ΔS/(S²√τ) for the regressor. A constant c leaves squared error Σy² − 2cΣxy + c²Σx², minimized at c* = Σxy/Σx². Dividing by Σy² gives the Gain exactly:

G(c) = G* · [1 − ((c − c*)/c*)²], where G* = (Σxy)²/(Σx²·Σy²) is the ceiling.

So a level twice too large gains nothing, and more than that loses to Black–Scholes. In market terms, the rule loses once the spot–volatility relation weakens by more than half between the fitting window and the hedging month. The identity holds for each monthly fit and its own test month, where c is a single number; the yearly columns above combine twelve monthly fits (medians for the levels, summed squared errors for the Gains) and do not satisfy it. The next cell checks it month by month.

In 2023 even the ceiling was small (0.04 for calls, 0.11 for puts, against 0.17–0.41 in 2011–2021): there was little relation left to hedge.
"""),
    code("""
lm = pd.read_csv(R / "walkforward/level_shape_by_month.csv")
G_c, G_star, ratio = 1 - lm.sse_P0 / lm.sse_R1, 1 - lm.sse_P0_post / lm.sse_R1, lm.c_fit / lm.c_post
print(f"{len(lm)} monthly fits; largest deviation from the identity: {(G_c - G_star * (1 - (1 - ratio) ** 2)).abs().max():.1e}")
print(f"months with the fitted level more than 2x the best: {(ratio > 2).sum()}, all of which lost: {((ratio > 2) & (G_c < 0)).sum()}")
print(f"losing months: {(G_c < 0).sum()}; of these, fitted level more than 2x the best or of the wrong sign: {((G_c < 0) & ((ratio > 2) | (ratio < 0))).sum()}")"""),
    md("## Our Gains under the published aggregations"),
    code("""
P = pd.read_csv(R / "walkforward/published_comparison.csv")
P[P.rule == "R2"].pivot_table(index=["window", "period", "sample"], columns="cp", values=["pooled", "mean_of_monthly"]).round(3)"""),
    md(r"""
**Reading.** On the overlapping Hull and White years, our pooled 2013–2015 Gains with 36-month fits are 0.22 / 0.25, while Hull and White report mean monthly Gains of 0.26 / 0.23 over 2007–2015.

Their monthly averaging makes our Gains look lower, not higher: our mean of monthly Gains on 2013–2015 is 0.10 / 0.09. Our data begin in 2010, so their 2007–2009 is not in our data. With 36-month fits, our first test month is 2013-01, so their 2007–2012 test months have no counterpart in this comparison. With 12-month fits, the overlap is 2011–2015. The comparison is therefore of different periods.

Against Ruf and Wang (their period is mid-2012 to mid-2019; our out-of-the-money comparison with 36-month fits covers January 2013 to June 2019), our puts gain 0.20 against their 0.17, and our calls fall short (0.15 against 0.23).

Our lower headline reflects the period (2017, 2018 and 2022–2023 are weak years), the 12-month window (pooled over mid-2012 to mid-2019, about half the 36-month Gain: 0.08 against 0.14–0.17), and in-the-money calls (about half our call sample; notebook 01). The last is the smallest of the three: restricting to out-of-the-money options raises the pooled 2011–2019 Gain only from 0.119 to 0.130 (calls) and 0.112 to 0.132 (puts). These are readings of the table, not a decomposition.

The volume rule is not the main cause: dropping it (`no volume rule`) moves our pooled Gains by 0.01–0.06, in opposite directions for calls and puts.
"""),
])


NOTEBOOKS["10"] = ("10_books_starvation_held_positions", [
    md(r"""
# 10 · Books, data starvation and held positions

**In the story** (notebook 00, §4.5, §5 and §6): this notebook examines books, held positions and reduced training data, including the theta and horizon assumptions.

**Books.** For SPX calls, the median yearly Gain over 2011–2023 is 0.22 on the book against 0.15 per option, about 1.4 times, because about 70% of an option's squared error is shared by all options on the day. Losses grow too, and the control gains little. Only a book's total correction matters, so on books the fixed scaling roughly ties the minimum-variance delta.

**Held positions.** In 2011–2019 the Gain rises from 12–13% one day at a time to 19–20% over 5 days on the same pairs; on the 10-day paths it rises from 12–15% one day at a time to 24–34%. Losses also grow, in 2021–2023. The five-day mean error exceeds Black–Scholes' by about 0.9 basis points of the index level, not significantly.

**Data starvation.** Three options of each type a day cost only about 0.01 in Gain. Windows below three months lose 0.02–0.07 a year, yet a three-month window would have adapted to 2022 (puts −0.058 → +0.047).

Plan §16.11, §16.13 and §16.14 were specified 2026-11-05 and revised 2026-11-06 before any of them ran. All are descriptive and exploratory; only SPX 2020's verdict is confirmatory. The rules are those of the preamble to §16.11: R1 (Black–Scholes), R2 (Hull–White), R3 (Ruf–Wang fixed), R4 (Ruf–Wang fitted), R6 (delta–vega–vanna), R9 (LightGBM on δ) and P0 (a constant correction).

Each is refitted monthly on the trailing 12 months unless stated. The intervals are session-block bootstraps, as everywhere in the project.
"""),
    code(SETUP + """
U = [u for u in ("spx", "spy") if (R / "extensions" / u).exists()]
U"""),
    md(r"""
## 1. Books (§16.14)

The Gain pools each option's squared error as if each were hedged alone. A dealer hedges the net delta of a book, where option-specific errors diversify away and the day's shared move adds up.

Four books are formed each session from day-one information: all calls; all puts; out-of-the-money puts and calls (long volatility); and a risk reversal, long OTM calls and short OTM puts, as the control. A book's error is the mean of its signed option errors, with puts counted negatively in the risk reversal.
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
    m = pd.read_csv(R / "extensions" / u / "books_median_yearly_gain.csv")
    print(u.upper(), "the fixed scaling (R3) and the fitted scaling (R4) over the minimum-variance delta (R2), median yearly Gain")
    display(m[(m.base == "R2") & m.rule.isin(["R3", "R4"])].pivot_table(index="book", columns=["rule", "measure"], values="median_yearly_gain").round(3))"""),
    code("""
for u in U:
    b = pd.read_csv(R / "extensions" / u / "books_by_year.csv")
    x = b[(b.rule == "R2") & (b.base == "R1") & b.year.isin([2020, 2022])]
    print(u.upper(), "R2 over R1 in 2020 and 2022")
    display(x.pivot_table(index=["year", "book"], columns="measure", values=["gain", "lo", "hi"]).round(3))"""),
    md(r"""
**Reading.** For SPX, a dealer hedging a book sees more of the Gain than the per-option numbers suggest; SPY is the same in direction. SPX's median yearly Gain of R2 over Black–Scholes is 0.22 on the call book against 0.15 per option, and 0.17 against 0.12 for puts.

About 70% of an option's squared error survives averaging across a book. That is the day's shared move, which the correction targets; option-specific noise diversifies away. For SPX's call, put and long-volatility books, the common share has a median of about 0.7 and ranges from 0.32 to 0.82 across books and years.

The amplification works both ways. In 2022 the SPX put book lost 0.14, against 0.06 per option (the book's interval, [−0.49, +0.13], includes zero). The risk reversal is the control. Its long and short volatility exposures partly offset. It keeps a median 12% of the Black–Scholes squared error, and R2's median yearly Gain is 0.04.

On a book, the fixed scaling roughly ties the minimum-variance delta. Per option, R3 trails R2 on SPX by a median −0.037 (calls) and −0.056 (puts); on the call and put books it is +0.011 and +0.003. The reason is arithmetic: every option's error on a session is divided by the same index level, so differences between hedge rules on a fixed book depend only on the signed average of their hedge ratios. A rule that gets the total correction about right but spreads it wrongly across strikes loses one option at a time, not on the book. R3 still fails when the level changes: SPX's call book under R3 lost 0.11 in 2022 and 0.33 in 2023.
"""),
    md(r"""
## 2. Data starvation (§16.13)

**Fewer sessions:** 1-, 2-, 3- and 6-month windows.

**Fewer options per session:** 12-month fits on 25%, 5% or 1% of each training session's options, or on 10 or 3 per session and type, with five seeds.

The plan stated the expectation in advance: the information is in the number of sessions, because every option on a day shares that day's index move.
"""),
    code("""
for u in U:
    sp = pd.read_csv(R / "extensions" / u / "starve_seed_spread.csv")
    first = sp.span.iloc[0]
    x = sp[(sp.base == "R1") & sp.rule.isin(["R2", "P0", "R9"]) & (sp.span == first)]
    print(u.upper(), "median yearly Gain over R1,", first, "(median over seeds; min and max for thinning)")
    display(x.pivot_table(index="config", columns=["rule", "cp"], values="median").round(3))
    f = sp[(sp.base == "R2full") & (sp.rule == "R2") & (sp.span == first)]
    print(u.upper(), "R2 on reduced data over R2 on the full 12 months, same pairs (median yearly Gain)")
    display(f.pivot_table(index="config", columns="cp", values="median").round(3))
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
    md(r"""
**Reading.** The plan's expectation holds: the information is in the number of sessions, not options. On SPX, three options per session and type keep a median yearly Gain of 0.138 (calls) and 0.124 (puts), against 0.151 and 0.120 with every option. Over five seeds the range is 0.130–0.140 and 0.120–0.131. Against the full-data fit on the same pairs, that costs only about 0.01 a year (−0.010 / −0.007).

Windows below three months lose 0.02–0.07 a year against the full 12 months (2 months −0.025 / −0.051; 1 month −0.036 / −0.071), cutting the Gain to about 0.09 for calls and 0.03–0.05 for puts.

Short windows adapt faster to a regime change. In 2022 a 3-month window gave +0.071 and +0.047, against +0.002 and −0.058 on 12 months. That is hindsight on one year, without an interval: the same window did worse in 2021 (0.082 / 0.104 against 0.154 / 0.161) and 2023 (−0.024 / −0.060 against +0.002 / −0.014), and in 2020 the 12-month window was best.

No window is best every year. A long window estimates the level precisely but goes stale; a short one tracks it but is noisy. SPY shows the same. R9, a tree learner, loses more than R2 when thinned on SPY and on SPX calls (three options a session: 0.053 against 0.070 for SPY calls, 0.156 against 0.207 for SPY puts, 0.128 against 0.138 for SPX calls). That is consistent with a learner needing more data than three linear coefficients. SPX puts are the exception: there R9 does slightly better than R2 (0.135 against 0.124).
"""),
    md(r"""
## 3. Held positions (§16.11)

A path is H one-session hedges in a row on one contract (H = 5 or 10 sessions), re-hedged at every close with that day's ratio, as a desk would do. For SPX, after the start the contract is followed whatever its delta, maturity or volume, because dropping it when it leaves the band would select on the outcome. SPY's paths are restricted (see the reading below).

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
    md(r"""
**Reading (SPX).** On 2,271,477 path starts (5- and 10-session paths together), the path code's first-day error equals the walk-forward's exactly. Of eligible paths, 94% (5 sessions) and 89% (10 sessions) complete. Of completed paths, 15% and 25% leave the band at least once. They would have been lost had positions been dropped there, and on the in-band-only subset the Gain is smaller.

On real SPX quotes the Gain grows with the holding period. In 2011–2019, R2 removes 0.185 / 0.200 of a 5-session position's squared error and 0.241 / 0.338 of a 10-session one's, against 0.133 / 0.118 one session at a time on the 5-session pairs (0.149 / 0.120 on the 10-session pairs). In 2020, the Gains are 0.256 / 0.277 (5 sessions) and 0.313 / 0.385 (10). Two mechanisms can contribute: intermediate option marks telescope out of a path's sum, though endpoint quote noise remains, and the spot–volatility move can accumulate over a multi-day sell-off.

Losses grow too: 2021–2023 puts −0.108 over 5 sessions, against +0.012 one session at a time. The fixed scaling falls behind on paths. In 2011–2019 it beats R2 one session at a time on these pairs (0.146 / 0.128), but over 5 sessions it gains less (0.155 / 0.148 against 0.185 / 0.200).

For the long-option position that the error represents, the correction leaves the position slightly longer the index: it under-hedges calls and over-hedges puts. R2's five-session mean error exceeds Black–Scholes' by 0.88 bp of the start-day index level for calls [−0.17, +1.83] and 0.96 bp for puts [−0.29, +2.05] in 2011–2019. That is consistent with earning some of the index's upward drift, and it is not significant.

If the mean P&L is taken as unchanged (the five-session mean errors differ by 0.88 and 0.96 bp, not significantly, but with intervals reaching about 2 bp, so equality is not established), and the reduction in squared error approximates the reduction in variance, a Gain g multiplies the hedged position's Sharpe ratio by about 1/√(1 − g): 1.05 at g = 0.10, 1.08 at 0.15 and 1.15 at 0.25.

SPY shows the same growth in 2011–2019. But its Greeks exist only for first-day candidates, so its paths are restricted to traded days with at least 14 days to expiry (§15). Only 53% (5 sessions) and 35% (10 sessions) of eligible SPY starts complete, against 94% and 89% for SPX.
"""),
])


NOTEBOOKS["11"] = ("11_single_stocks_and_etfs", [
    md(r"""
# 11 · Single stocks and ETFs: AAPL, NVDA, TSLA, QQQ and SLV, 2016–2023

**In the story** (notebook 00, §4.5 and §6): among the stocks and ETFs, AAPL gains a little; NVDA, TSLA and SLV gain nothing or lose; and QQQ, a Nasdaq-100 index ETF, behaves like SPX. Two failure modes appear here too: a crash entering the training window, followed by over-correction (the stocks' 2020), and a fixed scaling of delta applied outside the market it was read from (Ruf and Wang's 0.9/1.1 on single stocks).

Plan §16.15 applies the SPY protocol to five more underlyings. It was specified before any of their outcomes was computed. The analysis is exploratory, with no confirmatory verdict. Yearly and episode intervals are pointwise, without multiplicity adjustment.

The data are OptionsDX end-of-day files in the same format as SPX and SPY, with our own implied volatilities and Greeks. The inputs and methods are:

- puts from Lecture 12's American tree;
- calls from European Black–Scholes with the dividend yield;
- rates from SPX's parity curve;
- dividends from Nasdaq's history (TSLA and SLV pay none).

The level is the vendor's snapshot. Pairs straddling a stock split are excluded. The rules are R1 (Black–Scholes), R2 (Hull–White), R3 (Ruf–Wang fixed scaling), R4 (Ruf–Wang fitted scaling), R6 (delta–vega–vanna), R9 (LightGBM on δ) and P0 (a constant correction).

For context, Hull and White's Table 3 (2004–2015, 36-month window) gives an average Gain over the 30 Dow stocks of 10.3% for calls and 2.5% for puts, and 7.7% and 2.5% for three commodity ETFs, one of them SLV.
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
    md(r"""
**Reading.** None of the five passes H1 in 2020 (H1 requires the 95% lower bound of R2's Gain over Black–Scholes to exceed 0 for calls and puts). AAPL, TSLA and QQQ are Inconclusive. NVDA is Reject (b): both upper bounds are below the 0.05 the plan calls material. SLV is Reject (a): its put interval lies below zero, so R2 is significantly worse than Black–Scholes.

Outside the stress period, AAPL's, NVDA's and QQQ's calls lose significantly. That is consistent with SPX's April 2020 failure, the crash entering the training window and the fits over-correcting afterwards. No monthly evidence is shown here, though, and on SPX itself the rest of 2020 gained (calls +0.126).
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
    md(r"""
**Reading.** The single stocks gain little or lose. The medians cover 2017–2023, 2019–2023 and 2021–2023 for the 12-, 36- and 60-month fits, respectively. AAPL's median yearly Gain of R2 is 0.04–0.06 for calls with 12- and 36-month fits (0.023 with 60) and at most 0.02 for puts. NVDA and TSLA are near zero or negative.

QQQ, an index ETF, behaves like SPX: 0.06–0.08 on the 12- and 36-month windows. SLV gains nothing.

Ruf and Wang's fixed 0.9/1.1 scaling (R3), calibrated to S&P 500 options, is harmful off the index: −0.05 to −0.37 for calls on the stocks with 12-month fits (−0.02 to −0.42 across the 12-, 36- and 60-month windows).
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
    md(r"""
**Reading.** Using Hull and White's kind of aggregation gives our stocks far less than their Dow-stock average of 0.103 (calls) and 0.025 (puts). The direction matches theirs: much less than for indices, and almost nothing for puts.

Their explanation fits: noise inserts a wedge between the parameters estimated in one period and those that would hedge best in the next.

QQQ's row needs care. The monthly average can be negative even when the pooled yearly Gains are positive, because single months with large losses weigh as much as calm months.
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
    md(r"""
**Reading.** The spot–volatility relation exists within each period but does not carry forward reliably in these trailing 12-month fits. The level that fits each month best, after the fact, would have removed a median of 11–22% of the three stocks' yearly error (over 2017–2023, by stock and option type; single years run from 4% to 47%): the ceiling column. The level fitted on the previous 12 months gains little: its median yearly Gain is +0.047 / +0.021 for AAPL and negative for NVDA (−0.023 / −0.089) and TSLA (−0.046 / −0.038), calls / puts, though the level column is positive in some years (for example NVDA in 2018).

These trailing 12-month fits recover little of the three stocks' after-the-fact ceiling. For comparison, SPX's trailing level reached at least half of its ceiling in 15 of 26 type-years (2011–2023); it fell short in 2017–2019, 2022–2023 and for 2012's calls.
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
    md(r"""
**Reading.** Books amplify whatever the sign: gains for QQQ (calls 0.162 on the book, against 0.083 per option) and AAPL, losses for NVDA and TSLA.

The risk-reversal book gains 0.22–0.24 for AAPL, TSLA and SLV. That is unlike the indices, where it is the control. One possible reason, not investigated, is that out-of-the-money calls and puts on these underlyings may not share one volatility move.

QQQ's Gain grows with the holding period in 2017–2019 (10 sessions: 0.333 / 0.275, against 0.122 / 0.102 one session), as SPX's does. The stocks are mixed. Most of the five lose on paths in 2020 and 2021–2023.

On every underlying, the path code's first-day errors equal the walk-forward's exactly, and 79–94% of eligible paths complete.
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
