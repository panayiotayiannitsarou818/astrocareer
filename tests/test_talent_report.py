"""v22 -- Αναφορά από τη μηχανή ταλέντων (core/talent_report.py)."""
import io
from datetime import datetime, timezone

import docx

from core.ephemeris import compute_chart
from core.talent_report import build_engine_report
from core.talent_texts import field_text, talent_text
from core.validator import _absolute_claims, _past_experience_claims, _simple_presentation_technical_terms


def _pafos():
    return compute_chart(datetime(1982, 2, 10, 23, 45, tzinfo=timezone.utc), 34.7754, 32.4218, name="Μαρία")


def test_client_report_has_every_talent_and_field_and_no_technical_terms():
    for lang in ("el", "en"):
        r = build_engine_report(_pafos(), "Μαρία", lang)
        text = r.client_text
        for t in r.result.talents:
            assert talent_text(t.theme, lang)["title"] in text
        for f in r.result.fields:
            assert field_text(f.name, lang)["name"] in text
        assert not _simple_presentation_technical_terms(text)
        assert not _absolute_claims(text) and not _past_experience_claims(text)
        body = "\n".join(p.text for p in docx.Document(io.BytesIO(r.client_docx)).paragraphs)
        assert "Μαρία" in body and talent_text(r.result.talents[0].theme, lang)["title"] in body


def test_audit_documents_indicators_and_health_barrier():
    r = build_engine_report(_pafos(), "Μαρία", "en")
    assert "ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ ΤΟΜΕΑ ΥΓΕΙΑΣ" in r.audit_text and "Δείκτης 1: Χείρωνας στον Οίκο 6" in r.audit_text
    assert "Χείρωνας–Μεσουράνημα" in r.audit_text           # δείκτες στο δελτίο, όχι στον πελάτη
    assert "Χείρωνας" not in r.client_text and "Chiron" not in r.client_text
    assert r.audit_name.endswith("Εσωτερικό_Τεχνικό_Δελτίο.docx") and r.client_name.startswith("Μαρία_")


def test_same_chart_same_report():
    a, b = build_engine_report(_pafos(), "", "el"), build_engine_report(_pafos(), "", "el")
    assert a.client_text == b.client_text and a.client_name == "AstroCheck_Anadeixi_Talenton.docx"


def test_growth_phrases_v22_5():
    """Πώς αναπτύσσεται κάθε ταλέντο: από τα είδη όψεων (κώδικας, όχι AI), σε σύνοψη και στο κείμενο."""
    from core.talent_engine import Indicator, Talent

    def tal(*aspects):
        inds = [Indicator("Όψη", f"asp:{i}", ("Ήλιος", "Κρόνος"), "x", w, a, 1.0) for i, (a, w) in enumerate(aspects)]
        inds += [Indicator("Θέση", "pos:Ήλιος", ("Ήλιος",), "x")]
        return Talent("ORG", "", "", inds, [], "δύο δείκτες").growth
    N, S, W = "Κανονική", "Στενή/ισχυρή", "Πλατιά αλλά έγκυρη"
    assert tal(("Τρίγωνο", S)) == "easy"
    assert tal(("Τρίγωνο", S), ("Τετράγωνο", N)) == "mixed"
    assert tal(("Τρίγωνο", S), ("Εξάγωνο", N)) == "opportunity"    # αρμονικές με εξάγωνο (όπως v20.18)
    assert tal(("Αντίθεση", N), ("Τρίγωνο", W)) == "practice"      # οι πλατιές δεν μετρούν
    assert tal(("Τρίγωνο", W)) == "open"
    assert tal(("Χιαστί όψη 150°", S)) == "open" and tal(("Σύνοδος", S)) == "open" and tal() == "open"
    r = build_engine_report(_pafos(), "", "el")
    assert "Συνοπτικά, τα ταλέντα σου" in r.client_text
    assert "Οργάνωση και συνέπεια — *φαίνεται να βγαίνει αβίαστα*" in r.client_text
    assert "Αίσθηση του δικαίου — *θα φανεί στην πράξη*" in r.client_text
    assert "ανάπτυξη: mixed" in r.audit_text
    # ίδιος κανόνας με το core/talent_growth.py (λειτουργία "ai"): ίδιες φράσεις
    from core.talent_growth import PHRASES
    assert PHRASES["el"]["easy"] in r.client_text


def test_dynasai_closing_line():
    for lang, word in (("el", "δύνασαι"), ("en", "you may try")):
        r = build_engine_report(_pafos(), "", lang)
        assert r.client_text.rstrip().endswith("**") and word in r.client_text.splitlines()[-1]
        assert not _absolute_claims(r.client_text)


def test_report_shows_colour_subtitle_v22_15():
    from datetime import datetime, timezone
    from core.ephemeris import compute_chart
    from core.talent_engine import run_engine
    from core.talent_report import audit_markdown, client_markdown
    chart = compute_chart(datetime(1982, 2, 10, 23, 45, tzinfo=timezone.utc), 34.7754, 32.4218)
    r = run_engine(chart)
    el = client_markdown(r, "el")
    i = el.index("Ηγεσία και πρωτοβουλία**")
    assert el[i:].split("\n")[1].startswith("*με συνεργατικό πνεύμα · ")
    assert "*with a cooperative spirit · " in client_markdown(r, "en")
    assert "Απόχρωση: «με συνεργατικό πνεύμα» από Ζυγός" in audit_markdown(chart, r)


def test_growth_sentences_not_repeated_v22_18():
    """Αναφορά Β (11/02/1982): «Η πραγματική του δύναμη θα φανεί…» βγήκε 4 φορές."""
    import re
    from datetime import datetime, timezone
    from core.ephemeris import compute_chart
    from core.talent_engine import run_engine
    from core.talent_report import TXT, client_markdown
    r = run_engine(compute_chart(datetime(1982, 2, 10, 23, 45, tzinfo=timezone.utc), 34.7754, 32.4218))
    for lang in ("el", "en"):
        text = client_markdown(r, lang)
        for options in TXT[lang]["growth_long"].values():
            assert len(options) == 4
            for sentence in options:
                assert text.count(sentence) <= 1
