"""
v20.18 -- «Πώς φαίνεται να αναπτύσσεται» κάθε ταλέντο (core/talent_growth.py).

Η φράση υπολογίζεται από τους ΚΥΡΙΟΥΣ δείκτες όψης του τεχνικού δελτίου
(πραγματική βαρύτητα Στενή/ισχυρή ή Κανονική) και μπαίνει στη συνοπτική λίστα
του Word μόνο ΜΕΤΑ από εγκεκριμένο έλεγχο.

Τα δεδομένα του test_panayiota_* είναι οι πραγματικοί δείκτες της αναφοράς
της Παναγιώτας (Οκτ. 2026), με τις πραγματικές βαρύτητες της v20.3.
"""
import io

from docx import Document

from core import pipeline
from core.docx_builder import build_orientation_client_docx
from core.models import Aspect, Chart
from core.reference_loader import docx_text_in_order, simple_docx_format_issues
from core.talent_growth import (
    EASY, MIXED, NOTE, OPEN, OPPORTUNITY, PHRASES, PRACTICE, SEPARATOR,
    annotate_client_docx, classify_block, talent_growth,
)
from tests.test_docx_round_trip import CHART as RT_CHART
from tests.test_pipeline import BAD, GOOD


def _a(p1, p2, kind, weight):
    return Aspect(p1, p2, kind, 1.0, "1°00′", weight, "test")


def _ind(n, p1, kind, p2, weight):
    return (f"Δείκτης {n}: Τύπος: Όψη | Σημείο 1: {p1} | Όψη: {kind} | Σημείο 2: {p2} "
            f"| Orb: 1°00′ | Βαρύτητα: {weight}")


POS = "Δείκτης 9: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Ζυγός | Οίκος: 11"

# Πραγματικές όψεις της Παναγιώτας που χρησιμοποιούνται στους δείκτες (βαρύτητα v20.3).
PAN_ASPECTS = [
    ("Ήλιος", "Κρόνος", "Τρίγωνο", "Στενή/ισχυρή"),
    ("Αφροδίτη", "Κρόνος", "Τετράγωνο", "Στενή/ισχυρή"),
    ("Άρης", "Κρόνος", "Σύνοδος", "Κανονική"),
    ("Ερμής", "Ουρανός", "Εξάγωνο", "Στενή/ισχυρή"),
    ("Ουρανός", "Ωροσκόπος", "Σύνοδος", "Στενή/ισχυρή"),
    ("Σελήνη", "Ποσειδώνας", "Τετράγωνο", "Στενή/ισχυρή"),
    ("Ήλιος", "Ποσειδώνας", "Εξάγωνο", "Πολύ πλατιά/δευτερεύουσα"),
    ("Χείρωνας", "Μεσουράνημα", "Τρίγωνο", "Στενή/ισχυρή"),
    ("Άρης", "Χείρωνας", "Χιαστί όψη 150°", "Κανονική"),
    ("Ήλιος", "Χείρωνας", "Τετράγωνο", "Κανονική"),
    ("Ερμής", "Ωροσκόπος", "Εξάγωνο", "Κανονική"),
    ("Σελήνη", "Αφροδίτη", "Τρίγωνο", "Κανονική"),
    ("Αφροδίτη", "Μεσουράνημα", "Τρίγωνο", "Πλατιά αλλά έγκυρη"),
    ("Ήλιος", "Άρης", "Τρίγωνο", "Κανονική"),
    ("Αφροδίτη", "Πλούτωνας", "Τετράγωνο", "Κανονική"),
    ("Ήλιος", "Πλούτωνας", "Τρίγωνο", "Πλατιά αλλά έγκυρη"),
    ("Ερμής", "Πλούτωνας", "Τετράγωνο", "Πλατιά αλλά έγκυρη"),
    ("Ερμής", "Δίας", "Τετράγωνο", "Πλατιά αλλά έγκυρη"),
]
PAN_CHART = Chart(aspects=[_a(*x) for x in PAN_ASPECTS])
_W = {(a, b, k): w for a, b, k, w in PAN_ASPECTS}


