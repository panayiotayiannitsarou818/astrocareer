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
