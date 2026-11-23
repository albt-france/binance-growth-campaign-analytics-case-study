# Metrics dictionary

One definition per metric, used the same way in SQL (`sql/`), Python (`src/`), the dashboard, the workbook and
Power BI. **Time zones:** data are stored and computed in **UTC**; operations readouts (campaign "day 1", daily
reviews for the Hong Kong team) are cut in **UTC+8**, and say so.

## Growth funnel (SIMULATED exchange)

| Metric | Formula | Grain | Time zone | Trap avoided |
|---|---|---|---|---|
| Sign-up (registration) | one `register` event per user | user | UTC | count users, not raw rows: deduplicate on `event_id` (latest `ingested_at`) |
| KYC submitted / passed (7 d) | first `kyc_submitted` / `kyc_passed` within 7 days of sign-up | user | UTC | a retry after a vendor outage is a second submission, not a second user |
| KYC pass rate | submissions that pass / submissions, by **submission day** | region x day | UTC | measured on the submission cohort, not on the verdict day |
| First deposit (7 d) | first deposit after KYC approval, within 7 days of sign-up | user | UTC | the step must follow the previous one (monotone funnel test) |
| Activation | first trade after the first deposit | user | UTC | |
| Time to first deposit | days from KYC approval to first deposit, Kaplan-Meier | user | UTC | users who have not deposited yet are **censored**, not "never" |
| CAC (blended) | acquisition media + partner fees / new first depositors | week or campaign | UTC, **activity date** | the **booking date** moves invoices between weeks (false CAC jumps) |
| CAC (paid, per campaign) | campaign media / attributed first depositors | campaign | UTC | attributed is not incremental |
| 30-day net revenue | trading fees and spread (simulated take rate) in the 30 days after the first deposit | depositor | UTC | only depositors with 30 days of follow-up |
| 30-day ROI | (30-day net revenue - media - promo bonuses) / (media + promo) | campaign | UTC | bonuses are not in the CAC but are in the ROI |
| Payback (days) | total cost per depositor / (30-day revenue per depositor / 30) | campaign | UTC | a straight-line projection, labelled as such |
| 7-day retention | traded on any day 1-7 after the first deposit | first-deposit cohort | UTC | |
| 30-day retention | traded on any day 24-30 after the first deposit | first-deposit cohort | UTC | cohorts without 30 days of data are excluded; compare like with like (mix) |
| Net deposits | deposits - withdrawals | user, campaign, day | UTC | |
| Full-withdrawal guardrail | share of depositors who withdraw >= 90% of what they deposited within 30 days | campaign | UTC | the bonus-hunting signal |
| Incremental effect | outcome with the campaign - outcome without it (holdout, or control regions) | campaign | UTC+8 readout | see `docs/playbooks/incrementality_methods.md` |
| Reactivation (CRM) | dormant user who trades within 14 days of assignment | user | UTC | measured from **assignment** in both arms, never "opened the message" |

## Binance flows on Ethereum (PUBLIC DATA)

All on-chain metrics count **addresses and transfers on Ethereum only** (not Tron, BNB Chain, Solana or Bitcoin),
to and from the addresses Binance published in its Proof of Reserves. **An address is not a user** (one user can
have several deposit addresses on several networks) and an address "new" in the window is **not a new customer**.

| Metric | Definition | Notes |
|---|---|---|
| List definition | **A** = snapshot in force on the day; **B** = every address of the 8 snapshots (fixed); **C** = 11 Nov list only (fixed) | A manufactures growth as the list grows; B is the default |
| Deposit | transfer from a non-Binance address to a listed **deposit address** | native ETH (successful transactions) and ERC-20 transfers |
| Sweep | transfer from a listed deposit address to a listed hot/cold **wallet** | how an exchange consolidates deposits |
| To wallet, unlisted sender | transfer to a wallet from an address that is not listed | mostly deposit addresses absent from the list (indirect method), also other services |
| Swept address | any non-wallet address that sends to a Binance wallet that day (sweep + unlisted) | the list-independent activity measure, used for cohorts |
| Withdrawal | transfer from a listed wallet to a non-Binance address | |
| Withdrawal recipient | distinct receiving address of withdrawals | |
| Coverage | listed senders / all non-wallet senders to Binance wallets (token transfers) | how much of the active population the published list covers |
| Exclusions | failed transactions, zero-value transfers (address poisoning), internal Binance-to-Binance moves | kept in staging, removed from clean metrics, measured |
| Day | UTC day (`date_utc`) and UTC+8 day (`date_hkt`) | the first UTC+8 day of the window is partial |
| Address cohort | swept addresses by first week observed, after an 8-week burn-in (25 May - 19 Jul) | limits left censoring; cells under 20 addresses are never published |

## Reference definitions used only for the 20 Nov 2026 check

The handoff's reference figures for 20 Nov 2026 use the November list and **raw** counts (no filter on
`receipt_status`, internal and zero-value transfers included). `sql/tests/t_onchain_reference_20nov.sql`
reproduces all 15 of them exactly; the clean metrics above then apply the exclusions.
