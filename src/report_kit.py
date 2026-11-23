"""Shared HTML layout and PDF printing for build_pdf.py and the campaign readouts (tools/campaign_readout.py).

Pages are 16:9 HTML (grey-beige background, white cards, Segoe UI), printed to PDF with headless Edge (or Chrome),
then rewritten with empty metadata.
"""
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DISCLAIMER = "Independent case study based on public data · not affiliated with or endorsed by Binance · Not investment advice"
TAGS = {"PUBLIC": '<span class="tag tag-public">PUBLIC DATA</span>', "SIM": '<span class="tag tag-simulated">SIMULATED</span>',
        "BOTH": '<span class="tag tag-public">PUBLIC DATA</span> <span class="tag tag-simulated">SIMULATED</span>'}


def ai_note():
    """The AI-use note is written once, in README.md (Methods), and reused verbatim."""
    for line in (ROOT / "README.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("> AI-assisted workflow:"):
            return line[2:].strip()
    raise ValueError("AI note not found in README.md")


def page(n, title, subtitle, body, sources, collected="23 Nov 2026", total=None):
    num = f"{n + 1} / {total}" if total else str(n)
    return f"""
<section class="page">
  <header><div><h1>{title}</h1><p class="sub">{subtitle}</p></div></header>
  <main>{body}</main>
  <footer><span>{sources} · retrieved {collected}</span><span>{DISCLAIMER}</span><span>{num}</span></footer>
</section>"""


def card(inner, cls=""):
    return f'<div class="card {cls}">{inner}</div>'


def chart(src, title, tag, cap=""):
    return card(f'<h2>{title} {TAGS[tag]}</h2><figure><img src="{src}"/>{f"<figcaption>{cap}</figcaption>" if cap else ""}</figure>', "chart")


def tile(label, value, text, tag=None):
    t = f" {TAGS[tag]}" if tag else ""
    return card(f'<div class="label">{label}{t}</div><div class="big">{value}</div><p>{text}</p>', "tile")


def table(df, cols=None, cls="small"):
    cols = cols or list(df.columns)
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{v}</td>" for v in r) + "</tr>" for r in df[cols].itertuples(index=False))
    return f'<table class="{cls}"><tr>{head}</tr>{body}</table>'


CSS = """
@page { size: 1600px 900px; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: 'Segoe UI', Arial, sans-serif; color: #0B0B0B; background: #F1EFEA; }
.page { width: 1600px; height: 900px; padding: 30px 44px 22px; display: flex; flex-direction: column; page-break-after: always; overflow: hidden; background: #F1EFEA; }
header { display: flex; justify-content: space-between; align-items: flex-start; gap: 30px; }
h1 { font-size: 27px; margin: 0 0 6px; font-weight: 700; line-height: 1.15; max-width: 1450px; }
.sub { margin: 0; color: #52514E; font-size: 15px; max-width: 1450px; }
.tag { font-size: 10.5px; font-weight: 700; letter-spacing: .07em; padding: 2px 7px; border-radius: 4px; white-space: nowrap; vertical-align: 2px; margin-left: 4px; }
.tag-public { background: #E3EEFB; color: #1C5CAB; } .tag-simulated { background: #FBE9E0; color: #9A3B12; }
main { flex: 1; display: flex; flex-direction: column; gap: 12px; margin-top: 14px; min-height: 0; }
footer { display: flex; justify-content: space-between; gap: 20px; font-size: 11px; color: #898781; margin-top: 10px; }
.card { background: #FFFFFF; border: 1px solid #E1E0D9; border-radius: 8px; padding: 11px 15px; min-height: 0; overflow: hidden; }
.card h2 { font-size: 15px; margin: 0 0 6px; } .card h3 { font-size: 14px; margin: 0 0 4px; }
.card p, .card li { font-size: 13.5px; line-height: 1.4; margin: 3px 0; color: #2B2A27; }
.card ul, .card ol { padding-left: 18px; margin: 4px 0; }
.chart { display: flex; flex-direction: column; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.grid2x2 { display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 1fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.g21 { display: grid; grid-template-columns: 2fr 1fr; gap: 12px; flex: 1; min-height: 0; }
.g12 { display: grid; grid-template-columns: 1fr 2fr; gap: 12px; flex: 1; min-height: 0; }
figure { margin: 0; flex: 1; min-height: 0; display: flex; flex-direction: column; }
figure img { width: 100%; flex: 1; min-height: 0; object-fit: contain; }
figcaption { font-size: 11.5px; color: #52514E; margin-top: 3px; }
.tile .label { font-size: 12px; font-weight: 700; color: #52514E; letter-spacing: .04em; }
.tile .big { font-size: 40px; font-weight: 700; margin: 2px 0; color: #0B0B0B; }
.tile p { font-size: 13px; color: #52514E; }
.stack { display: flex; flex-direction: column; gap: 12px; min-height: 0; } .stack > .card { flex: 1; }
.auto { flex: 0 0 auto !important; }
.qs li { font-size: 14.5px !important; margin: 4px 0; }
.reco li { font-size: 13.5px !important; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th { text-align: left; color: #52514E; font-weight: 600; border-bottom: 1px solid #E1E0D9; padding: 4px 6px; }
td { border-bottom: 1px solid #EFEEE9; padding: 3px 6px; vertical-align: top; }
table.small, .small, .small li, .small p { font-size: 12.3px !important; }
.note { font-size: 11.5px !important; color: #6B6A65 !important; }
.ok { color: #1E7B4F; font-weight: 600; } .bad { color: #B42F2F; font-weight: 600; } .rev { color: #9A6A00; font-weight: 600; }
"""


def find_browser() -> str:
    for c in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              shutil.which("msedge") or "", shutil.which("google-chrome") or "", shutil.which("chromium") or ""]:
        if c and Path(c).exists():
            return c
    raise FileNotFoundError("Edge or Chrome is needed to print the PDF")


def write_html(pages, title, out_html: Path):
    out_html.write_text(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>{title}</title><style>{CSS}</style></head><body>{''.join(pages)}</body></html>""", encoding="utf-8")
    return out_html


def print_pdf(html: Path, pdf: Path, title: str) -> Path:
    tmp = pdf.with_name("_print.pdf")
    profile = tempfile.mkdtemp()            # own profile: an open Edge window would otherwise take the call
    subprocess.run([find_browser(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={profile}",
                    "--run-all-compositor-stages-before-draw", "--virtual-time-budget=5000",
                    f"--print-to-pdf={tmp}", html.as_uri()], check=True, timeout=180)
    last = -1
    for _ in range(120):                    # Edge can return before its child process has written the file
        time.sleep(1)
        size = tmp.stat().st_size if tmp.exists() else -1
        if size > 0 and size == last:
            break
        last = size
    shutil.rmtree(profile, ignore_errors=True)
    reader, writer = PdfReader(str(tmp)), PdfWriter()       # rewrite with neutral metadata
    for pg in reader.pages:
        writer.add_page(pg)
    writer.add_metadata({"/Title": title, "/Author": "", "/Creator": "", "/Producer": ""})
    with open(pdf, "wb") as fh:
        writer.write(fh)
    tmp.unlink()
    return pdf
