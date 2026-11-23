// funnel_by_region_channel: funnel counts with 7-day windows, region x channel
let
    Source = Csv.Document(File.Contents(DataFolder & "funnel_by_region_channel.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"region", type text}, {"channel", type text}, {"registrations", Int64.Type}, {"kyc_submitted", Int64.Type}, {"kyc_passed", Int64.Type}, {"first_deposit_7d", Int64.Type}, {"first_trade_7d", Int64.Type}, {"reg_to_deposit_7d", type number}}, "en-US")
in
    Typed
