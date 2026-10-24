"""v19.2 -- Κανόνας 17: το κείμενο δεν ισχυρίζεται τι έχει ζήσει ο άνθρωπος.
Οι λέξεις «πόνος»/«πληγή» επιτρέπονται γενικά ή υποθετικά."""
import pytest

from core.reference_loader import load_orientation_command
from core.validator import _past_experience_claims, validate_orientation
from tests.coverage_helper import add_coverage
from tests.past_claim_pairs import ALLOWED, FORBIDDEN
from tests.test_docx_round_trip import CHART, _build_audit_text, _build_client_text


@pytest.mark.parametrize("sentence", FORBIDDEN)
def test_claims_about_the_persons_past_are_rejected(sentence):
    assert _past_experience_claims(sentence), sentence


@pytest.mark.parametrize("sentence", ALLOWED)
def test_general_or_hypothetical_wording_is_allowed(sentence):
    assert not _past_experience_claims(sentence), sentence


def test_full_check_rejects_and_explains():
    client = _build_client_text(3).replace("Test. ", "Test. Όσα έχεις περάσει σε έκαναν πιο δυνατό. ", 1)
    audit = add_coverage(CHART, _build_audit_text(3), client)
    result = validate_orientation(CHART, client, {"Όνομα": "Test"}, presentation_mode="Απλή και πρακτική",
                                  audit_text=audit, format_issues=[])
    assert not result.ok
    assert any("Κανόνας 17" in line and "γενικά ή υποθετικά" in line for line in result.details_lines())


def test_binding_command_has_the_rule_with_wrong_and_right_examples():
    cmd = load_orientation_command()
    cmd = cmd[cmd.index("Κανόνας 17."):]  # μόνο τα παραδείγματα του Κανόνα 17
    assert "Μην ισχυρίζεσαι τι έχει ζήσει ή τι έχει νιώσει ο άνθρωπος" in cmd
    wrong = [l.split(":", 1)[1].strip(" «»") for l in cmd.split("\n") if l.startswith("Λάθος: «")]
    right = [l.split(":", 1)[1].strip(" «»") for l in cmd.split("\n") if l.startswith("Σωστό: «")]
    assert len(wrong) >= 3 and len(right) >= 3
    # τα παραδείγματα της εντολής πρέπει να συμφωνούν με τον validator
    assert all(_past_experience_claims(w) for w in wrong), wrong
    assert not any(_past_experience_claims(r) for r in right), right
