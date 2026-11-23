-- Q101 day_snapshot / onchain_classified (PUBLIC DATA)
-- Question : for every Ethereum row touching Binance, what kind of flow is it under each list definition?
--            A_asof = the Proof-of-Reserves snapshot in force on that day (latest snapshot <= day)
--            B_union = every address of the 8 snapshots      C_nov = the 11 Nov 2026 list only
-- Grain    : one row per transaction or token transfer x definition (rows outside the definition dropped)
-- Tables   : stg_tx, stg_tt, stg_por_membership, addr_union, addr_nov
-- Trap     : the list grows from 1.8 to 8.1 million deposit addresses between May and November: counting
--            with A_asof manufactures growth. Addresses are replaced by a 64-bit hash here (smaller, still
--            exact for distinct counts at this scale); no address ever leaves the raw layer.
CREATE OR REPLACE TABLE day_snapshot AS
SELECT d::DATE AS date_utc, max(s.snapshot_date) AS snapshot_date
FROM range(DATE '2026-05-25', DATE '2026-11-23', INTERVAL 1 DAY) t(d)
JOIN stg_por_snapshots s ON s.snapshot_date <= d::DATE
GROUP BY 1;

CREATE OR REPLACE TABLE stg_onchain AS
SELECT 'tx' AS src, date_utc, date_hkt, hour_utc, hour_hkt, asset, from_address, to_address, succeeded, zero_value, dust
FROM stg_tx
UNION ALL
SELECT 'tt', date_utc, date_hkt, hour_utc, hour_hkt, asset, from_address, to_address, succeeded, zero_value, dust
FROM stg_tt;

CREATE OR REPLACE TABLE onchain_classified AS
WITH k AS (
    SELECT 'A_asof' AS definition, o.*, coalesce(mf.kind, 'ext') AS kf, coalesce(mt.kind, 'ext') AS kt
    FROM stg_onchain o JOIN day_snapshot ds USING (date_utc)
    LEFT JOIN stg_por_membership mf ON mf.snapshot_date = ds.snapshot_date AND mf.address = o.from_address
    LEFT JOIN stg_por_membership mt ON mt.snapshot_date = ds.snapshot_date AND mt.address = o.to_address
    UNION ALL
    SELECT 'B_union', o.*, coalesce(uf.kind, 'ext'), coalesce(ut.kind, 'ext')
    FROM stg_onchain o
    LEFT JOIN addr_union uf ON uf.address = o.from_address
    LEFT JOIN addr_union ut ON ut.address = o.to_address
    UNION ALL
    SELECT 'C_nov', o.*, coalesce(nf.kind, 'ext'), coalesce(nt.kind, 'ext')
    FROM stg_onchain o
    LEFT JOIN addr_nov nf ON nf.address = o.from_address
    LEFT JOIN addr_nov nt ON nt.address = o.to_address
)
SELECT definition, src, date_utc, date_hkt, hour_utc, hour_hkt, asset, succeeded,
       zero_value OR dust AS zero_value,             -- zero-value and dust transfers: both excluded from clean counts
       dust, kf, kt,
       CASE WHEN kf = 'ext' AND kt = 'dep' THEN 'deposit'              -- someone pays into a deposit address
            WHEN kf = 'dep' AND kt = 'hot' THEN 'sweep'                -- deposit address emptied to a wallet
            WHEN kf = 'ext' AND kt = 'hot' THEN 'to_wallet_unlisted'   -- sender not in the list -> indirect
            WHEN kf = 'hot' AND kt = 'ext' THEN 'withdrawal'           -- wallet pays an outside address
            WHEN kf = 'dep' AND kt = 'ext' THEN 'deposit_addr_out'
            ELSE 'internal' END AS flow,                               -- Binance to Binance
       hash(from_address) AS from_id, hash(to_address) AS to_id
FROM k
WHERE NOT (kf = 'ext' AND kt = 'ext');
