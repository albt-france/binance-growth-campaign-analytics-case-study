# Measurement plan (fill in BEFORE the campaign)

| Field | Answer |
|---|---|
| Campaign id / name | `CMP___` |
| Owner (team) | |
| Region(s), channel(s), audience | |
| Launch (UTC and UTC+8) / end | e.g. 2026-11-02 16:00 UTC = 2026-11-03 00:00 UTC+8 |
| Business question | what decision will this campaign inform? |
| **Primary metric** (one) | e.g. first depositors still active on day 30; net deposits; 30-day ROI |
| Secondary metrics | sign-ups, CAC, KYC pass rate, time to first deposit |
| **Guardrails** and stop thresholds | full-withdrawal share > 30%; abuse flags; promo cost per depositor > X |
| **Control** | randomised holdout (share), or untreated regions (list) + method |
| Baseline of the primary metric | value and period |
| **Minimum detectable effect** | from `tools/holdout_planner.py` (alpha 5%, power 80%) |
| Expected effect and why | |
| Other campaigns live in the same regions | from the calendar |
| Readout date (and interim look, if any) | fixed now; no stopping on the first good day |
| Day cut for the readout | UTC+8 (operations) |
| Data checks | SQL tests green; partition watermark; dedup on `event_id` |
| Decision rule | scale if ..., fix if ..., stop if ... |

Sign-off: growth owner · analyst · operations (date).
