# Executive memo - growth measurement (one page)

**Decision asked:** adopt three measurement rules for every growth campaign from the next planning cycle.

**Why now.** In the simulated quarter (fictional exchange, not Binance data):
- the cheapest acquisition campaign (9 USD per first depositor) **lost 58%** of its cost over
  30 days, because 55% of the customers it brought left with the bonus;
- a trading competition looked like **+46%** trades; against regions without it, the real effect was
  about **+5%** - the market did the rest;
- a weekly alert "CAC +40%" was an invoicing delay: on the day the money was actually spent, CAC fell
  23%.

On real public data, counting with Binance's published address list as it grows would show deposits at
+43% instead of -31% on a fixed list: a
74-point illusion created by the measurement alone.

**The three rules**
1. **Judge on incremental 30-day value**, with a holdout (CRM) or untreated regions (regional campaigns), plus two
   guardrails: full withdrawals and abuse flags. A low CAC alone is not a success.
2. **Fix the counting first**: one event = one row, the day cut stated (UTC+8 for operations), CAC on the activity
   date, frozen definitions.
3. **Read every move against the market and the mix** before crediting a campaign.

**Cost:** a 10% holdout delays the effect on 10% of the audience. The CRM test kept that way measured
+1.75 points of reactivation (95% CI +1.55 to +1.96),
an answer no other method gives as reliably.

**Next step:** one pilot market, one quarter, the readout template of `reports/readouts/`.

Independent case study based on public data · not affiliated with or endorsed by Binance · Not investment advice
