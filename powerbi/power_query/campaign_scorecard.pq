// campaign_scorecard: one row per simulated campaign: attributed KPIs, incremental estimates, status
let
    Source = Csv.Document(File.Contents(DataFolder & "campaign_scorecard.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"campaign_id", type text}, {"type", type text}, {"region", type text}, {"channel", type text}, {"objective", type text}, {"status", type text}, {"attributed_signups", type number}, {"attributed_first_depositors", type number}, {"media_usd", type number}, {"promo_usd", type number}, {"cac_first_deposit", type number}, {"revenue_30d_per_depositor", type number}, {"roi_30d", type number}, {"retention_d30", type number}, {"share_withdrew_90pct_30d", type number}, {"did_lift", type number}, {"naive_lift", type number}}, "en-US")
in
    Typed
