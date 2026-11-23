# Campaign launch: tracking QA checklist (run BEFORE go-live)

A campaign that is not measurable on day 1 cannot be fixed on day 7. Tick every line, or write why not.

## 1. Measurement plan exists
- [ ] `docs/measurement_plan_template.md` filled in and agreed: primary metric, guardrails, control, minimum
      detectable effect, readout date.
- [ ] The primary metric is the **business outcome** (first depositors who stay, net deposits, 30-day ROI),
      not clicks or sign-ups alone.

## 2. Tagging
- [ ] Every link and creative carries the campaign id (`CMP…`) and the channel; partner and KOL codes are unique
      per partner.
- [ ] Test sign-up, KYC, deposit and trade with a test account in staging: the campaign id reaches `touchpoints`
      and the user's path table.
- [ ] Partners report on the **same user-level rule** (one credit per sign-up), or their reports are reconciled
      against the path table (no double counting).

## 3. Time zone
- [ ] Launch time written in **UTC** and in **UTC+8** in the tracker (e.g. 16:00 UTC = 00:00 UTC+8).
- [ ] The readout states which day cut it uses; operations readouts use UTC+8.
- [ ] A launch between 16:00 and 23:59 UTC is flagged: its UTC "day 1" holds only part of a campaign day.

## 4. Control group
- [ ] CRM / owned channels: a **randomised holdout** (10% by default), assigned before the send, stored in
      `holdout_assignments`; size checked with `tools/holdout_planner.py`.
- [ ] Paid or regional campaigns: at least two untreated regions with similar pre-trends (difference-in-differences,
      synthetic control); no other campaign planned in them during the window.
- [ ] Sample-ratio check planned (expected 90/10).

## 5. Guardrails (stop rules written in advance)
- [ ] Full-withdrawal share within 30 days (bonus hunting).
- [ ] Referral abuse indicators (`docs/playbooks/bonus_and_referral_abuse_guardrails.md`).
- [ ] KYC pass rate and deposit success rate by region (a downstream failure must not be read as a weak campaign).
- [ ] Budget pacing vs plan; promo cost per depositor capped.

## 6. Data checks on day 1 (automated)
- [ ] `python src/run_sql.py` green: no duplicate `event_id`, monotone funnel, spend = source file,
      UTC+8 day consistent, partitions present.
- [ ] First readout with `python tools/campaign_readout.py --campaign CMPxxx`.
