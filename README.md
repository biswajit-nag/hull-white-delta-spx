# Does Hull and White's minimum-variance delta hedge SPX options better? A pre-registered model validation, 2011–2023

**Verdict:** Inconclusive on the pre-registered 2020 test; usually helpful, but unstable, across 2011–2023; and no better than much simpler rules.

A dealer hedges each option by holding delta units of the index. The Black–Scholes delta treats volatility as fixed, although implied volatility, the volatility consistent with an option's price, tends to rise when the index falls. Hull and White's (2017) minimum-variance delta adds the expected volatility response to an index move, fitted by monthly regressions on past prices. This project tests it on SPX options. It is compared with three simpler rules: Ruf and Wang's fixed scaling of delta (0.9 times delta for calls, 1.1 times for puts), a fitted scaling a·δ, and a single fitted constant correction in place of Hull and White's three coefficients. The Gain of a hedge rule is the fraction of the Black–Scholes delta's squared hedging error that it removes, on identical option pairs.

- **The confirmatory test.** The pre-registered SPX 2020 test is inconclusive. The minimum-variance delta removed 18.5% of the Black–Scholes delta's squared one-day hedging error for calls and 12.0% for puts, on 1.06 million SPX option pairs. But the March 2020 crash leaves 95% intervals spanning about −0.4 to +0.46, so neither an improvement nor a loss is established. The verdict rule was committed before any test-year number was computed. All 11 pre-specified robustness variants preserve the verdict, though wide intervals limit what that agreement establishes.
- **Across years.** Repeated out of sample over 2011–2023, with monthly fits on the preceding 12 months, the correction usually helps. Its median yearly Gain over 2015–2023 is 0.12 for calls and 0.10 for puts, and in no year is it significantly worse than Black–Scholes. Its advantage disappears in 2022–2023, as implied volatility became less responsive to index moves.
- **Simpler rules.** One fitted constant correction gives essentially the same Gain as the three-coefficient form. Machine-learning corrections add no material improvement, and two fail badly in the crash. Ruf and Wang's (2022) fixed 0.9/1.1 scaling, an unfitted rule of thumb read off their results, matches the minimum-variance delta's median Gain but fails in 2022–2023.

![Yearly Gain of the minimum-variance delta over the Black–Scholes delta, SPX, 2011–2023](results/figures/summary_yearly_gain.png)

*Yearly Gain of the minimum-variance delta over the Black–Scholes delta, SPX, 2011–2023, calls and puts, with 12-, 36- and 60-month fits and 95% session-block bootstrap intervals. Grey: the clean held-out years (2011–2013, 2021–2023). Orange: the pre-registered test year, 2020.*

