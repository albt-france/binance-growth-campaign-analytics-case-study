"""excel/campaign_roi_workbook.xlsx - a working workbook with REAL formulas (SIMULATED campaign inputs).

Sheets: README · Campaign calculator (CAC, 30-day ROI, payback per campaign) · Scenarios (conversion, cost,
retention) · Holdout size (users per arm for a target effect) · Definitions.
Inputs come from data/processed/campaign_scorecard.csv; every output cell is a formula.

    python src/build_excel.py
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
OUT = ROOT / "excel" / "campaign_roi_workbook.xlsx"
INPUT = PatternFill("solid", fgColor="FFF4D6")       # yellow = input you can change
HEAD = Font(bold=True)
TAG = "SIMULATED - fictional exchange, not Binance data"


def widths(ws, w):
    for i, x in enumerate(w, 1):
        ws.column_dimensions[get_column_letter(i)].width = x


def main():
    s = pd.read_csv(PROC / "campaign_scorecard.csv")
    s = s[~s.has_holdout & s.attributed_first_depositors.notna()].sort_values("campaign_id")
    wb = Workbook()

    ws = wb.active
    ws.title = "README"
    lines = ["Campaign ROI workbook", TAG,
             "Yellow cells are inputs; every other number is a formula (change an input and the sheet recalculates).",
             "Campaign calculator: CAC = acquisition media / first depositors; 30-day ROI = (30-day net revenue - media"
             " - promo) / (media + promo); payback = days for revenue per depositor to cover cost per depositor.",
             "Scenarios: what CAC and ROI become if conversion, cost per click or retention change.",
             "Holdout size: users per arm to detect a target lift (two-sided 5%, 80% power by default).",
             "Figures are ATTRIBUTED (users who clicked a campaign), not incremental: see the PDF and the dashboard.",
             "Independent case study based on public data - not affiliated with or endorsed by Binance - "
             "Not investment advice"]
    for i, t in enumerate(lines, 1):
        ws.cell(i, 1, t).font = Font(bold=(i == 1), size=14 if i == 1 else 11)
    widths(ws, [130])

    ws = wb.create_sheet("Campaign calculator")
    hdr = ["campaign", "type", "region", "media USD", "promo USD", "first depositors", "30-day revenue / depositor",
           "CAC (media / depositor)", "total cost / depositor", "30-day ROI", "payback (days)", "verdict"]
    ws.append([TAG])
    ws.append(hdr)
    for c in ws[2]:
        c.font = HEAD
    for i, r in enumerate(s.itertuples(), start=3):
        ws.append([r.campaign_id, r.type, r.region, round(r.media_usd, 2), round(r.promo_usd, 2),
                   int(r.attributed_first_depositors),
                   None if pd.isna(r.revenue_30d_per_depositor) else round(r.revenue_30d_per_depositor, 2)])
        for col in "DEFG":
            ws[f"{col}{i}"].fill = INPUT
        ws[f"H{i}"] = f"=IFERROR(D{i}/F{i},\"\")"
        ws[f"I{i}"] = f"=IFERROR((D{i}+E{i})/F{i},\"\")"
        ws[f"J{i}"] = f"=IF(G{i}=\"\",\"too early\",(G{i}*F{i}-D{i}-E{i})/(D{i}+E{i}))"
        ws[f"K{i}"] = f"=IF(G{i}=\"\",\"\",IFERROR(I{i}/(G{i}/30),\"\"))"
        ws[f"L{i}"] = f"=IF(G{i}=\"\",\"too early\",IF(J{i}>0,\"pays back in 30 days\",\"not yet paid back\"))"
        ws[f"H{i}"].number_format = ws[f"I{i}"].number_format = "0.00"
        ws[f"J{i}"].number_format = "0%"
        ws[f"K{i}"].number_format = "0"
    n = 2 + len(s)
    ws.append([])
    ws.append(["TOTAL", "", "", f"=SUM(D3:D{n})", f"=SUM(E3:E{n})", f"=SUM(F3:F{n})", "",
               f"=D{n + 2}/F{n + 2}", f"=(D{n + 2}+E{n + 2})/F{n + 2}"])
    widths(ws, [11, 18, 11, 12, 12, 14, 16, 14, 14, 11, 12, 20])

    ws = wb.create_sheet("Scenarios")
    ws.append([TAG])
    ws.append(["input", "low", "base", "high", "note"])
    rows = [("visitors (clicks)", 50000, 50000, 50000, "same traffic in the three scenarios"),
            ("cost per click (USD)", 0.6, 0.45, 0.3, ""),
            ("click -> sign-up", 0.05, 0.07, 0.09, ""),
            ("sign-up -> first deposit (7 days)", 0.22, 0.28, 0.34, ""),
            ("net revenue per active day (USD)", 6, 8, 10, "fees + spread"),
            ("active days in 30 days per depositor", 3, 4.5, 6, "retention lever"),
            ("promo cost per depositor (USD)", 15, 10, 5, "bonus, boosted rate")]
    for r in rows:
        ws.append(list(r))
    for row in ws.iter_rows(min_row=3, max_row=9, min_col=2, max_col=4):
        for c in row:
            c.fill = INPUT
    ws.append([])
    outs = [("spend (USD)", "={c}3*{c}4"), ("sign-ups", "={c}3*{c}5"), ("first depositors", "={c}12*{c}6"),
            ("CAC per first depositor", "={c}11/{c}13"), ("30-day revenue", "={c}13*{c}7*{c}8"),
            ("promo cost", "={c}13*{c}9"), ("30-day ROI", "=({c}15-{c}11-{c}16)/({c}11+{c}16)"),
            ("payback (days)", "=({c}11+{c}16)/{c}13/{c}7/({c}8/30)")]
    for i, (lab, f) in enumerate(outs, start=11):
        ws.cell(i, 1, lab).font = HEAD
        for j, col in enumerate("BCD", start=2):
            ws.cell(i, j, f.format(c=col))
            ws.cell(i, j).number_format = "0%" if "ROI" in lab else "#,##0.00"
    widths(ws, [36, 12, 12, 12, 30])

    ws = wb.create_sheet("Holdout size")
    ws.append([TAG])
    ws.append(["input", "value", "note"])
    for r in [("baseline rate (e.g. 14-day reactivation)", 0.06, "holdout group"),
              ("target lift (absolute, points)", 0.005, "smallest effect worth detecting"),
              ("alpha (two-sided)", 0.05, ""), ("power", 0.8, ""), ("holdout share", 0.10, "share kept out")]:
        ws.append(list(r))
    for i in range(3, 8):
        ws[f"B{i}"].fill = INPUT
    ws["A9"], ws["B9"] = "z alpha/2", "=NORM.S.INV(1-B5/2)"
    ws["A10"], ws["B10"] = "z power", "=NORM.S.INV(B6)"
    ws["A11"], ws["B11"] = "total users to target", ("=ROUNDUP((B9+B10)^2*(B3*(1-B3)/B7+(B3+B4)*(1-B3-B4)/(1-B7))"
                                                     "/B4^2,0)")
    ws["A12"], ws["B12"] = "users in the holdout", "=ROUNDUP(B11*B7,0)"
    ws["A13"], ws["B13"] = "users in treatment", "=B11-B12"
    ws["C11"] = "unequal split: n_total = (z_a + z_b)^2 [p0(1-p0)/h + p1(1-p1)/(1-h)] / d^2, holdout = h x n_total"
    for c in ("A9", "A10", "A11", "A12", "A13"):
        ws[c].font = HEAD
    widths(ws, [40, 14, 80])

    ws = wb.create_sheet("Definitions")
    ws.append(["metric", "formula", "grain", "time zone", "trap"])
    for r in [("first depositor", "user whose first deposit lands after KYC approval", "user", "UTC", "dedupe events by event_id"),
              ("CAC", "acquisition media and partner fees / new first depositors", "campaign or week", "UTC (activity date)",
               "booking date moves invoices between weeks"),
              ("30-day ROI", "(30-day net revenue - media - promo) / (media + promo)", "campaign", "UTC",
               "bonus cost and withdrawals sit outside the CAC"),
              ("30-day retention", "traded on any day 24-30 after the first deposit", "first-deposit cohort", "UTC",
               "only cohorts with 30 days of follow-up"),
              ("incremental", "outcome with the campaign minus outcome without it (holdout or control regions)",
               "campaign", "UTC+8 for readouts", "attributed is not incremental")]:
        ws.append(list(r))
    for c in ws[1]:
        c.font = HEAD
    widths(ws, [18, 70, 20, 20, 45])
    for w in wb.worksheets:
        for row in w.iter_rows():
            for c in row:
                c.alignment = Alignment(wrap_text=False, vertical="top")
    wb.properties.creator = ""
    wb.properties.lastModifiedBy = ""
    wb.properties.title = "Campaign ROI workbook"
    OUT.parent.mkdir(exist_ok=True)
    wb.save(OUT)
    print(f"[excel] {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
