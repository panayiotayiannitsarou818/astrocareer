"""
Νέα tests, ύστερα από την προδιαγραφή "αναλυτικές αλλαγές στο AstroCheck
Career" (ευέλικτος αριθμός ταλέντων/τομέων, τεκμηρίωση με έναν ισχυρό
δείκτη, κατάργηση σταθερού ορίου έκτασης). Καλύπτουν ό,τι ο μηχανικός
validator μπορεί πραγματικά να ελέγξει δομικά -- η επιλογή του *ποια*
ταλέντα/τομείς είναι επαρκώς τεκμηριωμένα παραμένει ευθύνη του μοντέλου,
σύμφωνα με τη δεσμευτική εντολή, όχι κάτι που ένα regex μπορεί να κρίνει
σημασιολογικά.
"""
from core.models import Aspect, Chart, Point
from core.validator import (
    _duplicate_talent_titles,
    _exact_aspect_type,
    _exact_point_name,
    _exact_sign,
    _indicator_fingerprint,
    _indicator_grounding_error,
    _mentioned_point_names,
    _orientation_audit_errors,
    _talent_documentation_block_errors,
    _talent_paragraph_length_issues,
    validate_orientation,
)

CHART = Chart(
    name="Gavriela Doe", date="1 Jan 2000", time="12:00", place="Nicosia",
    house_system="Placidus",
    points=[Point("G", "Κρόνος", "Αιγόκερως", 10, 0, 0, 280.0, house=6)],
    cusps=[], aspects=[], warnings=[],
)


def _talent_card(n):
    return f"Ταλέντο {n}\n" + " ".join(["λέξη"] * 90) + "\n\n"


def _make_client_text(n_talents=10, n_fields=8, name="Gavriela Doe"):
    talents_body = "".join(_talent_card(i) for i in range(1, n_talents + 1))
    talent_titles = "\n".join(f"- Ταλέντο {i}" for i in range(1, n_talents + 1))
    fields_body = "".join(
        f"{i}. Τομέας {i}\nΓιατί μπορεί να ταιριάζει: συνδέεται με το Ταλέντο {i}.\n"
        f"Ενδεικτικά επαγγέλματα: επάγγελμα {i}α, επάγγελμα {i}β.\n\n"
        for i in range(1, n_fields + 1)
    )
    return (
        f"Σύντομο προφίλ\n{name}. {' '.join(['λέξη'] * 100)}\n\n"
        f"Ταλέντα προς διερεύνηση\n{talents_body}"
        f"Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:\n{talent_titles}\n\n"
        f"Επαγγελματικοί Τομείς\n{fields_body}"
        f"Τελική σύνθεση\n{' '.join(['λέξη'] * 60)} Η τελική επιλογή παραμένει πάντα δική του, ως έκφραση ελεύθερης βούλησης.\nΤι χρειάζεται να θυμάσαι\nΥπενθύμιση.\n"
    )


def _make_audit_text(n_talents=10, n_fields=8):
    fields_list = "\n".join(f"- Τομέας {i}" for i in range(1, n_fields + 1))
    jobs_list = "\n".join(f"- επάγγελμα {i}α, επάγγελμα {i}β" for i in range(1, n_fields + 1))
    # Fix: το _orientation_audit_errors πλέον ελέγχει ΚΑΘΕ ταλέντο ξεχωριστά
    # (chat κριτική #5) -- κάθε "Ταλέντο {i}" χρειάζεται δικό του μπλοκ
    # "ΤΑΛΕΝΤΟ: / Δείκτης" κοντά στο όνομά του, όχι μόνο μία γενική δήλωση.
    # Fix (7ος γύρος): κάθε Δείκτης πρέπει πλέον να είναι στη ΔΟΜΗΜΕΝΗ μορφή
    # «Τύπος: Θέση | Σημείο: ... | Ζώδιο/Οίκος: ...» -- βλ. _parse_indicator_fields.
    talents_docs = "".join(
        f"ΤΑΛΕΝΤΟ: Ταλέντο {i}\n"
        f"Δείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        f"Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Αιγόκερως\n"
        for i in range(1, n_talents + 1)
    )
    return (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        f"{talents_docs}"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        f"ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n{fields_list}\n"
        f"ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n{jobs_list}\n"
        "Τελικός έλεγχος: ολοκληρώθηκε.\n"
    )


# --- Spec: no fixed talent/field count ---

def test_more_than_eight_talents_is_not_penalized():
    """«επιτρέπονται περισσότερα από 8 ταλέντα»"""
    client = _make_client_text(n_talents=10, n_fields=8)
    audit = _make_audit_text(n_talents=10, n_fields=8)
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert result.ok, result.details_lines()


def test_fewer_than_four_talents_is_not_required():
    """«δεν απαιτούνται τουλάχιστον 4 ταλέντα»"""
    client = _make_client_text(n_talents=2, n_fields=1)
    audit = _make_audit_text(n_talents=2, n_fields=1)
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert result.ok, result.details_lines()


def test_more_than_six_career_fields_is_allowed():
    """«περισσότεροι από 6 τομείς επιτρέπονται»"""
    client = _make_client_text(n_talents=8, n_fields=8)
    audit = _make_audit_text(n_talents=8, n_fields=8)
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert result.ok, result.details_lines()


# --- Spec: no fixed length cap ---

def test_deliverable_not_rejected_for_exceeding_1800_words():
    """«το παραδοτέο δεν απορρίπτεται μόνο επειδή ξεπερνά τις 1.800 λέξεις»"""
    client = _make_client_text(n_talents=22, n_fields=8)  # πάνω από 1.800 λέξεις
    audit = _make_audit_text(n_talents=22, n_fields=8)
    word_count = len(client.split())
    assert word_count > 1800
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert result.ok, result.details_lines()
    assert not any("υπερβολικά μεγάλη" in line for line in result.details_lines())


# --- Spec: one especially strong indicator is enough ---

def test_audit_accepts_single_strong_indicator_phrasing():
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "Κάθε ταλέντο στηρίχθηκε είτε σε δύο ή περισσότερους διακριτούς δείκτες είτε σε έναν "
        "ιδιαίτερα ισχυρό και άμεσο δείκτη.\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
    )
    errors = _orientation_audit_errors(CHART, audit)
    assert not any("τουλάχιστον δύο" in e for e in errors)


def test_audit_still_flags_missing_documentation_statement():
    """Regression: αφαιρέσαμε τη ρητή απαίτηση 'τουλάχιστον δύο', αλλά ο
    έλεγχος πρέπει να συνεχίσει να απαιτεί ΚΑΠΟΙΑ δήλωση τεκμηρίωσης."""
    audit = "Παράρτημα τεκμηρίωσης ελέγχου\nΙεράρχηση βαρύτητας: Κανονική.\n"
    errors = _orientation_audit_errors(CHART, audit)
    assert any("δεν δηλώνει ότι κάθε ταλέντο στηρίχθηκε" in e for e in errors)


