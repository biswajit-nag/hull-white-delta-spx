# Data: sources and processing rules

This file says where the data come from and exactly how the code turns them into the analysis panel. The vendor files are not in the repository; the rules below rebuild everything from them.

## Sources

| Data | Source | Used for |
|---|---|---|
| SPX and SPY end-of-day option chains, 2010–2023 | [OptionsDX](https://www.optionsdx.com/) (free end-of-day files, downloaded October 2026). Field definitions: https://www.optionsdx.com/option-chain-field-definitions/ | Option quotes, the vendor's index snapshot, vendor IV and Greeks |
| S&P 500 official closes, 2016-10 on | FRED series `SP500`: https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500 | Index level, primary source |
| S&P 500 closes, 1975 on | Cboe: https://cdn.cboe.com/api/global/us_indices/daily_prices/SPX_History.csv | Index level before FRED's coverage starts |
| NYSE trading calendar | `pandas-market-calendars`, calendar `XNYS` | Sessions, early closes, next session |
| SPY daily closes, 2016-11 on | Nasdaq historical quotes: https://api.nasdaq.com/api/quote/SPY/historical?assetclass=etf | SPY's index level (`S_close` for SPY) |
| SPY daily closes, dividend-adjusted, 2010 on | Stooq: https://stooq.com/q/d/l/?s=spy.us&i=d (supplied by the author, 2026-11-05) | SPY's index level before 2016-11-03, with the dividend adjustment reversed (below) |
| SPY distributions, 1993 on | State Street (the sponsor), SPDR distributions workbook: https://www.ssga.com/library-content/products/fund-data/etfs/us/spdr-etf-historical-distributions.xlsx (SPY rows) | SPY ex-dates and cash amounts |
| Boot-camp option-pricing library | `option_pricing.py`, version 2026.11.02.1, in Lecture 12 of github.com/TheErdosInstitute/quant-finance (commit b2709e9). Imported from a local clone; set `ERDOS_LECTURE12` to its folder | Implied-volatility solver; Black–Scholes and American pricers |
| AAPL, NVDA, TSLA, QQQ and SLV end-of-day option chains, 2016–2023 | OptionsDX, as above; 75 archives in `data/raw/optionsdx_stocks/`, listed in `results/stocks/data_manifest_stocks.csv` | The five underlyings of `analysis_plan.md` §16.15, whose rules are in that section and the `scripts/*_stocks.py` headers |
| Cash dividends by ex-date | Nasdaq, one file per ticker: `https://api.nasdaq.com/api/quote/<TICKER>/dividends?assetclass=stocks` (`etf` for QQQ and SLV), saved as `nasdaq_<TICKER>_dividends.json` | The five underlyings' dividend yields and day-two dividends; TSLA and SLV pay none |

### The external files: checksums, not copies

The external files are not in the repository, because their providers' terms do not allow redistribution. For example, FRED's `SP500` series carries S&P Dow Jones Indices' notice that "reproduction of S&P 500 in any form is prohibited except with the prior written permission". The author can supply the exact files on request.

**The checksums are tracked.** `results/external_manifest.csv` gives, for each file the study used: its size, SHA-256 checksum, row count, date range, URL and download time. `scripts/check_inputs.py` checks your copies against it, and the OptionsDX archives against the two data manifests (`REPRODUCING.md`, Stage 0). `data/external/SOURCES.csv`, from which the manifest is written, records the download times.

**A later download is a different file.** Where a file differs, `check_inputs.py` says so. The effect on the results has been measured only where stated.

| File | Why a later download differs | What that changes |
|---|---|---|
| `fred_SP500.csv` | FRED serves ten years of daily history. The study's file, downloaded 2026-10-28, starts on 2016-10-28, so later downloads start later | Where FRED has no close, `processed.py` takes Cboe's. Where both closes exist (2016-10 to 2023), Cboe's file matches FRED to the cent on 99.5% of 1,804 dates. One Cboe value is stale (2019-02-28 repeats 2019-02-27), which is why FRED takes precedence |
| `cboe_SPX_History.csv` | It grows by a row each session | Nothing, unless Cboe revises a past close |
| `stooq_spy_us_d.csv` | Its closes are dividend-adjusted, so every later SPY distribution rescales every past close | The reversal (`processed.stooq_unadjusted`, below) works back from the file's last session through every SSGA ex-date. So pair a later Stooq file with an SSGA file at least as recent. Not measured |
| `ssga_SPY_distributions.csv`, `nasdaq_*_dividends.json` | They grow with each new distribution | Nothing for 2010–2023, unless a past entry is revised. AAPL's and NVDA's amounts are as paid, not adjusted for later splits |
| `nasdaq_SPY_history.csv` | The date range is fixed in the request (2009-12-01 to 2024-01-31), but the depth of Nasdaq's history may change | Not measured |

## Reproducing

[`REPRODUCING.md`](REPRODUCING.md) gives every step: what you need, the stages from raw archives to the committed tables, their run times, and what to compare.

## Step 1: raw archives

The archives are kept exactly as downloaded, and `data/raw/optionsdx/SHA256SUMS` holds their checksums. No script writes to this folder, except `scripts/check_inputs.py --write-sums`, which writes `SHA256SUMS` when it is absent and every archive matches the manifest.

## Step 2: interim Parquet (`scripts/build_interim.py`, `src/.../optionsdx.py`)

Each archive is extracted into a fresh temporary folder (Windows' `tar.exe` reads 7z) and every monthly file becomes one Parquet file, under `data/interim/optionsdx/underlying=<u>/year=<y>/`. The conversion is lossless and makes no judgements:

- **Header check:** the header must match the vendor's 33 documented fields, in order.
- **Parsing:** every field is read as text and trimmed, and an empty field becomes null. Empty is kept distinct from zero, and this matters for volume.
- **Types:** Unix times become integers, dates become dates, `QUOTE_READTIME` stays text, and every other field becomes a 64-bit float. Any failed cast stops the run.
- **Size strings:** `C_SIZE` and `P_SIZE` ("bid_size x ask_size") are split into four integer columns after a pattern check.
- **No changes:** no row is dropped, changed or reordered.

A cell-by-cell comparison with a plain CSV read (March 2020, 6,022,137 cells) found no differences. The manifest's integrity checks are clean for all 336 months:
- no row expires before its quote date;
- no duplicate (quote date, expiry, strike) rows;
- one index value per quote date;
- no parse failures;
- no quote date outside its month.

## Step 3: processed long panel (`scripts/build_processed.py`, `src/.../processed.py`)

Output: `data/processed/optionsdx_long/underlying=<u>/year=<y>/`. Per-year counts of every flag and status are in `results/processed_summary_<u>.csv`. Step 3 adds information and removes nothing; exclusions belong to the analysis plan.

### Rows and identifiers

- **One row per contract-day.** Each vendor row (one quote date, expiry stamp and strike, with call and put side by side) becomes two rows, `cp` = `C` and `cp` = `P`.
- **Row identifier:** (`quote_date`, `expire_date`, `strike`, `cp`). It is unique and traces each row back to one vendor line.
- **Contract identifier (the contract key):** (`am_settled`, `settle_date`, `strike`, `cp`). It is used to follow one contract from day to day (below).

### Columns

| Group | Columns |
|---|---|
| Vendor, unchanged | `quote_date`, `quote_unixtime`, `expire_date` (the vendor's stamp), `expire_unix`, `vendor_dte`, `strike`, `S` (the vendor's index snapshot, `UNDERLYING_LAST`), `bid`, `ask`, `bid_size`, `ask_size`, `last`, `volume`, `vendor_iv`, `vendor_delta`, `vendor_gamma`, `vendor_vega`, `vendor_theta`, `vendor_rho` |
| Derived prices | `mid` = (bid + ask)/2; `spread` = ask − bid; `rel_spread` = spread/mid (null when mid = 0) |
| Index close | `S_close`: FRED close on the quote date, else Cboe's; `S_close_source` says which |
| Calendar | `is_session`, `early_close`, `next_session` (the next NYSE session after the quote date), `vendor_has_next_session` |
| Contract identity | `am_settled`, `settle_date`, `settle_ts` |
| Next session | `bid_next`, `ask_next`, `mid_next`, `volume_next`, `S_next`, `S_close_next`, `next_status` |
| Flags | the `f_*` columns below |

The vendor fields `QUOTE_READTIME` and `QUOTE_TIME_HOURS` (always 16:00) and `STRIKE_DISTANCE` and `STRIKE_DISTANCE_PCT` (derivable) stay in the interim layer only.

### Settlement and the contract key

SPX has two kinds of contract with the same strikes and similar expiries:
- **The A.M.-settled monthly:** it stops trading the day before expiry and settles on a value computed from the next morning's opening prices.
- **The P.M.-settled weeklies and dailies:** they trade until 16:00 on expiry and settle on the close.

The vendor gives no column to tell them apart, and its `EXPIRE_DATE` stamp for the monthly changes convention over time. The rules, inferred from prices (A.M. contracts carry less time value the evening before, and their expiry-day prices track an opening value, not the close):

- **A.M. monthlies.** An SPX row is `am_settled` if its stamp equals the monthly's **settlement day**: the third Friday of the stamp's month, or the session before it when that Friday is a holiday (Good Friday in 2014, 2019 and 2022). It is also `am_settled` if the stamp equals the monthly's **last trading day** (the session before the settlement day) and the quote date is before 2016-09-01.
  - **Why the date matters:** until August 2016 the vendor stamps the monthly on its last trading day. From September 2016 it uses the settlement day, and a last-trading-day stamp then belongs to a genuine P.M. contract: a Wednesday weekly (2019-04-17, before the Good Friday monthly) or, from May 2022, a Thursday daily.
- **Everything else is P.M.** SPY is always P.M.: its options settle by delivering shares at the close.
- **Settlement date and time.** `settle_date` is the settlement day for A.M. contracts and the stamp itself for P.M. contracts. `settle_ts` is 09:30 New York time on the settlement day for A.M. contracts, and the session close (16:00, or 13:00 on early-close days) for P.M. contracts.
- **The contract key** (`am_settled`, `settle_date`, `strike`, `cp`) treats a contract the vendor re-stamped mid-life as one contract. This happened to the December 2016 and December 2017 monthlies on 2015-01-22 (352 rows flagged `f_restamped`).
- **The April 2019 window is not repaired.** On quote dates 2019-04-04 to 04-16, the Thursday-stamped copies of monthlies get their own P.M. keys; they differ in price and volume from the Friday-stamped copies, and the files can't say which series is which. Every pair touching the window carries `f_stamp_window`. Under these rules no contract key is duplicated on any date in 2010–2023.

### Flags (booleans; no row is removed)

| Flag | True when |
|---|---|
| `f_non_session` | The quote date is not an NYSE session. The vendor has 12 such SPX dates (Hurricane Sandy, 2018-12-05, and nine 2022 holidays); each holds the previous session's official close and quotes unlike that session's 16:00 row |
| `f_one_sided` | The bid or ask is missing, or the bid is 0 |
| `f_crossed` | ask < bid |
| `f_dup_key` | The contract key appears more than once on the quote date (a safety check; it never fires for SPX 2010–2023) |
| `f_stamp_window` | The quote date **or the next session** is in 2019-04-04 to 2019-04-16 (SPX), so the pair touches the window. On these dates the vendor stamps most expiries a day early and lists four monthlies twice, with different quotes |
| `f_restamped` | The row's stamp differs from the stamp the same contract had on its previous quote date |
| `f_post_settlement` | An A.M. contract quoted on or after its settlement day, so its settlement value is already fixed |
| `f_stamp_not_session` | The settlement date is not an NYSE session: shifted stamps on Sundays in the 2019 window, a weekly stamped on the 2018-12-05 market closure, and stray stamps on 2010-11-25 and 2014-12-25 |
| `f_settle_uncertain` | A 2010 SPX weekly stamped on Thursday. These still hold time value at the stamp, so their true settlement is later, and unknown |

### Next-session join

Each contract-day is joined to the **same contract key** on `next_session`, the next NYSE session from the exchange calendar, not the vendor's next file date. `next_status` records the outcome. The first matching rule applies:

| Status | Meaning |
|---|---|
| `non_session_row` | The row itself is on a non-session date; it is not paired |
| `expired` | The contract settles before the next session's snapshot |
| `ambiguous_key` | The key is duplicated today or on the next session, so the match is not unique |
| `vendor_missing_session` | The next NYSE session is absent from the vendor's files |
| `contract_absent` | The session is present, but this contract isn't |
| `one_sided_next` | The contract is present but lacks a two-sided quote (bid > 0, ask ≥ bid) |
| `ok` | A usable next-session quote |

The `*_next` values are blanked for `non_session_row`, `expired` and `ambiguous_key`. Because the next session comes from the calendar, a day missing from the vendor's files never turns into a two-day hedge: it shows up as `vendor_missing_session`.

### Volume coding (found 2026-11-04)

Through 2021 the vendor never records a volume above 999, and an empty `volume` covers two different things:
- **heavily traded days:** in 2019–2020, every contract that goes from 900–999 contracts to an empty volume has a positive `last` on the empty day;
- **untraded contracts,** whose `last` is 0. The vendor codes "no last price" as 0, not as empty.

From 2022 the vendor records volumes of 1,000 or more. The step-3 panel keeps `volume` and `last` unchanged. The analysis treats empty volume with a positive `last` as traded (`analysis_plan.md` §5, E7).

## Step 4: forwards, implied volatilities and Greeks (`scripts/build_greeks.py`, `src/.../parity.py`, `src/.../blackscholes.py`)

Per session and expiry, `data/processed/greeks/underlying=spx/year=YYYY/` holds the parity forward and discount factor and, per contract-day, the mid's implied volatility, the solver's status, and the Greeks. `sessions_YYYY.parquet` holds each session's zero-rate curve and the options-implied index level of sensitivity A. The rules are `analysis_plan.md` §2 and §4.

## Step 5: hedge pairs (`scripts/build_pairs.py`, `src/.../pairs.py`)

`data/processed/pairs/underlying=spx/year=YYYY/` holds, per contract-day passing E1–E6 and E8, the joined day-two quote, implied volatility, forward and discount factor, and both days' index levels, plus E7, its strict reading and `next_status` (`analysis_plan.md` §5). No hedging error is stored.

## Applying the rules to SPY

`scripts/build_processed.py --underlying spy` runs the same code, with `S_close` from SPY's close instead of the index's.
- **From 2016-11-03:** Nasdaq's close.
- **Before 2016-11-03:** Stooq's close, which is dividend-adjusted, with the adjustment reversed (`processed.stooq_unadjusted`). Going back from the last session with a factor f = 1, at each SSGA ex-date e the factor for earlier sessions becomes f/(1 + f·Div_e/C̃_{e−1}), where C̃ is Stooq's adjusted close. The close is C̃/f.
- **The check against Nasdaq,** 2016-11-03 to 2024-01-31 (1,821 sessions): the level differs by a median 0.43 bp (maximum 2.3 bp; bias −0.4 bp, growing further back), and one-session returns by a median 0.14 bp (99th percentile 1.7 bp). The vendor's snapshot differs from Nasdaq by 1.05 bp in level and 1.46 bp in return (99th percentile 11.8 bp, maximum 68 bp). Only 28% of sessions match to the cent, so Stooq's closes are not exact.
- `S_close_source` records which series each session uses (`analysis_plan.md` §16.3). For SPY, `am_settled` is always false, and no stamp window is defined. SPY's step 4 is `scripts/build_greeks_spy.py` (American put IVs from the Lecture 12 tree; `analysis_plan.md` §16.1), and its pairs, `scripts/build_pairs_spy.py`, add each pair's day-two distribution. SPY's light audit (`results/audit_light_spy.csv`, 2010–2023) runs before any SPY outcome. What American exercise and dividends require is handled in the analysis, not in this panel.
