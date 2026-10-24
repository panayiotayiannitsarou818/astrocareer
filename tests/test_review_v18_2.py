"""
v18.2 -- εξωτερική κριτική της v18.1. Κάθε test αναπαράγει ΑΚΡΙΒΩΣ το
σενάριο της κριτικής, με τον ΠΛΗΡΗ έλεγχο (Word -> επανάγνωση -> validator).
"""
import pytest

from core import pipeline
from core.validator import _career_consistency_errors, _health_career_mentioned
from tests.test_docx_round_trip import CHART, _build_audit_text, _build_client_text
from tests.test_pipeline import _raw

_HEALTH_BLOCK = (
    "ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ ΤΟΜΕΑ ΥΓΕΙΑΣ\n"
    "Δείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Αιγόκερως | Οίκος: 6\n"
    "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος | ORB_WEIGHT\n"
    "Παράρτημα Επιβεβαιωμένων Όψεων\n"
    "Κρόνος–Ήλιος | Τρίγωνο | orb 1°00′ | Στενή/ισχυρή | ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 1» ως δείκτης\n"
)


def _health_report(orb_weight="Orb: 1°00′ | Βαρύτητα: Στενή/ισχυρή", job="Καρδιολόγος"):
    client = _build_client_text(3).replace("επάγγελμα 1α", job)
    audit = _build_audit_text(3).replace("επάγγελμα 1α", job).replace(
        "Τελικός έλεγχος", _HEALTH_BLOCK.replace("ORB_WEIGHT", orb_weight) + "Τελικός έλεγχος")
    return _raw(client, audit)


def _check(raw):
    return pipeline.evaluate_response(CHART, "Test", raw)[0]


def test_baseline_health_report_with_correct_fields_is_approved():
    c = _check(_health_report())
    assert c.ok, c.details_lines()


@pytest.mark.parametrize("orb_weight, needle", [
    ("Orb: 99°99′ | Βαρύτητα: ΑΝΥΠΑΡΚΤΗ", "99°99′"),        # το σενάριο της κριτικής
    ("Orb: 2°30′ | Βαρύτητα: Στενή/ισχυρή", "2°30′"),         # λάθος orb μόνο
    ("Orb: 1°00′ | Βαρύτητα: Κανονική", "Κανονική"),          # λάθος βαρύτητα μόνο
    ("Βαρύτητα: Στενή/ισχυρή", "Orb"),                          # λείπει το Orb
    ("Orb: 1°00′", "Βαρύτητα"),                                 # λείπει η Βαρύτητα
])
def test_wrong_or_missing_orb_weight_rejected_in_full_check(orb_weight, needle):
    c = _check(_health_report(orb_weight))
    assert not c.ok
    assert any(needle in line for line in c.details_lines()), c.details_lines()


def test_wrong_orb_in_talent_indicator_also_rejected():
    """Το ίδιο κενό υπήρχε και στους δείκτες ΤΑΛΕΝΤΩΝ (κοινός έλεγχος)."""
    raw = _health_report().replace(
        "Σημείο 2: Ήλιος | Orb: 1°00′ | Βαρύτητα: Στενή/ισχυρή\nΔείκτης 2" if False else
        "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος | Orb: 1°00′ | Βαρύτητα: Στενή/ισχυρή\nΕσωτερική κατάταξη: κυρίαρχο\nΤΑΛΕΝΤΟ: Ταλέντο 2",
        "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος | Orb: 99°99′ | Βαρύτητα: ΑΝΥΠΑΡΚΤΗ\nΕσωτερική κατάταξη: κυρίαρχο\nΤΑΛΕΝΤΟ: Ταλέντο 2", 1)
    c = _check(raw)
    assert not c.ok and any("99°99′" in line for line in c.details_lines())


def test_prime_mark_variants_still_accepted():
    """Το «'» αντί για «′» (π.χ. από αυτόματη διόρθωση του Word) δεν είναι λάθος."""
    c = _check(_health_report("Orb: 1°00' | Βαρύτητα: στενή/ισχυρή"))
    assert c.ok, c.details_lines()