def _block(*pairs, positions=0):
    lines = [_ind(i + 1, a, k, b, _W[(a, b, k)]) for i, (a, b, k) in enumerate(pairs)]
    return "\n".join(lines + [POS] * positions)


PAN_AUDIT = "\n".join(f"ΤΑΛΕΝΤΟ: {title}\n{block}" for title, block in [
    ("Οργάνωση, συνέπεια και επιμονή", _block(("Ήλιος", "Κρόνος", "Τρίγωνο"),
                                              ("Αφροδίτη", "Κρόνος", "Τετράγωνο"), ("Άρης", "Κρόνος", "Σύνοδος"))),
    ("Πρωτότυπη σκέψη και νέες ιδέες", _block(("Ερμής", "Ουρανός", "Εξάγωνο"),
                                              ("Ουρανός", "Ωροσκόπος", "Σύνοδος"), positions=1)),
    ("Φαντασία και ενσυναίσθηση", _block(("Σελήνη", "Ποσειδώνας", "Τετράγωνο"),
                                         ("Ήλιος", "Ποσειδώνας", "Εξάγωνο"), positions=1)),
    ("Καθοδήγηση και στήριξη άλλων", _block(("Χείρωνας", "Μεσουράνημα", "Τρίγωνο"),
                                            ("Άρης", "Χείρωνας", "Χιαστί όψη 150°"), ("Ήλιος", "Χείρωνας", "Τετράγωνο"))),
    ("Επικοινωνία και μετάδοση γνώσεων", _block(("Ερμής", "Ωροσκόπος", "Εξάγωνο"), positions=1)),
    ("Αίσθηση της ομορφιάς και της αρμονίας", _block(("Σελήνη", "Αφροδίτη", "Τρίγωνο"),
                                                     ("Αφροδίτη", "Μεσουράνημα", "Τρίγωνο"), positions=1)),
    ("Συνεργασία και δίκαιη ισορροπία", POS + "\n" + POS),
    ("Ανάληψη πρωτοβουλίας", _block(("Ήλιος", "Άρης", "Τρίγωνο"), positions=1)),
    ("Έρευνα σε βάθος", _block(("Αφροδίτη", "Πλούτωνας", "Τετράγωνο"), ("Ήλιος", "Πλούτωνας", "Τρίγωνο"),
                               ("Ερμής", "Πλούτωνας", "Τετράγωνο"), ("Ερμής", "Δίας", "Τετράγωνο"))),
]) + "\nΙεράρχηση βαρύτητας: Στενή, Κανονική.\n"

PAN_EXPECTED = {
    "οργάνωση, συνέπεια και επιμονή": MIXED,
    "πρωτότυπη σκέψη και νέες ιδέες": OPPORTUNITY,
    "φαντασία και ενσυναίσθηση": PRACTICE,
    "καθοδήγηση και στήριξη άλλων": MIXED,
    "επικοινωνία και μετάδοση γνώσεων": OPPORTUNITY,
    "αίσθηση της ομορφιάς και της αρμονίας": EASY,
    "συνεργασία και δίκαιη ισορροπία": OPEN,
    "ανάληψη πρωτοβουλίας": EASY,
    "έρευνα σε βάθος": PRACTICE,
}


# ---------------------------------------------------------------- κανόνας

def test_panayiota_talents_get_the_agreed_phrases():
    assert talent_growth(PAN_AUDIT, PAN_CHART) == PAN_EXPECTED


def test_only_trines_is_easy_and_any_sextile_is_opportunity():
    chart = Chart(aspects=[_a("Ήλιος", "Άρης", "Τρίγωνο", "Κανονική"),
                           _a("Ερμής", "Δίας", "Εξάγωνο", "Κανονική")])
    assert classify_block(_ind(1, "Ήλιος", "Τρίγωνο", "Άρης", "Κανονική"), chart) == EASY
    both = _ind(1, "Ήλιος", "Τρίγωνο", "Άρης", "Κανονική") + "\n" + _ind(2, "Ερμής", "Εξάγωνο", "Δίας", "Κανονική")
    assert classify_block(both, chart) == OPPORTUNITY