# --- Spec: duplicate-talent detection ---

def test_duplicate_talent_titles_are_detected():
    text = (
        "Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:\n"
        "- Δημιουργική έκφραση\n- Λογική ανάλυση\n- Δημιουργική Έκφραση\n\nΕπαγγελματικοί Τομείς\n"
    )
    assert _duplicate_talent_titles(text) == ["Δημιουργική Έκφραση"]


def test_no_duplicate_talents_passes_validation():
    client = _make_client_text(n_talents=5, n_fields=4)
    audit = _make_audit_text(n_talents=5, n_fields=4)
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not any("ουσιαστικά ίδια" in line for line in result.details_lines())


def test_duplicate_talents_reject_validation():
    client = _make_client_text(n_talents=3, n_fields=2)
    client = client.replace(
        "Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:\n- Ταλέντο 1\n- Ταλέντο 2\n- Ταλέντο 3",
        "Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:\n- Ταλέντο 1\n- Ταλέντο 2\n- Ταλέντο 1",
    )
    audit = _make_audit_text(n_talents=3, n_fields=2)
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("ουσιαστικά ίδια" in line for line in result.details_lines())


# --- Spec: fields/professions still checked against the technical audit sheet ---

def test_field_missing_from_audit_is_still_rejected():
    """«οι τομείς και τα επαγγέλματα εξακολουθούν να ελέγχονται έναντι του
    τεχνικού δελτίου» -- ένας τομέας ΜΟΝΟ στο καθαρό παραδοτέο πρέπει να
    απορρίπτεται, ακριβώς όπως πριν."""
    client = _make_client_text(n_talents=3, n_fields=1)
    client = client.replace("1. Τομέας 1", "1. Τομέας Χωρίς Έγκριση")
    audit = _make_audit_text(n_talents=3, n_fields=1)  # δεν αναφέρει "Τομέας Χωρίς Έγκριση"
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok


# --- Spec: optional ~70-110 word per-talent check is non-blocking ---

def test_talent_length_note_is_non_blocking_warning():
    """130 λέξεις είναι εκτός στόχου (70-110) αλλά μέσα στο αποδεκτό εύρος
    40-160 -- πρέπει να δώσει μη δεσμευτική σημείωση, όχι απόρριψη."""
    long_talent = "Ταλέντο Μεγάλο\n" + " ".join(["λέξη"] * 130) + "\n\n"
    client = (
        f"Σύντομο προφίλ\nGavriela Doe. {' '.join(['λέξη'] * 100)}\n\n"
        f"Ταλέντα προς διερεύνηση\n{long_talent}"
        "Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:\n- Ταλέντο Μεγάλο\n\n"
        "Επαγγελματικοί Τομείς\n1. Τομέας 1\nΓιατί μπορεί να ταιριάζει: συνδέεται με το Ταλέντο Μεγάλο.\n"
        "Ενδεικτικά επαγγέλματα: επάγγελμα 1α, επάγγελμα 1β.\n\n"
        f"Τελική σύνθεση\n{' '.join(['λέξη'] * 60)} Η τελική επιλογή παραμένει πάντα δική του, ως έκφραση ελεύθερης βούλησης.\nΤι χρειάζεται να θυμάσαι\nΥπενθύμιση.\n"
    )
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο Μεγάλο\nΔείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Αιγόκερως\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
        "Τελικός έλεγχος: ολοκληρώθηκε.\n"
    )
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert result.ok, result.details_lines()  # η σημείωση δεν πρέπει να μπλοκάρει
    assert any("Μη δεσμευτική σημείωση" in line for line in result.details_lines())


def test_talent_paragraph_extreme_length_is_a_hard_error():
    """250 λέξεις είναι πολύ εκτός στόχου (>160) -- πρέπει να μπλοκάρει."""
    warnings, hard_errors = _talent_paragraph_length_issues(
        "Ταλέντα προς διερεύνηση\nΤίτλος\n" + " ".join(["λέξη"] * 250) + "\n\nΕπαγγελματικοί Τομείς\n"
    )
    assert not warnings
    assert hard_errors and "πολύ εκτός" in hard_errors[0]


def test_talent_paragraph_length_notes_flags_out_of_range():
    text = "Ταλέντα προς διερεύνηση\nΤίτλος\n" + " ".join(["λέξη"] * 130) + "\n\nΕπαγγελματικοί Τομείς\n"
    warnings, hard_errors = _talent_paragraph_length_issues(text)
    assert not hard_errors
    assert warnings and "στόχος 70" in warnings[0]


# --- Deep-review 3ος γύρος: free will πρέπει να ελέγχεται ΜΟΝΟ στην Τελική Σύνθεση ---

def test_free_will_mentioned_only_elsewhere_is_not_enough():
    """Η φράση στο Brief Profile δεν πρέπει να «καλύπτει» την απουσία της
    από την ίδια την Τελική Σύνθεση."""
    client = _make_client_text(n_talents=1, n_fields=1)
    client = client.replace(
        "Σύντομο προφίλ\nGavriela Doe.",
        "Σύντομο προφίλ\nGavriela Doe. Η τελική επιλογή παραμένει πάντα δική του, ελεύθερη βούληση.",
    )
    # Αφαίρεσε την αναφορά από την Τελική Σύνθεση.
    client = client.replace(
        " Η τελική επιλογή παραμένει πάντα δική του, ως έκφραση ελεύθερης βούλησης.", ""
    )
    audit = _make_audit_text(n_talents=1, n_fields=1)
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("ελεύθερη βούληση" in line for line in result.details_lines())


# --- Deep-review 3ος γύρος: ακριβής αντιστοίχιση τίτλων, όχι μόνο αριθμός ---

def test_summary_list_title_mismatch_is_rejected():
    """Παρουσιάστηκε 'Analytical thinking' αλλά η συνοπτική λίστα (και το
    τεχνικό δελτίο) αναφέρουν 'Creative writing' -- ίδιος αριθμός (1), αλλά
    διαφορετικό ταλέντο. Πρέπει να απορρίπτεται."""
    client = _make_client_text(n_talents=1, n_fields=1)
    client = client.replace("- Ταλέντο 1", "- Άλλο Ταλέντο")
    audit = _make_audit_text(n_talents=1, n_fields=1).replace("ΤΑΛΕΝΤΟ: Ταλέντο 1", "ΤΑΛΕΝΤΟ: Άλλο Ταλέντο")
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("δεν ταιριάζει ακριβώς" in line for line in result.details_lines())


