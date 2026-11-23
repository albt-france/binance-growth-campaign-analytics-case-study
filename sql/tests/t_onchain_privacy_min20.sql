-- T12 privacy: no published on-chain cohort cell is built on fewer than 20 addresses. PASS = 0 rows.
SELECT * FROM onchain_address_cohorts WHERE active_addresses < 20 OR cohort_size < 20;
