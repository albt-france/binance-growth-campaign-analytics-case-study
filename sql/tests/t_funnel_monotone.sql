-- T04 the funnel never grows from one step to the next. PASS = 0 rows.
SELECT * FROM funnel_weekly
WHERE kyc_submitted > registrations OR kyc_passed > kyc_submitted OR first_deposit_7d > kyc_passed
   OR first_trade_7d > first_deposit_7d;