def test_opposition_counts_like_square():
    chart = Chart(aspects=[_a("Σελήνη", "Κρόνος", "Αντίθεση", "Στενή/ισχυρή")])
    assert classify_block(_ind(1, "Σελήνη", "Αντίθεση", "Κρόνος", "Στενή/ισχυρή"), chart) == PRACTICE


def test_conjunction_and_quincunx_alone_are_neutral():
    chart = Chart(aspects=[_a("Άρης", "Κρόνος", "Σύνοδος", "Στενή/ισχυρή"),
                           _a("Άρης", "Χείρωνας", "Χιαστί όψη 150°", "Στενή/ισχυρή")])
    block = (_ind(1, "Άρης", "Σύνοδος", "Κρόνος", "Στενή/ισχυρή") + "\n"
             + _ind(2, "Άρης", "Χιαστί όψη 150°", "Χείρωνας", "Στενή/ισχυρή"))
    assert classify_block(block, chart) == OPEN


def test_wide_aspects_do_not_count():
    """Μια πλατιά όψη είναι υποστηρικτική -- δεν αλλάζει τη φράση."""
    chart = Chart(aspects=[_a("Ήλιος", "Άρης", "Τρίγωνο", "Κανονική"),
                           _a("Ερμής", "Δίας", "Τετράγωνο", "Πλατιά αλλά έγκυρη")])
    block = (_ind(1, "Ήλιος", "Τρίγωνο", "Άρης", "Κανονική") + "\n"
             + _ind(2, "Ερμής", "Τετράγωνο", "Δίας", "Πλατιά αλλά έγκυρη"))
    assert classify_block(block, chart) == EASY


def test_real_weight_from_chart_wins_over_declared_weight():
    """Ο δείκτης δηλώνει «Στενή/ισχυρή», ο χάρτης λέει «Πλατιά»: μετρά ο χάρτης.
    Έτσι η φράση προσαρμόζεται αυτόματα σε κάθε αλλαγή των ορίων orb."""
    chart = Chart(aspects=[_a("Ήλιος", "Άρης", "Τρίγωνο", "Κανονική"),
                           _a("Ερμής", "Δίας", "Τετράγωνο", "Πλατιά αλλά έγκυρη")])
    block = (_ind(1, "Ήλιος", "Τρίγωνο", "Άρης", "Κανονική") + "\n"
             + _ind(2, "Ερμής", "Τετράγωνο", "Δίας", "Στενή/ισχυρή"))
    assert classify_block(block, chart) == EASY


def test_aspect_missing_from_chart_does_not_count():
    chart = Chart(aspects=[])
    assert classify_block(_ind(1, "Ήλιος", "Τρίγωνο", "Άρης", "Στενή/ισχυρή"), chart) == OPEN


def test_phrases_exist_in_both_languages_and_never_name_aspects():
    forbidden = ("τρίγων", "εξάγων", "τετράγων", "αντίθεσ", "σύνοδ", "χιαστί",
                 "trine", "sextile", "square", "opposition", "conjunction", "quincunx")
    for lang in ("el", "en"):
        assert set(PHRASES[lang]) == {EASY, OPPORTUNITY, PRACTICE, MIXED, OPEN}
        for text in list(PHRASES[lang].values()) + [NOTE[lang]]:
            assert not any(word in text.lower() for word in forbidden)


def test_no_audit_means_no_growth():
    assert talent_growth(None, PAN_CHART) == {}
    assert talent_growth("", PAN_CHART) == {}


# ---------------------------------------------------------------- Word