def test_audiologist_triggers_health_gate_in_full_check():
    c = _check(_health_report(job="Ακουολόγος").replace(_HEALTH_BLOCK.split("Παράρτημα")[0].replace(
        "ORB_WEIGHT", "Orb: 1°00′ | Βαρύτητα: Στενή/ισχυρή"), ""))
    assert not c.ok and any("ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ" in line for line in c.details_lines())


@pytest.mark.parametrize("text", ["Ακουολόγος", "ΑΚΟΥΟΛΟΓΟΣ", "ακουολόγοι"])
def test_audiologist_detected(text):
    assert _health_career_mentioned(text)


@pytest.mark.parametrize("text", [
    "Βιοϊατρική τεχνολογία", "Μηχανικός βιοϊατρικής", "ΜΗΧΑΝΙΚΟΣ ΒΙΟΪΑΤΡΙΚΗΣ", "biomedical engineer",
])
def test_biomedical_technology_is_not_clinical(text):
    assert not _health_career_mentioned(text)


@pytest.mark.parametrize("text", ["Ιατρός", "Γιατρός", "Παιδίατρος", "Οδοντίατρος", "σπουδές Ιατρικής"])
def test_clinical_iatr_words_still_detected(text):
    assert _health_career_mentioned(text)


# ---------------------------------------------------------------- κόστος (κριτική #4)
from core.generator import GenerationResult
from tests.test_pipeline import MEDIUM, S, run


class WorstCaseModel:
    """Πάροχος όπου τα ΠΡΑΓΜΑΤΙΚΑ tokens εισόδου είναι πολύ περισσότερα από
    την παλιά εκτίμηση (σενάριο κριτικής: όριο $1 -> $1,048). Χωρίς
    καταμέτρηση: χειρότερη δυνατή περίπτωση = 1 token ανά byte."""
    def __init__(self, input_tokens_fn, counter=None):
        self.input_tokens_fn = input_tokens_fn
        if counter is not None:
            self.count_tokens = counter

    def __call__(self, prompt, max_output_tokens=None):
        out = 30000 if max_output_tokens is None else min(30000, max_output_tokens)
        return GenerationResult(text=MEDIUM if out == 30000 else MEDIUM[:40], model="claude-opus-5-5",
                                input_tokens=self.input_tokens_fn(prompt), output_tokens=out, truncated=out < 30000)


@pytest.mark.parametrize("cap", [0.5, 1.0, 1.5, 3.0])
def test_cap_holds_even_when_input_tokens_are_worst_case(cap):
    model = WorstCaseModel(lambda p: len(p.encode("utf-8")))          # χειρότερο δυνατό
    r = run(model, S(max_cost_usd=cap, stall_rounds=99, max_attempts=99), model_name="claude-opus-5-5")
    assert r.cost.total_usd <= cap + 1e-9, (cap, r.cost.total_usd)


