# Reproducing the results

There are two levels:

- **Without the vendor data** (anyone, a few minutes). Install the locked environment, run the tests, and re-execute every notebook, the story in `00_the_story` and the detail in 01–11, from the committed tables in `results/`.
- **From the raw data.** This needs the OptionsDX files. Rebuild the tables in `results/` from the vendor archives, then compare them with the committed ones. The SPX test of 2020, the confirmatory result, takes under an hour; everything takes about 18 hours.

Run every command from the repository root. Each script's header gives its usage and its outputs. Times come from `results/runtime_log.csv`, on the author's machine (Windows 11, 6 cores; peak memory about 5 GB).

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
- **Notebooks:** `make_notebooks.py` builds the 12 notebooks, 00–11, from the cell definitions in `scripts/make_notebooks.py` and executes them against `results/`. `00_the_story` recomputes every number in the executive summary from those tables, so running it checks the summary. In a fresh clone on the author's machine (2026-11-06), every printed number came out the same and every figure byte-identical. On another platform, font rendering may change the figures' bytes, but not what they show.
- **Two figures are images, not code.** Notebooks 00 and 04 show `results/figures/cumulative_sse_2020.png` (and 06 shows `walkforward_by_year.png`), which `scripts/make_figures.py` draws in Stage 7; the cumulative figure needs the per-pair errors of Stage 2, which are not committed. Every other figure is drawn in the notebook from the committed tables.
- **`git status`:** shows the notebooks as modified. That comes from matplotlib's object addresses (`<matplotlib.legend.Legend at 0x…>`), not from any result.

## Level 2: from the raw data

The stages run in order, because each stage reads what the earlier ones wrote. You can stop after any stage and compare only its outputs (see "Comparing" below). In PowerShell, write `Copy-Item` for `cp`.

### Stage 0: check the inputs (seconds)

```
uv run python -I scripts/check_inputs.py --write-sums
```

This checks each archive against the manifests and each external file against `results/external_manifest.csv`. A folder that is absent is skipped. `build_interim.py` needs a `SHA256SUMS` file beside the archives, and `--write-sums` writes one from the manifest, once every archive in that folder matches.

### Stage 1: the SPX data (about 15 minutes)

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

### Stage 2: the 2020 test, the confirmatory result (about 30 minutes)

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
- **Notebooks** differ in matplotlib's object addresses.
- **External files downloaded later** can change the tables that use them. `check_inputs.py` reports which files differ, and `DATA.md` says what each difference changes. For example, FRED serves ten years of S&P 500 closes, so a later download falls back to Cboe's closes for the earliest dates.
- **Partial runs.** A tracked table that a stage you didn't run would have written stays as committed.

`results/year_ledger.csv` and `results/spy/year_ledger_spy.csv` are records of which years' outcomes were seen and when. They are not outputs.