# --- Deep-review 3ος γύρος: bullet-formatted τομέας δεν πρέπει να παρακάμπτει τον έλεγχο ---

def test_unapproved_bullet_field_is_still_rejected():
    client = _make_client_text(n_talents=1, n_fields=1)
    client = client.replace("1. Τομέας 1", "- Εντελώς μη εγκεκριμένος τομέας")
    audit = _make_audit_text(n_talents=1, n_fields=1)
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("Εντελώς μη εγκεκριμένος τομέας" in line and "δεν έχει εγκριθεί" in line for line in result.details_lines())


# --- Deep-review 3ος γύρος (το πιο σοβαρό): επινοημένος δείκτης έναντι του χάρτη ---

def test_fabricated_indicator_referencing_nonexistent_planet_is_rejected():
    """Ο δοκιμαστικός χάρτης (CHART) έχει μόνο Κρόνο, καμία όψη. Ένας
    δείκτης που αναφέρει "Mercury-Saturn trine" (ο Ερμής δεν υπάρχει καν
    στα σημεία του χάρτη) πρέπει να απορρίπτεται, όχι απλώς να γίνεται
    δεκτός επειδή το κείμενο δεν είναι κενό."""
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Δείκτης 1: Τύπος: Όψη | Σημείο 1: Mercury | Όψη: Τρίγωνο | Σημείο 2: Saturn\n"
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("δεν επαληθεύονται έναντι του χάρτη" in line and "Ερμής" in line for line in result.details_lines())


def test_indicator_referencing_only_real_chart_point_is_accepted():
    """Το ίδιο σενάριο, αλλά ο δείκτης αναφέρει μόνο τον πραγματικό Κρόνο
    -- δεν πρέπει να απορριφθεί ως «ανύπαρκτο στοιχείο»."""
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Δείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Αιγόκερως\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not any("ανύπαρκτα στοιχεία" in line for line in result.details_lines())


# --- Deep-review 4ος γύρος: πλήρης επαλήθευση Οίκου/ζωδίου/όψης, όχι μόνο ύπαρξη ονόματος ---

def test_wrong_house_for_real_planet_is_rejected():
    """Ο δοκιμαστικός Κρόνος είναι στον 6ο Οίκο -- ένας δείκτης που τον
    τοποθετεί στον 3ο πρέπει να απορρίπτεται, όχι να γίνεται δεκτός επειδή
    ο Κρόνος υπάρχει κάπου στον χάρτη."""
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Δείκτης 1: Τύπος: Θέση | Σημείο: Saturn | Οίκος: 3\n"
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Αιγόκερως\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("3ο Οίκο" in line and "6ο" in line for line in result.details_lines())


