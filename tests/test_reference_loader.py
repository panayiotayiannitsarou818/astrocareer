from core.reference_loader import _filter_orientation_sections


# Η υπηρεσία ενοποιήθηκε σε ένα μόνο mode (Κανόνας 0Γ, "Ενοποιημένος κανόνας
# σύντομης και απλής έκδοσης") -- δεν υπάρχει πια ξεχωριστό 0Δ/παιδί ή service
# param. Αυτό το δείγμα αντικατοπτρίζει τη νέα δομή: ο Κανόνας 0 (mode-
# selector "Παιδί/έφηβος" vs "Ενήλικας") είναι πλέον νεκρό κείμενο της
# "Αναλυτικής" έκδοσης και αποκλείεται κι αυτός, μαζί με τα υπόλοιπα
# _ANALYTICAL_ONLY_HEADINGS.
_SAMPLE = """0. Υποχρεωτική επιλογή λειτουργίας
Διάβαζε ένα πεδίο "Τύπος υπηρεσίας" που δεν στέλνεται πια -- νεκρό κείμενο.
0Α. Υποχρεωτική μορφή παρουσίασης κάθε ταλέντου
Πίνακες, μόνο για την αναλυτική έκδοση.
0Γ. Ενοποιημένος κανόνας σύντομης και απλής έκδοσης
Κανόνες που ισχύουν για όλους τους πελάτες, χωρίς διάκριση.
1. Εξέτασε τους πέντε προσωπικούς πλανήτες
Μεθοδολογία που ισχύει πάντα.
10Α. Πλαίσιο εκπαιδευτικού συστήματος
Πλήρης αναλυτική εκδοχή -- καταργήθηκε εντελώς το χαρακτηριστικό.
16. Υποχρεωτική δομή τελικού κειμένου
Δομή μόνο για την αναλυτική έκδοση.
19. Υπερισχύων κανόνας χωρίς συλλογή πρόσθετων δεδομένων
Γενικός κανόνας που ισχύει πάντα.
"""


def test_keeps_unified_rule_and_shared_rules():
    text = _filter_orientation_sections(_SAMPLE)
    assert "Κανόνες που ισχύουν για όλους τους πελάτες, χωρίς διάκριση." in text
    assert "Μεθοδολογία που ισχύει πάντα." in text
    assert "Γενικός κανόνας που ισχύει πάντα." in text


def test_drops_dead_mode_selector_rule_0():
    text = _filter_orientation_sections(_SAMPLE)
    assert 'Διάβαζε ένα πεδίο "Τύπος υπηρεσίας"' not in text


def test_drops_analytical_only_sections():
    text = _filter_orientation_sections(_SAMPLE)
    assert "Πίνακες, μόνο για την αναλυτική έκδοση." not in text
    assert "Πλήρης αναλυτική εκδοχή -- καταργήθηκε εντελώς το χαρακτηριστικό." not in text
    assert "Δομή μόνο για την αναλυτική έκδοση." not in text


def test_no_service_argument_required():
    # Η _filter_orientation_sections δεν παίρνει πια δεύτερο όρισμα service --
    # καλώντας τη με ένα μόνο positional argument πρέπει να δουλεύει καθαρά.
    text = _filter_orientation_sections(_SAMPLE)
    assert isinstance(text, str) and len(text) > 0


def test_filtering_meaningfully_shrinks_the_document():
    filtered = _filter_orientation_sections(_SAMPLE)
    assert len(filtered) < len(_SAMPLE) * 0.7
