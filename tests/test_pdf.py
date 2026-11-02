"""v22.52: η αναφορά και σε PDF (ελληνικά, A4)."""
from datetime import date, time


def test_report_pdf_has_greek_text_and_pages():
    import pdfplumber, io
    from core.birth_input import chart_from_birth
    from core.pdf_builder import build_report_pdf, pdf_filename
    from core.talent_report import build_engine_report
    ch, _ = chart_from_birth("Παναγιώτα", date(1982, 2, 11), time(1, 45), 34.7768, 32.4245, "Asia/Nicosia")
    r = build_engine_report(ch, ch.name, "el")
    pdf = build_report_pdf("Ανάδειξη Ταλέντων", "Παναγιώτα", r.client_text)
    assert pdf.startswith(b"%PDF")
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        text = "\n".join(p.extract_text() or "" for p in doc.pages)
        assert len(doc.pages) >= 3
    assert "Παναγιώτα" in text and "Υποστήριξη και ενθάρρυνση" in text and "Πώς μαθαίνεις καλύτερα" in text
    assert "**" not in text                      # το markdown έγινε μορφοποίηση
    assert pdf_filename("AstroCheck_Anadeixi_Talenton.docx") == "AstroCheck_Anadeixi_Talenton.pdf"


def test_markup_is_escaped():
    from core.pdf_builder import _inline
    assert _inline("a < b & **c**") == "a &lt; b &amp; <b>c</b>"
