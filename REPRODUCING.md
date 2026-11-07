# Reproducing the results

There are two levels:

- **Without the vendor data** (anyone, a few minutes). Install the locked environment, run the tests, and re-execute every notebook from the committed tables in `results/`: the story in `00_the_story` and the detail in 01–11.
- **From the raw data.** This needs the OptionsDX files. Rebuild the tables in `results/` from the vendor archives, then compare them with the committed ones. The SPX test of 2020, the confirmatory result, takes under an hour; everything takes about 18 hours.

Run every command from the repository root. Each script's header gives its usage and its outputs. Times come from `results/runtime_log.csv`, on the author's machine (Windows 11, 6 cores), with one command at a time.

**Memory.** The heaviest analysis steps (`stress_episodes.py`, `level_shape.py`, `parameter_stability.py`, `compare_published.py`, `run_walkforward_r5_r8.py` and the held-position paths of `run_extensions.py`) peak at 6.5–7.5 GB. On a 16 GB machine, run them one at a time. In the test run of 2026-11-07, running other stages alongside stretched `stress_episodes.py` from 3 minutes to 7.5 hours. The implied-volatility builds and the Heston calibration need under 2 GB per process and can run alongside.

## What you need

- **uv** (https://docs.astral.sh/uv/). It installs Python 3.14.10 (pinned in `.python-version`) and the locked dependencies (`uv.lock`).
- **The boot camp's lecture repository at commit b2709e9**, for `option_pricing.py` version 2026.11.02.1: its implied-volatility solver and American pricers. It has no licence file, so it is imported from a clone rather than copied here:
  ```
  git clone https://github.com/TheErdosInstitute/quant-finance.git
  git -C quant-finance checkout b2709e9
  ```
  Point `ERDOS_LECTURE12` at the clone's `Fall 2026/Lecture 12` folder:
  - bash: `export ERDOS_LECTURE12="$PWD/quant-finance/Fall 2026/Lecture 12"`
  - PowerShell: `$env:ERDOS_LECTURE12 = "$PWD\quant-finance\Fall 2026\Lecture 12"`

  The code checks the library's version when it loads it. Without the clone, the tests that need it are skipped and the pipeline stops at its first IV solve.
- **For the rebuild only:**
  - **The OptionsDX end-of-day archives**, unrenamed. The 42 SPX and SPY archives go in `data/raw/optionsdx/` (1.2 GB). The 75 archives for AAPL, NVDA, TSLA, QQQ and SLV go in `data/raw/optionsdx_stocks/` (0.6 GB). `results/data_manifest.csv` and `results/stocks/data_manifest_stocks.csv` list every archive with its SHA-256 checksum. The vendor's terms do not allow redistribution, so the archives are not in this repository.
  - **The external files**, in `data/external/`: the S&P 500 closes, SPY's closes and distributions, and the dividend histories. `DATA.md` lists their URLs and says what a later download changes, and `results/external_manifest.csv` gives the checksum of each file the study used. Their providers' terms do not allow redistribution either.
  - **About 25 GB of free disk** for `data/interim/` and `data/processed/`.

## Level 1: without the vendor data

```
git clone https://github.com/biswajit-nag/hull-white-delta-spx.git
cd hull-white-delta-spx
uv sync --locked
uv run pytest
uv run python -I scripts/make_notebooks.py
git status --short
```

**What to expect:**
- **Tests:** all 44 pass with the lecture clone; without it, 38 pass and 6 are skipped.
- **Notebooks:** `make_notebooks.py` builds the 12 notebooks, 00–11, from the cell definitions in `scripts/make_notebooks.py` and executes them against `results/`. `00_the_story` recomputes the principal results from the committed tables, and points to the detail notebooks or sources for the other numbers. The fresh-clone test on the author's machine (2026-11-06) covered commit 3cfc09c, when the builder made only notebooks 01–11, before notebook 00 existed. In that test, every printed number came out the same and every figure was byte-identical. On another platform, font rendering may change the figures' bytes, but not what they show.
- **Two figures.** Notebooks 00 and 04 show `results/figures/cumulative_sse_2020.png`, and 06 shows `walkforward_by_year.png`, as images rather than drawing them in code. `scripts/make_figures.py` draws them in Stage 7; the cumulative figure needs the per-pair errors of Stage 2, which are not committed. Every other figure is drawn in the notebook from the committed tables.
- **`git status`:** shows the notebooks as modified. That comes from matplotlib's object addresses (`<matplotlib.legend.Legend at 0x…>`), pytest's elapsed time in notebook 02, and how the kernel splits printed output into chunks, not from any result.

## Level 2: from the raw data

The stages run in order, because each stage reads what the earlier ones wrote. You can stop after any stage and compare only its outputs (see "Comparing" below). In PowerShell, write `Copy-Item` for `cp`.

### Stage 0: check the inputs (seconds)

```
uv run python -I scripts/check_inputs.py --write-sums
```

This checks each archive against the manifests and each external file against `results/external_manifest.csv`. A folder that is absent is skipped. `build_interim.py` needs a `SHA256SUMS` file beside the archives, and `--write-sums` writes one from the manifest, once every archive in that folder matches.

### Stage 1: the SPX data (10–15 minutes)

```
uv run python -I scripts/build_interim.py
uv run python -I scripts/build_processed.py --underlying spx --years 2010-2023
uv run python -I scripts/build_greeks.py 2010 2023
uv run python -I scripts/build_pairs.py 2010 2023
uv run python -I scripts/build_pairs.py 2010 2023 --short
uv run python -I scripts/attrition.py
uv run python -I scripts/audit_light.py 2010 2014
cp results/audit_light.csv results/audit_light_2010_2014.csv
uv run python -I scripts/audit_light.py 2020 2023
cp results/audit_light.csv results/audit_light_2020_2023.csv
uv run python -I scripts/audit_light.py 2015 2019
cp results/audit_light.csv results/audit_light_2015_2019.csv
```

- **`build_interim.py`** converts every archive in `data/raw/optionsdx/`, SPX and SPY. It writes `data/interim/` and `results/data_manifest.csv`.
- **`audit_light.py`** always writes `results/audit_light.csv`, so each period is copied to its own file. The 2015–2019 audit runs last, because it is the one `audit_light.csv` keeps.
- **Outputs:**
  - `results/processed_summary_spx.csv`
  - `results/attrition/`
  - `results/audit_light*.csv`
  - the per-pair Parquet files in `data/processed/`

### Stage 2: the 2020 test, the confirmatory result (20–30 minutes)

```
uv run python -I scripts/run_rehearsal.py
uv run python -I scripts/tune_r8.py 2019
uv run python -I scripts/run_test_year.py 2019 dry-run results/dryrun_2019
uv run python -I scripts/run_test_year.py 2020 77b030e
uv run python -I scripts/extra_diagnostics.py
uv run python -I scripts/run_learners_variants.py 2020
```

- **The second argument of `run_test_year.py`** is a label for the run log. For 2020 it is the commit of the pre-registered plan (77b030e). For the dry run on 2019, which tested the script before 2020 was opened, it is `dry-run`.
- **Outputs:**
  - `results/rehearsal/`
  - `results/dryrun_2019/`
  - `results/2020/`, with the verdict in `results/2020/verdict.csv`

### Stage 3: SPX's other rules, the 2010–2023 walk-forward and its readings (about 2.5 hours)

```
uv run python -I scripts/tune_r8.py 2015 2016
uv run python -I scripts/tune_r8.py 2010
uv run python -I scripts/tune_r8.py --rule R9 2019
uv run python -I scripts/tune_r8.py --rule R9 2015 2016
uv run python -I scripts/tune_r8.py --rule R9 2010
uv run python -I scripts/tune_r8.py --rule R10 2019
uv run python -I scripts/tune_r8.py --rule R10 2015 2016
uv run python -I scripts/tune_r8.py --rule R10 2010
uv run python -I scripts/tune_r8.py --rule R11 2019
uv run python -I scripts/tune_r8.py --rule R11 2015 2016
uv run python -I scripts/tune_r8.py --rule R11 2010
uv run python -I scripts/run_walkforward.py
uv run python -I scripts/run_walkforward_r8.py
uv run python -I scripts/run_walkforward_r5_r8.py
uv run python -I scripts/run_r9_r11.py year 2020
uv run python -I scripts/run_r9_r11.py walkforward
uv run python -I scripts/run_degrees.py
uv run python -I scripts/run_short_dated.py
uv run python -I scripts/spot_vol_slope.py
uv run python -I scripts/level_shape.py
uv run python -I scripts/compare_published.py
uv run python -I scripts/parameter_stability.py
uv run python -I scripts/stress_episodes.py
uv run python -I scripts/correction_curves.py
```

- **Outputs:**
  - `results/walkforward/`
  - `results/short_dated/`
  - `results/2020/r9_r11.csv`
  - the remaining files in `results/rehearsal/`
- **The longest steps:** the tuning and R9–R11. The 2010–2023 walk-forward itself (`run_walkforward.py`, the source of the README's yearly figure) takes 6 minutes.

### Stage 4: SPY (about 3.5 hours, two of them for the American-option implied volatilities)

SPY's rates and yields come from SPX's parity curves, so Stage 1 must have run.

```
uv run python -I scripts/build_processed.py --underlying spy --years 2010-2023
uv run python -I scripts/build_greeks_spy.py 2010 2023
uv run python -I scripts/build_pairs_spy.py 2010 2023
uv run python -I scripts/audit_light.py 2010 2023 spy
uv run python -I scripts/run_spy.py
uv run python -I scripts/run_rehearsal.py --spy
uv run python -I scripts/tune_r8.py --spy 2019
uv run python -I scripts/tune_r8.py --spy 2015 2016
uv run python -I scripts/tune_r8.py --spy 2010
uv run python -I scripts/tune_r8.py --spy --rule R9 2019
uv run python -I scripts/tune_r8.py --spy --rule R9 2015 2016
uv run python -I scripts/tune_r8.py --spy --rule R9 2010
uv run python -I scripts/tune_r8.py --spy --rule R10 2019
uv run python -I scripts/tune_r8.py --spy --rule R10 2015 2016
uv run python -I scripts/tune_r8.py --spy --rule R10 2010
uv run python -I scripts/tune_r8.py --spy --rule R11 2019
uv run python -I scripts/tune_r8.py --spy --rule R11 2015 2016
uv run python -I scripts/tune_r8.py --spy --rule R11 2010
uv run python -I scripts/run_test_year.py 2019 3431a8d results/spy/dryrun_2019 --spy
uv run python -I scripts/run_test_year.py 2020 3431a8d --spy
uv run python -I scripts/run_learners_variants.py 2020 --spy
uv run python -I scripts/run_r9_r11.py year 2020 --spy
uv run python -I scripts/run_walkforward.py --spy
uv run python -I scripts/run_walkforward_r5_r8.py --spy
uv run python -I scripts/run_r9_r11.py walkforward --spy
uv run python -I scripts/run_degrees.py --spy
uv run python -I scripts/spy_exdate_by_year.py
uv run python -I scripts/level_shape.py --spy
uv run python -I scripts/parameter_stability.py --spy
uv run python -I scripts/stress_episodes.py --spy
```

- **Plan commit:** 3431a8d is the commit recorded in the run log for SPY's runs under the plan's §16.3.
- **Outputs:** `results/spy/` and `results/audit_light_spy.csv`.

### Stage 5: the five underlyings (about 6 hours, most of it for the American-option implied volatilities)

```
uv run python -I scripts/build_interim.py --raw data/raw/optionsdx_stocks --manifest results/stocks/data_manifest_stocks.csv
```

Then, for each `u` in `aapl nvda tsla qqq slv`:

```
uv run python -I scripts/build_processed.py --underlying u --years 2016-2023
uv run python -I scripts/build_greeks_stocks.py u 2016 2023
uv run python -I scripts/build_pairs_stocks.py u 2016 2023
```

and then:

```
uv run python -I scripts/audit_stocks.py aapl nvda tsla qqq slv
```

and, for each `u`:

```
uv run python -I scripts/run_protocol_stocks.py u
```

**Outputs:** `results/stocks/`.

### Stage 6: books, data starvation and held positions (about 5 hours)

On SPX, every rule in these experiments is scored on the pairs that have Heston Greeks, so that all rules share one sample (`analysis_plan.md` §15, 2026-11-06). Heston's results were withdrawn from the submission, but its calibration still defines that sample, so it runs first. It takes about 100 minutes on 6 processes, and its outputs (`results/heston2/`, `data/processed/heston2/`) are not committed.

```
uv run python -I scripts/heston2_calibrate.py 2010 2023 6
uv run python -I scripts/heston2_hedge.py 6
uv run python -I scripts/build_pairs_any.py 2010 2023
uv run python -I scripts/build_pairs_any.py 2010 2023 --spy
```

Then, for each `u` in `aapl nvda tsla qqq slv`:

```
uv run python -I scripts/build_pairs_any.py 2016 2023 --underlying u
```

and, for each `u` in `spx spy aapl nvda tsla qqq slv`:

```
uv run python -I scripts/run_extensions.py books --underlying u
uv run python -I scripts/run_extensions.py starve --underlying u
uv run python -I scripts/run_extensions.py paths --underlying u
```

**Outputs:** `results/extensions/`.

### Stage 7: finish and compare

```
uv run python -I scripts/drop_withdrawn.py
uv run python -I scripts/make_figures.py
uv run python -I scripts/make_notebooks.py
git status --short
git diff --stat
```

- **`drop_withdrawn.py`** is needed because the regression tree R7 and every Heston rule were withdrawn from the submission on 2026-11-06 (`analysis_plan.md` §15). Their code stays, so the scripts above write their rows again, and this script removes them as was done for the committed tables. Applied to the tables as they stood before the withdrawal, it reproduces the committed tables byte for byte.
- **`make_figures.py`** reads `results/2020/` and `results/walkforward/`, so it needs Stages 2 and 3.

## Comparing

After the rebuild, `git status --short results/` lists the tracked tables that changed. Any change outside the list below is a failure to reproduce, and `git diff` on that file shows where.

These differences are expected:
- **`results/runtime_log.csv`** gains a row for every run.
- **The `.log` files** record local paths and warnings.
- **The tuning logs** (`results/**/r*_trials_*.csv`) differ in Optuna's `datetime_start`, `datetime_complete` and `duration` columns. Each trial's parameters and value are the same.
- **Notebooks** differ in matplotlib's object addresses, pytest's elapsed time and the chunking of printed output, after Level 1 or Stage 7.
- **External files downloaded later** can change the tables that use them. `check_inputs.py` reports which files differ, and `DATA.md` says what each difference changes. For example, FRED serves ten years of S&P 500 closes, so a later download falls back to Cboe's closes for the earliest dates.
- **Partial runs.** A tracked table that a stage you didn't run would have written stays as committed.

`results/year_ledger.csv` and `results/spy/year_ledger_spy.csv` are records of which years' outcomes were seen and when. They are not outputs.

## Record of the reproduction tests

**2026-11-06, commit 3cfc09c, Windows 11.** The commit was cloned fresh from GitHub and run by an independent session that had only this repository, the input files and the lecture library.

- **Level 1:** passed. The install and all 44 tests succeeded, and the 11 notebooks executed.
- **Level 2, Stages 0–2,** plus Stage 3's `run_walkforward.py` and `spot_vol_slope.py`, then `drop_withdrawn.py` and `make_figures.py`: every command exited 0. Every table in `results/2020/`, `results/dryrun_2019/`, `results/rehearsal/`, `results/walkforward/`, `results/attrition/` and the audits came out byte-identical to the committed one, as did the PNG figures.
- **The only differences:**
  - the run log;
  - the Optuna timestamps in `r8_trials_2019_*.csv`;
  - six bytes of `summary_yearly_gain.pdf`, its creation date. Since then, `make_figures.py` writes the PDF without a creation date, so it reproduces exactly.
- **Run times:** Stage 1 took 10.5 minutes and Stage 2 20 minutes.

**2026-11-07, the same clone, Stages 3–6.** The rest of the pipeline ran in that clone, with the 75 archives of the five underlyings added. About 120 commands ran, every one as written above, and every one exited 0. After `drop_withdrawn.py`, every table for SPY's replication, the five underlyings, SPY's and the five underlyings' extensions, the stress episodes, parameter stability, level and shape, the polynomial degrees, the short-dated options and the published comparison came out byte-identical to the committed one.

Twenty-two tables did not. The rebuild was right and the committed tables were stale:
- **SPX pairs for 2010–2013 and 2022–2023.** These pair files had been built on 2026-11-04 by code from before the first commit, which computed the R8 features `rv20` and `ret5` on a shorter close history. The rebuilt pairs differ from them only in those two columns. The features enter R8 and R10, and through the feature-complete sample, the R8–R11 comparisons. That affected:
  - the 2010 tuning of R8–R11;
  - the R8–R11 rows of the walk-forward tables (`r5_r8_*`, `r8_by_year`, `r9_r11_*`);
  - R9's rows in SPX's books, starvation and held-position tables, because R9 uses its 2010 tuning until 2016-12;
  - `rehearsal/learners_2010.csv`.
- **SPY's first exploratory run** (`run_spy.py`: `results/spy/gains.csv`, `coefficients_*.csv`, `monthly_*.csv`). It ran on 2026-11-04, before SPY's closes and Greeks were revised on 2026-11-05, and had not been rerun.

The committed tables were replaced by the rebuilt ones (`analysis_plan.md` §15, 2026-11-07). Rerunning the R8 tuning on 2010 and `run_spy.py` on the author's machine, after its 2010–2013 and 2022–2023 pairs were rebuilt, reproduced the clone's tables byte for byte. Every other result is unchanged: the 2020 verdict, the walk-forward of R2 against R1, R3 and R4, and every rule other than R8–R11 in every table. The run took 16.5 hours, because steps ran in parallel and competed for memory (see "Memory" above).
