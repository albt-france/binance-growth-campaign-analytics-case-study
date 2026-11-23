# Bonus and referral abuse: guardrails (indicators and thresholds only)

This page describes **what to monitor**, not how abuse is done. Thresholds are starting points to tune on real
data with the risk and compliance teams; a flag opens a review, it never closes an account on its own.

## Campaign-level guardrails (written in the measurement plan, checked in every readout)
| Indicator | Starting threshold | Why |
|---|---|---|
| Share of depositors withdrawing >= 90% of deposits within 30 days | > 30% | promotion attracts users who leave with the reward |
| 30-day retention of the campaign's depositors vs the channel's usual level | less than half | low-value acquisition |
| Promo cost per depositor vs 30-day net revenue per depositor | cost > revenue | negative 30-day ROI even with a low CAC |
| Share of first deposits at exactly the minimum qualifying amount | > 50% | reward-driven deposits |

## Referrer-level indicators (`sql/50_attribution/504_referral_abuse_indicators.sql`)
| Indicator | Flag when |
|---|---|
| Referees on a device shared with other accounts | > 50% of referees |
| Referees signing up within any 60-minute window | >= 10 |
| Referees passing KYC | < 50% |
| Referees' first deposits at one identical amount | > 80% |

A referrer is **flagged when at least 3 of the 4 indicators fire**; one indicator alone also catches honest
power users (creators with large audiences).

## Process
1. Daily job computes the indicators; flagged referrers go to a review queue (risk team).
2. Rewards of flagged referrers are held until review; reported campaign results are shown **with and without**
   flagged accounts.
3. Thresholds are reviewed monthly against confirmed cases (precision of the flags).

## Boundaries
- No description of abuse techniques in any deliverable.
- No personal data in reports: referrer IDs only, and only internally.
- Rules on crypto promotions differ by jurisdiction; legal review is out of scope here.
