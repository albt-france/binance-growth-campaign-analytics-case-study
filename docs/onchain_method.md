# On-chain method

## Sources
- **Address lists**: Binance Proof-of-Reserves files of 1 May, 1 Jun, 1 Jul, 1 Aug, 1 Sep, 1 Oct, 31 Oct and 11 Nov 2026
  (public zip files); ETH network rows only; deposit addresses and hot/cold wallets.
- **Ethereum**: AWS Public Blockchain Data, `transactions` and `token_transfers`, 25 May - 22 Nov 2026 (182 UTC days),
  read anonymously one day at a time, only the needed columns, keeping rows that touch any listed address plus the
  day's totals. About 138 GB read in total.

## Definitions
See `METRICS.md` (deposit, sweep, unlisted sender to a wallet, swept address, withdrawal, coverage, exclusions).

## Three list definitions
| Definition | Deposit transfers per day | Change, last 4 weeks vs first 4 |
|---|---|---|
| A - list in force on the day | 9,706 | +43% |
| B - all 8 lists (fixed, default) | 30,831 | -31% |
| C - November list only (fixed) | 18,938 | -30% |

Coverage of active senders by the November list: 46% in the first 4 weeks,
31% in the last 4; with the list in force each day: 18% and
17%.

## Checks
- The 15 reference figures of 20 Nov 2026 are reproduced exactly with their raw definitions
  (`sql/tests/t_onchain_reference_20nov.sql`).
- Second method: clean USDT deposits and distinct USDT senders to wallets recomputed with pandas for
  3 days: all match (2026-06-15, 2026-09-21, 2026-11-20).
- `approx_count_distinct` vs exact distinct senders per day: mean error 9.63%, max
  38.98%; 0.06 s vs 0.59 s. Exact counts are kept.

## Limits
Ethereum only; the lists hold addresses with a balance at audit time; an address is not a user; senders to wallets
that are not listed can be other services. No address is published; cells under 20 addresses are suppressed.
