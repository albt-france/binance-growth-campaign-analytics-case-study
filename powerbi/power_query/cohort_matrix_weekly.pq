// cohort_matrix_weekly: first-deposit week x weeks since: active users and cohort size
let
    Source = Csv.Document(File.Contents(DataFolder & "cohort_matrix_weekly.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed = Table.TransformColumnTypes(Promoted, {{"cohort_week", type date}, {"weeks_since", Int64.Type}, {"active_users", Int64.Type}, {"cohort_size", Int64.Type}, {"retention", type number}}, "en-US")
in
    Typed
