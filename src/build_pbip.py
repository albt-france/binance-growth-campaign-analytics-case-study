"""Power BI project (PBIP, text format: TMDL model + PBIR report) on the CSVs of data/processed/ (SIMULATED exchange).

    python src/build_pbip.py                      # placeholder data folder (what is published)
    python src/build_pbip.py --data-folder "D:\\copy\\of\\repo\\data\\processed\\"   # your local copy

Writes powerbi/GrowthCampaigns.pbip, .SemanticModel (4 tables, measures in _Measures) and .Report (3 pages:
Campaign scorecard, Funnel, Cohorts & retention). Open it with Power BI Desktop and refresh (powerbi/HOW_TO_OPEN.md).
The model, measures and visual helpers are adapted from an earlier PBIP case study.
"""
import argparse
import json
import re
import shutil
import uuid
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
PBI = ROOT / "powerbi"
NAME = "GrowthCampaigns"
SM, RP = PBI / f"{NAME}.SemanticModel", PBI / f"{NAME}.Report"
DEF = SM / "definition"
PAGES = RP / "definition" / "pages"
PLACEHOLDER = "C:\\PATH\\TO\\REPO\\data\\processed\\"
VC_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json"
PAGES_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json"
M = "_Measures"
INK, INK2, MUTED, BLUE, ORANGE, GREY = "#0B0B0B", "#52514E", "#898781", "#1C5CAB", "#C2541B", "#A3A19A"
DISCLAIMER = "Independent case study based on public data · not affiliated with or endorsed by Binance · Not investment advice"
SIM = "SIMULATED"


def tag(*parts):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "growth-campaigns/" + "/".join(parts)))


# ======================================================================== PBIR helpers (reused)


# ---------- expressions ----------
def raw(v):
    if isinstance(v, bool):
        s = "true" if v else "false"
    elif isinstance(v, int):
        s = f"{v}L"
    elif isinstance(v, float):
        s = f"{v}D"
    else:
        s = "'" + str(v).replace("'", "''") + "'"
    return {"Literal": {"Value": s}}


def lit(v):
    return {"expr": raw(v)}


def color(h):
    return {"solid": {"color": lit(h)}}


def col(t, c):
    return {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}}


def meas(n):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": M}}, "Property": n}}


def qref(f):
    if "Column" in f:
        return f'{f["Column"]["Expression"]["SourceRef"]["Entity"]}.{f["Column"]["Property"]}'
    return f'{M}.{f["Measure"]["Property"]}'


def proj(f, label=None):
    p = {"field": f, "queryRef": qref(f), "nativeQueryRef": (f.get("Column") or f.get("Measure"))["Property"]}
    if label:
        p["displayName"] = label
    return p


def series_color(f, h):
    return {"properties": {"fill": color(h)}, "selector": {"metadata": qref(f)}}


def ref_line(value, label, h=INK2):
    return {"properties": {"show": lit(True), "value": lit(value), "displayName": lit(label), "lineColor": color(h),
                           "style": lit("dashed"), "dataLabelShow": lit(True), "dataLabelColor": color(h)},
            "selector": {"id": "1"}}


