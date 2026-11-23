# Incrementality: which method when

Incremental effect = what happened with the campaign minus what would have happened without it.
The second term is never observed; each method builds it differently.

| Situation | Method | What it assumes | Main risk |
|---|---|---|---|
| You control who receives it (CRM, push, e-mail, in-app) | **Randomised holdout** (10%) + SRM check + CUPED | randomisation worked (check the sample ratio) | too small a holdout: compute the minimum detectable effect first |
| One region (or market) treated, others not | **Difference-in-differences** (region and day fixed effects, errors clustered by region) | parallel trends without the campaign | other campaigns or shocks in the control regions; few clusters make intervals too narrow |
| One treated region, a handful of candidate controls with different levels | **Synthetic control** (weighted donors fitted on the pre-period) | the weighted donors track the treated region before the launch | poor pre-period fit; inference by placebo-in-space only |
| No control at all (global launch) | **Naive before/after** only, labelled as such, + **placebo in time** | nothing else changed | trend, market and seasonality are counted as campaign effect |
| Many overlapping campaigns, public data only | **Event study with placebo dates** and a minimum detectable effect | | overlap: usually nothing can be isolated - say so |

## Outcomes measured per campaign type (simulated exchange)
- acquisition (`new_user`, `referral`, `learn_quiz`): sign-ups of the campaign's region and channel
  (whole region for CMP014, which ran on every channel through partner codes);
- deposit and Earn (`deposit`, `earn_apr`, `p2p`): repeat deposits of the region;
- trading (`trading_competition`, `alpha`, `tokenized_stock`, `pay`, `other`): trades of the region;
- CRM: 14-day reactivation of the targeted users, against the holdout.

## Checks before believing a number
1. **Placebo in time**: the same estimator with a fake start 14 days earlier should give about zero.
2. **Pre-trend plot**: treated vs controls before launch.
3. **Market**: compare with the real BTC volume and volatility of the days (the "cycle").
4. **Contamination**: list the other campaigns live in treated and control regions.
5. **Interval**: report the interval and the minimum detectable effect, not just the point estimate.

The simulated study checks every method against the planted truth (`data/processed/methods_vs_truth.csv`).
