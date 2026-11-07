# Does Hull and White's minimum-variance delta hedge SPX options better? A pre-registered model validation, 2011–2023

**Verdict: Inconclusive on the pre-registered 2020 test; usually helpful, but unstable, across 2011–2023; and no better than much simpler rules.**

- **The pre-registered SPX 2020 test is inconclusive.** Hull and White's (2017) minimum-variance delta removed 18.5% of the Black–Scholes delta's squared one-day hedging error for calls and 12.0% for puts, on 1.06 million SPX option pairs. But the March 2020 crash leaves 95% intervals spanning about −0.4 to +0.46, so neither an improvement nor a loss is established. The verdict rule was committed before any test-year number was computed, and all 11 pre-specified robustness variants preserve the verdict.
- **Repeated out of sample over 2011–2023,** with monthly fits on the preceding 12 months, the correction usually helps. Its median yearly Gain over 2015–2023 is 0.12 for calls and 0.10 for puts, and in no year is it significantly worse than Black–Scholes. Its advantage disappears in 2022–2023, as implied volatility became less responsive to index moves.
- **Simpler rules do almost as well.** One fitted constant correction gives essentially the same Gain as the three-coefficient form. Machine-learning corrections add no material improvement, and two fail badly in the crash. Ruf and Wang's (2022) fixed 0.9/1.1 scaling, an unfitted rule of thumb read off their results, matches the minimum-variance delta's median Gain but fails in 2022–2023.

![Yearly Gain of the minimum-variance delta over the Black–Scholes delta, SPX, 2011–2023](results/figures/summary_yearly_gain.png)

*Yearly Gain of the minimum-variance delta over the Black–Scholes delta, SPX, 2011–2023, calls and puts, with 12-, 36- and 60-month fits and 95% session-block bootstrap intervals. Grey: the clean held-out years (2011–2013, 2021–2023). Orange: the pre-registered test year, 2020.*

The **Gain** of a hedge rule is the fraction of the Black–Scholes delta's squared hedging error that it removes, on identical option pairs. The one-page account is [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md).

## Read the study in the notebooks

The study is told in Jupyter notebooks, committed with their outputs. **Start with [`00_the_story`](notebooks/00_the_story.ipynb):** it follows the executive summary section by section, with more detail, and computes every number it quotes from the tables in `results/`. Notebooks 01–11 hold the detail, and each opens by saying which part of the story it supports.

| Notebook | What it shows | Story section |
|---|---|---|
| [00 The story](notebooks/00_the_story.ipynb) | The whole argument, with every headline number computed in place | All |
| [01 Audit and attrition](notebooks/01_audit_and_attrition.ipynb) | Which option-days enter, the vendor's volume coding, attrition, the sample's composition | 2. Data |
| [02 Forwards, implied volatilities, Greeks](notebooks/02_forwards_iv_greeks.ipynb) | Forwards and discount factors from put–call parity, implied volatilities, the options-implied index level; the test suite | 2–3 |
| [03 The rehearsal](notebooks/03_rehearsal_2019.ipynb) | The rehearsal on 2018–2019 and the dry run on 2019, before 2020 was opened; the model's form; why intervals resample sessions | 3, 4.4 |
| [04 The 2020 test](notebooks/04_results_2020.ipynb) | The verdict, its concentration in March 2020, the month-by-month path, the coefficients after the crash | 4.1 |
| [05 Breakdown and sensitivities](notebooks/05_breakdown_and_sensitivities.ipynb) | Every robustness variant, where the error comes from, the theta check, the boosted learner's failure | 4.1, 4.3, 5 |
| [06 The walk-forward](notebooks/06_walkforward_2011_2023.ipynb) | The yearly Gains over 2011–2023, against Black–Scholes and the scaling rules; the spot–volatility slope | 4.2, 4.3 |
| [07 SPY](notebooks/07_spy_replication.ipynb) | A full replication on SPY's American options | 4.2 |
| [08 More rules, short-dated options](notebooks/08_more_rules_and_short_dated.ipynb) | Polynomial degrees 0–8, a validated degree, the LightGBM corrections decomposed; options under 14 days | 4.3, 4.5 |
| [09 Stress, stability, interpretation](notebooks/09_stress_stability_and_interpretation.ipynb) | Stress episodes, parameter stability, the maturity scaling, the level and shape of the correction, the published Gains | 4.2, 4.4, 4.5, 5 |
| [10 Books, starvation, held positions](notebooks/10_books_starvation_held_positions.ipynb) | Hedging a book, holding a position 5 or 10 days, fitting on less data | 4.5, 5 |
| [11 Stocks and ETFs](notebooks/11_single_stocks_and_etfs.ipynb) | AAPL, NVDA, TSLA, QQQ and SLV under the same protocol | 4.5, 6 |

