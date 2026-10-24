"""
Νέο test, ύστερα από την κριτική #12: τα core/i18n.py::TR["el"]/TR["en"]
αντιγράφονταν χειροκίνητα με τα ίδια keys, χωρίς κανέναν αυτόματο έλεγχο
συνέπειας -- μια μελλοντική προσθήκη σε μία γλώσσα θα μπορούσε εύκολα να
ξεχαστεί στην άλλη, σκάγοντας με KeyError μόνο όταν κάποιος επέλεγε την
"ξεχασμένη" γλώσσα στην εφαρμογή.

Το TR εξήχθη σε ξεχωριστό core/i18n.py ειδικά ώστε να γίνεται αυτό το
test χωρίς να χρειάζεται να τρέξει ολόκληρη η Streamlit εφαρμογή.
"""
from core.i18n import TR


def test_tr_has_exactly_el_and_en():
    assert set(TR.keys()) == {"el", "en"}


def test_tr_el_and_en_have_identical_keys():
    el_keys = set(TR["el"].keys())
    en_keys = set(TR["en"].keys())
    missing_in_en = el_keys - en_keys
    missing_in_el = en_keys - el_keys
    assert not missing_in_en, f"Λείπουν από τα Αγγλικά: {sorted(missing_in_en)}"
    assert not missing_in_el, f"Λείπουν από τα Ελληνικά: {sorted(missing_in_el)}"


def test_tr_values_are_non_empty_strings():
    for lang in ("el", "en"):
        for key, value in TR[lang].items():
            assert isinstance(value, str) and value.strip(), f"{lang}.{key} is empty or not a string"


def test_validator_summary_follows_the_page_language():
    """v19.7: στα αγγλικά το μήνυμα έγκρισης/απόρριψης ήταν ελληνικό."""
    from core.validator import OrientationValidationResult
    import dataclasses
    fields = {f.name: ([] if f.type.startswith("list") else None) for f in dataclasses.fields(OrientationValidationResult)}
    ok = OrientationValidationResult(**{**fields, "ok": True})
    assert ok.summary("en").startswith("✓ The career orientation passed")
    assert ok.summary().startswith("✓ Ο προαιρετικός")
    bad = OrientationValidationResult(**{**fields, "ok": False, "technical_mismatches": ["x"],
                                         "technical_breakdown": {"audit": 1}})
    assert bad.summary("en") == "The orientation was rejected: 1 error in the technical audit sheet."
    assert "απορρίφθηκε" in bad.summary()


def test_every_language_has_the_details_note_key():
    from core.i18n import TR
    assert all("details_in_greek" in TR[lang] for lang in TR)
