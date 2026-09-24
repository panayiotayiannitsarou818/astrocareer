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


def test_anonymous_template_agrees_with_v12():
    """Το ανώνυμο πρότυπο στέλνεται στο μοντέλο μαζί με την εντολή· δεν πρέπει
    να δείχνει μορφή που ο validator απορρίπτει."""
    from core.reference_loader import load_unified_short_example
    example = load_unified_short_example()
    assert "Σημείωση πριν διαβάσεις τις κάρτες:" in example
    assert "Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:" in example
    assert "κουκκίδες" not in example            # προφίλ: μία παράγραφος
    assert "λιγότερο από μία πρόταση" not in example  # λίστα: μόνο τίτλοι
    assert "βασικές" not in example              # η v12 απαγορεύει «βασικό»
    jobs = [l for l in example.split("\n") if l.startswith("Ενδεικτικά επαγγέλματα:")]
    assert jobs and all("(" in l for l in jobs)  # εξήγηση σε παρένθεση


def test_command_examples_never_mix_usage_and_exclusion():
    """Αν ένα παράδειγμα της εντολής βάζει «χρησιμοποιείται» δίπλα στο
    «ΕΞΑΙΡΕΙΤΑΙ», το μοντέλο το αντιγράφει και ο validator απορρίπτει τη
    γραμμή ως αντιφατική (επιβεβαιωμένο με δοκιμή στον Κανόνα 7 της v12)."""
    import re
    for line in load_orientation_command().split("\n"):
        if "ΕΞΑΙΡΕΙΤΑΙ" in line:
            assert not re.search(r"χρησιμοποι", line, re.IGNORECASE), line