def bg_rule(f, lo, hi, mid=None, mid_value=None):
    rule = {"min": {"color": raw(lo)}, "max": {"color": raw(hi)}, "nullColoringStrategy": {"strategy": raw("asZero")}}
    key = "linearGradient2"
    if mid:
        key, rule["mid"] = "linearGradient3", {"color": raw(mid), **({"value": raw(mid_value)} if mid_value is not None else {})}
    return {"properties": {"backColor": {"solid": {"color": {"expr": {"FillRule": {"Input": f, "FillRule": {key: rule}}}}}}},
            "selector": {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": qref(f)}}


def table_style(extra=()):
    fs = {"properties": {"fontSize": lit(11)}}
    return {"values": [fs, *extra], "columnHeaders": [{"properties": {"fontSize": lit(11), "fontColor": color(INK2)}}],
            "total": [{"properties": {"totals": lit(False)}}]}


def no_legend(fill=BLUE):
    return {"dataPoint": [{"properties": {"fill": color(fill)}}], "legend": [{"properties": {"show": lit(False)}}]}


class Page:

    def __init__(self, pid, name, tag):
        self.pid, self.name, self.tag, self.visuals, self.n = pid, name, tag, [], 0

    def _add(self, vid, x, y, w, h, visual, filters=None):
        self.n += 1
        v = {"$schema": VC_SCHEMA, "name": vid,
             "position": {"x": round(x), "y": round(y), "z": self.n * 1000, "height": round(h), "width": round(w), "tabOrder": self.n * 1000},
             "visual": visual}
        if filters:
            v["filterConfig"] = {"filters": filters}
        self.visuals.append(v)

    @staticmethod
    def flt(table, column, values, negate=False):
        cond = {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": column}}],
                       "Values": [[raw(v)] for v in values]}}
        if negate:
            cond = {"Not": {"Expression": cond}}
        return {"name": f"f_{column}", "type": "Categorical", "field": col(table, column),
                "filter": {"Version": 2, "From": [{"Name": "t", "Entity": table, "Type": 0}], "Where": [{"Condition": cond}]}}

    def chart(self, vid, vtype, x, y, w, h, roles, title, objects=None, labels=None, sort=None, filters=None, tag=None):
        labels = labels or {}
        visual = {"visualType": vtype,
                  "query": {"queryState": {r: {"projections": [proj(f, labels.get(qref(f))) for f in fs]} for r, fs in roles.items() if fs}},
                  "drillFilterOtherVisuals": True}
        if sort:
            visual["query"]["sortDefinition"] = {"sort": [{"field": sort[0], "direction": sort[1]}], "isDefaultSort": False}
        if objects:
            visual["objects"] = objects
        full = f"{title}  ·  {tag or self.tag}" if title else None
        visual["visualContainerObjects"] = {"subTitle": [{"properties": {"show": lit(False)}}],
                                            "title": [{"properties": {"show": lit(bool(full)), **({"text": lit(full)} if full else {})}}]}
        self._add(vid, x, y, w, h, visual, filters)

    def text(self, vid, x, y, w, h, paragraphs, boxed=False):
        paras = [{"textRuns": [{"value": t, "textStyle": {"fontSize": f"{s}pt", "color": c, **({"fontWeight": "bold"} if b else {})}}
                               for t, s, c, b in runs]} for runs in paragraphs]
        visual = {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": paras}}]},
                  "visualContainerObjects": {"background": [{"properties": {"show": lit(boxed)}}],
                                             "border": [{"properties": {"show": lit(boxed)}}],
                                             **({"padding": [{"properties": {"top": lit(14), "bottom": lit(14), "left": lit(18), "right": lit(18)}}]} if boxed else {})}}
        self._add(vid, x, y, w, h, visual)

    def header(self, title, conclusion):
        self.text("title", 32, 18, 1480, 56, [[(title, 22, INK, True)]])
        self.text("tag", 1530, 26, 358, 40, [[(self.tag, 10, INK2, True)]])
        self.text("conclusion", 32, 74, 1856, 66, [[(conclusion, 12, INK2, False)]])

    def footer(self, source):
        self.text("footer", 32, 1040, 1856, 32, [[(source + "   ·   " + DISCLAIMER, 8, MUTED, False)]])

    def slicer(self, vid, x, y, w, h, field, title, single=False):
        objs = {"header": [{"properties": {"show": lit(False)}}], "data": [{"properties": {"mode": lit("Dropdown")}}]}
        if single:
            objs["selection"] = [{"properties": {"singleSelect": lit(True), "strictSingleSelect": lit(True)}}]
        visual = {"visualType": "slicer", "query": {"queryState": {"Values": {"projections": [proj(field)]}}},
                  "objects": objs, "visualContainerObjects": {"title": [{"properties": {"show": lit(True), "text": lit(title)}}]}}
        self._add(vid, x, y, w, h, visual)

    def card(self, vid, x, y, w, h, measure, title, filters=None, size=26):
        self.chart(vid, "card", x, y, w, h, {"Values": [meas(measure)]}, title,
                   {"labels": [{"properties": {"color": color(INK), "fontSize": lit(size)}}],
                    "categoryLabels": [{"properties": {"show": lit(False)}}]}, filters=filters)

    def write(self):
        d = PAGES / self.pid
        if d.exists():
            shutil.rmtree(d)
        (d / "visuals").mkdir(parents=True)
        page = {"$schema": PAGE_SCHEMA, "name": self.pid, "displayName": self.name, "displayOption": "FitToPage", "height": 1080, "width": 1920}
        (d / "page.json").write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")
        for v in self.visuals:
            (d / "visuals" / v["name"]).mkdir()
            (d / "visuals" / v["name"] / "visual.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")




# ======================================================================== semantic model
TABLES = {
    "campaign_scorecard": "one row per simulated campaign: attributed KPIs, incremental estimates, status",
    "funnel_by_region_channel": "funnel counts with 7-day windows, region x channel",
    "cohort_matrix_weekly": "first-deposit week x weeks since: active users and cohort size",
    "retention_by_channel_month": "D7 / D30 retention by first-deposit month and channel (full cohorts)",
}
KEEP = {"campaign_scorecard": ["campaign_id", "type", "region", "channel", "objective", "status",
                               "attributed_signups", "attributed_first_depositors", "media_usd", "promo_usd",
                               "cac_first_deposit", "revenue_30d_per_depositor", "roi_30d", "retention_d30",
                               "share_withdrew_90pct_30d", "did_lift", "naive_lift"]}
MEASURES = [
    ("Scorecard", "First depositors", "#,0", "attributed first depositors",
     "SUM ( campaign_scorecard[attributed_first_depositors] )"),
    ("Scorecard", "Media USD", "#,0", "campaign media spend", "SUM ( campaign_scorecard[media_usd] )"),
    ("Scorecard", "Promo USD", "#,0", "promo bonuses (boosted rates)", "SUM ( campaign_scorecard[promo_usd] )"),
    ("Scorecard", "CAC", "0.00", "media / attributed first depositors", "DIVIDE ( [Media USD], [First depositors] )"),
    ("Scorecard", "ROI 30d", "0%", "(30-day revenue - media - promo) / (media + promo), campaigns with 30-day data",
     "VAR c = FILTER ( campaign_scorecard, NOT ISBLANK ( campaign_scorecard[revenue_30d_per_depositor] ) )\n"
     "VAR rev = SUMX ( c, campaign_scorecard[revenue_30d_per_depositor] * campaign_scorecard[attributed_first_depositors] )\n"
     "VAR cost = SUMX ( c, campaign_scorecard[media_usd] + campaign_scorecard[promo_usd] )\n"
     "RETURN DIVIDE ( rev - cost, cost )"),
    ("Scorecard", "Campaigns", "0", "number of campaigns", "COUNTROWS ( campaign_scorecard )"),
    ("Funnel", "Registrations", "#,0", "sign-ups", "SUM ( funnel_by_region_channel[registrations] )"),
    ("Funnel", "KYC submitted", "#,0", "within 7 days", "SUM ( funnel_by_region_channel[kyc_submitted] )"),
    ("Funnel", "KYC passed", "#,0", "within 7 days", "SUM ( funnel_by_region_channel[kyc_passed] )"),
    ("Funnel", "First deposit 7d", "#,0", "within 7 days of sign-up", "SUM ( funnel_by_region_channel[first_deposit_7d] )"),
    ("Funnel", "First trade 7d", "#,0", "within 7 days of sign-up", "SUM ( funnel_by_region_channel[first_trade_7d] )"),
    ("Funnel", "Sign-up to deposit %", "0.0%", "first deposit within 7 days / sign-ups",
     "DIVIDE ( [First deposit 7d], [Registrations] )"),
    ("Cohorts", "Cohort retention", "0.0%", "active users / cohort size",
     "DIVIDE ( SUM ( cohort_matrix_weekly[active_users] ), SUM ( cohort_matrix_weekly[cohort_size] ) )"),
    ("Cohorts", "Retention D30", "0.0%", "depositor-weighted 30-day retention",
     "DIVIDE ( SUMX ( retention_by_channel_month, retention_by_channel_month[retention_d30] * "
     "retention_by_channel_month[depositors_full_30d] ), SUM ( retention_by_channel_month[depositors_full_30d] ) )"),
]


def qn(name):
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) else "'" + name.replace("'", "''") + "'"


