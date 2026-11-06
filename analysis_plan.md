# Analysis plan

*Version 1.0, 2026-11-04. Binding from its commit: it governs the endpoints and procedures, and every later change is logged, dated, in §15. Items marked **[confirmed]** are the author's decisions of 2026-11-04.*

**Draft history.** v0.1 (2026-11-02) was the first draft. v0.2 (2026-11-04) added the author's confirmations and the items below. v1.0 (2026-11-04) is v0.2 after a joint review by two models, Claude and GPT-6 Astra, which tightened definitions and corrected formulas and claims without changing any [confirmed] decision. All of it was decided before any hedging outcome was computed. v0.2's additions:
- mark sensitivities: bid, ask, the imbalance-weighted mid and Lecture 12's size-weighted price (§3);
- the spread screen S3 reported beside the primary and added to the robustness of the verdict (§3, §8);
- a 36-month training window, sensitivity W36 (§7);
- a theta sensitivity T (§2, §8);
- a Taylor attribution of the Black–Scholes hedging error (§8);
- exploratory challengers R7 (a regression tree) and R8 (gradient boosting, tuned with Optuna on 2019) (§6, §7);
- the specification checks made mandatory, with decision criteria fixed in advance (§10);
- at-the-money options in both halves of the out-of-the-money subsample (§8);
- the boot camp's final option-pricing library (Lecture 12) as the reference implementation (§4, §11);
- a rule that every item in §§1–13 is run, and any incomplete at submission is reported as pending (§12);
- a revision of E7, after the finding that the vendor leaves volume empty when 1,000 or more contracts trade (§5) **[confirmed]**;
- a 60-month window W60, and the 2010–2023 walk-forward design (§7, §14).

**What had been examined when this was written.** The published results of Hull and White (2017; S&P 500, 2004–2015) and of Ruf and Wang (2022; S&P 500, 2010 to June 2019). Also the 2019–2020 data audit: calendar coverage, next-session attrition of rough candidates, quote quality, volume completeness, put–call parity, the timing of the index level, and the vendor's Greeks. The audit used 2020 data, including March 2020, but only for data quality. A check of volume coding, quote sizes and quote staleness on 2019–2020 followed on 2026-11-04, again for data quality only. **No hedging error, Gain or fitted hedge coefficient had been computed for any year.**

**What that audit shaped.** Several choices were made after seeing data quality in 2019–2020, though not hedging outcomes:
- the eligibility rules of §5;
- the April 2019 exclusion;
- the implied-volatility bracket;
- the stress period;
- the index-level sensitivities;
- E7's treatment of empty volume, and the decision not to cut on volume above zero.

**Before the first 2020 hedging run:**
- version 1.0 is committed;
- the light audits of 2015–2018 (§7), and any rules they lead to, are complete and frozen;
- the §11 tests pass, and the rehearsal (§10) is done.

The run that unblinds 2020 records two commits in the `notes` column of the runtime log: the plan's (v1.0) and the implementation's.

## Status (updated 2026-11-06)

*Added 2026-11-06 at the author's request. It maps what has run, and where its results are. It changes no specification. Which years each run saw is in `results/year_ledger.csv`; every run's commit and wall time is in `results/runtime_log.csv`.*

| Item | Specified | Ran | Main scripts | Results | Notebook |
|---|---|---|---|---|---|
| The confirmatory core: rehearsal, dry run, the 2020 verdict (§§5–13) | v1.0, 2026-11-04 | 2026-11-04 (plan 77b030e) | `run_rehearsal.py`, `run_test_year.py` | `results/rehearsal/`, `results/2020/` | 01–05 |
| Walk-forward 2010–2023 (§14 item 2) | v1.0 | 2026-11-04 | `run_walkforward.py` | `results/walkforward/` | 06 |
| SPY (§16.1; a full replication from §16.3) | 2026-11-04; 11-05 | 2026-11-04; 11-05 | `build_greeks_spy.py`, `build_pairs_spy.py`, `run_spy.py`, `run_walkforward.py --spy` | `results/spy/` | 07 |
| Heston (§16.2; rewritten in §16.5) | 2026-11-04; 11-05 | 2026-11-04; 11-05 | `heston2_calibrate.py`, `heston2_hedge.py` | `results/heston/`, `results/heston2/` | 05, 09 |
| R5–R8 under every protocol (§16.4) | 2026-11-05 | 2026-11-05 | `run_learners_variants.py`, `run_walkforward_r5_r8.py` | `results/2020/`, `results/walkforward/` | 08 |
| Short-dated options (§16.6) | 2026-11-05 | 2026-11-05 | `run_short_dated.py` | `results/short_dated/` | 08 |
| R9–R11 (§16.7) | 2026-11-05 | 2026-11-05 | `run_r9_r11.py` | `results/2020/`, `results/walkforward/` | 08 |
| R2's degree, P0–P8 and PCV (§16.8) | 2026-11-05 | 2026-11-05 | `run_degrees.py` | `results/walkforward/` | 08 |
| Published aggregations; level and shape (§16.9) | 2026-11-05 | 2026-11-05 | `compare_published.py`, `level_shape.py` | `results/walkforward/` | 10 |
| Stress, parameter stability, maturity (§16.10) | 2026-11-05 | 2026-11-05 | `stress_episodes.py`, `parameter_stability.py` | `results/walkforward/` | 10 |
| Held positions, data starvation, books (§16.11, §16.13, §16.14) | 2026-11-05; revised 11-06 | 2026-11-06 | `run_extensions.py`, `build_pairs_any.py`, `ruleset.py` | `results/extensions/<u>/` (SPX, SPY and the five) | 11, 12 |
| The coverage simulation (§16.12) | 2026-11-05; revised 11-06 | 2026-11-06 | `run_coverage_sim.py` | `results/simulation/` | 11 |
| Single stocks and ETFs (§16.15) | 2026-11-05; revised 11-06 | 2026-11-06 | `build_greeks_stocks.py`, `build_pairs_stocks.py`, `audit_stocks.py`, `run_protocol_stocks.py`, `run_extensions.py` | `results/stocks/<u>/`, `results/extensions/<u>/` | 12 |

**The extensions of §14:**
1. Pending items of §§1–13: none known.
2. The walk-forward: run.
3. Short-dated options: run (§16.6).
4. A spline or varying-coefficient adjustment: not run. The polynomial degrees P0–P8 (§16.8) address the same question.
5. Smile-based and regime-dependent deltas: not run.
6. Further machine-learning challengers: LightGBM decomposed (§16.7). GAM, EBM and HedgeNet: not run.
7. Stochastic-volatility deltas: Heston run (§16.2, §16.5); SABR not run.
8. Simulations with a known truth: §16.12 (run 2026-11-06).
9. SPY: run (§16.1, §16.3).
10. The jump term: not run.

## 1. Question and scope

**Question.** On OptionsDX SPX end-of-day quotes in 2020, does Hull and White's minimum-variance (MV) delta reduce next-session squared hedging error:
- relative to the practitioner Black–Scholes delta;
- relative to Ruf and Wang's two scaling rules?

**Stability.** The confirmatory question is about 2020. Within 2020, stability is read from the monthly Gains, the coefficient paths through the crash, and a fit frozen at the end of 2019. Stability across years is the subject of the walk-forward extension (§14, item 2), which is reported separately and does not enter the verdict.

**Scope.**
- **Data:** SPX options, which are European and cash-settled.
- **Years:** 2019 supplies the primary training window (2015–2018 add to it for W36 and W60); 2020 is the test year.
- **Hedge:** one hedge per option per NYSE session, held from one session's 16:00 snapshot to the next.

**The hedge is a research proxy.** Hedging uses changes in the SPX index as a frictionless proxy. The results do not establish executable hedge performance after financing, basis and trading costs.

## 2. Data and the unit of observation

- **The panel.** The processed SPX panel described in `DATA.md` (step 3) has one row per contract-day. Its flags and next-session join are used as built.
- **A hedge observation is a pair:** a contract on NYSE session *t* (day one) and the same contract, matched by the contract key (`am_settled`, `settle_date`, `strike`, `cp`), on the next NYSE session *t+1* (day two).
  - Sessions come from the NYSE calendar. A session missing from the vendor's files is attrition, never a two-session hedge.
- **The index level S.**
  - **Primary:** the official close, `S_close`: FRED's series, and Cboe's file before 2016-10, where FRED has none.
  - **Sensitivity A:** the index level implied by the options themselves. On each session, fit the put–call parity line of the nearest P.M. expiry 0.5–5 days out, by weighted least squares across strikes within 1.5% of the close; the forward it gives is the level. If no such expiry fits, use the nearest P.M. expiry up to 10 days out; if that fails too, the session drops out of sensitivity A and is counted. **[confirmed]**
    - **What "fits" means:** the weights and candidate-strike conditions of §4's stage 1 (both legs two-sided), at least 6 strikes within 1.5% of the close, and a fitted discount factor in [0.95, 1.01]. The nearest *successful* expiry in 0.5–5 days is used before falling back to 10 days.
  - **Sensitivity A takes no carry adjustment.** At 0.5–10 days, carry moves the forward from spot by about 1 bp or less, against a 3.3 bp median mismatch. Most of it cancels in ΔS, but not all: the expiry used can change between the two days. A is an option-implied proxy, with its own estimation error and these expiry-roll effects.
  - **Quote overlap under A.** The 14-day eligibility cut guarantees that the day-one level excludes the hedged option's quotes. After a long calendar gap, the contract can have 10 days or less remaining on day two and can enter that day's fallback fit. Count and report these overlaps.
  - **Sensitivity B:** the vendor's snapshot, `S`.
  - **Why:** the audit found the option quotes synchronous with neither index series. Their own level sits a median 3.3 bp from the close, and the mismatch over one session has standard deviation 2.8 index points, against 41.6 for the index move.
  - **What changes under A and B.** D, F, σ and ν are computed once (§4), with S_close selecting the stage-1 strikes. Under A and B every quantity derived from S is recomputed with the variant's S: ΔS, the normalization by S_t (so y, x and every error), the F/S factor in δ, the correction factor ν/(S√τ), and the spot Greeks. E6 always uses the primary S. Table 8.1 gives what is refitted under each sensitivity.
- **Time to expiry τ:** calendar time in years (ACT/365), from the day-one snapshot (`quote_unixtime`) to `settle_ts`. A.M.-settled monthlies settle at 09:30 on their settlement day; P.M. contracts settle at the session close. The vendor's `DTE` is not used.
- **Weekends, holidays and early closes.** A pair always spans one session, whatever the calendar gap (a Friday-to-Monday pair spans three calendar days).
  - **Theta is not subtracted,** following Hull and White's equation (4). They found that subtracting θ_BS·Δt, with Δt one trading day, changed nothing material. Sensitivity T (§8) repeats their check, subtracting one day's theta from every pair.
  - **Why the primary leaves theta out.** Under Black–Scholes dynamics, time decay is offset on average by the gamma term: E[Δf − δ·ΔS] ≈ (θ_year + ½σ²S²Γ)·Δt = [r·f − (r − q)·δ·S]·Δt, where θ_year = 365·θ and Δt is in years. Here θ is the per-calendar-day quantity in §4. Subtracting the same theta amount from every rule changes their squared-error differences through cross terms, which T checks.
  - **Early closes.** On early-close sessions the index level is the 13:00 close, and the quotes are the vendor's later snapshot. These sessions are treated like any other. The early closes the vendor has (2019-07-03, 11-29 and 12-24) are all in training data; 2020's two fall on sessions the vendor lacks.

## 3. Price convention

- **Primary: the mid,** (bid + ask)/2, on both days. Hull and White, Ruf and Wang, and the boot camp's implied-volatility lecture all use the mid.
  - The comparison is between delta rules, and the option leg is identical under every rule. The option's bid–ask spread therefore costs every rule the same. The mid is the conventional estimate of value for a two-sided quote.
- **Not used: the last trade.** On days with zero volume it repeats the previous day's price in 95% of pairs, and it is not synchronous with the index.
- **Mark sensitivities P** (pre-specified). The Greek inputs remain those from the primary mid's implied volatility (§4). Only the option's marks change, on both days: Δf = P(day two) − P(day one). The fitted coefficients (R2, R4, R5, R6) are re-estimated on training data marked the same way.
  - **P-bid and P-ask:** the bid on both days, and the ask on both days. These are scenarios, not bounds: a within-spread value change can range from bid(two) − ask(one) to ask(two) − bid(one), which these two marks do not bracket.
  - **P-WM, the imbalance-weighted mid** ("weighted mid-price"): (bid·Q_ask + ask·Q_bid)/(Q_bid + Q_ask), where Q_bid and Q_ask are the displayed sizes. It leans toward the ask when more contracts are bid. Stoikov's (2018) micro-price refines it with a model fitted to tick data, which end-of-day files cannot support.
  - **P-SW, the size-weighted price of Lecture 12:** (bid·Q_bid + ask·Q_ask)/(Q_bid + Q_ask). It leans the other way, toward the side with more depth. Algebraically SW − mid = −(WM − mid): the two are reflections of each other about the mid.
  - **Availability.** P-WM and P-SW need positive sizes on both days (99.7% of positive-volume candidates have them on day one). The processed panel has no day-two sizes, so the analysis step joins them by contract key. Each P variant is evaluated on the primary sample intersected with its own availability (§5).
  - **Mark-sensitivity diagnostics.** They are descriptive; they do not establish which mark is closer to value, and they are not accounting decompositions of a Gain.
    - Spreads widen when the index falls, so bids fall faster than mids and asks slower. A fitted rule can learn that co-movement, which is not hedging value. A gap between G(P-bid) and G(P-ask) is consistent with it.
    - WM and SW mirror each other about the mid. So under R0 or R1, whose hedges don't depend on the marks, the SSE under WM minus the SSE under SW is 4·Σ e·u. Here e is the mid-marked error and u = Δ(WM − mid)/S_t, the normalized change in the imbalance term. This is an uncentered cross-product: Σe·u/n = Cov_n(e,u) + mean(e)·mean(u), using covariance with divisor n.
