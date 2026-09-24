"""Η δεσμευτική εντολή v12 περιέχει μόνο την «Απλή και πρακτική» έκδοση και
φορτώνεται ΟΛΟΚΛΗΡΗ. Αυτά τα tests ελέγχουν ότι τίποτα από όσα ελέγχει ο
validator δεν χάνεται πριν φτάσει στο μοντέλο."""
from core.reference_loader import COMMON_ORIENTATION, docx_text, load_orientation_command


def test_command_is_loaded_in_full():
    command = load_orientation_command()
    # Κάθε μη κενή παράγραφος και γραμμή πίνακα του αρχείου φτάνει στο μοντέλο.
    assert set(docx_text(COMMON_ORIENTATION).split("\n")) == set(command.split("\n"))


def test_structured_indicator_and_coverage_formats_reach_the_model():
    command = load_orientation_command()
    assert "Τύπος: Θέση" in command
    assert "Τύπος: Όψη" in command
    assert "Παράρτημα Επιβεβαιωμένων Όψεων" in command
    assert "Ιεράρχηση" in command


def test_mandatory_labels_reach_the_model():
    command = load_orientation_command()
    for label in (
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ",
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ",
        "ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ ΤΟΜΕΑ ΥΓΕΙΑΣ",
        "Σημείωση πριν διαβάσεις τις κάρτες",
        "Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:",
    ):
        assert label in command, label


def test_career_catalog_stays_inside_its_rule():
    """Ο κατάλογος τομέων διαβάζεται στη θέση του, μέσα στον κανόνα επιλογής
    τομέων, όχι στο τέλος του κειμένου μετά τον κανόνα ύφους."""
    command = load_orientation_command()
    catalog = command.index("Επαγγελματικός τομέας | Ενδεικτικά επαγγέλματα")
    assert command.index("Κανόνας 12.") < catalog < command.index("Κανόνας 13.")
    assert "Υγεία και θεραπευτικές υπηρεσίες (*)" in command


def test_dense_chart_note_is_recognised_in_both_languages():
    """Η σημείωση του Κανόνα 11 δεν πρέπει να μετρά ως ταλέντο, ούτε στα
    ελληνικά ούτε στο αγγλικό παραδοτέο."""
    from core.validator import _strip_dense_chart_note
    for note in (
        "Σημείωση πριν διαβάσεις τις κάρτες: Η ανάλυση δείχνει πολλές συνδέσεις.",
        "Note before reading the cards: The analysis shows many close links.",
    ):
        block = "\n" + note + "\nΤίτλος ταλέντου\nΠαράγραφος ταλέντου."
        assert note not in _strip_dense_chart_note(block)


def test_auto_prompt_does_not_repeat_the_consistency_rule():
    """Ο κανόνας συνέπειας ζει μόνο μέσα στη δεσμευτική εντολή (v12, Κανόνες
    14-15)· το prompt δεν πρέπει να τον στέλνει δεύτερη φορά."""
    from core.prompts import build_orientation_prompt
    command = load_orientation_command()
    prompt = build_orientation_prompt({"Όνομα": "Test"}, command, "ΠΗΓΗ", need_audit=True)
    assert prompt.count("ΥΠΟΧΡΕΩΤΙΚΟΣ ΚΑΝΟΝΑΣ ΣΥΝΕΠΕΙΑΣ") == 0
    assert command in prompt
