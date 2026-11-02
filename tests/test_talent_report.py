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
    assert el[i:].split("\n")[1].startswith("*με συνεργατικό πνεύμα")
    assert "*with a cooperative spirit" in client_markdown(r, "en")
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
            assert len(options) == 6
            for sentence in options:
                assert text.count(sentence) <= 1


def test_emerging_talent_is_never_described_as_effortless_v22_27():
    """Αναφορά Β: «Αισθητική» στα αναδυόμενα («πιο αχνά») με «φαίνεται να βγαίνει αβίαστα» -- αντίφαση."""
    import random
    from datetime import datetime, timedelta, timezone
    from core.ephemeris import compute_chart
    from core.talent_engine import run_engine
    from core.talent_growth import PHRASES
    from core.talent_report import TXT, client_markdown
    random.seed(31)
    seen = 0
    for _ in range(80):
        ut = datetime(1930, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=random.randint(0, 95 * 365 * 24 * 60))
        r = run_engine(compute_chart(ut, random.uniform(-45, 60), random.uniform(-120, 150)))
        text = client_markdown(r, "el")
        for t in r.talents:
            if t.rank == "αναδυόμενο" and t.growth == "easy":
                seen += 1
                assert f"{t.title_el} — *{PHRASES['el']['easy']}*" not in text
        part = text.split(TXT["el"]["rank"]["αναδυόμενο"])[-1] if TXT["el"]["rank"]["αναδυόμενο"] in text else ""
        assert not any(sentence in part for sentence in TXT["el"]["growth_long"]["easy"])
    assert seen


def test_all_emerging_gets_neutral_heading_v22_31():
    from dataclasses import replace
    from datetime import datetime, timezone
    from core.ephemeris import compute_chart
    from core.talent_engine import run_engine
    from core.talent_polish import build_polish_prompt
    from core.talent_report import TXT, client_markdown
    r = run_engine(compute_chart(datetime(1982, 2, 10, 23, 45, tzinfo=timezone.utc), 34.7754, 32.4218))
    for t in r.talents:
        t.rank = "αναδυόμενο"
    text = client_markdown(r, "el")
    assert "### Τα ταλέντα σου" in text and TXT["el"]["rank_note"]["αναδυόμενο"] not in text
    assert '"level": "αναδυόμενο"' not in build_polish_prompt(text, r, "el")


def test_learning_and_play_sections_v22_47():
    """Σημειώσεις αστρολόγου: στοιχεία των 5 προσωπικών πλανητών -> «Πώς μαθαίνεις καλύτερα»·
    για ανήλικο και «Τι να παρατηρήσεις στο παιχνίδι»."""
    from datetime import date, time
    from core.birth_input import chart_from_birth
    from core.talent_engine import run_engine, is_minor
    from core.talent_report import client_markdown
    adult, _ = chart_from_birth("", date(1982, 2, 11), time(1, 45), 34.7768, 32.4245, "Asia/Nicosia")
    r = run_engine(adult)
    assert r.learning == ["air", "earth"] and not r.minor     # Ήλιος/Ερμής/Άρης: Αέρας· Σελήνη/Αφροδίτη: Γη
    el = client_markdown(r, "el")
    assert "## Πώς μαθαίνεις καλύτερα" in el and "Μέσα από την αλληλεπίδραση" in el and "## Τι να παρατηρήσεις" not in el
    assert el.index("## Πώς μαθαίνεις") < el.index("## Επαγγελματικοί τομείς")
    assert "## How you learn best" in client_markdown(r, "en")
    child, _ = chart_from_birth("", date(2013, 6, 20), time(10, 0), 34.7768, 32.4245, "Asia/Nicosia")
    rc = run_engine(child)
    assert rc.minor and "## Τι να παρατηρήσεις στο παιχνίδι" in client_markdown(rc, "el")
    assert is_minor(child, today=date(2031, 6, 20)) is False    # 18 ετών


def test_adult_cultivation_texts_v22_48():
    """Ενήλικες: προτάσεις καλλιέργειας για ενήλικες (όχι «μαθητικά συμβούλια»)· ανήλικοι: οι αρχικές."""
    from datetime import date, time
    from core.birth_input import chart_from_birth
    from core.talent_engine import run_engine
    from core.talent_report import client_markdown
    from core.talent_texts import load_texts
    for e in load_texts()["talents"].values():
        assert e["el"]["develop_adult"] and e["en"]["develop_adult"]
    adult, _ = chart_from_birth("", date(1982, 2, 11), time(1, 45), 34.7768, 32.4245, "Asia/Nicosia")
    el = client_markdown(run_engine(adult), "el")
    assert "μαθητικά" not in el and "Σε επιτροπές δεοντολογίας" in el
    child, _ = chart_from_birth("", date(2013, 6, 20), time(10, 0), 34.7768, 32.4245, "Asia/Nicosia")
    rc = run_engine(child)
    first = rc.talents[0].theme
    assert load_texts()["talents"][first]["el"]["develop"] in client_markdown(rc, "el")
