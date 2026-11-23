# Anomaly triage: campaign, crowd, cycle or counting?

When a growth number moves, separate four causes **before** recommending anything.

```
A metric moved (alert, dashboard, question from a manager)
│
├─ 1. COUNTING - is the number itself right?            (check first: cheapest, most common)
│     ├─ duplicates? (raw rows vs distinct event_id)                 -> fix staging, re-run
│     ├─ late or missing partition? (watermark, row counts vs usual) -> wait / backfill, annotate
│     ├─ day cut? (UTC vs UTC+8)                                      -> state the cut, compare like with like
│     ├─ date field? (booking vs activity date)                      -> use activity date for decisions
│     └─ definition change? (address list, attribution rule)        -> recompute on a fixed definition
│
├─ 2. CYCLE - did the market move?
│     └─ compare with real BTC/ETH volume and volatility of the day; is the move in ALL regions?
│        -> if yes: market, not campaign (difference-in-differences against untreated regions)
│
├─ 3. CROWD - did the mix change?
│     ├─ by channel, region, cohort: does the metric move inside each group?
│     │    overall down but every group up -> mix (Simpson): standardise on a fixed mix
│     └─ abuse / bonus hunting / referral farms -> guardrail indicators
│
└─ 4. CAMPAIGN - what is left after 1-3?
      └─ holdout difference, or DiD / synthetic control, with interval and placebo
```

## The questions to ask, in order
1. Does the raw data agree with the clean data? How many rows were removed and why?
2. Is the latest partition complete (watermark), and is the comparison period complete too?
3. Is the move in every region and channel, or concentrated? Same direction in the market data?
4. Inside each channel/region, did the metric move the same way as the total?
5. What else launched (calendar), and in which regions?
6. Only then: what is the incremental effect, with its interval?

## Downstream failures look like weak campaigns
A campaign whose sign-ups are normal but whose first deposits collapse may be fine: check KYC pass rate, deposit
success and payment providers by region and day before cutting the budget.
