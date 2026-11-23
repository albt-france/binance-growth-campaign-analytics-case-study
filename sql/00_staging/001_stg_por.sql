-- Q001 stg_por_membership / stg_por_snapshots / addr_union / addr_nov
-- Question : which Ethereum addresses did Binance publish in each Proof-of-Reserves snapshot, and as what?
-- Grain    : snapshot x address (stg_por_membership); snapshot (stg_por_snapshots); address (addr_*)
-- Tables   : data/raw/por/eth_membership.parquet (raw, never published)
-- Trap     : an address can appear on several coin rows of the same file -> one row per address;
--            if it is listed both as deposit and hot/cold, hot/cold wins (it is a Binance wallet).
CREATE OR REPLACE TABLE stg_por_membership AS
SELECT strptime(snapshot, '%Y%m%d')::DATE AS snapshot_date,
       address,
       CASE WHEN bool_or(kind = 'hotcold') THEN 'hot' ELSE 'dep' END AS kind
FROM read_parquet('data/raw/por/eth_membership.parquet')
WHERE address LIKE '0x%' AND length(address) = 42
GROUP BY ALL;

CREATE OR REPLACE TABLE stg_por_snapshots AS
SELECT snapshot_date,
       count(*) FILTER (WHERE kind = 'dep') AS n_deposit_addresses,
       count(*) FILTER (WHERE kind = 'hot') AS n_hot_cold_wallets
FROM stg_por_membership GROUP BY snapshot_date ORDER BY snapshot_date;

-- definition B: every address of every snapshot
CREATE OR REPLACE TABLE addr_union AS
SELECT address, CASE WHEN bool_or(kind = 'hot') THEN 'hot' ELSE 'dep' END AS kind
FROM stg_por_membership GROUP BY address;

-- definition C: the latest list only (snapshot of 11 Nov 2026)
CREATE OR REPLACE TABLE addr_nov AS
SELECT address, kind FROM stg_por_membership WHERE snapshot_date = DATE '2026-11-11';
