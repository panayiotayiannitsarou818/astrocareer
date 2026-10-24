"""v19.9 (εξωτερικός έλεγχος): με επιλεγμένα English, ένα ελληνικό παραδοτέο εγκρινόταν."""
from core import pipeline
from core.validator import _language_errors
from tests.test_docx_round_trip import CHART, _build_audit_text, _build_client_text
from tests.test_pipeline import _raw

EN_CLIENT = (
    "Brief Profile\nThis analysis describes possibilities worth exploring, not certainties.\n"
    "Talents to Explore\n1. Original thinking\nYou may enjoy finding new ways to solve problems.\n"
    "Career Fields to Explore\n1. Technology\nWhy it may fit: It uses original thinking.\n"
    "Example Careers per Field: Programmer\n"
    "Final Synthesis\nThe final choice always remains yours.\n"
)


def test_greek_deliverable_is_rejected_when_english_was_requested():
    """Το ακριβές σενάριο του ελέγχου: σωστή ελληνική αναφορά, ζητούμενη γλώσσα English."""
    raw = _raw(_build_client_text(3), _build_audit_text(3))
    assert pipeline.evaluate_response(CHART, "Test", raw, "el")[0].ok
    check = pipeline.evaluate_response(CHART, "Test", raw, "en")[0]
    assert not check.ok
    assert any("στα αγγλικά" in l for l in check.details_lines())


def test_english_deliverable_with_greek_name_is_accepted():
    assert _language_errors(EN_CLIENT.replace("This analysis", "Παναγιώτα, this analysis"), "en", "Παναγιώτα") == []


def test_english_deliverable_is_rejected_when_greek_was_requested():
    errors = _language_errors(EN_CLIENT, "el")
    assert any("στα ελληνικά" in e for e in errors)


def test_greek_text_with_a_few_english_terms_is_accepted():
    text = (_build_client_text(1)
            + "Διαχειριστής έργων (γνωστός και ως project manager· συντονίζει ανθρώπους και χρόνο).\n")
    assert _language_errors(text, "el") == []


def test_no_language_given_keeps_the_old_behaviour():
    assert _language_errors(EN_CLIENT, None) == []


def test_full_english_report_is_approved_through_the_real_pipeline():
    """v19.10 (εξωτερικός έλεγχος): το αγγλικό Word έπαιρνε τον ελληνικό τίτλο της υπηρεσίας και
    μετά ο έλεγχος γλώσσας το απέρριπτε. Πλήρες, έγκυρο αγγλικό παραδοτέο μέσα από το
    evaluate_response (Word -> ξαναδιάβασμα -> validator), με ελληνικό τεχνικό δελτίο."""
    import io
    from core.reference_loader import docx_text
    from tests.coverage_helper import add_coverage
    from core.validator import ORDER_SENTENCE
    client = (
        _build_client_text(2)
        .replace(ORDER_SENTENCE["el"], ORDER_SENTENCE["en"])
        .replace("Σύντομο προφίλ", "Brief Profile")
        .replace("Ταλέντα προς διερεύνηση", "Talents to Explore")
        .replace("Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:", "In summary, the talents to explore are:")
        .replace("Επαγγελματικοί Τομείς προς Διερεύνηση", "Career Fields to Explore")
        .replace("Γιατί μπορεί να ταιριάζει: συνδέεται με το", "Why it may fit: it draws on")
        .replace("Ενδεικτικά επαγγέλματα:", "Example Careers per Field:")
        .replace("Τελική σύνθεση", "Final Synthesis")
        .replace("Ταλέντο", "Talent").replace("Τομέας", "Field").replace("επάγγελμα", "career")
        .replace("λέξη", "word")
        .replace("Η τελική επιλογή παραμένει πάντα δική του, ως έκφραση ελεύθερης βούλησης. Τα μαθήματα και η "
                 "πραγματική επίδοση θα χρειαστεί αργότερα να επιβεβαιώσουν ή να αναθεωρήσουν αυτό το συμπέρασμα.",
                 "What to Remember: the subjects and activities you enjoy and your actual performance can confirm or revise these "
                 "directions, and the final choice always remains yours, as an expression of your free will.")
    )
    audit = (_build_audit_text(2).split("Παράρτημα Κάλυψης")[0]
             .replace("ΤΑΛΕΝΤΟ: Ταλέντο", "ΤΑΛΕΝΤΟ: Talent").replace("Τομέας", "Field").replace("επάγγελμα", "career")
             + "Τελικός έλεγχος: ολοκληρώθηκε.\n")
    audit = add_coverage(CHART, audit, client)
    check, _, _, client_docx, _ = pipeline.evaluate_response(CHART, "Test", _raw(client, audit), "en")
    assert check.ok, check.details_lines()
    text = docx_text(io.BytesIO(client_docx))
    assert "Talent Discovery and Career Exploration" in text
    assert "Ανάδειξη Ταλέντων" not in text