| Hedge rule | Coefficients fitted | SPX 2020, calls | SPX 2020, puts | Median yearly Gain 2015–2023, calls / puts (12-month fits) |
|---|---|---|---|---|
| Fixed 0.9/1.1 scaling (Ruf and Wang's rule of thumb) | 0 | 0.181 [−0.13, 0.34] | 0.021 [−0.30, 0.23] | 0.125 / 0.099 |
| Fitted scaling a·δ | 1 | 0.151 [−0.32, 0.36] | −0.076 [−0.52, 0.22] | 0.120 / 0.060 |
| Constant correction | 1 | 0.190 [−0.32, 0.46] | 0.120 [−0.44, 0.46] | 0.119 / 0.105 |
| Minimum-variance delta (Hull and White) | 3 | 0.185 [−0.36, 0.46] | 0.120 [−0.45, 0.46] | 0.124 / 0.100 |

*Gains over the Black–Scholes delta, with 95% session-block bootstrap intervals. The constant correction's 2020 values come from the walk-forward, which uses the same 12-month fits as the 2020 test.*

## Read the study

The executive summary is [`EXECUTIVE_SUMMARY.md`](EXECUTIVE_SUMMARY.md). The study itself is told in Jupyter notebooks, committed with their outputs. Start with [`00_the_story`](notebooks/00_the_story.ipynb): it follows the executive summary section by section, with more detail. Notebook 00 recomputes the principal results from the committed tables in `results/`, and points to the detail notebooks or sources for the other numbers. Notebooks 01–11 hold the detail, and each opens by saying which part of the story it supports.

| Notebook | What it shows | Story section |
|---|---|---|
| [00 The story](notebooks/00_the_story.ipynb) | The whole argument, with the principal results computed in place | All |
| [01 Audit and attrition](notebooks/01_audit_and_attrition.ipynb) | Which option-days enter, the vendor's volume coding, attrition, the sample's composition | 2 |
| [02 Forwards, implied volatilities, Greeks](notebooks/02_forwards_iv_greeks.ipynb) | Forwards and discount factors from put–call parity, implied volatilities, the options-implied index level; the test suite | 2, 3, 6 |
| [03 The rehearsal](notebooks/03_rehearsal_2019.ipynb) | The rehearsal on 2018–2019 and the dry run on 2019, before 2020 was opened; the model's form; why intervals resample sessions | 3, 4.4, 6 |
| [04 The 2020 test](notebooks/04_results_2020.ipynb) | The verdict, its concentration in March 2020, the month-by-month path, the coefficients after the crash | 4.1, 6 |
| [05 Breakdown and sensitivities](notebooks/05_breakdown_and_sensitivities.ipynb) | Every robustness variant, where the error comes from, the theta check, the boosted learner's failure | 4.1, 4.3, 5, 6 |
| [06 The walk-forward](notebooks/06_walkforward_2011_2023.ipynb) | The yearly Gains over 2011–2023, against Black–Scholes and the scaling rules; the spot–volatility slope | 4.2, 4.3, 5, 6 |
| [07 SPY](notebooks/07_spy_replication.ipynb) | A full replication on SPY's American options | 4.2, 6 |
| [08 More rules, short-dated options](notebooks/08_more_rules_and_short_dated.ipynb) | Polynomial degrees 0–8, a validated degree, the LightGBM corrections decomposed; options under 14 days | 4.3, 4.4, 4.5, 6 |
| [09 Stress, stability, interpretation](notebooks/09_stress_stability_and_interpretation.ipynb) | Stress episodes, parameter stability, the maturity scaling, the level and shape of the correction, the published Gains | 4.2, 4.4, 4.5, 5, 6 |
| [10 Books, starvation, held positions](notebooks/10_books_starvation_held_positions.ipynb) | Hedging a book, holding a position 5 or 10 days, fitting on less data | 4.5, 5, 6 |
| [11 Stocks and ETFs](notebooks/11_single_stocks_and_etfs.ipynb) | AAPL, NVDA, TSLA, QQQ and SLV under the same protocol | 4.5, 6 |

The story sections are those of the executive summary and notebook 00: 2 data, 3 methodology, 4.1–4.5 findings, 5 financial interpretation, 6 assumptions, limitations and failure modes.

## In brief

**Data.** OptionsDX end-of-day quotes for SPX and SPY, 2010–2023, and for AAPL, NVDA, TSLA, QQQ and SLV, 2016–2023. A pair is one contract at consecutive NYSE closes: 1.06 million pairs in SPX 2020, and about 7.6 million over 2011–2023. The sample requires at least 14 days to expiry and an absolute delta of 0.05–0.95 (Hull and White's filters), and trading on day one (Ruf and Wang's). The audit found several vendor problems, each handled by a documented rule (`DATA.md`, notebook 01).

**Method.** For a hedge ratio h, the error is e = (Δf − h·ΔS)/S, where Δf is the option's mid-price change, ΔS the index's change and S the day-one index level; the Gain compares sums of squared errors on identical pairs. Monthly fits use trailing 12-month windows, with 36- and 60-month alternatives. Each fit hedges only the following month, and training pairs must end before the test month starts. The full specification is [`analysis_plan.md`](analysis_plan.md). It was reviewed jointly by two AI models, Claude and GPT-6 Astra, and committed (77b030e) before any hedging outcome was computed. Every later change is logged and dated in its §15. Before 2020 was opened, a rehearsal on 2018–2019 and a dry run of the test script on 2019 checked the code and the model's form. The walk-forward repeats the protocol over 2011–2023. Its untouched years, 2011–2013 and 2021–2023, are the clean held-out evidence. Intervals come from a circular block bootstrap of sessions, because every option on a day shares that day's index move; yearly significance is pointwise and not adjusted for multiple comparisons. The exploratory analyses are all descriptive, and most were specified after 2020 had been seen.

**Limitations.** There is one confirmatory year, and it contains a crash. The other analyses are exploratory, and clean years are few. The study uses one data vendor, whose quote timing is undocumented, and excludes transaction and financing costs. The intervals omit the training window's estimation error, and a crash strains the bootstrap's assumptions.

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

`results/runtime_log.csv` records every run, with its commit and wall time. `results/year_ledger.csv` records which years' outcomes were seen, and when. Both keep their rows for the regression tree, the Heston deltas and the coverage simulation, which ran but were withdrawn from the submission (`analysis_plan.md` §15); they are records, not results.

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
