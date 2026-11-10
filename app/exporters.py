"""Export of the folder list to PDF, TXT, CSV, XLSX, HTML and JSON.

Each format has its own function `export_xxx(ctx, path)`: to add a format, write a new
function and register it in EXPORTERS (and in FORMATS).
"""
from __future__ import annotations

import csv
import html
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, List, Tuple
from xml.sax.saxutils import escape as xml_escape

from .i18n import tr
from .scanner import ScanResult, SkippedFolder

PROGRAM_NAME = "Pino's Folder Scanner"
FORMATS = ["pdf", "txt", "csv", "xlsx", "html", "json"]

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class ExportContext:
    result: ScanResult
    lang: str
    generated_at: datetime
    depth_label: str


# ---------------------------------------------------------------- common helpers
def _clean(text: str) -> str:
    return _CTRL.sub("", text)


def _format_duration(seconds: float) -> str:
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _reason_text(ctx: ExportContext, item: SkippedFolder) -> str:
    if item.code == "denied":
        return tr(ctx.lang, "reason_denied")
    if item.code == "notfound":
        return tr(ctx.lang, "reason_notfound")
    return tr(ctx.lang, "reason_error", d=_clean(item.detail))


def _summary_rows(ctx: ExportContext) -> List[Tuple[str, str]]:
    r = ctx.result
    L = ctx.lang
    return [
        (tr(L, "rep_scanned_path"), r.root),
        (tr(L, "rep_date"), ctx.generated_at.strftime("%Y-%m-%d %H:%M:%S")),
        (tr(L, "rep_depth"), ctx.depth_label),
        (tr(L, "rep_hidden"), tr(L, "rep_hidden_yes" if r.include_hidden else "rep_hidden_no")),
        (tr(L, "rep_total"), f"{len(r.folders):,}"),
        (tr(L, "rep_skipped_count"), str(len(r.skipped))),
        (tr(L, "rep_duration"), _format_duration(r.duration)),
    ]


# ---------------------------------------------------------------- TXT
def export_txt(ctx: ExportContext, path: str) -> List[str]:
    L = ctx.lang
    lines: List[str] = [PROGRAM_NAME, tr(L, "rep_title").upper(), "=" * 70]
    for label, value in _summary_rows(ctx):
        lines.append(f"{label}: {value}")
    lines += ["=" * 70, "", tr(L, "rep_list_title"), "-" * 70]
    lines += [_clean(f) for f in ctx.result.folders] or [tr(L, "rep_empty")]
    lines += ["", tr(L, "rep_skipped_title", n=len(ctx.result.skipped)), "-" * 70]
    if ctx.result.skipped:
        for item in ctx.result.skipped:
            lines.append(f"{_clean(item.path)}  [{_reason_text(ctx, item)}]")
    else:
        lines.append(tr(L, "rep_skipped_none"))
    with open(path, "w", encoding="utf-8-sig", newline="\r\n") as fh:
        fh.write("\n".join(lines) + "\n")
    return [path]