- **Spread screen S3** (pre-specified): the analysis restricted to pairs whose day-one relative spread, (ask − bid)/mid, is at most 5% **[confirmed]**. The unscreened primary and S3 are both reported, and S3 enters the robustness of the verdict (§8). The screen uses day-one information only.
  - **For it:** a mid can sit anywhere within the half-spread of the value, so wider spreads permit greater mark uncertainty, in Δf and, through the implied volatility, in δ and ν. S3 examines a narrower-spread population.
  - **Against it:** relative spreads are largest for cheap options, because of the minimum tick, and in stress, when spreads widen. So S3 mostly removes cheap far-out-of-the-money options, Ruf and Wang's home domain, and crash-period pairs. It changes the population as well as the noise, which is why it is a sensitivity, not the primary.

## 4. Implied volatility and Greeks (design step 1)

**Forward and discount factor.** These are estimated in three stages, for each session and each expiry, identified by (`am_settled`, `settle_date`).
**The candidate strikes** of an expiry are those with 0.9 ≤ K/S_close ≤ 1.1 at which **both** the call and the put are two-sided (bid > 0, ask ≥ bid), on a session row (E1) with τ > 0 and none of E3's flags.
1. **Parity fit per expiry.**
   - **The regression:** C_mid − P_mid = D·F − D·K, by weighted least squares on the candidate strikes, with weights 1/(spread_C² + spread_P²) and spreads floored at 0.05.
   - **The output:** an implied zero rate r_e = −ln(D_e)/τ_e and its standard error. The slope's standard error uses the weighted residual variance with n − 2 degrees of freedom, and se(r_e) follows by the delta method, se(D_e)/(D_e·τ_e).
   - **A fit succeeds** with at least 6 candidate strikes, a finite D_e > 0, and a finite, positive standard error. A fit with a zero standard error (an exact parity line) is deliberately left out of the curve, which weights by 1/s.e.².
2. **A smooth discount curve per session.**
   - **Why a curve.** A short expiry's slope pins down D poorly. With a narrow strike range at 14 days, the implied rate has a standard error of several percentage points, so D is taken from a curve instead.
   - **The fit:** weighted least squares of r_e on (1, τ_e), with weights 1/s.e.², over that session's successful stage-1 fits with τ_e ≥ 30 days. With fewer than 3 such fits, the curve is their weighted mean (flat).
   - **Fallbacks.** If no successful fit is at least 30 days out, the same rule is applied to all successful fits. If the session has none at all, its rows get no Greeks and are counted as attrition.
   - **Then** D(τ) = exp(−r(τ)·τ), with r flat beyond the fitted range.
3. **The forward per expiry, given D.** F_e is the weighted mean of (C − P)/D(τ_e) + K over the candidate strikes. It needs at least 3 candidate strikes, not 6, and F_e > 0. An expiry without a forward gets no Greeks; its rows are counted as attrition.

**Reported:**
- how often each stage binds;
- the session rate curves;
- the parity residuals;
- the call–put implied-volatility gap at the same strike, a parity-consistency check: if mids satisfy parity at the fitted D and F, one σ prices both options.

The hedged option's own quotes help fix its expiry's forward. That is inherent: an implied volatility is a transformation of the option's own price.

**Why r and q never need separating.** The slope of the parity line gives D, and so the zero rate to that expiry, r = −ln(D)/τ. The forward gives the carry, r − q = ln(F/S)/τ.
- **Rates and dividends enter only through D and F.** Prices and implied volatilities depend on D and F alone; the spot Greeks (δ, Γ, vanna) also use S.
- **So q is never estimated as such.** If it were, it would absorb the index-timing mismatch of §2: 3 bp over 14 days is an apparent yield of 0.8% a year. It is not interpreted.

