-- Q002 stg_tx / stg_tt / stg_onchain_totals
-- Question : Ethereum rows touching any published Binance address, cleaned and typed.
-- Grain    : one row per transaction (stg_tx), per token transfer (stg_tt), per day (totals)
-- Tables   : data/raw/onchain/date=*/{tx,tt}.parquet and totals.json (raw extraction cache)
-- Trap     : token-transfer addresses are normalised to 20 bytes during extraction (they are padded to
--            32 bytes in the source); failed transactions and zero-value transfers are KEPT and flagged so
--            their effect can be measured; the UTC+8 day is derived, never stored twice.
CREATE OR REPLACE VIEW stg_tx AS
SELECT hash, block_timestamp, CAST("date" AS DATE) AS date_utc,
       CAST(block_timestamp + INTERVAL 8 HOUR AS DATE) AS date_hkt,
       hour(block_timestamp + INTERVAL 8 HOUR) AS hour_hkt, hour(block_timestamp) AS hour_utc,
       from_address, to_address, value / 1e18 AS value_eth,
       receipt_status = 1 AS succeeded, value = 0 AS zero_value, FALSE AS dust, 'ETH' AS asset
FROM read_parquet('data/raw/onchain/*/tx.parquet', hive_partitioning = true);

CREATE OR REPLACE VIEW stg_tt AS
SELECT transaction_hash AS hash, log_index, block_timestamp, CAST("date" AS DATE) AS date_utc,
       CAST(block_timestamp + INTERVAL 8 HOUR AS DATE) AS date_hkt,
       hour(block_timestamp + INTERVAL 8 HOUR) AS hour_hkt, hour(block_timestamp) AS hour_utc,
       from_address, to_address, token_address,
       TRUE AS succeeded,                -- a token transfer is a log: failed transactions emit no log
       value = 0 AS zero_value,
       -- dust: a stablecoin transfer under 1 USDT/USDC (6 decimals -> raw value < 1e6), typical of address poisoning
       value > 0 AND value < 1e6 AND sha256(token_address) IN ('63cbd95b98536412d438ab18ed85c35e326b10e413d89033ba7143f1744abecf',
                                                              '0f45bbea3a946b2c8c4ef0d236ec94580899d2a023771d1cc998d86d7a3ae6da') AS dust,
       -- token contracts are matched on the SHA-256 of their address, so that no address appears in the repo:
       -- USDT (ERC-20) and USDC (ERC-20), the two official stablecoin contracts on Ethereum
       CASE sha256(token_address) WHEN '63cbd95b98536412d438ab18ed85c35e326b10e413d89033ba7143f1744abecf' THEN 'USDT'
                                  WHEN '0f45bbea3a946b2c8c4ef0d236ec94580899d2a023771d1cc998d86d7a3ae6da' THEN 'USDC'
                                  ELSE 'other token' END AS asset
FROM read_parquet('data/raw/onchain/*/tt.parquet', hive_partitioning = true);

CREATE OR REPLACE TABLE stg_onchain_totals AS
SELECT CAST("date" AS DATE) AS date_utc, tx_total, tx_failed, tx_duplicate_hash, tt_total, tt_zero_value,
       tt_duplicate_key, CAST(tx_last_modified AS TIMESTAMP) AS tx_last_modified,
       CAST(tt_last_modified AS TIMESTAMP) AS tt_last_modified,
       CAST(tx_min_ts AS TIMESTAMP) AS tx_min_ts, CAST(tx_max_ts AS TIMESTAMP) AS tx_max_ts,
       tx_kept, tt_kept, mb_read, seconds
FROM read_json_auto('data/raw/onchain/*/totals.json');