# ---------------------------------------------------------------- CSV
def export_csv(ctx: ExportContext, path: str) -> List[str]:
    L = ctx.lang
    delim = ","
    created = [path]
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=delim)
        writer.writerow([tr(L, "rep_path")])
        for folder in ctx.result.folders:
            writer.writerow([_clean(folder)])
    if ctx.result.skipped:
        base, ext = os.path.splitext(path)
        extra = base + tr(L, "csv_skipped_suffix") + ext
        with open(extra, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.writer(fh, delimiter=delim)
            writer.writerow([tr(L, "rep_path"), tr(L, "rep_reason")])
            for item in ctx.result.skipped:
                writer.writerow([_clean(item.path), _reason_text(ctx, item)])
        created.append(extra)
    return created


# ---------------------------------------------------------------- XLSX
def export_xlsx(ctx: ExportContext, path: str) -> List[str]:
    from openpyxl import Workbook
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
    from openpyxl.styles import Alignment, Font, PatternFill

    L = ctx.lang

    def safe(text: str) -> str:
        return ILLEGAL_CHARACTERS_RE.sub("", text)

    wb = Workbook(write_only=True)
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", start_color="3730A3", end_color="3730A3")

    def head_cell(ws, text):
        cell = WriteOnlyCell(ws, value=text)
        cell.font = head_font
        cell.fill = head_fill
        cell.alignment = Alignment(vertical="center")
        return cell

    # Sheet 1: folder list
    ws = wb.create_sheet(title=tr(L, "rep_sheet_folders"))
    ws.column_dimensions["A"].width = 120
    ws.freeze_panes = "A2"
    ws.append([head_cell(ws, tr(L, "rep_path"))])
    for folder in ctx.result.folders:
        ws.append([safe(folder)])
    ws.auto_filter.ref = f"A1:A{max(1, len(ctx.result.folders) + 1)}"

    # Sheet 2: summary
    ws2 = wb.create_sheet(title=tr(L, "rep_summary"))
    ws2.column_dimensions["A"].width = 34
    ws2.column_dimensions["B"].width = 90
    for label, value in _summary_rows(ctx):
        bold = WriteOnlyCell(ws2, value=label)
        bold.font = Font(bold=True)
        ws2.append([bold, safe(value)])
    ws2.append([])
    ws2.append([tr(L, "rep_created_with"), PROGRAM_NAME])

    # Sheet 3: folders not scanned
    ws3 = wb.create_sheet(title=tr(L, "rep_sheet_skipped"))
    ws3.column_dimensions["A"].width = 100
    ws3.column_dimensions["B"].width = 40
    ws3.freeze_panes = "A2"
    ws3.append([head_cell(ws3, tr(L, "rep_path")), head_cell(ws3, tr(L, "rep_reason"))])
    for item in ctx.result.skipped:
        ws3.append([safe(item.path), safe(_reason_text(ctx, item))])

    wb.save(path)
    return [path]


# ---------------------------------------------------------------- JSON
def export_json(ctx: ExportContext, path: str) -> List[str]:
    r = ctx.result
    data = {
        "program": PROGRAM_NAME,
        "generated_at": ctx.generated_at.isoformat(timespec="seconds"),
        "scanned_path": r.root,
        "depth": {"max_levels": r.max_depth, "label": ctx.depth_label},
        "include_hidden_and_system": r.include_hidden,
        "scan_seconds": round(r.duration, 2),
        "folder_count": len(r.folders),
        "folders": list(r.folders),
        "not_scanned_count": len(r.skipped),
        "not_scanned": [
            {"path": s.path, "reason": s.code, "detail": s.detail} for s in r.skipped
        ],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    return [path]


# ---------------------------------------------------------------- HTML
_HTML_TEMPLATE = """<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;min-height:100vh;font-family:'Segoe UI Variable','Segoe UI',system-ui,sans-serif;color:#f4f6ff;
background:radial-gradient(900px 500px at 8% -10%,rgba(99,102,241,.55),transparent 60%),
radial-gradient(800px 500px at 100% 30%,rgba(45,212,191,.28),transparent 60%),
linear-gradient(135deg,#080c1c,#161040 55%,#08203a);background-attachment:fixed;padding:32px 20px 60px}}
.wrap{{max-width:1000px;margin:0 auto}}
h1{{font-size:28px;margin:0 0 4px}}
.sub{{color:rgba(255,255,255,.65);margin-bottom:24px}}
.card{{background:linear-gradient(145deg,rgba(255,255,255,.14),rgba(255,255,255,.05));border:1px solid rgba(255,255,255,.18);
border-radius:20px;padding:22px 24px;margin-bottom:20px;backdrop-filter:blur(18px);box-shadow:0 18px 44px rgba(0,0,0,.35)}}
h2{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:rgba(255,255,255,.7);margin:0 0 14px}}
dl{{display:grid;grid-template-columns:max-content 1fr;gap:8px 20px;margin:0}}
dt{{color:rgba(255,255,255,.65)}} dd{{margin:0;font-weight:600;word-break:break-all}}
input{{width:100%;padding:12px 16px;border-radius:12px;border:1px solid rgba(255,255,255,.2);background:rgba(8,12,28,.55);
color:#fff;font-size:15px;margin-bottom:10px}}
.count{{color:#99f6e4;font-size:13px;margin-bottom:10px}}
ul{{list-style:none;margin:0;padding:0;font-family:Consolas,'Courier New',monospace;font-size:13px}}
li{{padding:6px 4px;border-bottom:1px solid rgba(255,255,255,.07);word-break:break-all}}
.reason{{color:#fecdd3;font-family:'Segoe UI',sans-serif;font-size:12px;margin-left:8px}}
.empty{{color:rgba(255,255,255,.65)}}
footer{{text-align:center;color:rgba(255,255,255,.5);font-size:12px;margin-top:30px}}
</style>
</head>
<body>
<div class="wrap">
<h1>{title}</h1>
<div class="sub">{program}</div>
<div class="card"><h2>{summary_title}</h2><dl>{summary}</dl></div>
<div class="card">
<h2>{list_title}</h2>
<input id="q" type="search" placeholder="{search}" aria-label="{search}">
<div class="count" id="cnt"></div>
<ul id="list">{items}</ul>
{empty}
</div>
<div class="card"><h2>{skipped_title}</h2>{skipped}</div>
<footer>{program}</footer>
</div>
<script>
(function(){{
var q=document.getElementById('q'),items=document.querySelectorAll('#list li'),cnt=document.getElementById('cnt');
var tpl={shown_tpl};
function upd(){{var t=q.value.toLowerCase(),n=0;
for(var i=0;i<items.length;i++){{var ok=items[i].textContent.toLowerCase().indexOf(t)!==-1;items[i].style.display=ok?'':'none';if(ok)n++;}}
cnt.textContent=tpl.replace('{{n}}',n);}}
q.addEventListener('input',upd);upd();
}})();
</script>
</body>
</html>
"""


def export_html(ctx: ExportContext, path: str) -> List[str]:
    L = ctx.lang
    r = ctx.result
    esc = lambda s: html.escape(_clean(s))
    summary = "".join(f"<dt>{esc(a)}</dt><dd>{esc(b)}</dd>" for a, b in _summary_rows(ctx))
    items = "".join(f"<li>{esc(f)}</li>" for f in r.folders)
    empty = "" if r.folders else f'<p class="empty">{esc(tr(L, "rep_empty"))}</p>'
    if r.skipped:
        skipped = "<ul>" + "".join(
            f'<li>{esc(s.path)}<span class="reason">{esc(_reason_text(ctx, s))}</span></li>' for s in r.skipped
        ) + "</ul>"
    else:
        skipped = f'<p class="empty">{esc(tr(L, "rep_skipped_none"))}</p>'
    page = _HTML_TEMPLATE.format(
        lang=L,
        title=esc(tr(L, "rep_title")),
        program=esc(PROGRAM_NAME),
        summary_title=esc(tr(L, "rep_summary")),
        summary=summary,
        list_title=esc(tr(L, "rep_list_title")),
        search=esc(tr(L, "html_search")),
        items=items,
        empty=empty,
        skipped_title=esc(tr(L, "rep_skipped_title", n=len(r.skipped))),
        skipped=skipped,
        shown_tpl=json.dumps(tr(L, "html_shown", n="{n}"), ensure_ascii=False),
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)
    return [path]


# ---------------------------------------------------------------- PDF
_pdf_fonts: Tuple[str, str] | None = None


def _register_pdf_fonts() -> Tuple[str, str]:
    """Register a Unicode font (Segoe UI / Arial on Windows). If none is found, use Helvetica."""
    global _pdf_fonts
    if _pdf_fonts:
        return _pdf_fonts
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    windir = os.environ.get("WINDIR", r"C:\Windows")
    fonts_dir = os.path.join(windir, "Fonts")
    candidates = [
        (os.path.join(fonts_dir, "segoeui.ttf"), os.path.join(fonts_dir, "segoeuib.ttf")),
        (os.path.join(fonts_dir, "arial.ttf"), os.path.join(fonts_dir, "arialbd.ttf")),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for regular, bold in candidates:
        if os.path.exists(regular) and os.path.exists(bold):
            try:
                pdfmetrics.registerFont(TTFont("AppFont", regular))
                pdfmetrics.registerFont(TTFont("AppFont-Bold", bold))
                pdfmetrics.registerFontFamily(
                    "AppFont", normal="AppFont", bold="AppFont-Bold", italic="AppFont", boldItalic="AppFont-Bold"
                )
                _pdf_fonts = ("AppFont", "AppFont-Bold")
                return _pdf_fonts
            except Exception:
                continue
    _pdf_fonts = ("Helvetica", "Helvetica-Bold")
    return _pdf_fonts


# Fallback fonts for characters the main font does not have (Japanese, Chinese, Korean, symbols).
# The first font that contains the character wins. Files that do not exist are ignored.
_FALLBACK_FONTS = [
    ("YuGothR.ttc", 0),
    ("msyh.ttc", 0),
    ("malgun.ttf", 0),
    ("simsun.ttc", 0),
    ("seguisym.ttf", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),  # only used when testing on Linux
    ("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf", 0),
]
_pdf_chain: List[Tuple[str, frozenset]] | None = None  # [(font name, characters covered)]


def _font_coverage(font_name: str) -> frozenset:
    from reportlab.pdfbase import pdfmetrics

    if font_name.startswith("Helvetica"):  # built-in font: Windows-1252 characters only
        return frozenset(bytes(range(32, 256)).decode("cp1252", errors="ignore"))
    face = pdfmetrics.getFont(font_name).face
    return frozenset(chr(c) for c in face.charToGlyph if c <= 0xFFFF)


def _pdf_font_chain() -> List[Tuple[str, frozenset]]:
    """[(main font, coverage), (fallback 1, coverage), ...] - computed only once."""
    global _pdf_chain
    if _pdf_chain is not None:
        return _pdf_chain
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font, _bold = _register_pdf_fonts()
    chain = [(font, _font_coverage(font))]
    fonts_dir = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for i, (file, index) in enumerate(_FALLBACK_FONTS):
        full = file if os.path.isabs(file) else os.path.join(fonts_dir, file)
        if not os.path.exists(full):
            continue
        name = f"AppFallback{i}"
        try:
            pdfmetrics.registerFont(TTFont(name, full, subfontIndex=index))
            chain.append((name, _font_coverage(name)))
        except Exception:  # unusable font (e.g. PostScript outlines): try the next one
            continue
    _pdf_chain = chain
    return chain


def _pdf_markup(text: str) -> str:
    """Text ready for a Paragraph: special characters escaped and fallback fonts where needed."""
    text = _clean(text)
    chain = _pdf_font_chain()
    main_cov = chain[0][1]
    if set(text) <= main_cov or len(chain) == 1:
        return xml_escape(text)
    out: List[str] = []
    current = chain[0][0]
    buf: List[str] = []

    def flush() -> None:
        if buf:
            piece = xml_escape("".join(buf))
            out.append(piece if current == chain[0][0] else f'<font name="{current}">{piece}</font>')
            buf.clear()

    for ch in text:
        target = chain[0][0]
        if ch not in main_cov:
            for name, cov in chain[1:]:
                if ch in cov:
                    target = name
                    break
        if target != current:
            flush()
            current = target
        buf.append(ch)
    flush()
    return "".join(out)


def export_pdf(ctx: ExportContext, path: str) -> List[str]:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import (
        BaseDocTemplate,
        Frame,
        HRFlowable,
        PageTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )

    L = ctx.lang
    r = ctx.result
    font, bold = _register_pdf_fonts()
    ink = colors.HexColor("#111827")
    muted = colors.HexColor("#6b7280")
    accent = colors.HexColor("#3730a3")

    def clean_xml(text: str) -> str:
        return _pdf_markup(text)

    st_title = ParagraphStyle("t", fontName=bold, fontSize=21, leading=26, textColor=accent)
    st_sub = ParagraphStyle("s", fontName=font, fontSize=10, leading=13, textColor=muted)
    st_h2 = ParagraphStyle("h2", fontName=bold, fontSize=12.5, leading=16, textColor=accent, spaceBefore=14, spaceAfter=6)
    st_cell = ParagraphStyle("c", fontName=font, fontSize=9.5, leading=12.5, textColor=ink, wordWrap="CJK")
    st_cell_b = ParagraphStyle("cb", parent=st_cell, fontName=bold, textColor=muted)
    st_path_single = ParagraphStyle(
        "p1", fontName=font, fontSize=9, leading=12, textColor=ink, wordWrap="CJK", leftIndent=14, firstLineIndent=-14,
        spaceAfter=1.5,
    )
    st_path_chunk = ParagraphStyle("pc", fontName=font, fontSize=9, leading=12.5, textColor=ink, wordWrap="CJK")
    st_note = ParagraphStyle("n", fontName=font, fontSize=10, leading=13, textColor=muted)

    story: list = [
        Paragraph(clean_xml(tr(L, "rep_title")), st_title),
        Paragraph(clean_xml(PROGRAM_NAME), st_sub),
        Spacer(1, 4),
        HRFlowable(width="100%", thickness=2, color=accent, spaceAfter=10),
    ]

    rows = [[Paragraph(clean_xml(a), st_cell_b), Paragraph(clean_xml(b), st_cell)] for a, b in _summary_rows(ctx)]
    table = Table(rows, colWidths=[52 * mm, None], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f3ff")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story += [table, Paragraph(clean_xml(tr(L, "rep_list_title")), st_h2)]

    if not r.folders:
        story.append(Paragraph(clean_xml(tr(L, "rep_empty")), st_note))
    elif len(r.folders) <= 4000:
        for folder in r.folders:
            story.append(Paragraph(clean_xml(folder), st_path_single))
    else:
        chunk = 40
        for i in range(0, len(r.folders), chunk):
            block = "<br/>".join(clean_xml(f) for f in r.folders[i : i + chunk])
            story.append(Paragraph(block, st_path_chunk))
            story.append(Spacer(1, 1.5))

    story.append(Paragraph(clean_xml(tr(L, "rep_skipped_title", n=len(r.skipped))), st_h2))
    if r.skipped:
        data = [[Paragraph(clean_xml(tr(L, "rep_path")), st_cell_b), Paragraph(clean_xml(tr(L, "rep_reason")), st_cell_b)]]
        for s in r.skipped:
            data.append([Paragraph(clean_xml(s.path), st_cell), Paragraph(clean_xml(_reason_text(ctx, s)), st_cell)])
        sk = Table(data, colWidths=[None, 42 * mm], repeatRows=1, hAlign="LEFT")
        sk.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f5f3ff")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(sk)
    else:
        story.append(Paragraph(clean_xml(tr(L, "rep_skipped_none")), st_note))

    footer_left = PROGRAM_NAME
    page_tpl = tr(L, "rep_page", p="{p}", n="{n}")

    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_pages: list = []

        def showPage(self):
            self._saved_pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved_pages)
            for state in self._saved_pages:
                self.__dict__.update(state)
                self._draw_footer(total)
                super().showPage()
            super().save()

        def _draw_footer(self, total: int):
            width, _ = A4
            self.setStrokeColor(colors.HexColor("#d1d5db"))
            self.setLineWidth(0.5)
            self.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
            self.setFont(font, 8.5)
            self.setFillColor(muted)
            self.drawString(18 * mm, 10 * mm, footer_left)
            self.drawRightString(width - 18 * mm, 10 * mm, page_tpl.format(p=self._pageNumber, n=total))

    doc = BaseDocTemplate(
        path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=tr(L, "rep_title"),
        author=PROGRAM_NAME,
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame])])
    doc.build(story, canvasmaker=NumberedCanvas)
    return [path]


# ---------------------------------------------------------------- orchestration
EXPORTERS: Dict[str, Callable[[ExportContext, str], List[str]]] = {
    "pdf": export_pdf,
    "txt": export_txt,
    "csv": export_csv,
    "xlsx": export_xlsx,
    "html": export_html,
    "json": export_json,
}


def target_paths(base: str, formats: List[str]) -> List[str]:
    return [f"{base}.{fmt}" for fmt in formats]


def export_all(ctx: ExportContext, formats: List[str], base: str) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Create all the requested formats. An error in one format does not block the others.

    Returns (files_created, errors) where errors = [(format, message)].
    """
    created: List[str] = []
    errors: List[Tuple[str, str]] = []
    for fmt in formats:
        try:
            created += EXPORTERS[fmt](ctx, f"{base}.{fmt}")
        except Exception as exc:  # noqa: BLE001 - keep going with the other formats
            errors.append((fmt.upper(), str(exc)))
    return created, errors