_TITLES = [
    "Οργάνωση, συνέπεια και επιμονή", "Πρωτότυπη σκέψη και νέες ιδέες", "Φαντασία και ενσυναίσθηση",
    "Καθοδήγηση και στήριξη άλλων", "Επικοινωνία και μετάδοση γνώσεων",
    "Αίσθηση της ομορφιάς και της αρμονίας", "Συνεργασία και δίκαιη ισορροπία",
    "Ανάληψη πρωτοβουλίας", "Έρευνα σε βάθος",
]
_CLIENT = (
    "Ταλέντα προς διερεύνηση\n" + "".join(f"### {i}. {t}\nΚείμενο.\n\n" for i, t in enumerate(_TITLES, 1))
    + "**Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:**\n"
    + "\n".join(f"- {t}" for t in _TITLES)
    + "\n\nΕπαγγελματικοί Τομείς προς Διερεύνηση\n### 1. Τομέας\nΚείμενο.\n"
)


def _summary_lines(docx_bytes):
    lines = docx_text_in_order(docx_bytes).splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("Συνοπτικά"))
    end = next(i for i, line in enumerate(lines) if line.startswith("Επαγγελματικοί"))
    return lines[start + 1:end]


def test_word_summary_gets_phrase_next_to_each_title_and_the_choice_note():
    base = build_orientation_client_docx("Τίτλος", "Panayiota", _CLIENT)
    out = annotate_client_docx(base, PAN_AUDIT, PAN_CHART, "el")
    lines = _summary_lines(out)
    assert lines[:-1] == [t + SEPARATOR + PHRASES["el"][PAN_EXPECTED[t.lower()]] for t in _TITLES]
    assert lines[-1] == NOTE["el"]
    assert simple_docx_format_issues(out) == []


def test_word_phrase_is_italic_inside_the_same_bullet_and_note_has_no_bullet():
    base = build_orientation_client_docx("Τίτλος", "Panayiota", _CLIENT)
    doc = Document(io.BytesIO(annotate_client_docx(base, PAN_AUDIT, PAN_CHART, "el")))
    bullets = [p for p in doc.paragraphs if p.style.name == "List Bullet" and SEPARATOR in p.text]
    assert len(bullets) == len(_TITLES)
    assert all(p.runs[-1].italic and not p.runs[0].italic for p in bullets)
    note = next(p for p in doc.paragraphs if p.text == NOTE["el"])
    assert note.style.name == "Normal"
    assert not doc.tables  # Κανόνας 3: χωρίς πίνακες


def test_word_is_unchanged_without_audit_or_without_summary():
    base = build_orientation_client_docx("Τίτλος", "Panayiota", _CLIENT)
    assert annotate_client_docx(base, None, PAN_CHART, "el") == base
    no_summary = build_orientation_client_docx("Τίτλος", "Panayiota", _CLIENT.replace("Συνοπτικά", "Κάτι άλλο"))
    assert annotate_client_docx(no_summary, PAN_AUDIT, PAN_CHART, "el") == no_summary


def test_word_english_summary():
    client = _CLIENT.replace("Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:", "In summary, the talents to explore are:")
    out = annotate_client_docx(build_orientation_client_docx("Title", "P", client), PAN_AUDIT, PAN_CHART, "en")
    text = docx_text_in_order(out)
    assert "Έρευνα σε βάθος" + SEPARATOR + PHRASES["en"][PRACTICE] in text
    assert NOTE["en"] in text


# ---------------------------------------------------------------- ροή παραγωγής

def test_pipeline_adds_phrases_only_after_approval():
    check, _, _, client_docx, _ = pipeline.evaluate_response(RT_CHART, "Test", GOOD)
    assert check.ok
    text = docx_text_in_order(client_docx)
    for i in (1, 2, 3):
        assert f"Ταλέντο {i}{SEPARATOR}{PHRASES['el'][EASY]}" in text  # Κρόνος–Ήλιος τρίγωνο
    assert NOTE["el"] in text


def test_pipeline_leaves_rejected_drafts_untouched():
    check, _, _, client_docx, _ = pipeline.evaluate_response(RT_CHART, "Test", BAD)
    assert not check.ok
    assert NOTE["el"] not in docx_text_in_order(client_docx)
