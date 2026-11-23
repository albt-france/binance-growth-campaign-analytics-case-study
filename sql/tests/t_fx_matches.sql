-- T09 local-currency spend = USD x real exchange rate of the activity day (ASOF join). PASS = 0 rows.
SELECT * FROM stg_spend_check_fx WHERE abs(amount_local - expected_local) > 0.01 * expected_local + 0.02;
