# Privacy and ethics

## Blockchain addresses
- Addresses are pseudonymous, but an address can point to a person. **No address is published** in this
  repository, the report, the dashboard or any file: not deposit addresses, not withdrawal recipients, not even
  Binance's own wallets or token contracts (USDT and USDC are written "USDT (ERC-20)" and "USDC (ERC-20)"; the code
  recognises their contracts through the SHA-256 of the address).
- Only **aggregates** leave `data/raw/`; analysis tables use 64-bit hashes of addresses for counting.
- Every published cell built on addresses contains **at least 20 addresses** (smaller cells are suppressed; a SQL
  test enforces it on the cohort table).
- No attempt to link an address to a person, no following of any named large holder ("whale"), no clustering of
  addresses into entities beyond the lists Binance itself published.

## Binance's content
- Announcement titles and texts belong to Binance: none is published. The calendar keeps the article code, dates,
  the promotion period and derived categories (type, region, asset) only.
- Facts about Binance are quoted "as stated by Binance", with link and date. No internal Binance data is used or
  invented; nothing in the simulated part describes Binance's users, revenue, CAC, channels or campaign results.

## Simulated data
- The simulated exchange and its campaigns (`CMP001`-`CMP040`) are fictional; identifiers are synthetic (`U…`,
  `D…`, `CMP…`) and every simulated visual is tagged SIMULATED.

## Abuse and fraud
- Abuse detection is described at the level of indicators and thresholds only; no technique for exploiting
  bonuses, referrals or KYC is described.

## Domain caution
- **Not investment advice.** No price forecast, no trading signal, no incentive to buy crypto-assets.
- Rules on crypto promotions differ by jurisdiction.

## Collection
- Official APIs and public files only, at most one request per second to binance.com (slower for the article
  detail endpoint after it answered HTTP 429), `Retry-After` honoured, no workaround, no account, no cookie.
- AWS Public Blockchain Data read anonymously, only the needed columns, one day at a time.
