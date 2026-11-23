-- T11 the 15 reference figures of 20 Nov 2026 are reproduced exactly (November list, RAW definitions:
-- no filter on receipt_status; internal and zero-value transfers included). PASS = 0 rows.
WITH dep AS (SELECT address FROM addr_nov WHERE kind = 'dep'),
hot AS (SELECT address FROM addr_nov WHERE kind = 'hot'),
tx AS (SELECT * FROM stg_tx WHERE date_utc = DATE '2026-11-20'),
tt AS (SELECT * FROM stg_tt WHERE date_utc = DATE '2026-11-20'),
got AS (
  SELECT 'eth_tx_to_deposit' AS k, count(*) AS v FROM tx WHERE to_address IN (SELECT address FROM dep)
  UNION ALL SELECT 'eth_deposit_addresses', count(DISTINCT to_address) FROM tx
            WHERE to_address IN (SELECT address FROM dep)
  UNION ALL SELECT 'eth_deposit_senders', count(DISTINCT from_address) FROM tx
            WHERE to_address IN (SELECT address FROM dep)
  UNION ALL SELECT 'eth_sweeps', count(*) FROM tx
            WHERE from_address IN (SELECT address FROM dep) AND to_address IN (SELECT address FROM hot)
  UNION ALL SELECT 'eth_into_wallets', count(*) FROM tx WHERE to_address IN (SELECT address FROM hot)
  UNION ALL SELECT 'eth_out_of_wallets', count(*) FROM tx WHERE from_address IN (SELECT address FROM hot)
  UNION ALL SELECT 'tok_to_deposit', count(*) FROM tt WHERE to_address IN (SELECT address FROM dep)
  UNION ALL SELECT 'tok_deposit_addresses', count(DISTINCT to_address) FROM tt
            WHERE to_address IN (SELECT address FROM dep)
  UNION ALL SELECT 'tok_to_wallets', count(*) FROM tt WHERE to_address IN (SELECT address FROM hot)
  UNION ALL SELECT 'tok_wallet_senders', count(DISTINCT from_address) FROM tt
            WHERE to_address IN (SELECT address FROM hot)
  UNION ALL SELECT 'tok_wallet_senders_listed', count(DISTINCT from_address) FROM tt
            WHERE to_address IN (SELECT address FROM hot) AND from_address IN (SELECT address FROM dep)
  UNION ALL SELECT 'tok_withdrawals', count(*) FROM tt WHERE from_address IN (SELECT address FROM hot)
  UNION ALL SELECT 'tok_withdrawal_recipients', count(DISTINCT to_address) FROM tt
            WHERE from_address IN (SELECT address FROM hot)
  UNION ALL SELECT 'tok_withdrawals_usdt', count(*) FROM tt
            WHERE from_address IN (SELECT address FROM hot) AND asset = 'USDT'
  UNION ALL SELECT 'tok_withdrawals_usdc', count(*) FROM tt
            WHERE from_address IN (SELECT address FROM hot) AND asset = 'USDC'
),
expected(k, v) AS (VALUES ('eth_tx_to_deposit', 2223), ('eth_deposit_addresses', 1343), ('eth_deposit_senders', 1284),
  ('eth_sweeps', 1069), ('eth_into_wallets', 7812), ('eth_out_of_wallets', 63864), ('tok_to_deposit', 16498),
  ('tok_deposit_addresses', 7432), ('tok_to_wallets', 32206), ('tok_wallet_senders', 19770),
  ('tok_wallet_senders_listed', 6468), ('tok_withdrawals', 56319), ('tok_withdrawal_recipients', 30288),
  ('tok_withdrawals_usdt', 35021), ('tok_withdrawals_usdc', 6365))
SELECT e.k, e.v AS expected, g.v AS got FROM expected e LEFT JOIN got g USING (k) WHERE g.v IS DISTINCT FROM e.v;