def indent(text, n):
    return "\n".join("\t" * n + line if line else line for line in text.split("\n"))


def frame(name):
    df = pd.read_csv(PROC / f"{name}.csv")
    if name == "retention_by_channel_month":
        df = df[df.channel != "ALL"]
    return df[KEEP[name]] if name in KEEP else df


def col_types(df):
    out = []
    for c in df.columns:
        s = df[c]
        if c in ("cohort_week", "dep_month"):
            out.append((c, "dateTime", "type date"))
        elif pd.api.types.is_integer_dtype(s) or pd.api.types.is_bool_dtype(s):
            out.append((c, "int64", "Int64.Type"))
        elif pd.api.types.is_float_dtype(s):
            out.append((c, "double", "type number"))
        else:
            out.append((c, "string", "type text"))
    return out


def m_query(name, cols):
    types = ", ".join(f'{{"{c}", {m}}}' for c, _, m in cols)
    src = f'{name}_model.csv' if name == "retention_by_channel_month" else f"{name}.csv"
    return ("let\n"
            f'    Source = Csv.Document(File.Contents(DataFolder & "{src}"), [Delimiter=",", Encoding=65001, '
            "QuoteStyle=QuoteStyle.Csv]),\n"
            "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n"
            f'    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, "en-US")\n'
            "in\n    Typed")