## 1. The problem

A dealer hedges each option by holding delta units of the index. The Black–Scholes delta treats volatility as fixed, although implied volatility, the volatility consistent with an option's price, tends to rise when the index falls. Hull and White's minimum-variance delta adds the expected volatility response to an index move (their equation 2):

δ_MV ≈ δ_BS + ν_BS · ∂E[σ_imp]/∂S,

where ν_BS is the option's vega, its price sensitivity to volatility. They fit the response by monthly regressions on past prices (their equation 5):

δ_MV = δ_BS + ν_BS/(S√T) · (a + b·δ_BS + c·δ_BS²).

The 1/S factor makes volatility respond to index *returns*, the 1/√T factor is their empirical maturity scaling, and the quadratic lets the correction vary across strikes.

**The rules compared,** with the codes the tables and notebooks use:

| Rule | Code | Hedge ratio | Coefficients fitted |
|---|---|---|---|
| Black–Scholes delta (the benchmark) | R1 | δ | 0 |
| Fixed 0.9/1.1 scaling (Ruf and Wang's rule of thumb) | R3 | 0.9·δ for calls, 1.1·δ for puts | 0 |
| Fitted scaling | R4 | a·δ | 1 |
| Minimum-variance delta (Hull and White) | R2 | as above | 3 |
| *Exploratory:* constant correction | P0 | δ + c·ν/(S√T) | 1 |
| *Exploratory:* polynomials in δ of degree 0–8; a degree chosen by validation | P0–P8, PCV | δ + ν/(S√T)·p_k(δ) | k + 1 |
| *Exploratory:* relaxed Hull–White, with a free delta multiplier | R5 | a₀·δ + ν/(S√T)·(a + bδ + cδ²) | 4 |
| *Exploratory:* Ruf and Wang's delta–vega–vanna regression | R6 | a·δ + b·ν/S + c·vanna | 3 |
| *Exploratory:* LightGBM corrections on delta alone, or on market features | R9, R11; R10, R8 | δ + ν/(S√T)·h(·) | tuned |

R7, a regression tree, was specified but withdrawn from the submission (`analysis_plan.md` §15).

**Why it matters.** The question matters to dealers who hedge daily, and to the teams that validate their models. Black–Scholes leaves the volatility response unhedged. Hull and White read the evidence as favouring volatility feedback (higher volatility raises required returns and lowers prices) over leverage as its cause. This project is a model validation in the sense of the instructor's brief: where does the model work, where does it fail, and is it better than a simpler alternative?

## 2. Data

- **Option quotes:** OptionsDX end-of-day files for SPX and SPY, 2010–2023, and for AAPL, NVDA, TSLA, QQQ and SLV, 2016–2023.
- **Underlying levels:** FRED's official S&P 500 close (Cboe before 2016-10); Nasdaq's SPY close (Stooq before 2016-11, with its dividend adjustment reversed); the vendor's snapshot for the five stocks and ETFs. **Dividends:** SSGA for SPY; Nasdaq for AAPL, NVDA and QQQ. **Rates and the S&P 500's dividend yield** are not assumed: each expiry's forward and discount factor come from put–call parity on the quotes.
- **A pair** is one contract at consecutive NYSE closes: 1.06 million pairs in SPX 2020, and about 7.6 million over 2011–2023. The sample requires at least 14 days to expiry and an absolute delta of 0.05–0.95 (Hull and White's filters), and trading on day one (Ruf and Wang's). In 2020, 98.7% of eligible pairs have a usable next-session quote; results are conditional on it.
- **The audit found several vendor problems,** each handled by a documented rule (`DATA.md`, notebook 01):
  - **a volume field that leaves days with 1,000 or more contracts blank through 2021.** Rows with empty volume and a positive last price are the heavily traded ones; a naive "volume > 0" filter drops the busiest contracts;
  - option quotes synchronous with neither the official close nor the vendor's index snapshot (median gap 3.3 bp), handled with two sensitivities;
  - an April 2019 window of shifted expiry stamps, excluded;
  - 35 missing sessions, so pairs are formed across NYSE sessions, not the vendor's dates.

## 3. Method

The full specification is [`analysis_plan.md`](analysis_plan.md). It was reviewed jointly by two AI models, Claude and GPT-6 Astra, and committed (77b030e) before any hedging outcome was computed; every later change is logged, dated, in its §15.

- **The error and the Gain.** For a hedge ratio h, the error is e = (Δf − h·ΔS)/S, where Δf is the option's mid-price change and ΔS the index's. The Gain is 1 − SSE(rule)/SSE(Black–Scholes) on identical pairs. A Gain of 0.10 means 10% less squared error, or about 5% lower root-mean-square error.
- **Chronological fitting.** Monthly fits use trailing 12-month windows, with 36- and 60-month alternatives. Each fit hedges only the following month, and training pairs must end before the test month starts.
- **Inputs.** Implied volatilities come from the boot camp's Lecture 12 solver, and the Greeks are Black–Scholes at each option's own implied volatility.
- **Before 2020 was opened,** a rehearsal on 2018–2019 and a dry run of the test script on 2019 checked the code and the model's form (notebook 03). The verdict table and its thresholds ("material" means a Gain of at least 0.05) were fixed in advance.
- **The walk-forward** repeats the protocol over 2011–2023. Its untouched years, 2011–2013 and 2021–2023, are the clean held-out evidence (`results/year_ledger.csv`).
- **Inference by session, not by option.** Every option on a day shares that day's index move, so naive standard errors are far too small: 4.5–34 times, for the rehearsal's coefficients (notebook 03). Intervals come from a circular block bootstrap of sessions (blocks of 10, 10,000 draws). Yearly and episode significance is pointwise and not adjusted for multiple comparisons.
- **The exploratory analyses** are all descriptive, and most were specified after 2020 had been seen: the additional rules, the SPY replication, parameter stability, the polynomial degree and the maturity scaling, the correction's level and shape, the published benchmarks, books, 5- and 10-day held positions, reduced training data, short-dated options, and five stocks and ETFs. Stress episodes are defined from the S&P 500 close alone: 20-day realized volatility above 25%, or a peak-to-trough drawdown of at least 10%.

## 4. Findings

### 4.1 The confirmatory test (notebooks 04, 05)

Neither option type's 95% lower bound is above zero, so the verdict is **Inconclusive**, and the minimum-variance delta is not distinguished from either scaling rule.

| Hedge rule | Coefficients fitted | SPX 2020, calls | SPX 2020, puts | Median yearly Gain 2015–2023, calls / puts (12-month fits) |
|---|---|---|---|---|
| Fixed 0.9/1.1 scaling (Ruf and Wang's rule of thumb) | 0 | 0.181 [−0.13, 0.34] | 0.021 [−0.30, 0.23] | 0.125 / 0.099 |
| Fitted scaling a·δ | 1 | 0.151 [−0.32, 0.36] | −0.076 [−0.52, 0.22] | 0.120 / 0.060 |
| Constant correction | 1 | 0.190 [−0.32, 0.46] | 0.120 [−0.44, 0.46] | 0.119 / 0.105 |
| Minimum-variance delta (Hull and White) | 3 | 0.185 [−0.36, 0.46] | 0.120 [−0.45, 0.46] | 0.124 / 0.100 |

*Gains over the Black–Scholes delta, with 95% session-block bootstrap intervals. The constant correction's 2020 values come from the walk-forward, which uses the same 12-month fits as the 2020 test.*

- **Robustness.** All 11 pre-specified variants give Inconclusive: the options' own index level, the vendor's level, bid and ask marks, a frozen 2019 fit, 36- and 60-month windows, a spread screen, the rest of 2020 without the crash, and two scenarios for vanished quotes. With intervals this wide the verdict is hard to move; the point Gains move more (calls 0.10–0.18, puts −0.03 to 0.22).
- **Perspective.** The Black–Scholes delta alone removes 92–95% of the unhedged squared error. The minimum-variance delta lowers the calls' RMS error per contract from $825 to $727.
- **Concentration.** The stress period, 24 February to 30 April, contains 80–86% of the year's squared error, and ten sessions contain 65–73%. Given these interval widths, only a Gain above roughly 0.5 could have cleared zero: about twice what Hull and White report.
- **Month by month** the Gain swings from about +0.4 to −0.8, and averages about zero. April's fit was the first to contain March 2020, and in April the relation it expected had all but vanished; May and June, with the same crash in their windows, gained.

![Cumulative squared hedging error through 2020](results/figures/cumulative_sse_2020.png)

*Cumulative squared hedging error through 2020, as a share of the Black–Scholes delta's full-year total. Most of each year's error arrives in the shaded stress period.*

### 4.2 Years and stress episodes (notebooks 06, 09, 07)

- **Yearly Gains are mostly 0.10–0.25 through 2021, and about zero in 2022–2023.** With 12-month fits, the Gain is significantly positive in 7 of 26 call-or-put years and significantly negative in none. 2021, a year nobody had looked at, gains significantly for both types (0.15 and 0.16).
- **Longer windows gain more in a typical year and lose more when the market changes:** a median of about 0.16 with 36- or 60-month fits, but −0.16 to −0.23 in 2022.
- **Sell-offs gain** significantly in 2011, 2015–2016 and February 2018. **September–December 2022 loses significantly:** −0.52 for calls and −0.56 for puts.
- **SPY replicates the picture:** 2020 is inconclusive, and puts typically gain 16–28% a year through 2021.

### 4.3 Complex against simple rules (notebooks 06, 08)

- **Year by year,** the minimum-variance delta beats the fixed scaling significantly in 14 of 26 call-or-put years, and loses in two, both in 2018. The fitted scaling is significantly worse in 12 of 26, and never significantly better.
- **For SPX with 12-month fits, the constant correction, every polynomial degree and the delta-only LightGBM correction all stay within about 0.015 a year of the minimum-variance delta.** Ruf and Wang's delta–vega–vanna regression is slightly worse: median Gains of −0.011 / −0.004 relative to it, and −0.18 for 2020 puts.
- **The LightGBM corrections that use market features fail.** In 2020 their squared error for puts was 9–11 times Black–Scholes', after the crash took their features outside the training range. The delta-only versions did not fail, so the 2×2 design points to the features, not the boosting.

### 4.4 The level and the assumption checks (notebooks 09, 08, 03)

- **The level** replaces the quadratic with one constant: the hedge's assumed sensitivity of implied volatility to the index. A level of −0.13 means a 1% index fall raises implied volatility by 0.13 volatility points at one year to expiry, or 0.26 at three months. The fitted quadratic, averaged over the training options with the regression's weights, equals this constant exactly.
- **The level supplies the Gain;** variation across strikes adds only −0.014 to +0.015 a year. The individual coefficients are poorly identified, but the level is well identified.
- **A mis-estimated level costs quadratically.** For each monthly fit of a constant correction c, the month's Gain is exactly G*·[1 − ((c − c*)/c*)²], where c* is the best level for that month and G* its Gain. So in any month where the fitted level is more than twice the rewarded one, the correction loses to Black–Scholes; all 56 such monthly fits of the constant correction in 2011–2023 (counting calls and puts separately) lost. (Yearly averages of the monthly fits do not satisfy the identity.)
- **The level varies over time.** Fits 12 months apart differ by more than two reported standard errors in 19% of call and 10% of put comparisons. These standard errors omit serial dependence across sessions, so the counts somewhat overstate the instability.
- **The form holds.** With 12-month fits, degrees 0–8 give essentially the same Gain. Maturity powers T^(−α) for α = 0, 0.25, 0.75, 1 never consistently beat 1/√T.

### 4.5 Extensions and published benchmarks (notebooks 10, 11, 08, 09)

- **Books.** Scoring each day's average error across all calls, all puts, or long-volatility positions, the median yearly Gain for SPX calls over 2011–2023 is 0.22 on the book against 0.15 per option, about 1.4 times. Losses grow too, and the control, a risk reversal, gains little. Only a book's total correction matters, so on books the fixed scaling roughly ties the minimum-variance delta.
- **Held positions.** Accumulating the error over 5 or 10 days, rehedging daily, the Gain in 2011–2019 rises from 12–13% for one day to 19–20% over 5 days and 24–34% over 10 days. Losses also grow, in 2021–2023.
- **Data starvation.** Three options of each type a day cost only about 0.01 in Gain. Windows below three months lose 0.02–0.07 a year. Yet a three-month window would have adapted to 2022: puts go from −0.058 to +0.047 (in hindsight: the same window did worse in 2021 and 2023).
- **Stocks and ETFs.** AAPL gains a little; NVDA, TSLA and SLV gain nothing or lose; and QQQ behaves like SPX.
- **Short-dated options.** Options under 14 days gain 0.06 / 0.005 for calls / puts, and about zero under three days.
- **Published benchmarks.** Our pooled 2013–2015 Gains with 36-month fits are 0.22 / 0.25, while Hull and White report mean monthly Gains of 0.26 / 0.23 over 2007–2015. Our lower headline reflects the period, the 12-month window and in-the-money calls, the last of these the least (notebook 09).

## 5. Financial interpretation

- **The correction hedges the expected volatility response.** About 70% of an option's squared error is shared by all options on the day and survives averaging across a book, which explains the larger book Gain. The size of the response matters more than its shape across strikes.
- **The response and the advantage fell together.** For near-the-money options 20–60 days from expiry, the measured response fell from 0.55 volatility points per 1% index fall in 2021 to 0.13 in 2022–2023, and the Gain fell with it. That is consistent with fits that had learned a stronger relation than the market then delivered. It is a descriptive reading: across all years the response and the Gain correlate only loosely (2018, for one, had a strong response and small Gains).
- **Drift.** For one-day hedges we follow Hull and White's specification, with no intercept and no theta adjustment; subtracting one day's theta changes the 2020 Gains by at most 0.011. The correction leaves a long-option position slightly longer the index, and its five-day mean error exceeds Black–Scholes' by about 0.9 basis points in 2011–2019, not significantly.
- **What a Gain is worth.** If the mean P&L is unchanged, a Gain g multiplies the hedged position's Sharpe ratio by about 1/√(1 − g): 1.08 at g = 0.15.
- **Where it works:** index options; sell-offs; years in which the spot–volatility slope stays close to the preceding year's; books and held positions. **Where it fails:** after a crash enters the training window (April 2020); in rebounds and post-crash periods (late 2018, late 2022); when the slope weakens (2022–2023); on single stocks and silver; near expiry.

## 6. Assumptions, limitations and failure modes

| Assumption | Check | Result | Notebook |
|---|---|---|---|
| Volatility response is quadratic in delta | Degrees 0–8, a validated degree, LightGBM on delta | Not contradicted; shape barely matters | 03, 08 |
| Response scales as 1/√T | T^(−α), α ∈ {0, 0.25, 0.75, 1}, by year | Not beaten consistently | 03, 09 |
| Coefficients remain stable between windows | Coefficient paths; fits 12 months apart | Fails: the level drifts, badly in 2022 | 04, 09 |
| No intercept or theta term is needed | Theta-adjusted 2020 variant; held-position mean error | 2020 Gains change by at most 0.011; five-day mean-error difference about +0.9 bp in 2011–2019, not significant | 05, 10 |
| One day is the relevant horizon | 5- and 10-day held positions | Gain grows over longer horizons | 10 |
| Mid quotes are synchronous with the index | Two index-level sensitivities; bid and ask marks | Verdict unchanged | 02, 04, 05 |
| Frictionless index hedging | Turnover only | Not tested with costs; the minimum-variance delta's hedge ratio changes 3% less a day than Black–Scholes' (2020) | 05 |

- **What this does not establish.** There is one confirmatory year, and it contains a crash. The other analyses are exploratory, and clean years are few. The study uses one data vendor, whose quote timing is undocumented, and excludes transaction and financing costs. The intervals omit the training window's estimation error, and a crash strains the bootstrap's assumptions.
- **Sample restrictions.** SPY's held-position test follows a contract only through days on which it traded with at least 14 days to expiry, and the five stocks and ETFs use the vendor's underlying levels.
- **The observed failure modes:**
  - a crash entering the training window, followed by over-correction: April 2020, and the stocks' 2020;
  - the LightGBM corrections with market features extrapolating outside their training range in March 2020;
  - a fixed scaling of delta applied outside the market and period it was read from. Ruf and Wang's 0.9/1.1 comes from S&P 500 options from 2010 to mid-2019. It fails on SPY calls and single stocks, and on SPX itself in 2022–2023, as the volatility response weakened.

## Reproducing

[`REPRODUCING.md`](REPRODUCING.md) gives every step. The full test suite and the rebuild need the boot camp's lecture repository at commit b2709e9, with `ERDOS_LECTURE12` set to its `Fall 2026/Lecture 12` folder.

- **Without the vendor data.** These commands install the locked environment, run the tests, and re-execute every notebook, 00–11, from the committed tables in `results/`:
  ```
  uv sync --locked
  uv run pytest
  uv run python -I scripts/make_notebooks.py
  ```
  The notebooks are generated from the cell definitions in [`scripts/make_notebooks.py`](scripts/make_notebooks.py), so their narrative and the code that reads `results/` are versioned together. They also open in VS Code or Jupyter on the project's `.venv` kernel.
- **From the raw data.** The rebuild needs the OptionsDX archives and the external files, which are not redistributed here. With them, the pipeline rebuilds every table in `results/`. The 2020 test takes under an hour, and everything about 18 hours. `scripts/check_inputs.py` checks your inputs against the checksums of the files the study used.

**The record.** `results/runtime_log.csv` records every run, with its commit and wall time. `results/year_ledger.csv` records which years' outcomes were seen, and when. Both keep their rows for the regression tree, the Heston deltas and the coverage simulation, which ran but were withdrawn from the submission (`analysis_plan.md` §15); they are records, not results.

## Repository

| Path | Contents |
|---|---|
| `notebooks/` | The study: 00 the story, then 01–11 (table above), committed with outputs |
| `EXECUTIVE_SUMMARY.md` | The executive summary |
| `analysis_plan.md` | The pre-registered plan, its status, its deviation log (§15) and the extension specifications (§16) |
| `DATA.md` | Data sources and every processing rule |
| `REPRODUCING.md` | How to reproduce the results, with and without the vendor data |
| `src/erdos_quant_finance_project/` | The package: parsing, parity, Black–Scholes, pairs, hedging, diagnostics, learners, verdict |
| `scripts/` | Pipeline steps, experiments, figures and the notebook builder, each with usage in its header |
| `tests/` | pytest checks: Greeks against finite differences and the lecture library, parity recovery, known coefficients, no look-ahead, the bootstrap, the verdict table |
| `results/` | Derived tables and figures; per-pair files are regenerable and not committed |

## References

- Hull, J. and White, A. (2017). Optimal delta hedging for options. *Journal of Banking & Finance* 82, 180–190.
- Ruf, J. and Wang, W. (2022). Hedging with linear regressions and neural networks. *Journal of Business & Economic Statistics* 40(4), 1442–1454.
- OptionsDX. End-of-day option chains (data).
- Erdős Institute Quantitative Finance Boot Camp, Fall 2026. Lecture 12 option-pricing library.

**Use of AI tools.** This is an individual project. Claude (Anthropic) assisted with code, analysis and drafting. GPT-6 Astra (OpenAI) reviewed key steps and helped in wording the reports. The author directed the work and takes the responsibility for its correctness.
