# Attribution rules

## The rule
1. Build **one user-level path table** (`sql/50_attribution/501_paths.sql`): every touch in the 7 days before
   sign-up, in time order, capped at the last 5 touches; touches after sign-up get no credit.
2. Apply **one rule to everybody**, so that the credits sum to exactly the number of sign-ups:
   - default operational rule: **last touch** (simple, stable, explainable);
   - for budget questions: **Markov removal effect** (`src/stats.py`, with bootstrap intervals) and
     position-based (40/20/40) as a sensitivity check.
3. Partner and network reports are **inputs to reconcile**, never added together.

## Why
Each partner claims every user it touched. When two partners touch the same user, the sum of their reports exceeds
the real number of sign-ups (in the simulated LATAM case the two partner types claim about 128% of the sign-ups they
actually touched). Paying on the sum pays twice for the same customer.

## Reconciliation, every month
- Partner claims vs user-level paths, by partner and region (`sql/50_attribution/503_partner_claims.sql`).
- Any partner whose claims exceed its last-touch credit by more than an agreed margin gets a joint review of the
  path data before the invoice is approved.

## Limits
Attribution splits credit among touches; it does **not** measure incrementality. A channel can earn a lot of
last-touch credit for users who would have come anyway (brand search, organic). Use holdouts and geo tests for
"how much does this channel add".
