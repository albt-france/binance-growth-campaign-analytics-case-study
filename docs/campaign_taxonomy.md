# Campaign taxonomy (rules for the real Binance calendar)

Types are assigned by written rules on the announcement title, in priority order; the first match wins (code: `src/campaigns_calendar.py`). Region = a country, currency or region named in the title, else 'not stated'. Asset = the first of USDC, USDT, FDUSD, BTC, ETH, BNB, SOL, XRP, DOGE named; tokenized-stock campaigns are written 'tokenized stock' or 'tokenized-stock voucher', never with a company name or ticker.

| Priority | Type | Pattern idea |
|---|---|---|
| 1 | tokenized_stock | tokenized stocks, shares, equities, securities |
| 2 | new_user | new users, newcomers, first-time, welcome, sign-up |
| 3 | p2p | P2P |
| 4 | trading_competition | trading competition / tournament / challenge / sprint / cup, traders league, trade to win/share |
| 5 | referral | refer, referral, invite, friends |
| 6 | alpha | Alpha, booster, pre-TGE, Binance Wallet |
| 7 | learn_quiz | learn, quiz, academy, course, test your knowledge |
| 8 | pay | Binance Pay, payment, merchant, card, cashback |
| 9 | earn_apr | Earn, APR, APY, staking, savings, launchpool, hold, subscribe |
| 10 | deposit | deposit, top-up, buy, convert |
| - | other | anything else |

## Hand check
- Rules v1 on a random development sample of 50 titles (seed 7): **70%** correct.
- Rules refined on that sample (v2): 98% on the same sample (optimistic: tuned on it).
- Rules v2 on a **fresh** sample of 50 other titles (seed 8), checked once: **88%** correct.

Precision by predicted type on the fresh sample:

| type | correct | predicted | precision |
|---|---|---|---|
| alpha | 0 | 1 | 0% |
| deposit | 2 | 2 | 100% |
| earn_apr | 11 | 12 | 92% |
| learn_quiz | 4 | 4 | 100% |
| other | 7 | 9 | 78% |
| p2p | 1 | 1 | 100% |
| pay | 3 | 3 | 100% |
| referral | 2 | 3 | 67% |
| tokenized_stock | 0 | 1 | 0% |
| trading_competition | 14 | 14 | 100% |

Labels and titles stay in `data/raw/` (Binance's text is never published).