def test_fake_aspect_between_real_planets_is_rejected():
    """Χάρτης με δύο πραγματικά σημεία (Κρόνος, Ήλιος) αλλά ΚΑΜΙΑ όψη --
    μια δηλωμένη όψη μεταξύ τους πρέπει να απορρίπτεται ως ανύπαρκτη."""
    two_point_chart = Chart(
        name="Gavriela Doe", date="1 Jan 2000", time="12:00", place="Nicosia",
        house_system="Placidus",
        points=[
            Point("G", "Κρόνος", "Αιγόκερως", 10, 0, 0, 280.0, house=6),
            Point("A", "Ήλιος", "Κριός", 5, 0, 0, 5.0, house=1),
        ],
        cusps=[], aspects=[], warnings=[],
    )
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Δείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    result = validate_orientation(
        two_point_chart, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("δεν υπάρχει στο Παράρτημα Όψεων" in line for line in result.details_lines())


def test_indicator_with_no_chart_entity_at_all_is_rejected():
    """«Exceptional abstract analytical energy» -- καμία αναφορά σε
    πλανήτη, Οίκο, ζώδιο ή όψη -- πρέπει να απορρίπτεται ως μη επαληθεύσιμο."""
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Δείκτης 1: Exceptional abstract analytical energy.\n"
        "Δείκτης 2: Powerful conceptual reasoning capacity.\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("δεν χρησιμοποιεί τη δομημένη μορφή" in line for line in result.details_lines())


def test_english_word_boundary_false_positives_fixed():
    """«Sunday planning» δεν πρέπει να αναγνωρίζεται ως αναφορά στον Sun,
    ούτε «Marshall-style approach» ως αναφορά στον Mars -- πριν το regex
    δεν είχε όρια λέξης και έπιανε και τα δύο λανθασμένα."""
    mentioned = _mentioned_point_names("Sunday planning ability, a Marshall-style approach")
    assert "Ήλιος" not in mentioned
    assert "Άρης" not in mentioned


# --- Πραγματικά bugs, εντοπίστηκαν από πραγματικό ανέβασμα .docx ---

def test_dense_chart_note_is_not_misread_as_a_talent():
    """Η υποχρεωτική σημείωση πριν τις κάρτες ταλέντων (Κανόνας 8Α, για
    πυκνά διασυνδεδεμένους χάρτες) είναι μία μακριά παράγραφος που
    εμφανίζεται ΠΡΩΤΗ στην ενότητα -- πριν το fix, μετρούνταν σαν να ήταν
    η ίδια ένα ταλέντο, προκαλώντας ψευδή αναντιστοιχία με τη συνοπτική
    λίστα και ψευδή προειδοποίηση έκτασης."""
    client = _make_client_text(n_talents=1, n_fields=1)
    note = (
        "«Σημείωση πριν διαβάσεις τις κάρτες — ο συγκεκριμένος χάρτης παρουσιάζει ασυνήθιστα πυκνή "
        "διασύνδεση, γι' αυτό περισσότερα ταλέντα από το σύνηθες διαθέτουν ισχυρή και σαφή τεχνική "
        "τεκμηρίωση. Αυτό δεν σημαίνει ότι αποτελούν βεβαιωμένα χαρακτηριστικά ή προβλέψεις. Σημαίνει "
        "ότι υπάρχουν περισσότερες πιθανές κατευθύνσεις που αξίζει να διερευνηθούν και να δοκιμαστούν "
        "στην πράξη.»\n"
    )
    client = client.replace("Ταλέντα προς διερεύνηση\n", "Ταλέντα προς διερεύνηση\n" + note)
    audit = _make_audit_text(n_talents=1, n_fields=1)
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert result.ok, result.details_lines()


def test_narrative_orb_restating_with_adjective_form_does_not_cause_false_mismatch():
    """Πραγματικό σενάριο: το τεχνικό δελτίο ξαναλέει σε φυσική γλώσσα ένα
    ήδη σωστά τεκμηριωμένο orb («Στενή/Ισχυρή τριγωνική όψη Ήλιου–Κρόνου,
    orb 1°00′») -- το "τριγωνική" (επίθετο) δεν ταιριάζει με το μοτίβο
    "Τρίγωνο" (ουσιαστικό), αλλά αυτό ΔΕΝ πρέπει να προκαλεί σφάλμα, αφού
    το ίδιο orb είναι ήδη πλήρως τεκμηριωμένο στο δομημένο πεδίο Δείκτης."""
    chart = _two_point_chart_with_real_trine()
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\nΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Δείκτης 1: Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος | Orb: 1°00′ | Βαρύτητα: Στενή/ισχυρή\n"
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Ο Δείκτης 1 είναι από μόνος του Μοναδικός ισχυρός δείκτης (Στενή/Ισχυρή τριγωνική όψη Ήλιου–Κρόνου, orb 1°00′).\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    result = validate_orientation(
        chart, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert result.ok, result.details_lines()


# --- Πραγματικά bugs, εντοπίστηκαν από πραγματικό ανέβασμα .docx (γύρος με κεφαλαία χωρίς τόνους) ---

def test_all_caps_heading_without_tonos_is_still_recognized():
    """Πραγματικό bug: re.IGNORECASE αλλάζει πεζά/κεφαλαία αλλά ΔΕΝ
    εξισώνει τονισμένους με άτονους χαρακτήρες. "ΠΑΡΑΡΤΗΜΑ ΕΠΙΒΕΒΑΙΩΜΕΝΩΝ
    ΟΨΕΩΝ" (κεφαλαία, χωρίς τόνους -- τυπική ελληνική σύμβαση για
    επικεφαλίδες) δεν ταίριαζε ποτέ με το τονισμένο μοτίβο "Παράρτημα
    Επιβεβαιωμένων Όψεων"."""
    from core.validator import _between_headings
    text = "ΠΑΡΑΡΤΗΜΑ ΕΠΙΒΕΒΑΙΩΜΕΝΩΝ ΟΨΕΩΝ — ΜΟΝΑΔΙΚΗ ΠΗΓΗ ORB ΚΑΙ ΒΑΡΥΤΗΤΑΣ\nΠεριεχόμενο εδώ.\nΤελικός έλεγχος: τέλος.\n"
    block = _between_headings(text, r"Παράρτημα\s+Επιβεβαιωμένων\s+Όψεων", (r"Τελικός\s+έλεγχος",))
    assert "Περιεχόμενο εδώ" in block


def test_technical_bulletin_all_caps_heading_recognized():
    """Ίδιο bug, στον έλεγχο «αναγνωρίσιμη ενότητα τεκμηρίωσης» -- «ΕΣΩΤΕΡΙΚΟ
    ΤΕΧΝΙΚΟ ΔΕΛΤΙΟ ΕΛΕΓΧΟΥ» (κεφαλαία) δεν αναγνωριζόταν επειδή το μοτίβο
    ήταν τονισμένο."""
    audit = (
        "ΕΣΩΤΕΡΙΚΟ ΤΕΧΝΙΚΟ ΔΕΛΤΙΟ ΕΛΕΓΧΟΥ\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\nΔείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Αιγόκερως\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    errors = _orientation_audit_errors(CHART, audit, "Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:\n- Ταλέντο 1")
    assert not any("δεν έχει αναγνωρίσιμη ενότητα" in e for e in errors)


def test_inline_cross_reference_to_a_heading_does_not_truncate_the_block_early():
    """Πραγματικό bug: μια παρενθετική διασταυρούμενη παραπομπή («βλ. Ρητή
    Τεκμηρίωση Τομέα Υγείας») ΜΕΣΑ σε πρόταση της λίστας εγκεκριμένων
    τομέων εκλαμβανόταν λανθασμένα ως το όριο τέλους της ενότητας,
    κόβοντας τη λίστα πριν τις τελευταίες καταχωρήσεις."""
    from core.validator import _between_headings
    text = (
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n"
        "Τομέας Ένα\nΣύνδεση: κάτι (βλ. Ρητή Τεκμηρίωση Τομέα Υγείας)\n"
        "Τομέας Δύο -- ΤΕΛΕΥΤΑΙΟΣ\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\nεπάγγελμα\n"
    )
    block = _between_headings(
        text, r"ΕΓΚΕΚΡΙΜΕΝΟΙ\s+ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ\s+ΤΟΜΕΙΣ",
        (r"ΕΓΚΕΚΡΙΜΕΝΑ\s+ΕΠΑΓΓΕΛΜΑΤΑ", r"ΡΗΤΗ\s+ΤΕΚΜΗΡΙΩΣΗ\s+ΤΟΜΕΑ\s+ΥΓΕΙΑΣ"),
    )
    assert "Τομέας Δύο" in block
    assert "ΤΕΛΕΥΤΑΙΟΣ" in block


# --- Deep-review 5ος γύρος: το ίδιο στοιχείο με δύο διατυπώσεις δεν μετράει ως δύο δείκτες ---

def test_same_fact_worded_differently_is_not_two_distinct_indicators():
    """«Κρόνος στον 6ο Οίκο» δηλωμένο δύο φορές (με διαφορετική διατύπωση
    γύρω από την ίδια δομημένη τιμή) είναι το ΙΔΙΟ τεχνικό στοιχείο -- δεν
    πρέπει να μετρήσει ως δύο διακριτοί δείκτες."""
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\nΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Δείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok


def test_different_facts_about_same_planet_are_accepted():
    """Αντίθετα, θέση σε Οίκο ΚΑΙ θέση σε ζώδιο για τον ίδιο πλανήτη είναι
    δύο πραγματικά διακριτά στοιχεία -- δεν πρέπει να απορριφθούν."""
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\nΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Δείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Αιγόκερως\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert result.ok, result.details_lines()


def test_two_planets_mentioned_without_verifiable_relation_is_rejected():
    """«Saturn and Sun indicate structured creativity» αναφέρει δύο
    πραγματικούς πλανήτες αλλά καμία όψη, θέση ή άλλη επαληθεύσιμη σχέση
    -- δεν πρέπει να μετρήσει ως έγκυρος δείκτης."""
    two_point_chart = Chart(
        name="Gavriela Doe", date="1 Jan 2000", time="12:00", place="Nicosia",
        house_system="Placidus",
        points=[
            Point("G", "Κρόνος", "Αιγόκερως", 10, 0, 0, 280.0, house=6),
            Point("A", "Ήλιος", "Κριός", 5, 0, 0, 5.0, house=1),
        ],
        cusps=[], aspects=[], warnings=[],
    )
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\nΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Δείκτης 1: Saturn and Sun indicate structured creativity.\n"
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    result = validate_orientation(
        two_point_chart, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("δεν χρησιμοποιεί τη δομημένη μορφή" in line for line in result.details_lines())


# --- Deep-review 6ος γύρος: πραγματική όψη δεν πρέπει να "καλύπτει" λάθος Οίκο/ζώδιο ---

def _two_point_chart_with_real_trine():
    return Chart(
        name="Gavriela Doe", date="1 Jan 2000", time="12:00", place="Nicosia",
        house_system="Placidus",
        points=[
            Point("G", "Κρόνος", "Αιγόκερως", 10, 0, 0, 280.0, house=6),
            Point("A", "Ήλιος", "Κριός", 5, 0, 0, 5.0, house=1),
        ],
        cusps=[], aspects=[Aspect("Κρόνος", "Ήλιος", "Τρίγωνο", 1.0, "1°00′", "Στενή/ισχυρή", "test")],
        warnings=[],
    )


def test_real_aspect_and_wrong_house_claim_are_independently_checked():
    """Fix (deep review, 7ος γύρος): με τη δομημένη μορφή, ένας δείκτης
    δηλώνει ΕΝΑ Τύπο (Θέση ή Όψη) -- ο παλιός τρόπος όπου ένα ελεύθερο
    κείμενο μπορούσε ταυτόχρονα να δηλώνει όψη ΚΑΙ Οίκο στην ίδια πρόταση
    (και το πραγματικό τρίγωνο να "κρύβει" τον λάθος Οίκο) δεν υπάρχει
    πλέον δομικά. Εδώ: Δείκτης 1 = πραγματική όψη (σωστή), Δείκτης 2 =
    λάθος Οίκος για τον Κρόνο -- πρέπει να απορριφθεί λόγω του Δείκτη 2,
    ανεξάρτητα από το ότι ο Δείκτης 1 είναι απόλυτα έγκυρος."""
    chart = _two_point_chart_with_real_trine()
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\nΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Δείκτης 1: Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος\n"
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 3\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    result = validate_orientation(
        chart, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("3ο Οίκο" in line and "6ο" in line for line in result.details_lines())


def test_real_aspect_and_wrong_sign_claim_are_independently_checked():
    """Ίδιο σενάριο με λάθος ζώδιο αντί Οίκου."""
    chart = _two_point_chart_with_real_trine()
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\nΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Δείκτης 1: Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος\n"
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Ιχθύες\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    result = validate_orientation(
        chart, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("Ιχθύες" in line and "Αιγόκερως" in line for line in result.details_lines())


def test_real_aspect_with_correct_house_is_still_accepted():
    """Έλεγχος αρνητικού: σωστά δομημένος δείκτης θέσης με τον σωστό Οίκο
    -- ΔΕΝ πρέπει να απορριφθεί (ο νέος έλεγχος να μην είναι υπερβολικά
    αυστηρός όταν όλα είναι σωστά)."""
    chart = _two_point_chart_with_real_trine()
    problem = _indicator_grounding_error("Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6", chart)
    assert problem is None
    problem2 = _indicator_grounding_error("Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος", chart)
    assert problem2 is None


def test_unstructured_free_text_indicator_is_rejected_even_if_it_would_be_true():
    """Fix (deep review, 7ος γύρος): το ελεύθερο κείμενο «Saturn trine Sun
    in the 1st house» ήταν εγγενώς ΑΣΑΦΕΣ -- ο 1ος Οίκος είναι πράγματι
    του Ήλιου (όχι του Κρόνου) σε αυτόν τον χάρτη, αλλά καμία απόσταση
    χαρακτήρων δεν αποδεικνύει σε ΠΟΙΟΝ από τους δύο αναφέρεται. Τώρα
    τέτοιο ελεύθερο κείμενο απορρίπτεται εξαρχής ως μη δομημένο -- η ίδια
    πρόταση πρέπει να εκφραστεί ρητά ως δύο ξεχωριστά, ξεκάθαρα πεδία."""
    chart = _two_point_chart_with_real_trine()  # Κρόνος 6ος Οίκος, Ήλιος 1ος Οίκος
    assert _indicator_grounding_error("Saturn trine Sun in the 1st house.", chart) is not None
    # Η ίδια, αληθής παρατήρηση εκφρασμένη σωστά -- γίνεται δεκτή:
    assert _indicator_grounding_error("Τύπος: Θέση | Σημείο: Ήλιος | Οίκος: 1", chart) is None


# --- Deep-review 8ος γύρος: το ενεργό prompt πρέπει να περιέχει την οδηγία, άκυρες τιμές πρέπει να απορρίπτονται ---

def test_active_prompt_contains_structured_indicator_instructions():
    """Η οδηγία για τη δομημένη μορφή ζούσε αρχικά μόνο στην ενότητα 16
    (Rule 16), που το reference_loader αφαιρεί εξ ολοκλήρου ως υλικό της
    παλιάς αναλυτικής έκδοσης -- ο validator απαιτούσε κάτι που το μοντέλο
    δεν είχε καν κληθεί να παράγει. Τώρα ζει επίσης στον ενεργό Κανόνα 8."""
    from core.reference_loader import load_orientation_command
    from core.prompts import CAREER_CONSISTENCY_RULE_EL, CAREER_CONSISTENCY_RULE_EN

    active_prompt = load_orientation_command()
    assert "Τύπος: Θέση" in active_prompt
    assert "Τύπος: Όψη" in active_prompt
    assert "Τύπος: Θέση" in CAREER_CONSISTENCY_RULE_EL
    assert "Τύπος: Θέση" in CAREER_CONSISTENCY_RULE_EN


def test_unknown_sign_value_is_rejected():
    """«Ζώδιο: Μπανανία» δεν είναι κανένα πραγματικό ζώδιο -- πριν περνούσε
    σιωπηλά επειδή sign γινόταν None και το if απλώς δεν εκτελούνταν."""
    error = _indicator_grounding_error("Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Μπανανία", CHART)
    assert error is not None and "δεν είναι ακριβώς ένα αναγνωρίσιμο ζώδιο" in error


def test_nonnumeric_house_is_rejected():
    """«Οίκος: έξι» ή «Οίκος: άγνωστος» δεν έχουν καθόλου αριθμό -- πριν
    περνούσαν σιωπηλά επειδή ο έλεγχος έτρεχε μόνο ΑΝ βρισκόταν αριθμός."""
    error = _indicator_grounding_error("Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: έξι", CHART)
    assert error is not None and "πρέπει να είναι ακριβώς ένας ακέραιος 1" in error


def test_house_outside_1_to_12_is_rejected():
    error = _indicator_grounding_error("Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 15", CHART)
    assert error is not None and "εκτός του έγκυρου εύρους" in error


def test_invalid_field_value_still_rejects_the_whole_talent():
    """Πλήρες σενάριο αναπαραγωγής της κριτικής: Δείκτης 1 με άκυρο ζώδιο,
    Δείκτης 2 έγκυρος -- το ταλέντο πρέπει να απορριφθεί συνολικά, όχι να
    περάσει επειδή ο δεύτερος δείκτης είναι σωστός."""
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\nΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Δείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Μπανανία\n"
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    result = validate_orientation(
        CHART, client, {"Όνομα": "Gavriela Doe"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("δεν είναι ακριβώς ένα αναγνωρίσιμο ζώδιο" in line for line in result.details_lines())


# --- Deep-review 9ος γύρος: κενές τιμές και "σκουπίδια" γύρω από έγκυρη τιμή ---

def test_empty_sign_value_is_rejected():
    """«Ζώδιο:» χωρίς τιμή δεν πρέπει να μετρήσει σαν να δηλώθηκε κάτι."""
    error = _indicator_grounding_error("Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο:", CHART)
    assert error is not None and "δεν δηλώνει ούτε Ζώδιο ούτε Οίκο" in error


def test_empty_house_value_is_rejected():
    """«Οίκος:» χωρίς τιμή δεν πρέπει να μετρήσει σαν να δηλώθηκε κάτι."""
    error = _indicator_grounding_error("Τύπος: Θέση | Σημείο: Κρόνος | Οίκος:", CHART)
    assert error is not None and "δεν δηλώνει ούτε Ζώδιο ούτε Οίκο" in error


def test_both_fields_empty_is_rejected():
    error = _indicator_grounding_error("Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: | Οίκος:", CHART)
    assert error is not None and "δεν δηλώνει ούτε Ζώδιο ούτε Οίκο" in error


def test_house_value_with_extra_text_is_rejected():
    """«Οίκος: abc6xyz» δεν πρέπει να περάσει επειδή βρέθηκε ένα «6» κάπου
    μέσα σε σκουπίδια -- ολόκληρη η τιμή πρέπει να είναι μόνο ο αριθμός."""
    error = _indicator_grounding_error("Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: abc6xyz", CHART)
    assert error is not None and "χωρίς άλλο κείμενο" in error


def test_sign_value_with_extra_text_is_rejected():
    """«Ζώδιο: Αιγόκερως Μπανανία» δεν πρέπει να περάσει επειδή περιέχει
    ένα έγκυρο ζώδιο -- ολόκληρη η τιμή πρέπει να είναι μόνο το ζώδιο."""
    error = _indicator_grounding_error("Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Αιγόκερως Μπανανία", CHART)
    assert error is not None and "δεν είναι ακριβώς ένα αναγνωρίσιμο ζώδιο" in error


# --- Deep-review 10ος γύρος: κολλημένο πρόσθετο κείμενο (χωρίς κενό) ---

def test_sign_value_glued_with_extra_text_is_rejected():
    """«Ζώδιο: ΑιγόκερωςΜπανανία» (χωρίς κενό) -- το παλιό \\w* στο τέλος
    του στελέχους δεχόταν οποιαδήποτε συνέχεια χαρακτήρων."""
    assert _exact_sign("ΑιγόκερωςΜπανανία") is None
    assert _exact_sign("Αιγόκερωxyz") is None


def test_point_name_value_glued_with_extra_text_is_rejected():
    """«Σημείο: ΚρόνοςΜπανανία» -- η _mentioned_point_names() έκανε
    substring search και ταυτοποιούσε το "Κρόνος" μέσα σε αυτό."""
    assert _exact_point_name("ΚρόνοςΜπανανία") is None
    error = _indicator_grounding_error("Τύπος: Θέση | Σημείο: ΚρόνοςΜπανανία | Οίκος: 6", CHART)
    assert error is not None and "Σημείο" in error


def test_valid_sign_and_point_values_still_accepted():
    """Έλεγχος αρνητικού: οι ίδιες, καθαρές τιμές πρέπει να συνεχίσουν να
    γίνονται δεκτές μετά την αυστηροποίηση."""
    assert _exact_sign("Αιγόκερως") == "Αιγόκερως"
    assert _exact_point_name("Κρόνος") == "Κρόνος"
    assert _indicator_grounding_error("Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Αιγόκερως", CHART) is None


# --- Deep-review 11ος γύρος: ίδιο μοτίβο για το πεδίο «Όψη» ---

def test_aspect_type_value_with_extra_text_is_rejected():
    """«Όψη: ΤρίγωνοΜπανανία» / «Τρίγωνο Μπανανία» / «trine junk» δεν
    πρέπει να ταυτοποιούνται ως «Τρίγωνο» -- ολόκληρη η τιμή πρέπει να
    είναι μόνο ο τύπος όψης."""
    assert _exact_aspect_type("ΤρίγωνοΜπανανία") is None
    assert _exact_aspect_type("Τρίγωνο Μπανανία") is None
    assert _exact_aspect_type("trine junk") is None


def test_aspect_field_with_extra_text_is_rejected_in_full_indicator():
    chart = _two_point_chart_with_real_trine()
    error = _indicator_grounding_error(
        "Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: ΤρίγωνοΜπανανία | Σημείο 2: Ήλιος", chart
    )
    assert error is not None and "Όψη" in error


def test_valid_aspect_type_still_accepted():
    """Έλεγχος αρνητικού: η καθαρή τιμή πρέπει να συνεχίσει να γίνεται δεκτή."""
    assert _exact_aspect_type("Τρίγωνο") == "Τρίγωνο"
    assert _exact_aspect_type("trine") == "Τρίγωνο"
    chart = _two_point_chart_with_real_trine()
    assert _indicator_grounding_error(
        "Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος", chart
    ) is None


# --- Deep-review 13ος γύρος (αίτημα χρήστη): πραγματικός έλεγχος βαρύτητας δεικτών ---

def _chart_with_only_wide_aspects():
    """Χάρτης όπου ο Δίας έχει μόνο δύο αδύναμες όψεις (Πλατιά/Πολύ πλατιά),
    καμία Στενή/Κανονική -- ακριβές σενάριο από πραγματική συζήτηση χρήστη."""
    return Chart(
        name="Test", date="1 Jan 2000", time="12:00", place="Nicosia",
        house_system="Placidus",
        points=[
            Point("G", "Ερμής", "Υδροχόος", 3, 0, 0, 303.0, house=2),
            Point("F", "Δίας", "Σκορπιός", 10, 0, 0, 220.0, house=11),
            Point("L", "Χείρωνας", "Ταύρος", 18, 0, 0, 48.0, house=6),
        ],
        cusps=[], aspects=[
            Aspect("Ερμής", "Δίας", "Τετράγωνο", 6.8, "6°48′", "Πλατιά αλλά έγκυρη", "test"),
            Aspect("Δίας", "Χείρωνας", "Αντίθεση", 7.97, "7°58′", "Πολύ πλατιά/δευτερεύουσα", "test"),
        ],
        warnings=[],
    )


def test_single_wide_aspect_alone_is_not_sufficient_documentation():
    """Πριν το fix, ο validator δεν ήλεγχε ΚΑΘΟΛΟΥ τη βαρύτητα -- μία
    μεμονωμένη «Πλατιά αλλά έγκυρη» όψη μαζί με μια άλλη ασύνδετη Πλατιά/
    Πολύ πλατιά περνούσε σιωπηλά, αντίθετα με τον ρητό κανόνα ότι οι
    Πλατιές χρησιμοποιούνται μόνο υποστηρικτικά."""
    chart = _chart_with_only_wide_aspects()
    errors = _talent_documentation_block_errors(
        "ΤΑΛΕΝΤΟ: Χ\n"
        "Δείκτης 1: Τύπος: Όψη | Σημείο 1: Ερμής | Όψη: Τετράγωνο | Σημείο 2: Δίας | Βαρύτητα: Πλατιά αλλά έγκυρη\n"
        "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Δίας | Όψη: Αντίθεση | Σημείο 2: Χείρωνας | Βαρύτητα: Πολύ πλατιά/δευτερεύουσα\n",
        ["Χ"], chart,
    )
    assert errors and "δεν έχει πλήρη τεκμηρίωση" in errors[0]


def test_position_plus_any_second_indicator_is_still_sufficient():
    """Η θέση (Τύπος: Θέση) ενός σημείου είναι πάντα πρωτεύουσας βαρύτητας
    από μόνη της -- δεν χρειάζεται κατηγορία βαρύτητας. Ο Δίας μπορεί να
    τεκμηριωθεί κανονικά μέσω της δικής του θέσης + μιας υποστηρικτικής
    Πλατιά όψης, χωρίς να χρειάζεται η νέα εξαίρεση των δύο Πλατιά."""
    chart = _chart_with_only_wide_aspects()
    errors = _talent_documentation_block_errors(
        "ΤΑΛΕΝΤΟ: Χ\n"
        "Δείκτης 1: Τύπος: Θέση | Σημείο: Δίας | Ζώδιο: Σκορπιός | Οίκος: 11\n"
        "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Ερμής | Όψη: Τετράγωνο | Σημείο 2: Δίας | Βαρύτητα: Πλατιά αλλά έγκυρη\n",
        ["Χ"], chart,
    )
    assert errors == []


def test_two_wide_aspects_sharing_a_point_are_accepted_via_new_exception():
    """Η νέα εξαίρεση (αίτημα χρήστη): δύο ΔΙΑΚΡΙΤΕΣ όψεις «Πλατιά αλλά
    έγκυρη» -- όχι «Πολύ πλατιά» -- που μοιράζονται κοινό σημείο, μετράνε
    ως επαρκής τεκμηρίωση (μηχανική προσέγγιση «ίδιο θέμα»)."""
    chart = Chart(
        name="Test", date="1 Jan 2000", time="12:00", place="Nicosia",
        house_system="Placidus",
        points=[
            Point("G", "Ερμής", "Υδροχόος", 3, 0, 0, 303.0, house=2),
            Point("F", "Δίας", "Σκορπιός", 10, 0, 0, 220.0, house=11),
            Point("L", "Αφροδίτη", "Αιγόκερως", 18, 0, 0, 288.0, house=2),
        ],
        cusps=[], aspects=[
            Aspect("Ερμής", "Δίας", "Τετράγωνο", 6.8, "6°48′", "Πλατιά αλλά έγκυρη", "test"),
            Aspect("Δίας", "Αφροδίτη", "Τρίγωνο", 6.5, "6°30′", "Πλατιά αλλά έγκυρη", "test"),
        ],
        warnings=[],
    )
    errors = _talent_documentation_block_errors(
        "ΤΑΛΕΝΤΟ: Χ\n"
        "Δείκτης 1: Τύπος: Όψη | Σημείο 1: Ερμής | Όψη: Τετράγωνο | Σημείο 2: Δίας | Βαρύτητα: Πλατιά αλλά έγκυρη\n"
        "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Δίας | Όψη: Τρίγωνο | Σημείο 2: Αφροδίτη | Βαρύτητα: Πλατιά αλλά έγκυρη\n",
        ["Χ"], chart,
    )
    assert errors == []


def test_declared_weight_does_not_matter_only_the_real_one():
    """Αν δηλωθεί εσφαλμένα «Στενή/ισχυρή» για μια όψη που στην
    πραγματικότητα είναι Πλατιά, ο έλεγχος πρέπει να βασιστεί στην
    ΠΡΑΓΜΑΤΙΚΗ βαρύτητα από το chart.aspects, όχι στη δήλωση."""
    chart = _chart_with_only_wide_aspects()
    errors = _talent_documentation_block_errors(
        "ΤΑΛΕΝΤΟ: Χ\n"
        "Δείκτης 1: Τύπος: Όψη | Σημείο 1: Ερμής | Όψη: Τετράγωνο | Σημείο 2: Δίας | Βαρύτητα: Στενή/ισχυρή\n"
        "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Δίας | Όψη: Αντίθεση | Σημείο 2: Χείρωνας | Βαρύτητα: Πολύ πλατιά/δευτερεύουσα\n",
        ["Χ"], chart,
    )
    assert errors and "δεν έχει πλήρη τεκμηρίωση" in errors[0]


def test_single_strong_indicator_must_be_genuinely_narrow():
    """«Μοναδικός ισχυρός δείκτης» με πραγματική βαρύτητα Κανονική (όχι
    Στενή/ισχυρή) δεν πρέπει να μετρήσει ως «ιδιαίτερα ισχυρός»."""
    chart = _two_point_chart_with_real_trine()  # Κρόνος-Ήλιος Τρίγωνο 1° Στενή/ισχυρή
    errors = _talent_documentation_block_errors(
        "ΤΑΛΕΝΤΟ: Χ\n"
        "Μοναδικός ισχυρός δείκτης: Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος\n"
        "Αιτιολόγηση ισχύος και άμεσης συνάφειας: πολύ στενή και άμεση.\n",
        ["Χ"], chart,
    )
    assert errors == []  # Στενή/ισχυρή όντως -- πρέπει να περάσει


# --- Deep-review 12ος γύρος: η Χιαστί όψη (quincunx) είναι πραγματικός, υποστηριζόμενος τύπος ---

def test_quincunx_aspect_type_is_accepted():
    """Η «Χιαστί όψη 150°» αναγνωρίζεται από τον parser (Astrodienst «s»)
    -- δεν πρέπει να αποκλείεται από τον αυστηρό έλεγχο τύπου όψης."""
    assert _exact_aspect_type("Χιαστί") == "Χιαστί όψη 150°"
    assert _exact_aspect_type("Χιαστί όψη") == "Χιαστί όψη 150°"
    assert _exact_aspect_type("Χιαστί όψη 150°") == "Χιαστί όψη 150°"
    assert _exact_aspect_type("quincunx") == "Χιαστί όψη 150°"


def test_quincunx_with_extra_text_is_still_rejected():
    assert _exact_aspect_type("Χιαστί όψη 150° Μπανανία") is None


def test_quincunx_indicator_fingerprint_is_built_correctly():
    """Το αποτύπωμα ενός δείκτη Χιαστί όψης πρέπει να δημιουργείται
    κανονικά, όπως και για κάθε άλλο τύπο όψης."""
    chart = Chart(
        name="Gavriela Doe", date="1 Jan 2000", time="12:00", place="Nicosia",
        house_system="Placidus",
        points=[
            Point("G", "Κρόνος", "Αιγόκερως", 10, 0, 0, 280.0, house=6),
            Point("A", "Ήλιος", "Κριός", 5, 0, 0, 5.0, house=1),
        ],
        cusps=[], aspects=[Aspect("Κρόνος", "Ήλιος", "Χιαστί όψη 150°", 1.0, "1°00′", "Στενή/ισχυρή", "test")],
        warnings=[],
    )
    assert _indicator_grounding_error(
        "Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Χιαστί όψη 150° | Σημείο 2: Ήλιος", chart
    ) is None
    fp = _indicator_fingerprint("Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Χιαστί όψη 150° | Σημείο 2: Ήλιος", chart)
    assert fp == ("aspect", frozenset({"Κρόνος", "Ήλιος"}), "Χιαστί όψη 150°")


# --- Spec: per-talent documentation verification (not just one generic statement) ---

def test_audit_flags_talent_missing_its_own_indicator_block():
    client = _make_client_text(n_talents=2, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\nΔείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\nΔείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Αιγόκερως\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 2\n"  # λείπει ο δείκτης για το Ταλέντο 2
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας 1\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα 1α, επάγγελμα 1β\n"
    )
    errors = _orientation_audit_errors(CHART, audit, client)
    assert any("Ταλέντο 2" in e and "δεν έχει πλήρη τεκμηρίωση" in e for e in errors)
    assert not any("Ταλέντο 1»" in e and "δεν έχει πλήρη τεκμηρίωση" in e for e in errors)


def test_audit_rejects_empty_indicator_labels():
    """«Δείκτης 1: γενική ένδειξη.» -- έχει τη λέξη αλλά ουσιαστικά κενό
    περιεχόμενο -- δεν πρέπει να αρκεί ΜΟΝΟ του χωρίς Δείκτη 2."""
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\nΔείκτης 1: \nΔείκτης 2: \n"  # και τα δύο ουσιαστικά κενά
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
    )
    errors = _orientation_audit_errors(CHART, audit, client)
    assert any("Ταλέντο 1" in e and "δεν έχει πλήρη τεκμηρίωση" in e for e in errors)


def test_audit_rejects_two_identical_indicators():
    """Δύο «δείκτες» με ταυτόσημο περιεχόμενο δεν μετρούν ως δύο διακριτοί."""
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\nΔείκτης 1: Ήλιος σε τρίγωνο με Ερμή.\nΔείκτης 2: Ήλιος σε τρίγωνο με Ερμή.\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
    )
    errors = _orientation_audit_errors(CHART, audit, client)
    assert any("Ταλέντο 1" in e and "δεν έχει πλήρη τεκμηρίωση" in e for e in errors)


def test_audit_accepts_single_strong_indicator_with_justification():
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "Μοναδικός ισχυρός δείκτης: Στενή σύνοδος Ήλιου-Ερμή στον 3ο Οίκο.\n"
        "Αιτιολόγηση ισχύος και άμεσης συνάφειας: μικρό orb, προσωπικός πλανήτης, γωνιακό σημείο.\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
    )
    errors = _orientation_audit_errors(CHART, audit, client)
    assert not any("δεν έχει πλήρη τεκμηρίωση" in e for e in errors)


def test_audit_rejects_single_strong_indicator_without_justification():
    """«Μοναδικός ισχυρός δείκτης» χωρίς αιτιολόγηση δεν αρκεί."""
    client = _make_client_text(n_talents=1, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\nΜοναδικός ισχυρός δείκτης: Στενή σύνοδος Ήλιου-Ερμή.\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
    )
    errors = _orientation_audit_errors(CHART, audit, client)
    assert any("Ταλέντο 1" in e and "δεν έχει πλήρη τεκμηρίωση" in e for e in errors)


def test_audit_indicators_do_not_leak_across_talent_blocks():
    """Παλιό bug: σταθερό παράθυρο 400 χαρακτήρων μπορούσε να δει τους
    δείκτες του ΕΠΟΜΕΝΟΥ ταλέντου. Εδώ το Ταλέντο 1 δεν έχει δικούς του
    δείκτες -- μόνο ο τίτλος του, ακολουθούμενος αμέσως από το πλήρες
    μπλοκ του Ταλέντου 2 -- και πρέπει να απορριφθεί ΠΑΡΟΛΟ που υπάρχουν
    δείκτες αμέσως μετά (ανήκουν στο άλλο ταλέντο)."""
    client = _make_client_text(n_talents=2, n_fields=1)
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 2\nΔείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\nΔείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Αιγόκερως\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
    )
    errors = _orientation_audit_errors(CHART, audit, client)
    assert any("Ταλέντο 1" in e and "δεν έχει πλήρη τεκμηρίωση" in e for e in errors)
    assert not any("Ταλέντο 2»" in e and "δεν έχει πλήρη τεκμηρίωση" in e for e in errors)


def test_audit_title_matching_does_not_confuse_prefix_titles():
    """Deep-review εύρημα: 'Ταλέντο 1' δεν πρέπει ποτέ να "δανείζεται"
    τεκμηρίωση από το μπλοκ 'Ταλέντο 10' μόνο επειδή είναι textual prefix
    (πριν το ταίριασμα γινόταν με .startswith(), όχι ακριβές)."""
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 10\nΔείκτης 1: ένδειξη Άλφα.\nΔείκτης 2: ένδειξη Βήτα.\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\n"  # σκόπιμα χωρίς δικούς του δείκτες
    )
    errors = _talent_documentation_block_errors(audit, ["Ταλέντο 1", "Ταλέντο 10"])
    assert any("Ταλέντο 1»" in e for e in errors)
    assert not any("Ταλέντο 10»" in e for e in errors)
