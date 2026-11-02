"""
pdf_builder.py
==============
v22.52 -- Η αναφορά πελάτη και σε PDF (εκτός από Word): ανοίγει σε κάθε κινητό χωρίς Word.
Από το ΙΔΙΟ markdown της αναφοράς (talent_report.client_markdown), με reportlab και γραμματοσειρά DejaVu
(ελληνικά), A4, μαύρο κείμενο σε λευκό φόντο (όπως το Word -- Κανόνας 3), αρίθμηση σελίδων.
"""
from __future__ import annotations

import html
import io
import os
import re

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_REGISTERED = False


def _fonts():
    global _REGISTERED
    if _REGISTERED:
        return
    for name, file in (("DV", "DejaVuSans.ttf"), ("DV-B", "DejaVuSans-Bold.ttf"),
                       ("DV-I", "DejaVuSans-Oblique.ttf"), ("DV-BI", "DejaVuSans-BoldOblique.ttf")):
        pdfmetrics.registerFont(TTFont(name, os.path.join(_FONT_DIR, file)))
    pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")
    _REGISTERED = True


def _styles():
    base = dict(fontName="DV", textColor="black")
    return {
        "title": ParagraphStyle("t", fontSize=17, leading=22, alignment=TA_CENTER, spaceAfter=2, fontName="DV-B"),
        "name": ParagraphStyle("n", fontSize=17, leading=22, alignment=TA_CENTER, spaceAfter=18, fontName="DV-B"),
        "h1": ParagraphStyle("h1", fontSize=14, leading=18, spaceBefore=12, spaceAfter=5, fontName="DV-B"),
        "h2": ParagraphStyle("h2", fontSize=12.5, leading=16, spaceBefore=10, spaceAfter=4, fontName="DV-B"),
        "h3": ParagraphStyle("h3", fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=3, fontName="DV-B"),
        "p": ParagraphStyle("p", fontSize=10, leading=14, spaceAfter=5, **base),
        "li": ParagraphStyle("li", fontSize=10, leading=14, spaceAfter=2, **base),
    }


def _inline(text: str) -> str:
    """Markdown μέσα στη γραμμή -> mini-HTML του reportlab (με ασφαλή escaping)."""
    t = html.escape(text, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"~~(.+?)~~", r"<strike>\1</strike>", t)
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("DV", 8.5)
    canvas.drawCentredString(A4[0] / 2, 1.1 * cm, str(doc.page))
    canvas.restoreState()


def build_report_pdf(doc_title: str, subtitle_name: str, markdown: str) -> bytes:
    _fonts()
    st = _styles()
    flow = [Paragraph(_inline(doc_title), st["title"])]
    flow.append(Paragraph(_inline(subtitle_name or ""), st["name"]) if subtitle_name else Spacer(1, 16))
    items, kind = [], None

    def flush():
        nonlocal items, kind
        if items:
            flow.append(ListFlowable(
                [ListItem(Paragraph(_inline(x), st["li"]), leftIndent=14) for x in items],
                bulletType="1" if kind == "ol" else "bullet", start="1" if kind == "ol" else "•",
                bulletFontName="DV", bulletFontSize=9, leftIndent=14))
            flow.append(Spacer(1, 4))
        items, kind = [], None

    for raw in markdown.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        m_ul = re.match(r"^\s*[-•]\s+(.*)$", line)
        m_ol = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if m_ul or (m_ol and not line.startswith("**")):
            k = "ul" if m_ul else "ol"
            if kind and kind != k:
                flush()
            kind = k
            items.append((m_ul or m_ol).group(1))
            continue
        flush()
        if line.startswith("### "):
            flow.append(Paragraph(_inline(line[4:]), st["h3"]))
        elif line.startswith("## "):
            flow.append(Paragraph(_inline(line[3:]), st["h2"]))
        elif line.startswith("# "):
            flow.append(Paragraph(_inline(line[2:]), st["h1"]))
        else:
            flow.append(Paragraph(_inline(line), st["p"]))
    flush()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm, title=doc_title, author="AstroCheck Career")
    doc.build(flow, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def pdf_filename(docx_name: str) -> str:
    return re.sub(r"\.docx$", "", docx_name or "AstroCheck") + ".pdf"
