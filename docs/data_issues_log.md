# Data issues log

| # | Date found | Source | Issue | Impact | Detection | Fix | Status |
|---|---|---|---|---|---|---|---|
| 1 | 2026-11-23 | Binance announcements API | HTTP 429 on the article detail endpoint after about 110 calls at 1 request/s | detail of 317 articles delayed | HTTP status | stopped, waited, resumed at 1 request / 6 s honouring Retry-After; no workaround | closed: 430 / 430 read |
| 2 | 2026-11-23 | AWS Public Blockchain Data | token-transfer addresses padded to 32 bytes | zero matches with the address lists | reference check | normalise to the last 20 bytes | closed (pytest) |
| 3 | 2026-11-23 | AWS Public Blockchain Data | 14 daily partitions landed more than 6 h after the end of the day (latest 2026-06-20, 71 h) | a daily job reading too early sees an incomplete day | watermark on `last_modified` | refresh waits for the partition; alert after 06:00 UTC | monitored |
| 4 | 2026-11-23 | AWS Public Blockchain Data | zero-value token transfers (6.0% of all transfers; address poisoning) | inflated counts | `value = 0` flag | excluded from clean counts, counted apart | closed |
| 5 | 2026-11-23 | Binance Proof of Reserves | the ETH list grows from 1,818,261 to 8,139,203 deposit addresses (max 11,509,406) | fake growth with the list in force | three definitions compared | fixed list (all snapshots) as default | documented |
| 5b | 2026-11-23 | Binance address lists vs Ethereum | on 2026-10-30, 2026-10-31, 2026-11-01, 2026-11-02 transfers into listed wallets fell to 0.1%-12% of their usual level while deposits to listed deposit addresses continued (about 79% of usual); partitions complete, address formats checked | wallet-based metrics (sweeps, coverage, withdrawals) unreliable on those days | daily ratio to the 14-day median (`onchain_wallet_inflows_daily.csv`) | consistent with wallets absent from all 8 published lists (rotation); days flagged, not imputed | documented |
| 6 | 2026-11-23 | Kline files | timestamps in milliseconds (2024) and microseconds (2026) | wrong dates | length test | convert by magnitude | closed (pytest) |
| 7 | sim | deposits feed | pipeline replay on 27 Oct: same `event_id`, later `ingested_at` (raw rows x2.1) | deposits doubled that day | `dq_duplicate_event_ids_raw.sql`, monitoring | dedup in staging (QUALIFY) | closed (test T06) |
| 8 | sim | campaign tracker | CMP027 launched 2026-11-02 16:00:00 UTC = midnight UTC+8 | two different "day 1" readouts | `dq_launch_day_differs_utc_hkt.sql` | readouts use the UTC+8 day, stated on the page | closed (test T07) |
| 9 | sim | KYC vendor | TR pass rate 77% -> 22% on 6-8 Oct | TR campaign looks failed | `dq_kyc_pass_rate_drop.sql`, control chart | re-contact affected users; KYC guardrail in readouts | closed |
| 10 | sim | finance | partner invoices of two weeks booked with a third on 2 Nov | booking-date CAC +40% WoW | CAC by activity vs booking date | CAC decisions on the activity date | closed |