def table_tmdl(name):
    df = frame(name)
    if name == "retention_by_channel_month":
        df.to_csv(PROC / f"{name}_model.csv", index=False)      # channels only (no ALL row) for the model
    cols = col_types(df)
    mq = m_query(name, cols)
    (PBI / "power_query" / f"{name}.pq").write_text(f"// {name}: {TABLES[name]}\n{mq}\n", encoding="utf-8")
    lines = [f"/// {TABLES[name]} (SIMULATED)", f"table {name}", f"\tlineageTag: {tag(name)}", ""]
    for c, t, _ in cols:
        lines += [f"\tcolumn {qn(c)}", f"\t\tdataType: {t}"]
        if t == "dateTime":
            lines.append("\t\tformatString: yyyy-mm-dd")
        lines += [f"\t\tlineageTag: {tag(name, c)}", "\t\tsummarizeBy: none", f"\t\tsourceColumn: {c}", ""]
        if t == "dateTime":
            lines += ["\t\tannotation UnderlyingDateTimeDataType = Date", ""]
    lines += [f"\tpartition {name} = m", "\t\tmode: import", "\t\tsource =", indent(mq, 4), ""]
    return "\n".join(lines)


def measures_tmdl():
    lines = ["/// All measures (dictionary: METRICS.md)", "table _Measures", f"\tlineageTag: {tag('_Measures')}", ""]
    for folder, name, fmt, desc, dax in MEASURES:
        lines.append(f"\t/// {desc}")
        lines += [f"\tmeasure {qn(name)} =", indent(dax, 3)] if "\n" in dax else [f"\tmeasure {qn(name)} = {dax}"]
        lines += [f"\t\tformatString: {fmt}", f"\t\tdisplayFolder: {folder}", f"\t\tlineageTag: {tag('m', name)}", ""]
    lines += ["\tcolumn Measures", "\t\tdataType: string", "\t\tisHidden", f"\t\tlineageTag: {tag('_Measures', 'c')}",
              "\t\tsummarizeBy: none", "\t\tsourceColumn: Measures", "",
              "\tpartition _Measures = m", "\t\tmode: import", "\t\tsource = #table(type table [Measures = text], {})", ""]
    return "\n".join(lines)