@pytest.mark.parametrize("cap", [0.5, 1.0, 3.0])
def test_cap_holds_with_token_count_slightly_off(cap):
    """Με καταμέτρηση: η πραγματική χρήση είναι 4% πάνω από τη μέτρηση."""
    model = WorstCaseModel(lambda p: int(len(p) / 2 * 1.04), counter=lambda p: len(p) // 2)
    r = run(model, S(max_cost_usd=cap, stall_rounds=99, max_attempts=99), model_name="claude-opus-5-5")
    assert r.cost.total_usd <= cap + 1e-9, (cap, r.cost.total_usd)


def test_counted_tokens_give_more_room_than_byte_bound():
    from core.costs import CostTracker
    c = CostTracker()
    prompt = "α" * 60000
    assert c.output_budget("claude-opus-5-5", prompt, 2.0, counted_tokens=30000) > c.output_budget("claude-opus-5-5", prompt, 2.0)


def test_failing_token_counter_falls_back_to_safe_bound():
    def boom(p):
        raise RuntimeError("count_tokens down")
    model = WorstCaseModel(lambda p: len(p.encode("utf-8")), counter=boom)
    r = run(model, S(max_cost_usd=1.0, stall_rounds=99, max_attempts=99), model_name="claude-opus-5-5")
    assert r.cost.total_usd <= 1.0 + 1e-9


# ---------------------------------------------------------------- v18.2.1: τρίτος γύρος κριτικής
from core.validator import _absolute_claims
from tests.test_pipeline import GOOD, GOOD_RESTYLED, FakeModel

_ABS = "Είσαι γεννημένος για αυτό το επάγγελμα και πρέπει να το ακολουθήσεις."


def test_repeated_conflicting_field_rejected_in_full_check():
    """Το ακριβές σενάριο: «Σημείο: Κρόνος | Οίκος: 12 | Οίκος: 6», πραγματικός 6ος."""
    raw = _health_report().replace("Σημείο: Κρόνος | Οίκος: 6\n", "Σημείο: Κρόνος | Οίκος: 12 | Οίκος: 6\n", 1)
    assert "Οίκος: 12 | Οίκος: 6" in raw
    c = _check(raw)
    assert not c.ok and any("επαναλαμβάνει το πεδίο «Οίκος»" in line for line in c.details_lines())


def test_repeated_field_with_same_value_also_rejected():
    raw = _health_report().replace("Ζώδιο: Αιγόκερως | Οίκος: 6", "Ζώδιο: Αιγόκερως | Οίκος: 6 | Οίκος: 6", 1)
    c = _check(raw)
    assert not c.ok and any("επαναλαμβάνει" in line for line in c.details_lines())


def test_repeated_orb_field_rejected():
    raw = _health_report("Orb: 5°00′ | Orb: 1°00′ | Βαρύτητα: Στενή/ισχυρή")
    c = _check(raw)
    assert not c.ok and any("«Orb»" in line for line in c.details_lines())


def test_absolute_claim_in_profile_rejected_in_full_check():
    """Το ακριβές σενάριο της κριτικής, στο προφίλ πλήρους αναφοράς."""
    c = _check(GOOD.replace("Test. ", "Test. " + _ABS + " ", 1))
    assert not c.ok
    assert any("γεννημένος" in line and "Απαγορευμένη απόλυτη διατύπωση" in line for line in c.details_lines())


@pytest.mark.parametrize("sentence", [
    "Η Μαρία είναι γεννημένη για τη διδασκαλία.", "Πρέπει να γίνει μηχανικός.", "Θα πρέπει να σπουδάσεις Νομική.",
    "Δεν μπορεί να κάνει δουλειά γραφείου.", "Δεν θα μπορέσεις να πετύχεις στις πωλήσεις.",
    "Το πεπρωμένο του είναι η μουσική.", "Είναι προορισμένη για ηγεσία.",
    "Αυτό είναι το μοναδικό κατάλληλο επάγγελμα για εσένα.", "Η μόνη σωστή επιλογή είναι η Νομική.",
    "Ο χάρτης αποδεικνύει ότι έχεις ταλέντο.", "Σίγουρα θα πετύχεις ως δικηγόρος.",
    "ΕΙΣΑΙ ΓΕΝΝΗΜΕΝΟΣ ΓΙΑ ΗΓΕΤΗΣ.",
    "You were born to lead.", "You must become an engineer.", "This is your destiny.",
    "It is the only suitable career for you.", "The chart proves that you are creative.", "You will definitely succeed.",
])
def test_absolute_claims_detected(sentence):
    assert _absolute_claims(sentence), sentence


@pytest.mark.parametrize("sentence", [
    "Φαίνεται να διαθέτει δυνατότητα στην οργάνωση.", "Αξίζει να διερευνηθεί η κατεύθυνση της διδασκαλίας.",
    "Θα μπορούσε να δοκιμάσει δραστηριότητες με ομάδες.", "Οι κατευθύνσεις αυτές δεν αποτελούν τελική απόφαση.",
    "Η τελική επιλογή παραμένει πάντα δική του, ως έκφραση ελεύθερης βούλησης.",
    "Δεν μπορεί να θεωρηθεί τελική απόφαση.", "Δεν πρέπει να γίνει βιαστική επιλογή.", "Πρέπει να διερευνηθεί με προσοχή.",
    "Δεν μπορούμε να ξέρουμε από τώρα.", "It may be worth exploring.", "The final choice always remains theirs.",
])
def test_allowed_hedged_wording_not_flagged(sentence):
    assert not _absolute_claims(sentence), sentence


def test_reference_template_has_no_absolute_claims():
    from core.reference_loader import load_unified_short_example
    assert _absolute_claims(load_unified_short_example()) == []


def test_quality_round_rejects_added_absolute_claim():
    """Κριτική: ο γύρος ποιότητας δεχόταν την προσθήκη (ίδιοι τίτλοι/μήκος)."""
    restyled_bad = GOOD.replace("Test. ", "Test. " + _ABS + " ", 1)
    r = run(FakeModel([GOOD, restyled_bad]), S(quality_pass=True))
    assert r.ok and not r.quality_applied and r.raw == GOOD


def test_quality_round_rejects_added_paragraph():
    """Νέα παράγραφος (ακόμη και «ουδέτερη») = νέο περιεχόμενο, όχι ύφος."""
    extra = GOOD.replace("Ταλέντα προς διερεύνηση\n", "Μια επιπλέον παράγραφος που προστέθηκε.\nΤαλέντα προς διερεύνηση\n", 1)
    r = run(FakeModel([GOOD, extra]), S(quality_pass=True))
    assert r.ok and not r.quality_applied


def test_quality_round_rejects_big_growth_in_one_section():
    grown = GOOD.replace("Test. " + " ".join(["λέξη"] * 100), "Test. " + " ".join(["λέξη"] * 140), 1)
    r = run(FakeModel([GOOD, grown]), S(quality_pass=True))
    assert r.ok and not r.quality_applied


def test_quality_round_still_accepts_pure_restyle():
    r = run(FakeModel([GOOD, GOOD_RESTYLED]), S(quality_pass=True))
    assert r.ok and r.quality_applied


# ---------------------------------------------------------------- v18.4: ισορροπημένα ζεύγη
from tests.absolute_claim_pairs import HELD_OUT_ALLOWED, HELD_OUT_FORBIDDEN, PAIRS


@pytest.mark.parametrize("forbidden, allowed", PAIRS)
def test_balanced_pair(forbidden, allowed):
    """Κάθε ζεύγος: σχεδόν ίδιες λέξεις, αντίθετο νόημα."""
    assert _absolute_claims(forbidden), f"έπρεπε να απορριφθεί: {forbidden}"
    assert not _absolute_claims(allowed), f"απορρίφθηκε άδικα: {allowed} -> {_absolute_claims(allowed)}"


@pytest.mark.parametrize("sentence", HELD_OUT_FORBIDDEN)
def test_held_out_forbidden(sentence):
    assert _absolute_claims(sentence), sentence


@pytest.mark.parametrize("sentence", HELD_OUT_ALLOWED)
def test_held_out_allowed(sentence):
    assert not _absolute_claims(sentence), (sentence, _absolute_claims(sentence))


@pytest.mark.parametrize("sentence", [
    "Η επιτυχία σου είναι βέβαιη.", "Αποκλείεται να αποτύχεις.", "You are certain to succeed.",
])
def test_review_certainty_examples_rejected_in_full_check(sentence):
    """Τα τρία παραδείγματα της κριτικής, μέσα σε πλήρη αναφορά (Word -> επανάγνωση)."""
    c = _check(GOOD.replace("Test. ", "Test. " + sentence + " ", 1))
    assert not c.ok and any("Απαγορευμένη απόλυτη διατύπωση" in l for l in c.details_lines())


@pytest.mark.parametrize("sentence", [
    "Δεν υπάρχει ένα μοναδικό κατάλληλο επάγγελμα.", "Δεν είσαι γεννημένος για ένα μόνο επάγγελμα.",
    "You do not have to choose a career now.", "You are not born for one specific career.",
])
def test_review_negated_examples_approved_in_full_check(sentence):
    """Τα τέσσερα σωστά παραδείγματα της κριτικής δεν απορρίπτουν πλέον την αναφορά."""
    c = _check(GOOD.replace("Test. ", "Test. " + sentence + " ", 1))
    assert c.ok, c.details_lines()


@pytest.mark.parametrize("sentence", ["Η επιτυχία σου είναι βέβαιη.", "Αποκλείεται να αποτύχεις."])
def test_quality_round_rejects_review_certainty_examples(sentence):
    r = run(FakeModel([GOOD, GOOD.replace("Test. ", "Test. " + sentence + " ", 1)]), S(quality_pass=True))
    assert r.ok and not r.quality_applied and r.raw == GOOD


def test_validator_has_no_duplicate_top_level_names():
    """v18.4: ένα νέο _NEGATION_RE αντικατέστησε σιωπηλά το παλιό (που ελέγχει
    το Παράρτημα). Κανένα όνομα δεν πρέπει να ορίζεται δύο φορές στο module."""
    import ast
    from collections import Counter
    from pathlib import Path
    tree = ast.parse(Path("core/validator.py").read_text(encoding="utf-8"))
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            names += [t.id for t in node.targets if isinstance(t, ast.Name)]
    dups = [n for n, c in Counter(names).items() if c > 1]
    assert not dups, dups


# ---------------------------------------------------------------- v18.6: πρώτη πραγματική αναφορά
def test_title_and_name_not_duplicated_when_model_repeats_them():
    """Στην πρώτη πραγματική αναφορά τίτλος+όνομα εμφανίζονταν δύο φορές."""
    from core.docx_builder import build_orientation_client_docx
    from core.reference_loader import docx_text_in_order
    title = "Ανάδειξη Ταλέντων και Διερεύνηση Επαγγελματικών Επιλογών"
    body = f"# {title}\n**Panayiota**\n\nΣύντομο προφίλ\nΚείμενο.\n"
    text = docx_text_in_order(build_orientation_client_docx(title, "Panayiota", body))
    assert text.count(title) == 1 and text.count("Panayiota") == 1
    assert "Σύντομο προφίλ" in text and "Κείμενο." in text


def test_name_inside_body_is_kept():
    from core.docx_builder import build_orientation_client_docx
    from core.reference_loader import docx_text_in_order
    body = "Σύντομο προφίλ\nΗ Μαρία φαίνεται να διαθέτει δυνατότητα.\nΜαρία\n"
    text = docx_text_in_order(build_orientation_client_docx("Τίτλος", "Μαρία", body))
    assert text.count("Μαρία") == 3   # τίτλος + 2 μέσα στο σώμα (μόνο οι ΑΡΧΙΚΕΣ γραμμές αφαιρούνται)


def test_report_with_repeated_heading_still_approved():
    raw = GOOD.replace("===CLIENT_DELIVERABLE===\n",
                       "===CLIENT_DELIVERABLE===\n# Ανάδειξη Ταλέντων και Διερεύνηση Επαγγελματικών Επιλογών\n**Test**\n", 1)
    assert _check(raw).ok


# ---------------------------------------------------------------- v18.8: χωρίς πεδίο ονόματος
def test_pdf_without_name_gives_empty_name_not_filename():
    from core.parser import parse_astrodienst_pdf
    data = open("tests/fixtures/astro_paradeigma_2.pdf", "rb").read()
    assert parse_astrodienst_pdf(data, "astro_w_809135.pdf").name == ""


def test_pdf_with_name_keeps_it():
    from core.parser import parse_astrodienst_pdf
    data = open("tests/fixtures/astro_paradeigma.pdf", "rb").read()
    assert parse_astrodienst_pdf(data, "x.pdf").name == "Paradeigma"


def test_report_without_name_is_approved_and_has_no_name_line():
    from core.reference_loader import docx_text_in_order
    check, _, _, client_docx, _ = pipeline.evaluate_response(CHART, "", GOOD)
    assert check.ok, check.details_lines()
    first_lines = docx_text_in_order(client_docx).splitlines()[:2]
    assert first_lines[0] == pipeline.SERVICE_TITLE and first_lines[1] == "Σύντομο προφίλ"


def test_prompt_tells_model_not_to_invent_a_name():
    assert "Μη γράψεις κανένα όνομα" in pipeline.build_auto_prompt(CHART, "", "el")
    assert "Do not write or invent any name" in pipeline.build_auto_prompt(CHART, "", "en")
    assert pipeline.client_docx_filename("") == "AstroCheck_Anadeixi_Talenton.docx"
