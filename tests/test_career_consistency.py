from core.validator import _career_consistency_errors


def _client(field="Τεχνολογία και καινοτομία", jobs="προγραμματιστής, αναλυτής δεδομένων"):
    return f"""Επαγγελματικοί Τομείς προς Διερεύνηση
1. {field}
Γιατί μπορεί να ταιριάζει: αξιοποιεί δύο τεκμηριωμένα ταλέντα.
Ενδεικτικά επαγγέλματα: {jobs}.
Τελική Σύνθεση
Οι επιλογές χρειάζονται πραγματική διερεύνηση.
"""


_APPENDIX = """Παράρτημα Επιβεβαιωμένων Όψεων
- Χείρωνας στον 6ο Οίκο, Τρίγωνο, orb 0°26′, Στενή/ισχυρή
- Ποσειδώνας–Πλούτωνας, Εξάγωνο, orb 0°26′, Στενή/ισχυρή
- Σελήνη–Ποσειδώνας, Τετράγωνο, orb 0°29′, Στενή/ισχυρή
Τελικός έλεγχος: ολοκληρώθηκε.
"""


def _audit(fields="Τεχνολογία και καινοτομία", jobs="προγραμματιστής, αναλυτής δεδομένων", extra="",
           include_appendix=True):
    appendix = _APPENDIX if include_appendix else ""
    return f"""ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ
- {fields}
ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ
- {jobs}
{extra}
{appendix}
"""


_GROUNDED_HEALTH_BLOCK = """ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ ΤΟΜΕΑ ΥΓΕΙΑΣ
Δείκτης 1: Χείρωνας στον 6ο Οίκο (θέση).
Δείκτης 2: Ποσειδώνας–Πλούτωνας, Εξάγωνο, orb 0°26′.
"""


def test_approved_field_and_jobs_pass():
    assert _career_consistency_errors(_client(), _audit()) == []


def test_unapproved_job_is_rejected():
    errors = _career_consistency_errors(
        _client(jobs="προγραμματιστής, ιατρός"),
        _audit(jobs="προγραμματιστής"),
    )
    assert any("ιατρός" in error and "δεν έχει εγκριθεί" in error for error in errors)


def test_health_job_needs_explicit_two_indicator_block():
    errors = _career_consistency_errors(
        _client(field="Υγεία και φροντίδα", jobs="ιατρός"),
        _audit(fields="Υγεία και φροντίδα", jobs="ιατρός"),
    )
    assert any("ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ" in error for error in errors)


def test_health_job_passes_with_grounded_two_indicator_block():
    errors = _career_consistency_errors(
        _client(field="Υγεία και φροντίδα", jobs="ιατρός"),
        _audit(fields="Υγεία και φροντίδα", jobs="ιατρός", extra=_GROUNDED_HEALTH_BLOCK),
    )
    assert errors == []


def test_missing_manifest_is_rejected():
    errors = _career_consistency_errors(_client(), "Παράρτημα Ελέγχου Τεκμηρίωσης")
    assert any("ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ" in error for error in errors)
    assert any("ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ" in error for error in errors)


# --- Νέα tests από την κριτική ---

def test_health_job_rejected_when_indicators_not_in_appendix():
    """Δύο 'δείκτες' που δεν αντιστοιχούν σε καμία πραγματική όψη του Παραρτήματος."""
    fake_block = """ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ ΤΟΜΕΑ ΥΓΕΙΑΣ
Δείκτης 1: γενική αίσθηση φροντίδας για άλλους ανθρώπους.
Δείκτης 2: γενική ευαισθησία και καλοσύνη στις σχέσεις.
"""
    errors = _career_consistency_errors(
        _client(field="Υγεία και φροντίδα", jobs="ιατρός"),
        _audit(fields="Υγεία και φροντίδα", jobs="ιατρός", extra=fake_block),
    )
    assert any("δεν εντοπίστηκε" in error and "Παράρτημα" in error for error in errors)


def test_health_job_rejected_when_same_indicator_used_twice():
    dup_block = """ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ ΤΟΜΕΑ ΥΓΕΙΑΣ
Δείκτης 1: Χείρωνας στον 6ο Οίκο (θέση).
Δείκτης 2: Χείρωνας στον 6ο Οίκο (θέση).
"""
    errors = _career_consistency_errors(
        _client(field="Υγεία και φροντίδα", jobs="ιατρός"),
        _audit(fields="Υγεία και φροντίδα", jobs="ιατρός", extra=dup_block),
    )
    assert any("ίδιος δείκτης" in error for error in errors)


def test_health_job_rejected_without_appendix_at_all():
    errors = _career_consistency_errors(
        _client(field="Υγεία και φροντίδα", jobs="ιατρός"),
        _audit(fields="Υγεία και φροντίδα", jobs="ιατρός", extra=_GROUNDED_HEALTH_BLOCK,
               include_appendix=False),
    )
    assert any("Δεν βρέθηκε" in error and "Παράρτημα" in error for error in errors)


def test_generic_health_topic_without_clinical_job_is_not_gated():
    """'Τεχνολογία υγείας' δεν πρέπει να ενεργοποιεί τον αυστηρό κλινικό έλεγχο,
    αφού δεν είναι κλινικό επάγγελμα (fix #4 της κριτικής)."""
    errors = _career_consistency_errors(
        _client(field="Τεχνολογία υγείας", jobs="προγραμματίστρια εφαρμογών υγείας"),
        _audit(fields="Τεχνολογία υγείας", jobs="προγραμματίστρια εφαρμογών υγείας"),
    )
    assert not any("ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ" in error for error in errors)


def test_clinical_job_still_gated_even_with_unrelated_sector_title():
    """Το ίδιο το επάγγελμα (π.χ. 'ψυχολόγος') ενεργοποιεί τον έλεγχο,
    ανεξάρτητα από τον τίτλο του τομέα."""
    errors = _career_consistency_errors(
        _client(field="Φροντίδα και ανθρώπινη υποστήριξη", jobs="ψυχολόγος"),
        _audit(fields="Φροντίδα και ανθρώπινη υποστήριξη", jobs="ψυχολόγος"),
    )
    assert any("ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ" in error for error in errors)
