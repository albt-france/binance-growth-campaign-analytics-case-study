-- D03 detector: region-days whose KYC pass rate is below 50% (expected: TR, 6-8 Oct vendor outage).
SELECT * FROM kyc_daily_region WHERE submissions >= 200 AND pass_rate < 0.5 ORDER BY date_utc;
