# Executive summary

**Hull and White's minimum-variance delta on SPX options, 2020: a pre-registered model validation**

## The problem

An options dealer hedges its book with the underlying index, using each option's *delta*.

**The Black–Scholes delta** assumes volatility does not move with the index. In equity markets it does: when the index falls, implied volatility tends to rise.

**The minimum-variance (MV) delta** of Hull and White (2017) builds that co-movement into the hedge ratio. It uses three coefficients fitted monthly on historical data, and reported 23–26% lower squared hedging error over 2007–2015.

**The simpler alternative.** Ruf and Wang (2022) found most of that improvement came from simply scaling the Black–Scholes delta (0.9·δ for calls, 1.1·δ for puts).

**The validation question.** Out of sample, on a stress year, does the MV delta reduce one-day squared hedging error relative to Black–Scholes? And does it beat the simpler scaling rules?

## Methodology

- **Data.** OptionsDX end-of-day SPX option quotes. The test is 2020: 1.06 million option-days, each hedged from one close to the next.
- **Pre-registration.** The plan fixed the samples, rules, endpoints, thresholds and verdict table before any 2020 hedging number was computed. It was reviewed jointly by two AI models and committed to git, and every later change is logged with its date.
- **Fitting.** Forwards and discount factors come from put–call parity, so no rate or dividend assumption is needed. Each 2020 month is hedged with coefficients fitted on the 12 months before it.
- **Inference.** Intervals come from a block bootstrap over trading sessions, not over options. Options on the same day share one index move, so naive standard errors here are 4.5–34 times too small.
- **Before the test year:** a rehearsal on 2018–2019, 38 automated checks, and an independent code review for look-ahead.

## Principal findings

1. **Inconclusive.** The MV delta reduced squared hedging error by 18.5% (calls) and 12.0% (puts). The 95% intervals, [−0.36, 0.46] and [−0.45, 0.46], include both a 40% improvement and a substantial loss. The verdict is unchanged under every robustness variant: the index level, the training window, the price marks, the spread screen, the vanished quotes, and leaving out the crash.
2. **The year is decided by a few days.** The February–April stress period holds 80–86% of the year's squared error, and ten sessions hold 65–73%.
3. **The advantage was unstable.** Monthly Gains ranged from about +0.4 to −0.8, and their average was about zero. After the crash entered the training window in April, the coefficients over-corrected. In several months even a fit to that month's own data found almost nothing to exploit.
4. **The simpler rules are not beaten.** Against the fixed and fitted scaling rules the MV delta is not distinguished, overall or on out-of-the-money options. Outside the crash it beat the fitted scaling rule for calls by 5%, with an interval of [3%, 8%].
5. **Perspective.** The Black–Scholes delta alone removed 92–95% of the unhedged variance. The MV correction works on the remainder, worth about $100 per contract in RMS error.
6. **Across years, the advantage is not stable.** A walk-forward over 2011–2023 finds positive Gains in every year through 2021, mostly 0.10–0.25, including the clean held-out year 2021 (calls 0.15 [0.02, 0.26]). It vanishes in 2022–2023: about 0 with a 12-month window, and negative (−0.16 to −0.23) with 36- and 60-month windows in 2022. That coincides with the near-the-money spot–volatility slope falling from 0.25–0.55 to 0.13 vol points per 1% index fall.
7. **Extensions.** SPY (American options, dividends) shows the same picture as SPX in 2020. A gradient-boosted challenger tuned on calm 2019 failed in March 2020, when its inputs left their training range: a concrete model-risk lesson.

## Important limitations

- The hedge is frictionless, at closing prices, with the index as the instrument; no costs.
- There is one confirmatory test year, containing a crash. The walk-forward is exploratory, and only 2011–2013 and 2021–2023 were untouched before it.
- One vendor. Quote timing is undocumented, and the volume field needed a correction: through 2021 the vendor leaves days with 1,000 or more contracts blank.
- The model assumes a diffusion with a stable spot–volatility relation; 2020 and 2022–2023 violated the second.

**Recommendation for the stated use** (a daily delta rule for SPX index options): the evidence does not support replacing the Black–Scholes delta with Hull and White's MV delta on the strength of 2020. The walk-forward shows its historical advantage gone since 2022. Where any correction is wanted, a one-parameter scaling rule was not distinguished from it, needs one coefficient instead of three, and is easier to monitor. Equivalence was not established either. A rule fitted to recent data should be monitored, since 2020 showed its advantage can reverse within a month.
