"""v19.11 -- Σειρά ταλέντων (απόφαση ιδιοκτήτριας).

Το Σύντομο προφίλ κλείνει με σταθερή πρόταση: «Πρώτα εμφανίζονται τα ταλέντα που ο χάρτης
δείχνει πιο έντονα…». Για να είναι πάντα αληθινή, τα ταλέντα γράφονται με τη σειρά
κυρίαρχα -> βασικά -> αναδυόμενα, και αυτό ελέγχεται μηχανικά από το δελτίο.
"""
from core import pipeline
from core.reference_loader import load_orientation_command, load_unified_short_example
from core.validator import ORDER_SENTENCE, _order_errors
from tests.test_docx_round_trip import CHART, _build_audit_text, _build_client_text
from tests.test_pipeline import _raw


def _ranked_audit(ranks):
    audit = _build_audit_text(len(ranks))
    parts = audit.split("Εσωτερική κατάταξη: κυρίαρχο")
    out = parts[0]
    for rank, rest in zip(ranks, parts[1:]):
        out += f"Εσωτερική κατάταξη: {rank}" + rest
    return out


def test_valid_order_and_sentence_pass_the_full_pipeline():
    raw = _raw(_build_client_text(3), _ranked_audit(["κυρίαρχο", "βασικό", "αναδυόμενο"]))
    check = pipeline.evaluate_response(CHART, "Test", raw, "el")[0]
    assert check.ok, check.details_lines()


def test_wrong_order_is_rejected():
    raw = _raw(_build_client_text(3), _ranked_audit(["βασικό", "κυρίαρχο", "αναδυόμενο"]))
    lines = pipeline.evaluate_response(CHART, "Test", raw, "el")[0].details_lines()
    assert any("Λάθος σειρά ταλέντων" in l and "«Ταλέντο 2» (κυρίαρχο)" in l for l in lines), lines


def test_missing_rank_line_is_rejected():
    audit = _build_audit_text(2).replace("Εσωτερική κατάταξη: κυρίαρχο\n", "", 1)
    errors = _order_errors(_build_client_text(2), audit, "el")
    assert any("χρειάζεται γραμμή «Εσωτερική κατάταξη" in e for e in errors)


def test_missing_order_sentence_is_rejected():
    client = _build_client_text(2).replace(" " + ORDER_SENTENCE["el"], "")
    errors = _order_errors(client, _build_audit_text(2), "el")
    assert any("πρόταση για τη σειρά" in e for e in errors)


def test_sentence_tolerates_typographic_variants():
    variant = ORDER_SENTENCE["el"].replace("·", ";").replace("  ", " ")
    client = _build_client_text(2).replace(ORDER_SENTENCE["el"], variant)
    assert _order_errors(client, _build_audit_text(2), "el") == []


def test_rank_with_short_reason_is_read():
    audit = _build_audit_text(2).replace("Εσωτερική κατάταξη: κυρίαρχο",
                                         "Εσωτερική κατάταξη: Κυρίαρχο (δύο στενές όψεις)", 1)
    assert _order_errors(_build_client_text(2), audit, "el") == []


def test_no_language_keeps_old_behaviour():
    assert _order_errors("χωρίς τίποτα", "", None) == []


def test_command_and_template_carry_the_exact_sentence():
    assert ORDER_SENTENCE["el"] in load_orientation_command()
    assert ORDER_SENTENCE["el"] in load_unified_short_example()
    assert "κυρίαρχα», έπειτα τα «βασικά», τέλος τα «αναδυόμενα»" in load_orientation_command()


def test_english_instructions_carry_the_english_sentence():
    assert ORDER_SENTENCE["en"] in pipeline.reinforcement_instructions("Test", "en")


def test_sentence_passes_the_other_client_checks():
    """Η ίδια η σταθερή πρόταση δεν πρέπει να ενεργοποιεί άλλους ελέγχους (απόλυτες
    διατυπώσεις, ισχυρισμοί παρελθόντος, τεχνικοί όροι)."""
    from core.validator import _absolute_claims, _past_experience_claims, _simple_presentation_technical_terms
    for lang in ("el", "en"):
        s = ORDER_SENTENCE[lang]
        assert not _absolute_claims(s) and not _past_experience_claims(s)
        assert not _simple_presentation_technical_terms(s)


def test_glued_sentences_get_a_space_before_the_word_file():
    from core.pipeline import fix_sentence_spacing
    assert fix_sentence_spacing("να αλλάξει.Πρώτα εμφανίζονται") == "να αλλάξει. Πρώτα εμφανίζονται"
    assert fix_sentence_spacing("can change.The talents") == "can change. The talents"
    for unchanged in ("Κανόνας 3.2 ισχύει", "π.χ. ΟΗΕ", "version 19.12", "Ο ΟΗΕ.ΕΕ", "ήδη. Πρώτα"):
        assert fix_sentence_spacing(unchanged) == unchanged


def test_command_forbids_a_duplicate_caution_before_the_fixed_sentence():
    assert "μη γράψεις πριν από αυτήν άλλη πρόταση με το ίδιο μήνυμα" in load_orientation_command()
