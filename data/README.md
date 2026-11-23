# Data

**No raw data is redistributed.** `data/raw/` (tens of GB), `data/sim/`, `data/_hidden_truth.csv` and the DuckDB
file are rebuilt locally by the scripts and are not in the repository.

## Published here
- `processed/` - aggregates only: daily on-chain counts by list definition, asset and flow; coverage; exclusions;
  address cohorts (every cell >= 20 addresses); hourly profile; data-quality log; official daily market data;
  the campaign calendar **without titles** (article code, dates, promotion period, derived type/region/asset);
  simulated-exchange tables and results; `findings.json` (every number of the report and README).
- `sample/` - 10,000-row samples of the simulated tables, to try the SQL without running the simulator.

## Sources and conditions
| Source | What | Access | Conditions / notes |
|---|---|---|---|
| Binance market data, `data.binance.vision` | daily klines BTCUSDT, ETHUSDT, BNBUSDT, USDCUSDT, USDTBRL, USDTTRY, USDTMXN, USDTARS, EURUSDT | public files, SHA-256 `.CHECKSUM` verified | official public dataset published by Binance; aggregated daily values only |
| Binance public API, `api.binance.com/api/v3/exchangeInfo` | number of spot pairs | one request | public market endpoint |
| Binance Proof of Reserves, `public.bnbstatic.com/static/proof-of-reserve/wallet_address_YYYYMMDD.zip` | 8 address lists (May-Nov 2026) | public files | used to classify Ethereum flows; **no address is published** |
| AWS Public Blockchain Data (`s3://aws-public-blockchain/v1.0/eth/`) | Ethereum transactions and token transfers, 25 May - 22 Nov 2026 | anonymous S3 access, only needed columns, one day at a time | AWS Open Data; raw rows never redistributed |
| Binance announcements, "Latest Activities" (`bapi/composite/v1/public/cms/article/...`) | 750 articles: code, release date, promotion period | public endpoints, <= 1 request/s (slower after HTTP 429) | Binance's text is never published; derived categories only |
| Binance careers (Greenhouse board API) | the job post and the number of open roles | public API | facts quoted "as stated by Binance" |

Collected on 23 Nov 2026. Simulated data: `src/simulate_exchange.py`, seed 42, fictional exchange.
