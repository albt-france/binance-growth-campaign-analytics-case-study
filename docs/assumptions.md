# Assumptions of the simulated exchange

The simulated exchange ("the simulated exchange") is **fictional**. It exists to practise growth measurement on
data with a known truth. It is **not** a model of Binance: no Binance user, revenue, CAC, channel or campaign result
is used or implied. Code: `src/simulate_exchange.py` (seed 42).

## Anchored on public data
| Anchor | Real source | How it is used |
|---|---|---|
| Market factor | official Binance daily klines, BTCUSDT: absolute daily log return and quote volume | volatility lifts deposits and sign-ups a little; trade intensity follows (BTC volume / mean)^k |
| Most volatile day | the day with the largest BTC absolute return in the window (with 14 days before, 7 after) | start of the simulated trading competition (event 6) |
| Hourly profile | hourly distribution of deposits to Binance-listed addresses on Ethereum (UTC) | time of day of sign-ups and deposits |
| Campaign types | type mix of the 750 "Latest Activities" announcements (rules of `docs/campaign_taxonomy.md`) | types of the 33 non-fixed simulated campaigns |
| Campaign rhythm | promotion start dates and durations read in the announcements of the window | start dates and durations of those campaigns |
| Local currencies | USDTBRL, USDTTRY, USDTMXN, USDTARS, EURUSDT daily closes | spend and deposits in local currency |

## Parameters (choices, not facts)
- 13 weeks, 24 Aug - 22 Nov 2026; 9 fictional regions; 6 acquisition channels + CRM.
- Baseline sign-ups per day by region (about 12,600 in total) and channel mix (organic 28.5%, referral 21.5%,
  app-store ads 15%, paid social 14%, paid search 13%, affiliate/KOL 8%), weekday factors, region-day noise (5%).
- Funnel: KYC submitted 74%, KYC pass 78%, first deposit after KYC 50-62% by channel, first trade 85%.
- 30-day retention targets by channel (September) and +4 points in every channel in October; an affiliate partner
  push multiplies affiliate sign-ups by 6.5 in October.
- Revenue: a net take rate of 0.25% of traded volume (fees and spread); trade sizes log-normal.
- Spend: cost per sign-up by paid channel (6-9 USD, +25% in EU and MENA), partner invoices booked the Monday after
  the activity week; campaign budgets set so that CAC differs across campaigns.
- Existing base: 4 million accounts (CRM targets are drawn among dormant ones).
- Events 1-8 and the CRM experiment are described in `src/simulate_exchange.py`; their true sizes are stored in
  `data/_hidden_truth.csv` (never published) and read only by the final verification step.

## What is calibrated
A few parameters are solved numerically so that the planted events have the intended size: the market sensitivity
of trades (naive +45% for the competition), the share of partner invoices booked late (+40% CAC week over week by
booking date). The calibration is printed by the simulator and kept in `data/sim/_meta.json`.
