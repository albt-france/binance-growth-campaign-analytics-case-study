# Campaign readout: standard operating procedure

Goal: one page, one decision, the same structure for every campaign, ready the morning after the readout date.

## Steps
1. **Refresh** the data (`python pipelines/daily_refresh.py`), check the SQL tests are green.
2. **Generate** the page: `python tools/campaign_readout.py --campaign CMPxxx` (HTML, printable to PDF).
3. **Read it in this order**
   1. Objective and primary metric (from the measurement plan): did we measure what we said we would?
   2. Reported numbers (attributed): sign-ups, first depositors, CAC, 30-day ROI, retention.
   3. **Incremental** numbers: holdout difference, or difference-in-differences / synthetic control against untreated
      regions, with intervals and a placebo check. If the methods disagree, say so.
   4. Guardrails: withdrawals, abuse indicators, KYC and downstream health.
   5. The four causes (`docs/playbooks/anomaly_triage.md`): campaign, crowd, cycle (market) or counting?
4. **Write** three recommendations (scale / fix / stop, with the condition that would change the call), the box
   "for operations" (what to change on the ground) and three lines "for executives".
5. **Log** the decision and the data issues met (`docs/data_issues_log.md`).

## Rules
- Attributed is not incremental: never decide on attributed numbers alone when a control exists.
- An interval that contains zero is "no measurable effect", not "it works a bit".
- Quote the day cut (UTC or UTC+8) and the data freshness (latest partition) on the page.
- Never publish personal data or raw addresses; IDs in readouts are campaign and simulated user IDs only.