def write_model(data_folder):
    if DEF.exists():
        shutil.rmtree(DEF)
    (DEF / "tables").mkdir(parents=True)
    pq = PBI / "power_query"
    if pq.exists():
        shutil.rmtree(pq)
    pq.mkdir(parents=True)
    (SM / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": tag("logical", "sm")}}, indent=2), encoding="utf-8")
    (SM / "definition.pbism").write_text(json.dumps({"version": "4.2", "settings": {}}, indent=2), encoding="utf-8")
    (DEF / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1606\n\n", encoding="utf-8")
    all_t = list(TABLES) + ["_Measures"]
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: en-US", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
             "annotation __PBI_TimeIntelligenceEnabled = 0", "",
             f"annotation PBI_QueryOrder = {json.dumps(['DataFolder'] + all_t)}", ""]
    model += [f"ref table {qn(t)}" for t in all_t]
    (DEF / "model.tmdl").write_text("\n".join(model) + "\n", encoding="utf-8")
    (DEF / "expressions.tmdl").write_text("\n".join([
        "/// Folder of the CSV files (data/processed of your copy of the repository, with a trailing backslash).",
        f'expression DataFolder = "{data_folder}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
        f"\tlineageTag: {tag('DataFolder')}", "", "\tannotation PBI_ResultType = Text", ""]), encoding="utf-8")
    for t in TABLES:
        (DEF / "tables" / f"{t}.tmdl").write_text(table_tmdl(t), encoding="utf-8")
    (DEF / "tables" / "_Measures.tmdl").write_text(measures_tmdl(), encoding="utf-8")
    dax = ["// Growth campaign case study - all DAX measures (SIMULATED exchange).", ""]
    for folder, name, fmt, desc, d in MEASURES:
        dax += [f"// [{folder}] {desc}  Format: {fmt}", f"[{name}] =", indent(d, 1).replace("\t", "    "), ""]
    (PBI / "measures.dax").write_text("\n".join(dax), encoding="utf-8")


def write_report_shell():
    (RP / "definition").mkdir(parents=True, exist_ok=True)
    (RP / ".platform").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NAME},
        "config": {"version": "2.0", "logicalId": tag("logical", "rp")}}, indent=2), encoding="utf-8")
    (RP / "definition.pbir").write_text(json.dumps({"version": "4.0", "datasetReference": {
        "byPath": {"path": f"../{NAME}.SemanticModel"}}}, indent=2), encoding="utf-8")
    (RP / "definition" / "version.json").write_text(json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0"}, indent=2), encoding="utf-8")
    theme = {"name": "Growth Case Study", "dataColors": [BLUE, ORANGE, "#1E7B4F", "#6B4FA0", "#B8A27A", "#B42F2F",
                                                         "#3F8FA6", GREY],
             "background": "#FFFFFF", "foreground": INK, "tableAccent": BLUE,
             "textClasses": {"label": {"fontFace": "Segoe UI", "fontSize": 10, "color": INK2},
                             "title": {"fontFace": "Segoe UI Semibold", "fontSize": 12, "color": INK}}}
    res = RP / "StaticResources"
    (res / "RegisteredResources").mkdir(parents=True, exist_ok=True)
    (res / "RegisteredResources" / "GrowthCaseStudy.json").write_text(json.dumps(theme, indent=2), encoding="utf-8")
    base = res / "SharedResources" / "BaseThemes"
    base.mkdir(parents=True, exist_ok=True)
    src = Path("C:/case-study-eays/powerbi/RailPunctuality.Report/StaticResources/SharedResources/BaseThemes/"
               "Fluent2-CY26SU10.json")
    if src.exists() and not (base / src.name).exists():
        shutil.copy(src, base / src.name)          # Power BI Desktop's own base theme file
    ver = {"visual": "2.14.0", "report": "3.4.0", "page": "2.3.1"}
    report = {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
              "themeCollection": {
                  "baseTheme": {"name": "Fluent2-CY26SU10", "reportVersionAtImport": ver, "type": "SharedResources"},
                  "customTheme": {"name": "GrowthCaseStudy.json", "reportVersionAtImport": ver, "type": "RegisteredResources"}},
              "resourcePackages": [
                  {"name": "SharedResources", "type": "SharedResources",
                   "items": [{"name": "Fluent2-CY26SU10", "path": "BaseThemes/Fluent2-CY26SU10.json", "type": "BaseTheme"}]},
                  {"name": "RegisteredResources", "type": "RegisteredResources",
                   "items": [{"name": "GrowthCaseStudy.json", "path": "GrowthCaseStudy.json", "type": "CustomTheme"}]}],
              "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                           "defaultDrillFilterOtherVisuals": True, "useEnhancedTooltips": True}}
    (RP / "definition" / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (PBI / f"{NAME}.pbip").write_text(json.dumps({"version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
                                                  "settings": {"enableAutoRecovery": True}}, indent=2), encoding="utf-8")


# ======================================================================== report pages
L, R, TOP, GAP = 32, 1888, 156, 20


def cols(n, x0=L, x1=R):
    w = (x1 - x0 - (n - 1) * GAP) / n
    return [(x0 + i * (w + GAP), w) for i in range(n)]


def C(t, c):
    return col(t, c)


def write_pages():
    F = json.loads((PROC / "findings.json").read_text(encoding="utf-8"))
    ev = F["sim"]["events"]
    if PAGES.exists():
        shutil.rmtree(PAGES)
    PAGES.mkdir(parents=True)
    src = "Source: simulated exchange (seed 42), data/processed/*.csv"

    p = Page("p1scorecard", "Campaign scorecard", SIM)
    p.header("Campaign scorecard: the cheapest campaign lost money",
             f"CMP014 had the lowest CAC ({ev['E1']['cac']:.2f} USD) but a 30-day ROI of {ev['E1']['roi_30d']:+.0%}: "
             f"{ev['E1']['withdrew_90pct']:.0%} of its depositors withdrew >= 90% within 30 days. Decide on ROI and "
             "incremental effect, not on CAC alone.")
    for (x, w), (m, t) in zip(cols(4), [("First depositors", "First depositors (attributed)"), ("CAC", "CAC (USD)"),
                                         ("ROI 30d", "30-day ROI"), ("Campaigns", "Campaigns")]):
        p.card(f"c_{m[:4]}".replace(" ", ""), x, TOP, w, 120, m, t)
    t = "campaign_scorecard"
    p.chart("tbl", "tableEx", L, TOP + 140, 1100, 720,
            {"Values": [C(t, c) for c in ["campaign_id", "type", "region", "channel", "attributed_first_depositors",
                                          "cac_first_deposit", "roi_30d", "share_withdrew_90pct_30d", "did_lift",
                                          "status"]]}, "Campaigns", table_style())
    p.chart("roi", "clusteredBarChart", L + 1120, TOP + 140, R - L - 1120, 720,
            {"Category": [C(t, "campaign_id")], "Y": [meas("ROI 30d")]}, "30-day ROI by campaign",
            sort=(meas("ROI 30d"), "Ascending"))
    p.footer(src)
    p.write()

    p = Page("p2funnel", "Funnel", SIM)
    f = F["sim"]["funnel"]
    p.header("Funnel: one sign-up in four makes a first deposit within 7 days",
             f"{f['registrations']:,} sign-ups, {f['reg_to_deposit_7d']:.1%} first deposit within 7 days; KYC pass rate "
             f"{f['kyc_pass_of_submitted']:.0%} of submissions. Filter by region and channel.")
    t = "funnel_by_region_channel"
    p.slicer("s_region", L, TOP, 300, 90, C(t, "region"), "Region")
    p.slicer("s_channel", L + 320, TOP, 300, 90, C(t, "channel"), "Channel")
    p.chart("steps", "clusteredColumnChart", L, TOP + 110, 1100, 740,
            {"Y": [meas(m) for m in ["Registrations", "KYC submitted", "KYC passed", "First deposit 7d",
                                     "First trade 7d"]]}, "Funnel steps (7-day windows)")
    p.chart("conv", "clusteredBarChart", L + 1120, TOP + 110, R - L - 1120, 740,
            {"Category": [C(t, "channel")], "Y": [meas("Sign-up to deposit %")]}, "Sign-up to first deposit by channel",
            sort=(meas("Sign-up to deposit %"), "Descending"))
    p.footer(src)
    p.write()

    p = Page("p3cohorts", "Cohorts & retention", SIM)
    e7 = ev["E7"]
    p.header("Retention fell overall but rose in every channel",
             f"30-day retention went from {e7['overall_sep']:.1%} (Sep) to {e7['overall_oct']:.1%} (Oct) while it rose in "
             f"{e7['channels_up']} of {e7['channels']} channels: the affiliate share of new depositors went from "
             f"{e7['affiliate_share_sep']:.0%} to {e7['affiliate_share_oct']:.0%} (mix effect).")
    t = "cohort_matrix_weekly"
    p.chart("matrix", "pivotTable", L, TOP, 1100, 860,
            {"Rows": [C(t, "cohort_week")], "Columns": [C(t, "weeks_since")], "Values": [meas("Cohort retention")]},
            "Weekly cohorts: % of first depositors active in week W+k", table_style())
    t = "retention_by_channel_month"
    p.chart("ret", "clusteredColumnChart", L + 1120, TOP, R - L - 1120, 860,
            {"Category": [C(t, "channel")], "Y": [meas("Retention D30")], "Series": [C(t, "dep_month")]},
            "30-day retention by channel, Sep vs Oct")
    p.footer(src)
    p.write()
    (PAGES / "pages.json").write_text(json.dumps({"$schema": PAGES_SCHEMA, "pageOrder": ["p1scorecard", "p2funnel",
                                                                                         "p3cohorts"],
                                                  "activePageName": "p1scorecard"}, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-folder", default=PLACEHOLDER)
    a = ap.parse_args()
    write_model(a.data_folder)
    write_report_shell()
    write_pages()
    print(f"[pbip] {len(TABLES)} tables, {len(MEASURES)} measures, 3 pages -> powerbi/{NAME}.pbip")


if __name__ == "__main__":
    main()
