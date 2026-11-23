// retention_by_channel_month: D7 / D30 retention by first-deposit month and channel (full cohorts)
let
    Source = Csv.Document(File.Contents(DataFolder & "retention_by_channel_month_model.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"dep_month", type date}, {"channel", type text}, {"depositors_full_30d", Int64.Type}, {"retention_d7", type number}, {"retention_d30", type number}}, "en-US")
in
    Typed
