# Statistics notes (plain language)

Every method below is implemented in `src/stats.py`, one function per idea, so each number can be re-derived.

## Wilson interval (proportions)
For a rate x/n, the usual "p +/- 1.96 x standard error" goes wrong for small n or rates near 0 or 1. Wilson's
interval re-centres and stays inside [0, 1]. Used for funnel and retention rates.

## Bootstrap
Resample the units (users, addresses) with replacement many times, recompute the statistic, read the 2.5% and
97.5% quantiles. For a share of independent addresses, resampling addresses is the same as drawing
binomial(n, p): that is how the on-chain retention intervals are computed.

## Difference-in-differences (DiD)
Effect = (treated after - treated before) - (controls after - controls before). Implemented as a regression of
log(1 + outcome) on region and day fixed effects plus a "treated and after" dummy; standard errors are clustered
by region. **Condition: parallel trends** - without the campaign, treated and controls would have moved together.
Check it with the pre-period plot and a **placebo in time** (fake start 14 days earlier must give about zero).
With only 9 regions (clusters) the intervals are too narrow; the methods-vs-truth table shows it.

## Synthetic control
Instead of all other regions, use a weighted mix of them (weights >= 0, summing to 1) that best reproduces the
treated region before launch. The effect is the gap after launch minus the gap before. Inference: repeat the
exercise pretending each donor was treated (placebo in space); the interval used here is the 90th percentile of
those placebo gaps.

## Randomised holdout, SRM, CUPED, minimum detectable effect
- **SRM**: a chi-square test that the 90/10 split happened as planned; a tiny p-value means the assignment is
  broken and the result should not be read.
- **Difference with interval**: z-test on two proportions.
- **CUPED**: subtract theta x (pre-period activity - its mean) from each user's outcome, with
  theta = cov(pre, outcome) / var(pre). Same expected difference, smaller variance.
- **MDE**: (1.96 + 0.84) x standard error: the smallest effect detected 80% of the time at 5% significance.
  Holdout size for a target effect: `tools/holdout_planner.py` and the workbook.

## Kaplan-Meier
Time to first deposit when some users have not deposited **yet**: at each time, survival is multiplied by
(1 - events / users still at risk). Censored users leave the risk set without counting as "never".

## Event study with placebo dates and Benjamini-Hochberg
For each real campaign start: log(mean of the 7 days after / mean of the 14 days before) on a market-adjusted
series. The same statistic on 1,000 random dates gives the "no campaign" distribution: its 97.5th percentile of
absolute values is the smallest effect that could stand out (MDE). Many campaigns tested at once inflate false
positives: Benjamini-Hochberg q-values control the false discovery rate.

## Mix effect (Simpson) and direct standardisation
A total can fall while every group rises if the weight of a low-value group grows. Direct standardisation
recomputes every period with **one** reference mix (the average mix), so only the within-group changes remain.

## Monitoring: control charts and CUSUM
Control chart: alert when a value leaves mean +/- 3 standard deviations of a baseline. CUSUM accumulates small
standardised deviations and alerts when the sum passes a threshold (k = 0.5, h = 5). Growing series need rolling
baselines (median of the previous days), otherwise fixed limits fire every day. The backtest replays the rules
day by day and counts true, false and missed alerts.