**Implied volatility.**
- **Model:** the Black–Scholes price in forward form, C = D·[F·N(d₁) − K·N(d₂)] with d₁ = [ln(F/K) + σ²τ/2]/(σ√τ).
- **This is the boot camp's formula.** It equals the lectures' Black–Scholes formula with a continuous dividend yield (Lecture 9), with r = −ln(D)/τ and q = r − ln(F/S)/τ.
- **The solver:** `bs_euro_iv` from the boot camp's final option-pricing library (Lecture 12, `option_pricing.py`, version 2026.11.02.1). It is Lecture 11's vectorized safeguarded Newton–bisection solver, now for calls and puts, with an upper bracket that can expand to σ = 8. It is called with r = −ln(D)/τ and q = r − ln(F/S)/τ, which reproduces the forward-form price for any S. Tolerance: 10⁻⁸ index points, absolute (the library's default). The wide bracket removes one cause of failure; it does not guarantee a solution for every March 2020 quote.
- **Failures.** Only an implied volatility returned with status `converged` is admitted for analysis. Every other status (`return_info=True`) is kept and counted as attrition: a mid outside the no-arbitrage bounds, a quote at a volatility bound, or one above the bracket.
- **The library is not copied into this repository.** The lecture repository has no licence file, so the library is imported from a local clone of github.com/TheErdosInstitute/quant-finance, pinned to commit b2709e9 (2026-11-03). The pipeline requires the clone. Only the cross-check tests of §11 are skipped without it.

**Greeks,** all at the option's own implied volatility (the "practitioner" Black–Scholes convention):

| Greek | Formula | Units | Role |
|---|---|---|---|
| δ | D·(F/S)·N(d₁) for calls; δ_C − D·F/S for puts | — | the base delta |
| ν | D·F·φ(d₁)·√τ | per unit of σ (1.00 = 100 vol points) | the MV correction |
| Γ | D·(F/S)·φ(d₁)/(S·σ·√τ) | | diagnostic |
| vanna | −D·(F/S)·φ(d₁)·d₂/σ | | attribution (§8); exploratory rule R6 |
| volga | ν·d₁·d₂/σ | | attribution only |
| θ | the library's `bs_euro_greeks` theta (Lectures 6 and 9), ÷ 365 | per calendar day | sensitivity T |
| θ_F | −D·F·φ(d₁)·σ/(2√τ): decay at fixed F and D | per year | attribution only |
| ∂V/∂F, ∂V/∂D | D·N(d₁) for calls, −D·N(−d₁) for puts; V/D | | attribution only |

The library supplies price, δ, Γ, ν, θ and the rhos. Vanna, volga, θ_F and the forward and discount sensitivities are the project's own, checked by finite differences (§11).

The vendor's IV and Greeks are a diagnostic only. They are approximately Black–Scholes values at the vendor's own IV, but that IV is not the Black–Scholes inverse of the mid at the vendor's index level and `DTE` under any single carry. Their inputs are undocumented.

## 5. Eligibility

These rules are fixed before any hedging outcome is seen. Apart from E2's pre-declared calendar exclusion, they use day-one information only. A pair is **eligible** when all of the following hold:

| # | Rule | Source |
|---|---|---|
| E1 | Day one is an NYSE session and the row is not a vendor non-session row | `f_non_session` |
| E2 | Neither end of the pair is in the 2019-04-04 to 04-16 stamp window | `f_stamp_window` |
| E3 | The contract is not settled or ambiguous: not `f_post_settlement`, `f_settle_uncertain`, `f_stamp_not_session` or `f_dup_key` | flags |
| E4 | The day-one quote is two-sided: bid > 0 and ask ≥ bid | `f_one_sided`, `f_crossed` |
| E5 | τ ≥ 14 calendar days on day one | Hull and White §II |
| E6 | 0.05 ≤ \|δ\| ≤ 0.95, using the recomputed day-one δ under the primary S | Hull and White §II |
| E7 | Day-one volume > 0, **or volume empty with a positive last-trade price** **[confirmed 2026-11-04]**. Empty volume with a last price of 0 (the vendor's code for none) is ineligible | Ruf and Wang p. 1453; the vendor coding below |
| E8 | Implied volatility and Greeks exist (§4) | §4 |

**Why E7 reads as it does (found 2026-11-04, from data quality only).** Through 2021 the vendor never records a volume above 999; from 2022 it does. In 2019–2020 a contract that traded 900–999 contracts has a 22% chance of *empty* volume the next session, against about 1% for one that traded under 10. In 2023 that chance is 0.03%, and 15% of such contracts show 1,000 or more the next day. So in our years an empty field also covers days with 1,000 or more contracts traded.
- **The last price separates the two meanings.** The vendor codes "no last price" as 0. All 873 transitions in 2019, and all 819 in 2020, from a volume of 900–999 to empty volume have a positive last-trade price on the empty day. Among matched near-the-money empty-volume rows with a last price of 0, the previous session's volume was empty or zero.
- **So E7 counts empty volume with a positive last as traded,** and treats empty volume with a last of 0 as untraded. Reading every empty as untraded, as Ruf and Wang's rule does on complete volume data, would exclude the most heavily traded contracts.
- **Sensitivity V:** the strict reading (volume > 0 only), reported for the primary endpoints, to show what the coding choice moves.
- **No volume threshold above zero.** Within a fixed cell (|δ| 0.3–0.7, 14–60 days), the median relative spread is flat in volume, at 1.3–1.5% from zero volume up to 100 or more contracts, and the 90th percentile falls only from 4.2% to 3.7% for calls (4.7% to 4.0% for puts). Spread, not volume, is the measure of quote noise, so noise is screened by S3 (§3), not by a volume cut.

- **The analysis sample** is the eligible pairs with `next_status == "ok"`, i.e. a usable day-two quote.
- **Every comparison uses identical pairs for the rules being compared,** with the availability and fit-failure exceptions specified in §§6–8.
- **Results are conditional on it.** Attrition (eligible, but no usable day-two quote) is reported by status, month, delta bucket, maturity bucket and spread decile. The stress period, 2020-02-24 to 04-30, is shown separately.
- **Exclusions reported.** Also reported: the rows admitted by E7's empty-with-a-positive-last clause (51,836 among the audit's rough 2019–2020 candidates), and the delta × maturity composition of the training and test samples. Among the rough candidates (vendor delta, strict volume reading), calls were about half in the money and puts a fifth to a quarter.
- **No outcome filters.** There is no filter on day-two volume and no removal of "wrong-way" price moves.
- **The day-two price is the day-two mid, whatever the day-two volume.** A quote is a standing offer to trade and exists without a trade. Quotes are refreshed daily whether or not the contract trades: only 0.05% of positive-volume pairs show an identical bid and ask on day two, whatever day two's volume. Requiring a day-two trade would select on the outcome, because trading responds to price moves (Ruf and Wang §6). About a fifth of pairs have zero or empty day-two volume (2019: 24%; 2020: 20%; the stress period: 23%). Reported descriptively: the Gains split by day-two volume, labelled as conditioning on day-two information.
- **Endpoint scenarios for vanished quotes.** As decided on 2026-11-02, the primary and secondary endpoints are recomputed with the vanished pairs (`one_sided_next`) included, using the fitted coefficients unchanged.
  - **Their day-two value** is set first at the low end and then at the high end of a band, all on day two:
    - **For a call,** the parity band [max(L, P_bid + D(F − K)), min(C_ask, P_ask + D(F − K))] where the put is two-sided, with L = max(0, D(F − K)), the no-arbitrage floor. For a put, swap C and P and the sign of D(F − K).
    - **Otherwise** the band is [L, ask]. Without a day-two D and F it is [0, ask].
    - **Two imputations,** labelled and counted separately because they are not no-arbitrage bounds. Apply these in order: if the ask is below L, set both ends to the ask. Otherwise, if the parity band crosses (lower > upper), set both ends to the synthetic mid, P_mid + D(F − K) for a call (C_mid − D(F − K) for a put), clipped to [0, ask].
  - **These are scenarios, not bounds.** The difference in squared error between two rules is affine in each vanished value, with coefficients whose signs vary across pairs, so setting all values low, or all high, need not be the worst case for a comparison.
  - **The adversarial scenario** (exploratory) is the worst case for one comparison. Write v for a vanished pair's day-two value and H_j = h_j·ΔS for rule j's hedge. Then e_R2² − e_X² = [2(H_X − H_R2)(v − V_t) + H_R2² − H_X²]/S_t². So for R2 against X, each v is set at the upper end where H_X − H_R2 > 0 and at the lower end otherwise, which maximizes SSE_R2 − SSE_X over the assigned bands, with fits and pricing inputs fixed.
    - It bounds the sign of that comparison only: not the size of a relative Gain, materiality or equivalence.
    - Each comparator has its own assignment; they are not combined into one scenario or verdict.
  - **Other attrition.** `contract_absent` occurs only inside the excluded April 2019 window, and `vendor_missing_session` removes whole sessions, not particular contracts.
- **Sensitivities and the sample.** Table 8.1 gives, for every variant, its training data, its test sample, and what is recomputed. The primary is re-reported on each intersection or subsample.

## 6. Hedge rules

Each rule's hedging error is e = (Δf − δ_rule·ΔS)/S_t, where Δf is the change in the mid and ΔS the change in the index from day one to day two. There is no financing term and no theta adjustment, following Hull and White's equation (4). Changes in rates and dividends between the two days are hedged by no rule. The attribution's carry term (§8) measures their size.

| Rule | Hedge ratio | Parameters |
|---|---|---|
| R0 | 0 (no hedge) | none; reference for effectiveness only |
| R1 | δ, the practitioner Black–Scholes delta | none |
| R2 | Hull–White MV delta: δ + ν/(S√τ)·(a + b·δ + c·δ²) | a, b, c, fitted separately for calls and puts |
| R3 | Ruf–Wang fixed: 0.9·δ for calls, 1.1·δ for puts | none |
| R4 | Ruf–Wang fitted scaling: â·δ | â, fitted separately for calls and puts |
| R5 *(exploratory)* | Relaxed Hull–White: a₀·δ + ν/(S√τ)·(a + b·δ + c·δ²) | 4 per type |
| R6 *(exploratory)* | Ruf–Wang delta–vega–vanna, on the normalized scale (S_t = 1): a·δ + b·ν/S_t + c·vanna | 3 per type |
| R7 *(exploratory)* | Regression tree: δ + ν/(S√τ)·g(z), with g piecewise constant | a depth-3 tree per type |
| R8 *(exploratory)* | Gradient boosting from R2: δ + ν/(S√τ)·[a + b·δ + c·δ² + h(z)] | LightGBM; hyperparameters tuned on 2019 |

**The features z of R7 and R8,** all known when the hedge is set on day one:
- δ and ln τ;
- the option's position on its smile, σ/σ_ATM − 1. σ_ATM is its expiry's at-the-money implied volatility on day one. It is interpolated linearly in ln K between the nearest strikes bracketing F, using day one's valid quotes with a converged implied volatility (not only analysis pairs). Each strike's implied volatility comes from its out-of-the-money option: the call at K ≥ F (so the call itself if K = F), the put below. There is no extrapolation;
- σ_ATM itself;
- rv20: √252 times the sample standard deviation (ddof = 1) of the 20 daily log close-to-close returns ending on day one, from 21 closes, which may reach into the preceding year;
- ret5: ln(S_close,t / S_close,t−5).

A pair missing any feature is left out of R7 and R8 only. They are compared with R2 on their feature-complete subsample, with R2 re-reported there, so the confirmatory sample never shrinks.

## 7. Fitting and the chronological protocol

**R2.** Following Hull and White (§II), prices are normalized so that S_t = 1 on day one. Their equation (6) is then fitted by ordinary least squares, with no intercept and separately for calls and puts:

  y = a·x + b·δ·x + c·δ²·x + ε, where y = (Δf − δ·ΔS)/S_t and x = (ν/S_t)·(ΔS/S_t)/√τ.

Do not divide through by ΔS: that changes the weighting.

**R4.** Ordinary least squares of Δf/S_t on δ·ΔS/S_t, with no intercept, on the same windows: the same normalized loss as R2. R5 and R6 minimize that loss too.

**R7 and R8: a learner fitted on the hedging loss.** For x ≠ 0, (y − x·g)² = x²·(y/x − g)². So minimizing the hedging loss over g is a weighted regression of the realized ratio y/x on z, with weights x², and any learner that accepts sample weights can fit it.
- **Pairs with x = 0** contribute the constant y² whatever g is. They are left out of learner fitting and kept in evaluation.
- **Weights are rescaled to mean 1** in each training set; raw x² is of order 10⁻⁵. That leaves an unpenalized minimizer unchanged. Regularization parameters are defined on the mean-1 scale.
- **R7:** scikit-learn's DecisionTreeRegressor, depth 3, min_weight_fraction_leaf = 0.05, random_state 2026. It is fixed in advance, not tuned. It is the supervised partition that takes the place of clustering: its leaves are buckets chosen by the hedging loss.
- **R8:** LightGBM, L2 objective, boosted from R2. Its initial score is R2's fitted a + b·δ + c·δ² on the same window, refitted inside every training window, including each rehearsal fold. The trees learn only a correction h(z): the prediction is R2's polynomial plus h(z), added explicitly, and strong regularization shrinks R8 back to R2.
  - **Fixed settings:** CPU; feature_fraction 1; no bagging; min_data_in_leaf 20; deterministic = true with force_col_wise = true; seed 2026; 8 threads; no early stopping. Package versions are pinned in `uv.lock`, and other settings are the library defaults.
  - **Search space:** num_leaves in [4, 64] (integer, log scale); learning_rate in [0.01, 0.2] (log); n_estimators in [50, 1000] (integer, log); lambda_l2 in [10⁻³, 100] (log); and min_sum_hessian_in_leaf = f × N, with f in [10⁻⁴, 10⁻²] (log). N is the training rows left after the feature and x = 0 exclusions, so this is a minimum leaf weight that scales with the window, not a row count.
  - **Tuning, on 2019 only:** separate Optuna studies for calls and puts, each with the TPE sampler (seed 2026), 60 serial trials and no pruning. Each study's objective is the pooled out-of-sample normalized hedging SSE of the rehearsal design (§10), including validation pairs with x = 0: trailing 6-month windows, test months 2019-07 to 12, and the boundary rule below.
  - **Then frozen.** The best hyperparameters are fixed before 2020 is unblinded, and R8 is refitted monthly on the primary window, like R2.
- Both are fitted separately for calls and puts. Neither enters the verdict.

**Primary policy.**
- **Window and refits:** refit at the start of each 2020 month on a trailing 12-month window.
- **What the training set may contain:** the training set for test month *m* contains the analysis-sample pairs (§5) with day one in the 12 months before the first session of *m*, **and day two strictly before that session**. No outcome observed on or after the first test session enters the fit.
- **Minimum training coverage:** 150 sessions with pairs, per option type. If R2 or R4 cannot be fitted for a type and month (fewer sessions, or a singular design matrix), that month is dropped for every rule of that type within that experiment, so all rules keep a common sample. A failure of R5–R8 leaves only that rule's result missing, and a failure in a sensitivity never removes primary observations. This is not expected to bind in 2020.
- **Period membership** is by day one, the hedge-start date, throughout: a pair belongs to the month, and the year, of its first session. The pairs that start on 2020-12-31 end on 2021-01-04, so January 2021 quotes are used for their day two.
- **Departure from Hull and White.** They used 36 months and found 12–60 made no material difference. That finding does not establish the 12-month window for 2020, so sensitivity W36 runs theirs.

**Sensitivity F (frozen).** One fit on all 2019 pairs whose day two falls before 2020-01-02, applied unchanged through 2020: the model "as deployed without recalibration".

**Sensitivity W36 (Hull and White's window).** As the primary, but with a trailing 36-month window, so the January 2020 fit uses 2017-01 to 2019-12. Still one month out, refitted monthly.
- **It needs 2017–2018:** step 1 (§4) run on those years and, before any of their hedging outcomes is computed, a light audit by month: flag rates, attrition, expiries per session, and the volume coding of §5. An anomaly found there is handled by a rule decided before fitting, or W36 is dropped and the reason reported. These audits and rules are frozen before any 2020 outcome is unblinded.
- **Why it is informative.** The 12-month window that enters 2020 holds only calm 2019 data. Thirty-six months include the February 2018 and late-2018 sell-offs. W36 asks whether a fit that has seen stress hedges the 2020 crash better.

**Sensitivity W60.** As W36, with a trailing 60-month window: the January 2020 fit uses 2015-01 to 2019-12, which adds the August 2015 and early-2016 sell-offs. Hull and White's 12–60-month range is then covered at both ends.
- **It needs 2015–2016 as well,** under the same light audit. Two features of those years are already handled by the step-3 rules but get checked: A.M. monthlies stamped on Thursdays until August 2016, and the January 2015 re-stamping (`f_restamped`). The official close comes from Cboe's file before 2016-10, where FRED has none.
- **No window is selected.** W12, W36 and W60 are all pre-specified and all reported on the same 2020 test months; W12 stays primary.

**Stability.** Plot a, b, c and â at each monthly refit, with standard errors clustered by session. These allow any correlation within a session but none across sessions.

**Implementation.** Store X′X and X′y per session and type, so that any window is a sum. Assert in code that every training pair's day two precedes the first test session.

## 8. Outcomes and the verdict

**Gain** (Hull and White's equation (3)), over a set of pairs: Gain(rule) = 1 − Σe²_rule / Σe²_R1. The relative Gain of R2 over a rule X is 1 − Σe²_R2 / Σe²_X.

**Primary endpoints (confirmatory).**
- G_C and G_P: the Gain of R2 over R1 for calls and for puts, pooled over the analysis pairs with day one in 2020.
- **H1** (the MV delta reduces next-session squared hedging error relative to Black–Scholes in 2020) is supported only if **both** 95% lower bounds exceed 0. This is an intersection–union test: each lower bound is a one-sided 0.025 test, so no multiplicity adjustment applies. Neither type may be chosen after the fact.

**Secondary (pre-specified).**
- **The family:** the relative Gains of R2 over R3 and over R4, for calls and puts (four comparisons).
- **"R2 beats X"** requires a Holm-adjusted one-sided bootstrap p-value below 0.025, within the family of four superiority tests, with p₊ = (1 + #{replicates ≤ 0})/(B + 1).
- **"R2 is worse than X"** requires the same within a separate family of four inferiority tests, with p₋ = (1 + #{replicates ≥ 0})/(B + 1). The two families together hold the directional familywise error at or below 0.05, provided the p-values are valid.
- **Otherwise,** R2 and X are "not distinguished". That is not equivalence; equivalence has its own test below.
- **What the p-values are.** They are percentile-inversion measures from the session-block bootstrap (§9), not exact null-simulation p-values. Their calibration is approximate and rests on the bootstrap's validity.
- **The out-of-the-money subsample** reports the same four comparisons, and the primary G_C and G_P: calls with K ≥ F and puts with K ≤ F on day one. The rules are those fitted on the original chronological training windows, which contain both in- and out-of-the-money pairs. These results are descriptive, with intervals.
  - **At the money belongs to both halves,** as in Ruf and Wang's ranges (calls 0.8 ≤ S/K ≤ 1, puts 1 ≤ S/K ≤ 1.5). With 5-point strikes and a continuous F, an exact tie is rare; what matters is that near-the-money options are never dropped.
  - **A related population, not a replication.** It is cut by the forward, not by spot, and is not bounded in moneyness as Ruf and Wang's is.
  - **Why this subsample.** It is close to the domain on which Ruf and Wang derived and tested the scaling rules. For a deep-in-the-money call, δ approaches D·F/S, the delta of the corresponding forward claim, so scaling by 0.9 under-hedges that limiting exposure by 10%. The Hull–White band includes such options.
  - **It also counts each strike's exposure once.** By parity, an in-the-money call is the out-of-the-money put at its strike plus a forward position. Their Black–Scholes hedging errors therefore differ by Δ[D(F − K)] − (D·F/S)_t·ΔS: the carry term, which includes the timing mismatch, plus parity noise. The full sample holds many such near-duplicates: about half the calls are in the money.
  - **Exploratory variant:** R2 and R4 refitted on out-of-the-money training pairs only, as Ruf and Wang fit.
- **The secondary family is also reported under sensitivity A.** Against the close, the pooled timing evidence suggests an attenuation of about 1.7% in the options' index moves. Fitted rules can absorb it and the fixed R3 cannot, so the close-based comparisons with R3 may lean toward the fitted rules.

**Reported beside every primary result** (descriptive):
- **Effectiveness** (Ederington 1979): 1 − Σe²_rule / Σe²_R0, for R1 and R2.
- **Aggregation:** the average of monthly Gains, which is Hull and White's aggregation.
- **Concentration:** the share of 2020's Σe²_R1 from the stress period.
- **Size of the improvement:** the root-mean-square error ratio √(1 − Gain).
- **Bias:** the mean error per rule.
- **Dollar RMS error per contract:** e·S_t·$100, before aggregating.

**A retrospective stress comparison** (a case study, with no predicted direction): the Gains over 2020-02-24 to 04-30 against the rest of 2020, each with its own interval. The "rest of 2020" Gain is also the leave-stress-out result. The 10 sessions contributing most to 2020's Σe²_R1 are listed with their share.

**Wording thresholds [confirmed].**
- **The thresholds are substantive.** They are fixed before the rehearsal (§10), whose interval widths are reported only to show what the design can resolve.
- **"Material":** a Gain of at least m = 0.05, about 2.5% lower RMS error. This is the smallest improvement taken to justify replacing the Black–Scholes delta. A point Gain ≥ m is "material in the point estimate"; a lower bound ≥ m would make it statistically established.
- **"No material benefit"** requires the upper end of the 95% interval to be below m.
- **"Equivalent to a scaling rule"** requires the whole 95% interval of the relative Gain to lie within (−0.02, +0.02). Crisis-year intervals may well be too wide for that.
- **Failing to reject zero shows neither.**

**Verdict for the stated research use** (a daily delta rule on SPX index options). The verdict is the first row that applies:

| Verdict | Condition |
|---|---|
| **Reject** | (a) For either type, the 95% upper bound of G is below 0; or (b) both upper bounds are below m; or (c) H1 is supported, but R2 is worse than R4 or R3 (secondary test) for either type. In case (c) the simpler rule is preferred |
| **Approve** | H1 supported; both point Gains ≥ m; R2 beats R4 for both types |
| **Approve with conditions** | H1 supported and both point Gains ≥ m, but R2 is not distinguished from R4 for at least one type. The condition: superiority over the one-parameter rule has not been established, so the validator prefers the simpler rule on parsimony grounds unless the three coefficients are shown to earn their place |
| **Inconclusive** | Anything else, for example H1 not supported without (a) or (b) |

R3, the fixed rule, enters the verdict only through (c), because its comparison with the fitted rules may be biased by the timing attenuation.

**Table 8.1. What each variant changes.** It governs R0–R6. "Train" says what the fitted rules (R2, R4, R5, R6) are fitted on; "test" is the sample evaluated. R7 and R8 run under the primary protocol only, and are not retuned for any variant.
- Training sets use the variant's availability; E6 always uses the primary δ.
- Every comparison is on identical pairs for all rules.
- Every variant except the adversarial scenario reports the primary endpoints and the four secondary comparison estimates. For the adversarial scenario, construct a separate assignment for each comparison of R2 with R1, R3 or R4, per option type, and report only that assignment's target comparison; do not assemble a common verdict. Descriptive rows (the OTM subsample, OTM-refit and the others not in the robustness list) stay descriptive; they add no confirmatory families.
- V changes the evaluation population only. It does not measure the full effect of changing E7 in both training and evaluation.

| Variant | Train | Test | Recomputed |
|---|---|---|---|
| A | refit under S_A | primary ∩ A available | all S-dependent quantities listed in §2 |
| B | refit under the vendor's S | primary | all S-dependent quantities listed in §2 |
| P-bid, P-ask, P-WM, P-SW | refit on the same marks | primary ∩ marks available | Δf |
| T | refit on Δf − θ·(one day) | primary | Δf |
| F | 2019 only, frozen | primary | — |
| W36, W60 | 36- or 60-month windows | primary | — |
| S3, V, the OTM subsample, the rest of 2020, the day-two-volume split | primary fits | the subsample | — |
| OTM-refit | refit R2 and R4 on out-of-the-money training pairs; retain primary fits for R5 and R6 | the OTM subsample | — |
| Endpoint scenarios (low, high, adversarial) | primary fits, unchanged | primary + vanished pairs | Δf of vanished pairs |

All variants apply to the primary 12-month protocol unless the row says otherwise.

**Robustness of the verdict.** The verdict is recomputed under each of the following:
- sensitivity A;
- sensitivity B;
- the frozen fit F;
- the windows W36 and W60;
- the spread screen S3;
- each of the marks P-bid and P-ask;
- the low and high endpoint scenarios;
- the rest-of-2020 sample.

Each variant whose verdict differs is listed, and the verdict is stated as conditional on it: for example, "Approve, conditional on the index level; Inconclusive under the options' own level".

**Diagnostic, carried from the audit.** Report the change in G_C and G_P from the primary to sensitivity A. Changes in opposite directions are consistent with the timing artefact; they do not identify it uniquely.

**Diagnostic: a partial second-order attribution of the Black–Scholes hedging error.** For each pair, with day-one Greeks and Δσ the change in the contract's own implied volatility (day two's from day two's mid, forward and discount factor):

  Δf − δ·ΔS = ν·Δσ + ½Γ·(ΔS)² + θ_F·Δt + vanna·ΔS·Δσ + ½·volga·(Δσ)² + carry + R.

- **The terms.** θ_F is per year and Δt is the calendar time between the snapshots in years (ACT/365). carry = (∂V/∂D)·ΔD + (∂V/∂F)·[ΔF − (F/S)·ΔS] collects the changes in the discount factor and forward not explained by ΔS: rate moves, dividend revisions and the index-timing mismatch. R is the remainder.
- **What R measures.** R is the residual of this partial expansion, up to the IV solver's price tolerance. It includes third-order terms and omitted second-order terms: the squared residual forward move, its cross terms with ΔS and Δσ, and discount and time terms. Quote noise can affect the inputs and therefore R; it is not separately identified. A large R can reflect omitted terms or implementation errors. Large March 2020 moves make the approximation a concern to check, not a failure already established.
- **What the vega line shows** (a first-order diagnostic, not a bound). Hull and White's correction approximates ν·E[Δσ | ΔS]/ΔS. For the normalized squared loss, the best scalar delta correction within a cell is E[(R₀/S_t)·(ΔS/S_t)] / E[(ΔS/S_t)²], where R₀ = Δf − δ·ΔS and the denominator is positive. Report each normalized attribution term's cross-moment and covariance with ΔS/S_t. The cross-moments, including carry's, add to the numerator; covariances alone omit mean products.
- **Reported:** divide every attribution term, including R, by S_t before aggregation. Report their mean squares and all pairwise cross-products relative to the mean squared normalized hedging error. The terms' mean squares do not add up to the total without the cross-products. Results by delta and maturity bucket, for the stress period and the rest. Pairs without a day-two implied volatility are left out of the attribution only, and counted. It runs on 2019 in the rehearsal, as verification, and on 2020 in the unblinding run.
- **The in-sample ceiling.** R2 refitted on each test month's own pairs: the empirical optimum within the exact R2 family for that month. Descriptive only; it never feeds back into fitting or selection.

**Exploratory.** Each item below is reported with pointwise intervals, and no winner is chosen by significance:
- **Gains by bucket.** The delta buckets are δ to the nearest tenth, as in Hull and White's Table 1: [0.05, 0.15), [0.15, 0.25), …, [0.85, 0.95], with puts by |δ|. The maturity buckets are their seven, on τ·365 calendar days: [14, 31), [31, 61), [61, 92), [92, 123), [123, 183), [183, 366), [366, ∞);
- sensitivities A, B, F, W36, W60, S3 and V;
- the marks P-bid, P-ask, P-WM and P-SW (§3), with their mark-sensitivity diagnostics;
- the adversarial endpoint scenario (§5);
- **sensitivity T:** Δf replaced by Δf − θ·(one day) for every rule, Hull and White's own check; and the mean error per rule by calendar gap (1, 3 and 4 days);
- the monthly Gain path;
- rules R5 and R6;
- **the challengers R7 and R8:** their relative Gains over R2, with intervals. A challenger is called "promising" if the 95% lower bound exceeds 0. It never changes the verdict. Two smoothness diagnostics are reported beside them, because a desk would reject a hedge that jumps:
  - the share of adjacent-strike pairs (same expiry and day) whose hedge ratios are out of order;
  - each rule's mean daily |Δh| per contract (turnover), against R2's;
- the Gains split by day-two volume (§5);
- **a monitoring illustration** in place of a switching rule: the trailing 20-session Gain, computed from completed, lagged hedges and plotted through 2020. It makes no claim that switching would have helped.

## 9. Inference

- **The unit of resampling is the session, not the option.** Every option on a session shares the same ΔS and the same volatility shock, so errors are strongly correlated across options within a day; volatility clustering correlates them across days.
  - Hull and White's Appendix B corrects for serial correlation within each option series but treats different options on the same day as independent. Its t-statistics are therefore likely to overstate significance.
- **The bootstrap.**
  - **The session index:** within the evaluation period, retain sessions with at least one pair in any variant being compared (the primary sample, plus vanished pairs in the endpoint scenarios), in calendar order. The primary period is 2020; rehearsal statistics use their own evaluation periods, and a monthly interval uses that month. Stress/rest statistics use the strata below. Sessions the vendor lacks are simply absent. A variant with no pairs on a retained session contributes zero there.
  - **What it resamples:** keep, for each session, type and rule, the sum of squared errors and the count. Draw a circular block bootstrap of sessions, with blocks of 10 consecutive retained sessions (vendor gaps compressed) and B = 10,000 (seed 2026).
  - **Pairing:** within the same evaluation period and resampling design, every rule, both types and every variant use the same draws, so comparisons are paired.
  - **Each replicate** recomputes the pooled Gains.
  - **Intervals:** two-sided 95% percentile intervals. The "lower bound" is the 2.5th percentile, which matches the one-sided 0.025 level of the secondary tests.
  - **Statistics that separate stress from the rest** use three strata: 2020-01-02 to 02-21, the stress period 02-24 to 04-30, and 05-01 to 12-31. Each is resampled circularly within itself, keeping its length, so no block crosses the stress period.
  - **Checks:** block lengths 5 and 20, reported beside the main intervals.
  - **Diagnostic:** a Ljung–Box test on the daily differences in squared error (Lecture 8).
- **What the intervals mean.** They approximate the sampling uncertainty of the realized 2020 loss series, holding the fitted prediction paths fixed. They rest on the block bootstrap's assumptions (weak dependence and approximate stationarity of the resampled series within each stratum, or across the full evaluation period when unstratified), which a crisis year strains. They do not quantify the uncertainty of a newly trained deployment: estimation uncertainty from the training window is not propagated.
- **One crisis year.** A few March 2020 sessions may dominate the pooled sums, making intervals wide and skewed. That limits generalization.
- **Coefficient standard errors** (for plots only) are clustered by session: they allow correlation within a session but omit serial dependence.

## 10. Rehearsal on training data, before 2020 is unblinded

- **The rehearsal.** The complete pipeline runs first with 2019 alone: a trailing 6-month window refitted monthly, tested on 2019-07 to 12. Every rehearsal evaluation pair must have day two strictly before 2020-01-02. This cutoff also applies to R8 tuning scores and the 2019 outcome diagnostics, so none uses the hedge from 2019-12-31 to 2020-01-02.
  - **It is not the §7 protocol.** Its window is 6 months, not 12, and is exempt from the 150-session minimum. Its interval widths only roughly preview 2020's.
- **What it is for:**
  - checking the code end to end;
  - previewing interval widths;
  - hosting the specification checks below, the R8 tuning study (§7) and the 2019 attribution (§8).
- **Specification checks** (required: they are the recorded evidence on R2's form). They use 2019 data with the rehearsal's walk-forward design. They are repeated separately for 2018, with trailing 6-month windows and evaluation months 2018-07 to 12, restricted to pairs whose day two precedes 2019-01-02. Checks are performed separately by option type and rehearsal year. This makes 2018 an evaluated year (§14).
  1. **Degree.** The polynomial in δ of degree 0, 1, 2 and 3, on an orthogonal (Legendre) basis over the δ band (puts by |δ|).
     - **Criterion, fixed now:** the quadratic is *not contradicted by this diagnostic* unless degree 3 beats it out of sample: unless the walk-forward relative Gain of degree 3 over degree 2 has a 95% session-bootstrap lower bound above 0. That is one pre-specified comparison per option type and rehearsal year. Non-rejection is not proof that the quadratic is right.
     - A lower degree that is not distinguished from the quadratic is reported as such.
  2. **Maturity scaling.** τ^(−α) in place of τ^(−1/2), for α ∈ {0, 0.25, 0.5, 0.75, 1}.
     - **Criterion:** 1/√T is *not contradicted* unless one of the four alternatives beats α = 0.5. Each alternative is tested as in check 1, with Holm's adjustment across the four, per option type, at one-sided 0.025. Within each rehearsal year, across both types the error allowance is at most 0.05 if the constituent tests are valid; this is not a joint guarantee across both years.
     - **Reported beside it:**
       - the bucket analysis Hull and White describe in §IV; they give no table of it. Separately for each type and rehearsal year, use that year's evaluation pairs for this descriptive bucket analysis. Per delta × maturity bucket, κ̂ is the no-intercept OLS coefficient of y on w = (ν/S_t)·(ΔS/S_t), with y as defined in §7, so that δ_MV − δ_BS = κ·ν/S. 1/√T predicts √τ·κ flat across maturity within each delta row. A bucket has no single τ, so the plotted quantity is √τ_eff·κ̂, with τ_eff^(−1/2) = Σ w²·τ^(−1/2) / Σ w² over the bucket's pairs. Flatness is approximate within a delta bucket;
       - the regression of Δσ on ΔS/(S·√τ) by bucket, after the implied-volatility relation below their equation (5), whose slope should not trend with maturity.
  3. **The bucket table itself,** κ̂ and the arithmetic mean of κ̂·ν/S_t over the bucket's pairs, separately by type and rehearsal year, using §8's bucket edges.
  4. **Naive against session-clustered standard errors** for a, b and c. Their ratio shows how much the within-day dependence of §9 matters.
- **None of these changes R2.** The question is about Hull and White's delta, so R2 stays as they specified it. Every variant that contradicts the quadratic or 1/√T in either rehearsal year is carried to 2020 for the qualifying option type as a labelled exploratory rule, under the primary 12-month protocol. All qualifying variants are retained; none is selected as the winner. The diagnostic result is reported as a limitation of the model.
- **Unblinding 2020** happens in one run, after the tests in §11 pass, with the git hash recorded in the runtime log (§13).

## 11. Verification (pytest)

1. Black–Scholes prices satisfy put–call parity; δ, ν, Γ, vanna, volga, θ_F and the forward and discount sensitivities match central finite differences. For δ and Γ, perturb S with F scaled as F·S′/S and D, σ, τ fixed. Check vanna by differentiating δ with respect to σ at fixed S, F, D and τ; check volga by differentiating ν with respect to σ. Check θ_F as minus the τ derivative at fixed F, D and σ. For ν, ∂V/∂F and ∂V/∂D, perturb only σ, F and D respectively.
2. The forward-form functions agree with Lecture 12's `option_pricing.bs_euro_greeks` and `bs_euro_iv` when given the same r and q. The test is skipped, with a message, when the lecture clone is absent.
3. Implied volatility round-trips for σ from 0.01 to 3.0 and τ from 14 days to 3 years, and fails cleanly outside the no-arbitrage bounds.
4. The three-stage parity fit recovers a known D and F from synthetic quotes with spread noise, including a 14-day expiry with only a few strikes.
5. **Known-coefficient test:** manufactured regression data with known a, b, c are recovered within floating-point tolerance, including feature construction and normalization.
6. Gain is invariant to the normalization scale and equals 0 for identical rules.
7. **No look-ahead:** the training/test boundary assertion of §7, tested on a toy panel.
8. The bootstrap reproduces the full-sample Gain when every session is drawn once.
9. **The learners' objective is the hedging loss:** for any g, Σx²·(y/x − g)² over pairs with x ≠ 0 equals Σ(y − x·g)² over them. R8's prediction adds R2's polynomial explicitly, and R8 with zero trees reproduces R2.
10. **The attribution:** on synthetic Black–Scholes quotes in which only S moves (F as F·S′/S; D, σ, τ fixed), R is third order in ΔS, and the vega, vanna and volga terms vanish.
11. **The marks:** P-WM and P-SW lie in [bid, ask], are mirror images about the mid, and equal the mid when the sizes are equal.

## 12. Reporting

- **The README** opens with the verdict and one figure.
- **Notebooks,** numbered by design step:
  - 01 audit and attrition;
  - 02 forwards, implied volatility, Greeks and verification;
  - 03 the 2019 rehearsal and the coefficient paths;
  - 04 the 2020 results;
  - 05 the breakdown and sensitivities.
- **Tables:**
  - attrition;
  - the primary and secondary Gains with intervals;
  - the bucket Gains beside Hull and White's Table 1 and Ruf and Wang's Tables 2 and 5 (as context, not targets: the samples differ);
  - the sensitivities of Table 8.1;
  - the specification checks;
  - the attribution;
  - R7 and R8 against R2.
- **Figures:** the coefficient paths; the monthly Gains; cumulative Σe² through 2020 for each rule; the bucket Gains.
- **An executive summary** (verdict first) and a short video.
- **Every item in §§1–13 is run.** Anything incomplete at submission is reported there as pending, and completed and reported afterwards. A declared item that cannot be run is reported with the reason.

## 13. Runtime log

Every run of a pipeline step (including step 1 for 2015–2018), fit, bootstrap, rehearsal or tuning study is timed with `erdos_quant_finance_project.runlog.timed`. That appends a row to `results/runtime_log.csv` with:
- the start time;
- the step;
- the status;
- the wall time;
- the process's peak memory where the platform reports it (not isolated per step);
- the row counts;
- the inputs;
- the git hash and whether the tree was dirty;
- the Python version and the machine.

Runs before the helper existed are backfilled from the build notes. An Optuna study is one row, with its trial count and best value in the `notes` column; its trials are saved beside the results.

## 14. Extensions beyond the confirmatory core (pre-declared, in order)

They may run once the confirmatory core is complete, before or after submission, without changing its specification. The verdict of §8 rests on 2020 alone. Item 2 is specified here. Items 3–10 are exploratory, and each gets a dated specification appended to this plan before it is run.

**The year-status ledger.** Years are by hedge-start date. At v1.0 no hedging outcome has been computed for any year; only the data-quality audits have used them. The 2020 pairs that end in January 2021 use January 2021 quotes.

| Years | Planned exposure | Actual exposure, with date |
|---|---|---|
| 2019 | evaluated (the rehearsal); tuned (R8) | unseen at v1.0 |
| 2020 | evaluated at unblinding | unseen at v1.0 |
| 2018 | fit-only (W36, W60); evaluated (the specification checks, §10) | unseen at v1.0 |
| 2015–2017 | fit-only (W36, W60) | unseen at v1.0 |
| 2010–2014, 2021–2023 | untouched until the walk-forward | unseen at v1.0 |

- **The definitions.** *Fit-only* means outcomes entered a fit, and its coefficients were seen, but no out-of-sample Gain was computed. Only years untouched before the walk-forward are clean held-out evidence. Evaluated or tuned years are reported as such.
- **Upkeep.** The actual column is updated in the results after each run.

1. Anything in §§1–13 still pending at submission.
2. **More test years: a walk-forward over 2010–2023,** with W12, W36 and W60, under the same audit and policy.
   - **Training:** always the W months before each test month, refitted monthly, with the §7 boundary rule. Any year may be used for training.
   - **Test months: 2015-01 to 2023-12 for all three windows.** That is the common period: W60's first possible test month is 2015-01, since the data start in 2010-01. W12 (from 2011-01) and W36 (from 2013-01) are also reported over their longer spans, as supplements; windows are compared only on common months.
   - **Validation:** none for the OLS rules. They have no hyperparameters, and no window is selected: all three are reported. R8 is retuned once for the walk-forward, then frozen, and tested from 2017 on using the primary 12-month fitting window. It uses §7's tuning design moved to 2015–2016: trailing 6-month windows, test months 2015-07 to 2016-12, and validation pairs whose day two is strictly before the first 2017 test session.
   - **Clean and seen years.** The ledger above says which test years are clean. Results for untouched years are reported separately as the clean held-out evidence; the R8 tuning years 2015–2016 are not clean.
   - **Reporting:** a Gain per year and per window with session-block intervals, and the median yearly Gain. A pooled 2015–2023 Gain would be dominated by 2020. This answers the question's second half: how stable the advantage is across years.
   - **Data checks first:** each year gets the light audit of §7 before its outcomes are computed. 2022–2023 need more: the vendor records volumes of 1,000 or more from 2022, but near-the-money empty volume persists there unexplained (§5). Daily expiries arrive in 2022, and 2022 has the nine non-session holiday rows.
3. Short-dated options (< 14 days) included, as Ruf and Wang did.
4. Specification: a spline or varying-coefficient form of the adjustment, on held-out years.
5. Smile-based deltas: the slope-of-smile delta; regime-dependent coefficients, with days grouped by information available on day one, as in Alexander et al.'s (2012) regime-dependent delta.
6. Further machine-learning challengers, trained on the hedging loss with time-series validation: a GAM or EBM on the weighted realized ratio; a HedgeNet-style network.
7. Stochastic-volatility MV deltas: SABR with Bartlett's delta, per expiry; Heston.
8. Simulations with a known truth: Black–Scholes with the measured timing mismatch; Heston or SABR with a known MV delta.
9. SPY, which brings American exercise and discrete dividends.
10. The jump term omitted from Hull and White's Appendix A.

## 15. Deviation log

| Date | Section | Change | Reason | Results seen before the change? |
|---|---|---|---|---|
| 2026-11-04 | §10 | Added a dry run: after the rehearsal, the full test-year script (`scripts/run_test_year.py`) runs end to end with 2019 as the test year, on 12-month windows, excluding pairs whose day two is in 2020. It produces no 2020 number and is not evidence; it tests the code, so that nothing is debugged with 2020 results in view. 2019 is already an evaluated year (§14). | Recommended by an independent code review before unblinding | No |
| 2026-11-04 | §14, §16 | Appended §16 with the specifications of the SPY (item 9) and Heston (item 7) extensions, as §14 requires before an extension runs. | The author's choices of 2026-11-04 | No |
| 2026-11-04 | §16.2 | Calibration B changed. (1) Each session's fit runs from three starts (that session's L-iv solution, the default (0.04, 2, 0.04, 0.5, −0.7), and the previous month's median B solution), keeping the lowest cost. (2) A fit counts as successful when least_squares converges. Parameters at a bound and the IV RMSE are reported, not excluded; the hedging comparison is repeated on the fits with no parameter within 0.1% of a bound. | The first run's warm start from the previous month trapped the optimizer: 49% success, March 2020 fits with v₀ ≈ 0.02 and IV errors of 20–37 vol points. Fresh starts converge to sensible solutions (2020-03-16: v₀ = 0.89, ρ = −0.86). For SPX across 14 days to a year, Heston fits sit at κ = 10 or ξ ≈ 5 on many days. That is the model's misfit to the skew, not an optimizer failure, so excluding bound hits would leave mainly calm days | Calibration fit quality only; no Heston hedging outcome |
| 2026-11-05 | §16.1, §16.3 | SPY becomes a full replication of the SPX protocol (§16.3), no longer an exploratory extension: every §§5–10 and §14 item 2 procedure that applies to SPY, the verdict table included. | The author's decision of 2026-11-05 | Yes: SPY's 2020 Gains for R0–R5 (primary and B) were computed on 2026-11-04. So the SPY 2020 verdict is reported as post hoc. The SPY years untouched until now are the clean evidence (§16.3) |
| 2026-11-05 | §16.1, §16.3 | SPY's index level before 2016-11-03 comes from Stooq's daily closes, with their dividend adjustment reversed (§16.3); Nasdaq's close from 2016-11-03 on. | Nasdaq's history starts on 2016-11-03. Stooq's closes are dividend-adjusted, so they fail a cent-for-cent check. Reversed, they match Nasdaq within 0.43 bp in level and 0.14 bp in one-session return (medians, 1,821 sessions), against the vendor snapshot's 1.05 and 1.46 bp. The author chose them over the agreed fallback, the vendor snapshot, on that evidence | No SPY outcome before 2019 has been computed |
| 2026-11-05 | §6, §7, §14, §16.4 | R5–R8 run under every protocol that R0–R4 run under: all Table 8.1 variants in 2020 (R7 and R8 included), and the 2010–2023 walk-forward on all three windows (§16.4). | The author's request of 2026-11-05 | Yes: R5–R8 in the 2020 primary, R5 and R6 under the 2020 variants, and R8 in the 12-month walk-forward 2017–2023 |
| 2026-11-05 | §16.2, §16.5 | Heston: the project's own pricer and calibrator replace the Lecture 12 functions; calibration extended to 2010–2023; a fitted minimum-variance delta added (§16.5). | The library's pricer uses 256 nodes whatever the integration range (5.9 vol points wrong at 14 days, K/S = 0.6, ξ = 5). The calibration took 6.6 hours, and its 49 failures all hit scipy's 500-evaluation cap | Yes: the library-based 2020 Heston Gains (§16.2) |
| 2026-11-05 | §14 item 3, §16.6 | Short-dated SPX options (under 14 days) specified (§16.6). | The author's request of 2026-11-05 | No |
| 2026-11-05 | §16.5 | Calibration B2 searches on Gauss–Legendre panels three times as wide (9 radians), then polishes from that solution on the specified 3-radian grid. The accuracy check and the bound and regrid rules are unchanged. | On 2019-10-24 this gives the identical solution (cost 0.084286) in 3.2 s instead of 11.2 s | Calibration timing and fit on benchmark sessions only; no B2 hedging outcome |
| 2026-11-05 | §16.1, §16.3 | SPY's dividend yield q: on sessions where SPX's options-implied level S_A is missing, SPX's carry is measured against the official SPX close, flagged per session (`q_level`). | S_A is missing on 223 of 242 SPX sessions in 2010 (few short-dated SPX expiries), which left SPY with Greeks on 19 of 250 sessions in 2010 and lost 64 of 245 in 2011. The author's choice of 2026-11-05 | Data quality only; no SPY outcome before 2019 computed |
| 2026-11-05 | §6, §16.7 | Rules R9–R11 specified (§16.7): LightGBM corrections fitted from scratch on δ (R9) or on R8's features (R10), and boosted from R2 on δ alone (R11). | The author's request of 2026-11-05 | Yes: every result of §16.3–§16.6, R8's included |
| 2026-11-05 | §16.8 | The degree of R2's polynomial, 0 to 8 (P0–P8), and a degree chosen by validation inside each training window (PCV), in the walk-forward for SPX and SPY (§16.8). | The author's request of 2026-11-05 | Yes: every result of §16.3–§16.7, and the 2019 analysis of R9 |
| 2026-11-05 | §16.9 | Two descriptive diagnostics: SPX Gains under the published aggregations and samples (mean monthly Gain, delta buckets, no volume rule, out of the money), and the level and shape of the correction by refit and year (§16.9). | The author's questions of 2026-11-05 | Yes: every result above |
| 2026-11-05 | §16.10 | Stress episodes over 2010–2023 (two definitions from the index alone), parameter stability (coefficient paths with clustered standard errors, non-overlapping comparisons, Heston's daily parameters) and the maturity-scaling check by year (§16.10). | The author's request of 2026-11-05, following the brief's model-validation direction | Yes: every result above |
| 2026-11-05 | §16.11 | Holding-period hedging error: 5- and 10-session paths of one contract, rebalanced daily with the W12 fits, scored by Gain on the path error, with mean path errors and attrition (§16.11). | The author's request of 2026-11-05, after a review of past Erdős projects (one found that a one-session Gain did not carry over to a contract's life, on simulated data) | Yes: every result above |
| 2026-11-05 | §16.12 | Interval coverage and power under a known truth: a regression-level simulation calibrated to 2010–2019 returns and 2019's cross-section and residuals (§16.12; §14 item 8). | The author's request of 2026-11-05: the verdict rests on the session-block intervals in a year whose error is concentrated in ten sessions | Yes: every result above |
| 2026-11-05 | §7, §16.13 | Training-data starvation: windows of 1, 2, 3 and 6 months, with the minimum training coverage relaxed to ⌈0.7·21·W⌉ sessions for these windows only; and W12 fits on a random fraction or a fixed number of each training session's pairs (§16.13). | The author's request of 2026-11-05, after the review of past projects (the Summer 2026 winner tested its models on less data) | Yes: every result above |
| 2026-11-05 | §16.14 | Hedging error at the level of a book: four books formed from day-one information, each session's error the mean over the book (§16.14). | The author's request of 2026-11-05 | Yes: every result above |
| 2026-11-05 | §16.15 | Single stocks and ETFs after Hull and White's §VIII (AAPL, NVDA, TSLA, SLV, QQQ, as the data allow): out of the money only, the vendor's IV and Greeks, W12 and W36 (§16.15). Runs only if the data are obtained. | The author's request of 2026-11-05 | No single-stock or non-SPX ETF data had been obtained |
| 2026-11-06 | §16.11–§16.15, preamble | Revised after the author's review, before any of them ran. One rule set for every experiment from §16.11 on (R1–R4, R6, R9, P0; Heston on SPX). §16.11: a path is H one-session hedges in a row; after the start no band, maturity floor or volume rule applies (requiring them selects on the outcome), and the contract must outlive the path, replacing the 14 + 2H days rule. §16.13: the spread over seeds; all underlyings. §16.14: every year, 2020 and 2022 highlighted; all underlyings. §16.15: its own IV and Greeks as for SPY, over the full band (the out-of-the-money restriction and the vendor's Greeks dropped), the SPY protocol on all five underlyings, the vendor's snapshot as the level. Raw files copied to `data/raw/optionsdx_stocks/` with checksums. | The author's review of 2026-11-06 | No: none of §16.11–§16.15 had run, and no outcome on the five underlyings had been computed |
| 2026-11-06 | Status | A status section after the version note: what has run, its scripts, results and notebooks, and the status of §14's items. No specification changes. | The author's request of 2026-11-06 | — |
| 2026-11-06 | §16.12 | Three changes after the first run: (1) the primary truth is the Gain conditional on the test year's volatility path and cross-sections (closed form), because a block bootstrap within one year targets that, not the stationary Gain, which stays as a secondary truth; (2) the calibration must reproduce real 2019's in-sample Gain of R2 over R1 at κ = 1 within 0.01, with s_η and s_ε recalibrated if the moment estimates miss; (3) two fixed-path scenarios: 2019 → 2020's GARCH-filtered volatility path, and 2018 → 2019's. | The first run's coverage fell with κ and its estimates were about twice its stationary truth; its κ = 1 truth (about 0.01) was a tenth of real 2019's Gain, and its years were far less concentrated than 2020 (median top-10 share 0.27) | Yes: the first run's simulated results (kept as `_v1` files); no real-data outcome |
| 2026-11-06 | §16.12 | Two calibration adjustments in the revised run: the gamma term scaled by λ_g = 0.46 (realized over model-expected gamma error in 2019; the fitted Student-t tails, ν ≈ 5.1, make the model's gamma error about as large as the whole real Black–Scholes error), and s_ε rescaled per type (×1.16 calls, ×1.40 puts) so that the replayed 2019 reproduces real 2019's in-sample Gains exactly. Both are in `results/simulation/calibration.json`. | The moment calibration gave a replayed-2019 Gain of 0.05 (calls) and 0.09 (puts) against a real 0.17 and 0.19 | Yes: the first and second runs' simulated results; no real-data outcome |
| 2026-11-06 | §16.15 item 4 | Each underlying's own RV episodes use a threshold of twice its own 2016–2023 median 20-session realized volatility, in place of 25%. Split sessions are not returns. The S&P 500's episodes are unchanged. | SPX's 25% threshold is exactly twice its median (12.5%, 2010–2023); for TSLA and NVDA a fixed 25% is below their ordinary volatility, so most sessions would be stress | No: no outcome on the five underlyings had been computed |
| 2026-11-06 | §16.11–§16.14 | On SPX every rule, not only Heston's, is scored on the pairs with Heston Greeks, so that all rules share one sample. | One sample for all comparisons. The Heston Greeks cover the analysis sample (every B2 session converged): the books run reproduces the W12 walk-forward Gains of R2 over R1 to four decimals in every year | Yes: the SPX books results |
| 2026-11-06 | §16.11 | SPY's held positions can follow a contract only through days with a SPY implied volatility, and `build_greeks_spy.py` solves only day-one candidates (at least 14 days, two-sided, E7). So every SPY path day is traded and has at least 14 days to expiry, which reimposes the volume and maturity selection §16.11 avoids. SPY's held-position results are reported as this restricted version. SPX's Greeks cover every quoted contract-day, and so do the five underlyings'. Recomputing SPY's Greeks for every quote is the fix (1–2 hours), left for after submission. | Found 2026-11-06 from the Greeks files' status counts (SPY 2020: 987,138 of 2,328,802 rows `not_candidate`) | No result seen: the SPY held-position run had finished at 02:32, but its output was not opened before this entry (corrected 03:05; the entry first said none had been computed) |

## 16. Extension specifications (appended under §14's rule)

### 16.1 SPY (§14, item 9). Specified 2026-11-04, before any SPY hedging outcome

The author's choices of 2026-11-04: American pricing with the Lecture 12 library, and public data for SPY's close and distributions.
- **Data.**
  - OptionsDX SPY, step-3 panel built with the SPX rules (`DATA.md`). SPY is P.M.-settled throughout, and no stamp window is defined.
  - **Closes:** SPY's exchange close from Nasdaq's historical quotes (`data/external/nasdaq_SPY_history.csv`, from 2016-11). Sensitivity B is the vendor's snapshot.
  - **Distributions:** ex-dates and cash amounts from the sponsor's SPDR distributions file (`data/external/ssga_SPY_distributions.csv`).
  - The light audit of §7 runs on SPY 2018–2021 first.
- **Rates and dividends.**
  - **The rate** r(τ) is that session's SPX parity curve (§4).
  - **The yield.** q(τ) is SPX's implied carry, r(τ) − ln(F_e/S_A)/τ_e, from the SPX expiries 30 days to 2 years out, fitted linearly in τ (flat beyond), less SPY's 0.0945% expense ratio. S_A is the options-implied SPX level of §2, used so that the index-timing mismatch does not enter q.
- **Implied volatility and Greeks** at the mid:
  - **puts:** Lecture 12's American `bs_american_put_iv`, a CRR tree with 150 steps and the control variate, using r(τ) and q(τ). δ and ν are central differences on the same tree, with S bumped by ±0.5% and σ by ±0.01;
  - **calls:** Lecture 12's `bs_euro_iv` and `bs_euro_greeks`, with continuous yield q, as the lecture prices SPY calls. Early exercise of calls before ex-dates is ignored, a stated limitation;
  - only day-one candidates are solved: τ ≥ 14 days, two-sided, and E7 as for SPX.
- **The hedge P&L** includes the distribution: e = (Δf − h·(ΔS + Div·1{day two is an ex-date}))/S_t.
- **Design:** the SPX protocol of §5–§9 unchanged: E1–E8, W12 refitted monthly, 2019 training and 2020 test, rules R0–R5 (R6 needs vanna, which the tree does not give), the same bootstrap and Gains. Exploratory: no verdict. Results are reported beside SPX's, with SPY's own attrition.
- **Limitations stated in advance.** Continuous yield in the tree, not the discrete schedule; American calls priced as European; SPY options may trade after the 16:00 close (unverified).

### 16.2 Heston (§14, item 7). Specified 2026-11-04, before any Heston hedging outcome

The author's choices of 2026-11-04: both the lecture's calibration and a broader one; daily calibration over 2019–2020, compared on 2020.
- **The model and code:** Lecture 12's `heston_call` and `heston_european_greeks` (Gauss–Legendre, 256 nodes, the library's integration-limit heuristic). r and q per expiry come from that expiry's parity D and F, so the pricing forward matches §4's.
- **Calibration L (the lecture's).** SPX calls only, 50–100 days to expiry, 0.8 < S/K < 1.2, bid and ask sizes above 10, the Lecture 12 size-weighted price. Two fits each session with `scipy.optimize.least_squares` and the lecture's bounds (v₀ ∈ [10⁻⁴, 2.25], κ ∈ [0.1, 10], θ ∈ [10⁻⁴, 1], ξ ∈ [0.05, 5], ρ ∈ [−0.999, 0]): price errors, and implied-volatility errors.
- **Calibration B (broad).** SPX out-of-the-money calls and puts (calls K ≥ F, puts K < F), 14 days to 1 year, two-sided, E7, mids; implied-volatility errors; the same bounds.
- **Starting values.** January 2019 starts at (v₀, κ, θ, ξ, ρ) = (0.04, 2, 0.04, 0.5, −0.7). Every fit in a later month starts from the median of the previous month's successful calibration-B solutions, so the sessions within a month can run in parallel. A fit needs at least 10 options. A fit is *failed* if least_squares does not converge or any parameter sits within 10⁻⁶ of a bound. Fit quality and failures are reported per session.
- **Hedging, on the 2020 analysis sample,** with the day-one parameters of calibration B:
  - the Heston model delta, C_S;
  - the Heston minimum-variance delta, C_S + (ρξ/S)·C_v. C_v is a central difference in v₀ (±1% of v₀), and S moves with the forward fixed in carry.
  - Both are compared with R1 and R2 on the pairs where calibration B succeeded on day one, using the same bootstrap. Exploratory: no verdict. 2019 serves as the calibration warm-up and parameter-path illustration, not as a test.
- **Compute.** Calibrations run in parallel within each month and are logged in the runtime log.

### 16.3 SPY, a full replication of the SPX protocol. Specified 2026-11-05

This replaces §16.1's design; §16.1's pricing choices stand except where stated here.

**Data**
- **Panels:** step-3 panels for 2010–2023 under the SPX rules (`DATA.md`). SPY is P.M.-settled, and no stamp window is defined.
- **The index level `S_close`:**
  - from 2016-11-03: Nasdaq's close;
  - before 2016-11-03: Stooq's daily close (`data/external/stooq_spy_us_d.csv`), with its dividend adjustment reversed. Going back from the file's last session with a factor f = 1, at each SSGA ex-date e the factor for every earlier session becomes f / (1 + f·Div_e / C̃_{e−1}), where C̃_{e−1} is Stooq's adjusted close on the session before e. The close is then C̃/f.
  - **The check, on 2016-11-03 to 2024-01-31 (1,821 sessions):** the level gap to Nasdaq has median 0.43 bp and maximum 2.3 bp, with a bias of −0.4 bp that grows further back. The one-session return gap has median 0.14 bp and 99th percentile 1.7 bp.
  - `S_close_source` records which series each session uses. Sensitivity B remains the vendor's snapshot.
- **Light audit:** §7's audit on every SPY year, 2010–2023, before any of that year's outcomes is computed.
- **Greeks:** §16.1's method for every year: puts on the 150-step CRR tree with the control variate, calls European. For puts, two more central differences on the same tree:
  - **vanna,** ∂δ/∂σ with σ ± 0.01, each δ from S ± 0.5% (for R6);
  - **theta,** from the price at τ and at τ − 1/365 (for sensitivity T).
  - **The attribution of §8 is run for calls only.** It is a European forward-form expansion and is not defined for the tree's puts.
- **Pairs:** as in §16.1, with each pair's day-two distribution in the hedge P&L.

**The protocol** is that of §§5–10 and §14 item 2, with these differences:
- **Sensitivity A is not applicable.** American put–call parity gives only bounds, so there is no options-implied level. A leaves both Table 8.1 and the robustness set.
- **The endpoint band for vanished quotes** is [L, ask]. L is the day-two intrinsic value: an American option is worth at least that. No parity band is used.
- **The rehearsal (§10)** runs on SPY 2018 and 2019, specification checks included. The variants that contradict R2's form there are carried to SPY's 2020.
- **R8** is tuned on SPY 2019 with §7's design (60 trials per type) and then frozen for 2020.
- **The dry run:** the test-year script with SPY 2019 as the test year.
- **2020:** the test year, with R0–R8, every Table 8.1 variant except A, and the verdict table with its robustness set (without A).
- **The walk-forward, 2010–2023:**
  - windows of 12, 36 and 60 months, testing from 2011, 2013 and 2015;
  - rules R0–R8;
  - R8's hyperparameters as in §16.4: tuned on SPY 2010 for test months up to 2016-12, and on SPY 2015–2016 for months from 2017-01.

**Status**
- **SPY 2020 is post hoc.** Its Gains for R0–R5 (primary and B) were seen on 2026-11-04. Its verdict is therefore reported as the confirmatory procedure applied after the outcome was seen.
- **The SPY year ledger:**
  - 2018 and 2019 are evaluated in the rehearsal, and 2019 is also the R8 tuning year;
  - 2010 and 2015–2016 are R8 tuning years for the walk-forward;
  - 2020 has been seen;
  - **2011–2014, 2017 and 2021–2023 are the clean held-out SPY years.**
- The results are reported beside SPX's, with SPY's own attrition, and the ex-date pairs are reported separately each year.

### 16.4 R5–R8 under every protocol. Specified 2026-11-05

**2020, SPX**
- **Variants that refit:** R7 and R8 join every Table 8.1 variant that refits: A, B, P-bid, P-ask, P-WM, P-SW, T, F, W36 and W60. They are refitted on that variant's training data, with R8's 2019 hyperparameters frozen. Under F, the one fit uses 2019 pairs ending before 2020-01-02.
- **Subsample variants** use the primary R7 and R8 fits: S3, V, OTM, stress, the rest of 2020, the day-two-volume split, and block lengths 5 and 20. OTM-refit keeps the primary R7 and R8 fits, as it does for R5 and R6.
- **R7 and R8 are compared on each variant's feature-complete pairs,** with R2 re-reported there.
- **The endpoint scenarios are not run for R7 and R8.** Their effect on R2 was in the third decimal (2026-11-04).

**The walk-forward, SPX 2010–2023**
- R5 and R6 (least squares), R7 and R8 for W12, W36 and W60, over each window's test span.
- **R8's hyperparameters:**
  - for test months from 2017-01: the 2015–2016 tuning;
  - for test months up to 2016-12: a new tuning on 2010, using §7's design moved to 2010. That means trailing 6-month windows, test months 2010-07 to 12, validation pairs ending before 2011-01-03, and 60 TPE trials per type (seed 2026), then frozen.
- **Reported:** per year and window, the Gains of R5–R8 over R1 and over R2, with session-block intervals, and the median yearly Gains over 2015–2023.

**Status:** exploratory, with no verdict. Their 2020 primary results, and R8's 12-month walk-forward for 2017–2023, were seen before this specification.

### 16.5 Heston, rewritten. Specified 2026-11-05

This replaces §16.2's code; its sample and bounds are kept.

**The pricer:** project code, `erdos_quant_finance_project/heston.py`.
- **The formula:** Lewis's formula with the Black–Scholes control variate, using the Albrecher et al. form of the characteristic function, as in Lecture 12's library.
- **The integration:** composite Gauss–Legendre panels whose width resolves the strike oscillation, out to the library's integration-range heuristic.
- **Its outputs:** C_S at fixed variance, as the library defines it, and C_v = ∂C/∂v₀ in closed form.
- **Tests:** within 0.01 vol points of an adaptive-quadrature reference on a grid of 14 days to 1 year, K/F 0.6–1.3, and parameters spanning the lecture's bounds, including 2020's fits.

**Calibration B2**
- **Sample and bounds:** calibration B's sample, unchanged: out-of-the-money calls and puts, 14 days to 1 year, two-sided, E7, mids, at least 10 options. The lecture's bounds.
- **The residuals:** (model − mid)/ν, where ν is the option's Black–Scholes vega at its own IV, floored at 1% of the at-the-money vega of its expiry. That is a first-order implied-volatility error, with no inversion inside the loop.
- **The solver:** scipy's `least_squares` (trf, bounds, `x_scale="jac"`), with a central-difference Jacobian. The strike terms are precomputed per session, and at most 300 function evaluations are allowed.
- **A fit succeeds** when `least_squares` stops on a tolerance (status ≥ 1).
- **Starts:** two per session, keeping the lower cost:
  1. the previous session's solution in the same calendar year;
  2. a data start, v₀ = θ = σ_ATM² of the nearest expiry at least 14 days out, with κ = 2, ξ = 1, ρ = −0.7.

  The first session of each year uses the data start and the lecture default (0.04, 2, 0.04, 0.5, −0.7).
- **Reported per session:**
  - wall and CPU time;
  - function and Jacobian evaluations;
  - the cost;
  - the exact IV RMSE at the solution;
  - bound hits (within 0.1% of the range);
  - an accuracy check at the solution, comparing a doubled range and node count. Any change above 0.05 vol points is flagged.

**Timing, before the full run.** The old calibration B (library, three starts) and B2 run alone, in one process, on the same 20 sessions: every 25th session of 2019–2020, plus 2020-03-16. Then the full run goes one process per calendar year, years in parallel, and is logged in the runtime log.

**Years:** calibration on every session of 2010–2023.

**Hedging,** per year on the SPX analysis sample, using pairs whose day-one calibration succeeded:
- **The three Heston deltas:**
  - H_model = C_S;
  - H_mv = C_S + (ρξ/S)·C_v;
  - H_fit = C_S + β̂·C_v/S, with β̂ fitted per option type by least squares without intercept. The regression is of (Δf − C_S·ΔS)/S_t on C_v·ΔS/S_t², over the trailing 12 months with §7's boundary rule, applied one month out. Test months start in 2011-01.
- **Comparisons:** with R1 and with R2 (the walk-forward's 12-month fits) on the same pairs, per year, with the session bootstrap.
- **The β̂ path** is reported beside the calibrated ρξ, which is what H_mv uses. 2020 is also compared with §16.2's library-based results.

**Status:** exploratory, with no verdict. The library-based 2020 results have been seen.

### 16.6 Short-dated SPX options (§14, item 3). Specified 2026-11-05

- **The sample:** §5, with E5 replaced by τ < 14 days on day one and τ > 0 at day two's snapshot. So the pair ends before settlement: for a P.M. contract the last pair ends on the session before expiry, and for an A.M. monthly on the session before its settlement morning. Every other rule is unchanged.
- **The rules:**
  - R1;
  - **R2s,** R2 refitted on short-dated training pairs (12-month window, monthly refits, §7's boundary rule, at least 150 sessions);
  - **R2m,** R2 with the main study's 12-month coefficients, fitted on options of at least 14 days, applied to the short-dated pairs.
- **The tests:** 2020, and the 12-month walk-forward over 2011–2023. Reported: the Gains of R2s and R2m over R1, and of R2s over R2m, per year, with the session bootstrap, plus day-one maturity buckets of 1–2, 3–6 and 7–13 days.
- **Status:** exploratory.

### 16.7 R9–R11: the boosted learner, decomposed. Specified 2026-11-05

At the author's request, after the results of §16.3–§16.6 (R8's among them) were seen. With R8, these rules form a 2×2 design: the learner is either fitted from scratch or boosted from R2's polynomial, and its input is either δ alone or R8's six features z.

| Rule | Hedge ratio | From scratch or boosted | Input |
|---|---|---|---|
| R9 | δ + ν/(S√τ)·h(δ) | from scratch | δ |
| R10 | δ + ν/(S√τ)·h(z) | from scratch | z |
| R11 | δ + ν/(S√τ)·[a + b·δ + c·δ² + h(δ)] | boosted from R2 | δ |
| R8 (§6) | δ + ν/(S√τ)·[a + b·δ + c·δ² + h(z)] | boosted from R2 | z |

- **The learner:** LightGBM on the weighted regression of y/x, with weights x² rescaled to mean 1 (§7). Pairs with x = 0 are left out of the fit and kept in evaluation.
  - **R9 and R10** start from LightGBM's weighted mean of the target (`boost_from_average`), so a fully regularized h is a constant correction.
  - **R11** starts from R2's fitted polynomial on the same window, as R8 does, so a fully regularized h gives R2 back.
  - Everything else is as for R8: CPU, feature_fraction 1, no bagging, min_data_in_leaf 20, deterministic, seed 2026, 8 threads, no early stopping.
- **Tuning:** R8's search space and design, separately for each rule and option type: Optuna TPE (seed 2026), 60 trials, the rehearsal folds.
  - for 2020: SPX 2019, and SPY 2019 for SPY;
  - for the walk-forward: 2010 for test months up to 2016-12, and 2015–2016 from 2017-01, as in §16.4. Frozen after tuning.
- **Protocols:** R8's, on SPX and SPY.
  - **2020:** the primary, and the Table 8.1 variants. Variants that refit do so with the frozen hyperparameters; subsample variants use the primary fits. There are no endpoint scenarios, as §16.4.
  - **The walk-forward:** 2011–2023 on W12, W36 and W60.
  - **The sample:** the feature-complete pairs, with R2's all-pairs fit re-reported there.
- **Reported:** the Gains over R1, R2 and R8, with session-block intervals. In the walk-forward, per year and window, the median yearly Gains over 2015–2023, and R8's §16.4 results on the same pairs.
- **Status:** exploratory, with no verdict.

### 16.8 The degree of R2's polynomial, 0 to 8, and a validated choice. Specified 2026-11-05

At the author's request, after the results of §16.3–§16.7 were seen; the R9 analysis found that a constant matched R2's quadratic out of sample in 2019.
- **Rules P0–P8:** Hull–White's form with a polynomial of degree k in δ: δ + ν/(S√τ)·p_k(|δ|). Each is fitted by least squares without intercept on §7's normalized scale, per option type, with the rehearsal's Legendre basis in |δ| (the band [0.05, 0.95] mapped to [−1, 1]).
  - P2 spans the same functions as R2 and must reproduce it, a check on the code.
  - P0 is the one-parameter rule δ + c·ν/(S√τ).
- **Rule PCV, the degree chosen by validation inside each training window.**
  - **The folds:** at each monthly refit, every degree 0–8 is fitted on the window's months before each of its last three months, and scored on that month. Only pairs whose day two falls before the validation month's first session enter the fit.
  - **The choice:** the degree with the lowest validation SSE, pooled over the three months, is refitted on the whole window and applied to the test month.
  - **What it uses:** pairs ending before the test month's first session only.
- **Protocol:** the walk-forward of §14 item 2, 2011–2023, on W12, W36 and W60, for SPX and SPY (§16.3), with the §7 boundary rule and the 150-session minimum.
- **Reported:**
  - per year and window, every rule's Gain over R1 and over R2, with session-block intervals;
  - the median yearly Gains over 2015–2023;
  - PCV's chosen degrees.

  Since nine fixed degrees are compared, the best of them is not a validated result; PCV is.
- **Status:** exploratory, with no verdict.

### 16.9 Two descriptive diagnostics. Specified 2026-11-05

At the author's request, after every result above had been seen. Both are descriptive; neither adds a rule or a test.

1. **Comparison with the published aggregations, SPX.** For the walk-forwards on W12 (test months 2011–2019) and W36 (2013–2019), with R1–R4 under §7's protocol:
   - **Three aggregations of the Gain over R1:**
     - pooled per year, as reported throughout this plan;
     - the mean of monthly Gains, Hull and White's aggregation;
     - the mean over months of the Gain within each of their nine delta buckets (|δ| rounded to the nearest tenth), their Table 1.
   - **Three samples:**
     - the analysis sample;
     - the same pairs without E7, the day-one volume rule (Hull and White apply no volume rule);
     - the out-of-the-money subsample (Ruf and Wang's population: calls with K ≥ F, puts with K ≤ F).
   - **Reported** over Hull and White's overlapping years (2011–2015 on W12, 2013–2015 on W36) and Ruf and Wang's (2012-07 to 2019-06).
   - **The pairs without E7** are evaluated here only; that changes no other result.
2. **The level and the shape of the correction, SPX and SPY, 2011–2023 on W12.**
   - **Per monthly refit:**
     - the constant c of P0 (§16.8), fitted on the training window;
     - the constant that fits the test month best, after the fact;
     - R2's average correction, the x²-weighted mean of a + bδ + cδ² over the training pairs.
   - **Per year:**
     - the Gain of P0 over R1 (the level);
     - the Gain of R2 over P0 (the shape added to it);
     - the Gain of P0 with the after-the-fact constant over R1, a ceiling for the level;
     - and, for SPX, the spot–volatility slope of `scripts/spot_vol_slope.py` beside them.

### 16.10 Stress periods, parameter stability and the maturity assumption, 2010–2023. Specified 2026-11-05

At the author's request, after every result above had been seen. All descriptive, for SPX and SPY. The brief's model-validation direction names "stress-test assumptions" and "study parameter stability".

1. **Stress episodes, defined from the S&P 500 close alone.** Both definitions are fixed here, before any episode's Gains are computed.
   - **RV:** sessions whose trailing 20-session realized volatility (√252 × standard deviation of daily log returns) exceeds 25%. Runs separated by 10 sessions or fewer are merged into one episode.
   - **DD:** drawdowns of 10% or more from the running peak, from the peak to the trough.
   - **Reported for each episode, and for each year's RV-stress and calm sessions:**
     - the out-of-sample Gains (W12 and W36) of R2, R3, R4, R5, R6 and P0 over R1 and over R2, pooled within the episode, with a session-block bootstrap inside it (block length the smaller of 10 and a fifth of its sessions);
     - the episode's share of the year's Black–Scholes squared error;
     - the constant correction that fits the episode best after the fact, against the one fitted beforehand.
   - The 2020 stress window of §8 (2020-02-24 to 04-30) is reported beside them for reference.
2. **Parameter stability**, at every monthly refit of W12, W36 and W60, 2011–2023.
   - **What is estimated:**
     - R2's (a, b, c);
     - R4's â;
     - P0's constant c, which equals R2's loss-weighted average correction (`level-and-shape-of-the-correction.md` §3).
   - Each has session-clustered standard errors and, for R2, the correlations between its coefficient estimates.
   - **Summaries per window and coefficient:**
     - the range;
     - the median month-to-month change relative to its standard error;
     - for W12, the z-statistic between fits 12 months apart, whose windows do not overlap, and the share of |z| > 2 (a Chow-type comparison).
   - **Heston:** the daily calibration-B2 parameters' yearly median, interquartile range, median day-to-day change and share at a bound.
3. **The maturity assumption, by year.** The specification check of §10 (τ^(−α) in place of 1/√τ, α ∈ {0, 0.25, 0.5, 0.75, 1}), run on the 12-month walk-forward for every test year 2011–2023 and for the RV-stress and calm sessions. Reported: each α's Gain over α = 0.5, with intervals. Unadjusted, so descriptive.

### The rules scored from §16.11 on. Fixed 2026-11-06

The author's choice, before any experiment from §16.11 on had run. Every experiment specified from here on scores the same rules, unless its section says otherwise:
- R1, R2, R3, R4, R6, R9 and P0;
- on SPX, also Heston's H_model, H_mv and H_fit (§16.5);
- R0 wherever an effectiveness figure is needed.

Fitting and tuning:
- **R9** keeps the hyperparameters frozen for its walk-forward (§16.7). No rule is retuned.
- **Not carried forward:** R5, R11, P1–P8 and PCV, which are equal to R2 within ±0.02 a year; and R7, R8 and R10, which are worse (§16.4, §16.7, §16.8).

### 16.11 Holding-period hedging error. Specified 2026-11-05; revised 2026-11-06, before any run

At the author's request, after every result above had been seen. Descriptive.

**The question.** The verdict scores one-session hedges. A desk holds a position and re-hedges it every day: does the one-session Gain carry over to the error of a position held for several sessions? A Summer 2026 project on simulated data found a 46% one-session Gain and no gain at all over a contract's life.

**Paths**
- **A path is H one-session hedges in a row,** not one hedge held for H sessions. The position in one contract (keyed as in §2) is re-hedged at every close, with that day's hedge ratio from the rule, as a desk would do. H ∈ {5, 10} sessions.
- **Starts:** every H-th session of the test period, numbered from its first session. So the paths of one length never overlap in time, and all paths that start on one session share one index path.
- **At the start,** the path's first pair is in the analysis sample (§5), so the start uses day-one information only. The contract also expires after the path's last session (by the NYSE calendar), so it is alive throughout.
- **Every later day needs only a usable hedge:** a two-sided quote on both ends and an implied volatility and Greeks on that day, from the Greeks panel, which covers every quoted contract-day.
  - No delta band, maturity floor or volume rule applies after the start.
  - Requiring them would select on the path's outcome: an option leaves the band exactly when the index moves a lot, so the paths that leave are the large-error ones. The same reasoning is why §5 conditions on day one only, never on day two.
  - A path with a missing day is dropped and counted.

**Hedge ratios**
- Each day's ratio comes from the fit for that day's month on W12 (in 2020, the test-year fits).
- The rules are those of the preamble above. On days outside the band, a fitted correction is evaluated at that day's δ, an extrapolation that is reported as such.
- **Heston's** Greeks exist only for analysis-sample pairs. So the Heston rules are reported on the paths whose every day is in the analysis sample, with every other rule re-reported on that subset.

**The path error,** in units of the index level on the start day:
  E = Σₖ Sₖ·eₖ / S₀,
where eₖ is the one-session normalized error of §6 and Sₖ the level. The option-price changes telescope, so quote noise in the mids enters only at the path's two ends.

**Reported for each year and H**
- Gain_H = 1 − ΣE²(rule)/ΣE²(R1), over R1 and over R2.
- Beside it, the one-session Gain on exactly the same pairs (the H = 1 reference).
- Each rule's mean path error, and its difference from R1's. This is the expected-P&L cost of the correction, which the Sharpe argument assumes is negligible.
- Attrition: the share of eligible starts that complete their path, by year and by whether the path left the band.

**Intervals:** a circular block bootstrap over start sessions, with blocks of max(1, round(10/H)) starts and B = 10,000.
- With H = 10, a year has about 25 starts, so the yearly intervals are rough.
- For SPX and SPY, 2011–2019, 2020 and 2021–2023 are also reported pooled.

**Underlyings:** SPX and SPY, 2011–2023 (no Heston for SPY), and the five of §16.15.

### 16.12 Interval coverage and power under a known truth (simulation). Specified 2026-11-05

At the author's request, after every result above had been seen. This is §14 item 8 in a form that runs overnight. The rule set of the preamble does not apply: the simulation's truth lies in R2's family, and it scores R2 against R1, the comparison behind H1.

**The question.** The verdict rests on §9's session-block intervals, in a year when ten sessions hold 65–73% of the error. Do the intervals cover the truth at the nominal rate under that concentration? And how large a true Gain would §8's H1 criterion confirm in such a year?

**A regression-level market, not an option-pricing one.** It keeps what matters for inference: every option on a session shares that session's index move, the error comes in volatility bursts, and coefficients are fitted on one year and applied to the next.
- **Index returns:** r_t = σ_t·z_t, a GARCH(1,1) with standardized Student-t innovations, fitted by maximum likelihood to the S&P 500's daily log returns over 2010–2019 (the closes of §2).
- **The cross-section:** each simulated session copies the options of a randomly drawn real 2019 session: type, δ, v = ν/(S√τ), τ, and the gamma coefficient g = ½Γ·S. It is subsampled to at most 300 options per type.
- **The Black–Scholes error:**
  y_it = κ·q(δ_i)·v_i·r_t + v_i·η_t + g_i·(r_t² − σ_t²) + v_i·√τ_i·σ_t·s_ε·ε_it,
  where:
  - q(δ) is 2019's fitted R2 quadratic for that type, and κ ∈ {0, 0.5, 1, 1.5, 2} sets the true effect;
  - η_t = s_η·σ_t·w_t is the part of the session's volatility move that the index doesn't explain, with w_t a standardized Student-t independent of z_t;
  - the third term is gamma's P&L net of theta, at the session's true variance;
  - ε_it is i.i.d. standard normal.
- **Calibration:** s_η and s_ε by moments, from 2019's real R2 errors scaled by each session's GARCH-filtered σ_t. s_η comes from the session means of e/v, and s_ε from the deviations within a session.

**One replication**
- Simulate 252 training and 252 test sessions from the stationary GARCH, after 500 burn-in sessions. Calls and puts share the returns, η_t and the session draws.
- Fit R2 on the training year (§7; one fit stands in for the monthly refits).
- Compute the test year's R1 and R2 errors, and §9's interval for R2 over R1, with blocks of 10 and B = 2,000 (not 10,000, for time).
- 1,000 replications for each κ.

**The truth:** G(β̂) = 1 − E[(y − β̂ᵀX)²]/E[y²] under the stationary law. It is computed in closed form in β̂, from the moments of one long simulation (200 years) per type and κ.

**Reported**
- Coverage of the 95% interval, over all replications and over the "2020-like" ones: those whose test year puts at least 50% of R1's squared error in its ten largest sessions (2020 had 65–73%).
- The median interval width.
- The H1 pass rate (both types' lower bounds above 0), against the mean true Gain, for all years and for 2020-like years.

**Revised 2026-11-06, after a first run (§15).** The primary truth is G_cond(β̂), the Gain conditional on the test year's volatility path and cross-sections, in closed form; the stationary truth is secondary. The calibration must reproduce real 2019's in-sample Gain of R2 over R1 at κ = 1 within 0.01. Two fixed-path scenarios are added: training on 2019's and testing on 2020's GARCH-filtered volatility path, and 2018's then 2019's.

**Limits, stated in advance.** The spot–volatility relation here is stationary and linear in r_t, with no drift in the level. Coverage here is therefore a best case: real years add the drift of §16.10.

### 16.13 Training-data starvation. Specified 2026-11-05; revised 2026-11-06, before any run

At the author's request, after every result above had been seen. Descriptive.

**The question.** How much training data do the fitted rules need, and in which unit?

**The expectation, stated now.** Every option on a session shares that session's index move, so the information is in the number of sessions, not the number of options. Thinning the options within each session should cost little until very few remain; shortening the window should matter.

**Rules:** the preamble's.
- H_model and H_mv are fitted to no hedging data, so they are reported once, as references.
- H_fit's β̂ is trained on the shortened or thinned data, like the other fitted rules.

1. **Fewer sessions.**
   - **Windows:** W ∈ {1, 2, 3, 6} months, refitted monthly under §7's boundary rule, beside W12.
   - **Minimum training coverage:** ⌈0.7·21·W⌉ sessions per type (15, 30, 45, 89), in place of §7's 150, which only W12 and longer can meet.
   - **Test months:** SPX and SPY 2011-01 to 2023-12; the five of §16.15 2017-01 to 2023-12. Common months only.
2. **Fewer options per session.**
   - **Window:** W12, with the test pairs unchanged.
   - **Thinning:** within each training session and type, keep a random fraction φ ∈ {0.25, 0.05, 0.01} of the pairs (at least one), or a fixed k ∈ {10, 3} pairs.
   - **Seeds:** five, 2026 to 2030.
   - **Chronology:** thinning happens inside the chronological training window and never touches the test set, so this is not a random train/test split.

**Reported, for both axes**
- The yearly Gain over R1 and over R2 (full-data W12), with session-block intervals as in §14 item 2.
- The median yearly Gain over 2011–2023 and over 2015–2023 (for the five, 2017–2023).
- The change from the full-data W12 fit, on common months.
- 2020 and 2022 shown separately: there a short window could adapt faster to a changed level.
- For thinning, the spread over the five seeds: the minimum, median and maximum of each yearly Gain and of the median yearly Gain.

**Underlyings:** SPX, SPY and the five of §16.15.

### 16.14 Hedging error at the level of a book. Specified 2026-11-05; revised 2026-11-06, before any run

At the author's request, after every result above had been seen. Descriptive.

**The question.** The Gain pools every option's squared error as if each were hedged alone, but a dealer hedges the net delta of a book. Errors specific to one option diversify away across a book, while errors common to the session, which the minimum-variance correction targets, add up. Is the Gain on a book larger or smaller?

**Books,** formed each session from that session's analysis pairs, using day-one information only, with one contract of each option:
1. all calls;
2. all puts;
3. a long-volatility book: out-of-the-money puts (K ≤ F) and out-of-the-money calls (K ≥ F), all long;
4. a risk reversal: long out-of-the-money calls and short out-of-the-money puts. Their volatility exposures partly cancel, so the corrections should partly cancel too. This book is the control.

**The book's error** on a session is the mean of its options' normalized errors (weights 1/N_t). That way the growth in listed strikes over the years doesn't weight the later sessions more.

**Reported for each year 2011–2023 on W12** (the five of §16.15: 2017–2023), with 2020 and 2022 shown separately in the summaries:
- the book Gain 1 − Σ_t B_t(rule)²/Σ_t B_t(R1)², for the preamble's rules, over R1 and over R2, with §14 item 2's session-block intervals;
- beside it, each book's pooled per-option Gain;
- the common share Σ_t B_t(R1)² / Σ_t mean_i e_it(R1)², the part of the per-option error that survives averaging.

**Underlyings:** SPX, SPY and the five of §16.15.

### 16.15 Single stocks and ETFs: the SPY protocol on five underlyings. Specified 2026-11-05; revised 2026-11-06, before any run

At the author's request, after every result above had been seen, and before any outcome on these underlyings was computed. Exploratory; no verdict.

**Context:** Hull and White's Table 3 (2004–2015, 36-month window) gives an average Gain over the 30 Dow stocks of 10.3% for calls and 2.5% for puts, and 7.7% and 2.5% for three commodity ETFs.

**Data**
- **The files:** `data/raw/optionsdx_stocks/`, 75 archives with `SHA256SUMS`, downloaded by the author on 2026-11-05. They cover AAPL, NVDA and TSLA (single stocks), QQQ (an index ETF) and SLV (a silver ETF; Hull and White used it among their commodity ETFs), for every month from 2016-01 to 2023-12.
- **One anomaly:** TSLA's 2021 archive holds an empty July file. The July file in the 2021q3 archive is used.
- **Format:** the same 33 columns as SPX and SPY; the project's parser reads them unchanged. In the month checked, volume never exceeds 998, so E7's reading of empty volume applies.

**The pipeline, as for SPY (§16.1, §16.3)**
- **Panels:** interim and step-3 panels under the SPY rules: P.M.-settled, no stamp window, NYSE sessions.
- **The level:** the vendor's `UNDERLYING_LAST` is the primary S, and `S_close`, for these five.
  - Why: no official close for them is in hand without reversing split and dividend adjustments (Stooq's files are adjusted for both).
  - On SPX, the snapshot sat a median 0.7 bp from the official close.
  - Level B is therefore the same series, and level A doesn't exist for American options.
- **Splits:** a pair whose two sessions straddle a split is excluded and counted.
  - Splits are identified by a one-session move in `UNDERLYING_LAST` above 30%, and checked against AAPL 4:1 (2020-08-31), NVDA 4:1 (2021-07-20), and TSLA 5:1 (2020-08-31) and 3:1 (2022-08-25).
  - Hull and White also removed split days.
- **Rates:** r(τ) from the same session's SPX parity curve (§16.1).
- **Dividends:**
  - TSLA and SLV pay none, so q = 0.
  - For AAPL, NVDA and QQQ: cash dividends (ex-date and amount) from a public dividend history, with its source and download date in `data/external/SOURCES.csv`. Pricing uses q = the trailing 12 months' dividends over the price, as a continuous yield. Each pair's day-two dividend enters the hedge P&L as `div_next` (§16.3).
  - If no history can be obtained, q = 0 and `div_next` = 0, flagged.
- **Implied volatility and Greeks:** our own, as for SPY.
  - Puts use Lecture 12's American CRR tree, with δ, ν and vanna by differences on the tree.
  - Calls use the European Black–Scholes formula with yield q. That is exact for TSLA and SLV, where an American call is never exercised early, and an approximation for the dividend payers, as for SPY.
  - The vendor's Greeks are a diagnostic only. So there is no out-of-the-money restriction: the full band, as for SPX and SPY.
- **Pairs:** SPY's pair rules (§16.3).

**The protocol, for each underlying separately.** The SPY protocol of §16.3, with these items:
1. The light audit and the attrition table (§7, §12), before any outcome.
2. **2020 as the test year,** with 2019 training on W12, under §8's verdict procedure (H1 and the secondary tests), as a descriptive replication, not a confirmatory test.
   - Robustness variants: W36, F, S3, V, and the rest of 2020 (outside the stress period).
   - Not run: level A (none exists), the marks, and the vanished-quote scenarios.
3. **The walk-forward:** W12 from 2017-01, W36 from 2019-01 and W60 from 2021-01, to 2023-12. Yearly Gains and the median yearly Gain.
4. **§16.10:**
   - stress episodes: the S&P 500's, as market-wide stress, and each underlying's own RV episodes, with the threshold at twice its own 2016–2023 median 20-session realized volatility (§15, 2026-11-06);
   - parameter stability;
   - the maturity check.
5. **§16.9 item 2:** level and shape, with the after-the-fact ceiling.
6. **§16.11, §16.13 and §16.14.**
7. **Hull and White's Table 3 comparison:** the mean of monthly Gains on W36, overall and by |δ| tenth.

**Rules:** the preamble's, without Heston. R9 uses SPX's frozen hyperparameters.

**Not run, with reasons:**
- Heston: a daily calibration to American options on five underlyings doesn't fit the time;
- short-dated options (§16.6);
- the published-aggregation comparison other than Table 3;
- the rules dropped in the preamble.

**Year status:** every year of these five is untouched until these runs. Rows are added to `results/year_ledger.csv`.
