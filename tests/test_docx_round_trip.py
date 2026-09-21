"""
Το πιο σημαντικό test-αρχείο στο repo, με μία έννοια: όλα τα προηγούμενα
tests περνάνε το ΩΜΟ κείμενο κατευθείαν στον validate_orientation(). Αλλά
στην πραγματική χρήση (είτε αυτόματη δημιουργία είτε το χειροκίνητο
upload-and-check flow), το κείμενο πρώτα γίνεται πραγματικό .docx
(core/docx_builder.py) και μετά ΞΑΝΑδιαβάζεται σε κείμενο (docx_text())
πριν φτάσει στον validator. Αυτό το round-trip ΔΕΝ είναι ταυτοτικό:

- το docx_text() δεν διατηρεί ΠΟΤΕ κενές γραμμές (τις φιλτράρει ρητά),
  οπότε καμία λογική διαχωρισμού που βασίζεται σε "\\n\\s*\\n" δεν δουλεύει
  μετά το round-trip·
- τα bullet/αριθμημένα markers ("-", "1.") που γράφτηκαν στο αρχικό
  κείμενο μετατρέπονται σε ΕΓΓΕΝΗ μορφοποίηση λίστας Word -- ο ίδιος ο
  χαρακτήρας δεν επιβιώνει σαν literal κείμενο στην επαναφόρτωση.

Αυτό το bug ανακαλύφθηκε ΟΧΙ από κάποια θεωρητική ανάλυση αλλά από
πραγματικό ανέβασμα ενός πραγματικού, σωστά γραμμένου παραδοτέου: το ίδιο
ακριβώς κείμενο περνούσε άψογα σε ωμή μορφή αλλά απορριπτόταν πλήρως μετά
το round-trip σε πραγματικό .docx -- ακριβώς το σενάριο που θα συναντούσε
ΚΑΘΕ πραγματικός χρήστης της εφαρμογής.
"""
from core.docx_builder import build_orientation_audit_docx, build_orientation_client_docx
from core.models import Aspect, Chart, Point
from core.reference_loader import docx_text
from core.validator import validate_orientation

CHART = Chart(
    name="Test", date="1 Jan 2000", time="12:00", place="Nicosia",
    house_system="Placidus",
    points=[
        Point("G", "Κρόνος", "Αιγόκερως", 10, 0, 0, 280.0, house=6),
        Point("A", "Ήλιος", "Κριός", 5, 0, 0, 5.0, house=1),
    ],
    cusps=[], aspects=[Aspect("Κρόνος", "Ήλιος", "Τρίγωνο", 1.0, "1°00′", "Στενή/ισχυρή", "test")],
    warnings=[],
)


def _talent(n_words=90):
    return "Τίτλος Ταλέντου {n}\n" + " ".join(["λέξη"] * n_words) + "\n\n"


def _build_client_text(n_talents=3):
    talents = "".join(
        f"Ταλέντο {i}\n" + " ".join(["λέξη"] * 90) + "\n\n" for i in range(1, n_talents + 1)
    )
    titles = "\n".join(f"- Ταλέντο {i}" for i in range(1, n_talents + 1))
    fields = "".join(
        f"{i}. Τομέας {i}\nΓιατί μπορεί να ταιριάζει: συνδέεται με το Ταλέντο {i}.\n"
        f"Ενδεικτικά επαγγέλματα: επάγγελμα {i}α, επάγγελμα {i}β.\n\n"
        for i in range(1, n_talents + 1)
    )
    return (
        f"Σύντομο προφίλ\nTest. {' '.join(['λέξη'] * 100)}\n\n"
        f"Ταλέντα προς διερεύνηση\n{talents}"
        f"Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:\n{titles}\n\n"
        f"Επαγγελματικοί Τομείς προς Διερεύνηση\n{fields}"
        f"Τελική σύνθεση\n{' '.join(['λέξη'] * 60)} Η τελική επιλογή παραμένει πάντα δική του, "
        "ως έκφραση ελεύθερης βούλησης. Τα μαθήματα και η πραγματική επίδοση θα χρειαστεί "
        "αργότερα να επιβεβαιώσουν ή να αναθεωρήσουν αυτό το συμπέρασμα.\n"
    )


def _build_audit_text(n_talents=3):
    fields_list = "\n".join(f"- Τομέας {i}" for i in range(1, n_talents + 1))
    jobs_list = "\n".join(f"- επάγγελμα {i}α, επάγγελμα {i}β" for i in range(1, n_talents + 1))
    talents_docs = "".join(
        f"ΤΑΛΕΝΤΟ: Ταλέντο {i}\n"
        f"Δείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        f"Δείκτης 2: Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος | Orb: 1°00′ | Βαρύτητα: Στενή/ισχυρή\n"
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


def test_valid_deliverable_survives_the_real_docx_round_trip():
    """Το κρίσιμο test: κείμενο -> πραγματικό .docx -> επαναφόρτωση -> validator.
    Πριν το fix, αυτό απέτυχε ΠΑΝΤΑ για κάθε έγκυρο παραδοτέο."""
    client_text = _build_client_text(n_talents=3)
    audit_text = _build_audit_text(n_talents=3)

    client_bytes = build_orientation_client_docx("Τίτλος Υπηρεσίας", "Test", client_text)
    audit_bytes = build_orientation_audit_docx("Εσωτερικό Τεχνικό Δελτίο", "Test", audit_text)

    client_from_docx = docx_text(__import__("io").BytesIO(client_bytes))
    audit_from_docx = docx_text(__import__("io").BytesIO(audit_bytes))

    result = validate_orientation(
        CHART, client_from_docx, {"Όνομα": "Test"},
        presentation_mode="Απλή και πρακτική", audit_text=audit_from_docx, format_issues=[],
    )
    assert result.ok, result.details_lines()


def test_round_trip_with_six_talents_still_works():
    """Μεγαλύτερο παραδοτέο (6 ταλέντα) -- επιβεβαιώνει ότι η ομαδοποίηση
    παραγράφων δεν σπάει με περισσότερα ταλέντα."""
    client_text = _build_client_text(n_talents=6)
    audit_text = _build_audit_text(n_talents=6)

    client_bytes = build_orientation_client_docx("Τίτλος Υπηρεσίας", "Test", client_text)
    audit_bytes = build_orientation_audit_docx("Εσωτερικό Τεχνικό Δελτίο", "Test", audit_text)

    import io
    client_from_docx = docx_text(io.BytesIO(client_bytes))
    audit_from_docx = docx_text(io.BytesIO(audit_bytes))

    result = validate_orientation(
        CHART, client_from_docx, {"Όνομα": "Test"},
        presentation_mode="Απλή και πρακτική", audit_text=audit_from_docx, format_issues=[],
    )
    assert result.ok, result.details_lines()


def test_round_trip_still_rejects_a_genuinely_too_long_talent():
    """Αρνητικός έλεγχος: το round-trip δεν πρέπει να κάνει τον έλεγχο
    αδρανή -- μια πραγματικά υπερβολική παράγραφος πρέπει να εξακολουθεί
    να απορρίπτεται μετά το round-trip."""
    import io
    client_text = _build_client_text(n_talents=1)
    client_text = client_text.replace(
        "Ταλέντο 1\n" + " ".join(["λέξη"] * 90),
        "Ταλέντο 1\n" + " ".join(["λέξη"] * 250),
    )
    audit_text = _build_audit_text(n_talents=1)
    client_bytes = build_orientation_client_docx("Τίτλος Υπηρεσίας", "Test", client_text)
    audit_bytes = build_orientation_audit_docx("Εσωτερικό Τεχνικό Δελτίο", "Test", audit_text)
    client_from_docx = docx_text(io.BytesIO(client_bytes))
    audit_from_docx = docx_text(io.BytesIO(audit_bytes))
    result = validate_orientation(
        CHART, client_from_docx, {"Όνομα": "Test"},
        presentation_mode="Απλή και πρακτική", audit_text=audit_from_docx, format_issues=[],
    )
    assert not result.ok
    assert any("πολύ εκτός του στόχου" in line for line in result.details_lines())


# --- Πραγματικό εύρημα χρήστη: η κάλυψη έπρεπε να καλύπτει ΟΛΕΣ τις όψεις Στενής/Κανονικής βαρύτητας, όχι μόνο τις 5 στενότερες ---

def test_coverage_check_now_requires_all_strong_and_normal_aspects_not_just_top_5():
    """Χάρτης με ΠΕΡΙΣΣΟΤΕΡΕΣ από 5 όψεις Στενής/ισχυρής ή Κανονικής βαρύτητας
    -- πριν το fix, μόνο οι 5 στενότερες ελέγχονταν μηχανικά, αφήνοντας τις
    υπόλοιπες εντελώς εκτός ελέγχου (πραγματική αιτία γιατί διαφορετικές
    συνεδρίες παραγωγής μπορούσαν να βρουν πολύ διαφορετικό αριθμό ταλέντων
    από τον ίδιο χάρτη, χωρίς κανένα μηχανικό εμπόδιο)."""
    chart = Chart(
        name="Test", date="1 Jan 2000", time="12:00", place="Nicosia",
        house_system="Placidus",
        points=[
            Point("G", "Κρόνος", "Αιγόκερως", 10, 0, 0, 280.0, house=6),
            Point("A", "Ήλιος", "Κριός", 5, 0, 0, 5.0, house=1),
            Point("B", "Σελήνη", "Καρκίνος", 5, 0, 0, 95.0, house=4),
        ],
        cusps=[], aspects=[
            Aspect("Κρόνος", "Ήλιος", "Τρίγωνο", 1.0, "1°00′", "Στενή/ισχυρή", "test"),
            Aspect("Σελήνη", "Ήλιος", "Τετράγωνο", 3.0, "3°00′", "Κανονική", "test"),  # ΔΕΝ τεκμηριώνεται πουθενά
        ],
        warnings=[],
    )
    client = _build_client_text(n_talents=1)
    audit = _build_audit_text(n_talents=1)  # μόνο Κρόνος–Ήλιος καλύπτεται
    result = validate_orientation(
        chart, client, {"Όνομα": "Test"},
        presentation_mode="Απλή και πρακτική", audit_text=audit, format_issues=[],
    )
    assert not result.ok
    assert any("Σελήνη–Ήλιος" in line and "δεν τεκμηριώνεται πλήρως" in line for line in result.details_lines())


# --- Έλεγχος αιτήματος χρήστη: η λίστα «ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ» επιβιώνει το ίδιο round-trip; ---
# Σε αντίθεση με τη λίστα τομέων/ταλέντων, η εξαγωγή επαγγελμάτων ΔΕΝ βασίζεται
# καθόλου σε bullet markers -- ενώνει τις γραμμές του μπλοκ με κόμμα και
# χωρίζει σε κόμμα/άνω τελεία, οπότε η απώλεια της παύλας από το Word δεν
# επηρεάζει τίποτα. Επιβεβαιώθηκε εδώ και προς τις δύο κατευθύνσεις.

def test_approved_job_list_survives_docx_round_trip():
    """Θετικός έλεγχος: επαγγέλματα γραμμένα με bullets στο τεχνικό δελτίο
    (που χάνουν την παύλα στο πραγματικό .docx) πρέπει να εγκρίνουν κανονικά
    τα ίδια επαγγέλματα στο καθαρό παραδοτέο."""
    client = (
        "Σύντομο προφίλ\nTest. " + " ".join(["λέξη"] * 100) + "\n\n"
        "Ταλέντα προς διερεύνηση\nΤαλέντο 1\n" + " ".join(["λέξη"] * 90) + "\n\n"
        "Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:\n- Ταλέντο 1\n\n"
        "Επαγγελματικοί Τομείς προς Διερεύνηση\n1. Τομέας Ένα\n"
        "Γιατί μπορεί να ταιριάζει: συνδέεται με το Ταλέντο 1.\n"
        "Ενδεικτικά επαγγέλματα: επάγγελμα άλφα, επάγγελμα βήτα, επάγγελμα γάμα.\n\n"
        "Τελική σύνθεση\n" + " ".join(["λέξη"] * 60) +
        " Η τελική επιλογή παραμένει πάντα δική του, ως έκφραση ελεύθερης βούλησης."
        " Τα μαθήματα και η πραγματική επίδοση θα χρειαστεί αργότερα να επιβεβαιώσουν ή να αναθεωρήσουν αυτό το συμπέρασμα.\n"
    )
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\nΔείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος | Orb: 1°00′ | Βαρύτητα: Στενή/ισχυρή\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας Ένα\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα άλφα, επάγγελμα βήτα\n- επάγγελμα γάμα\n"
        "Τελικός έλεγχος: ολοκληρώθηκε.\n"
    )
    client_bytes = build_orientation_client_docx("Τίτλος", "Test", client)
    audit_bytes = build_orientation_audit_docx("Τεχνικό Δελτίο", "Test", audit)
    import io
    client_rt = docx_text(io.BytesIO(client_bytes))
    audit_rt = docx_text(io.BytesIO(audit_bytes))
    result = validate_orientation(
        CHART, client_rt, {"Όνομα": "Test"},
        presentation_mode="Απλή και πρακτική", audit_text=audit_rt, format_issues=[],
    )
    assert result.ok, result.details_lines()


def test_unapproved_job_still_rejected_after_docx_round_trip():
    """Αρνητικός έλεγχος: το round-trip δεν πρέπει να κάνει τον έλεγχο
    επαγγελμάτων αδρανή -- ένα μη εγκεκριμένο επάγγελμα πρέπει να συνεχίσει
    να απορρίπτεται."""
    client = (
        "Σύντομο προφίλ\nTest. " + " ".join(["λέξη"] * 100) + "\n\n"
        "Ταλέντα προς διερεύνηση\nΤαλέντο 1\n" + " ".join(["λέξη"] * 90) + "\n\n"
        "Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:\n- Ταλέντο 1\n\n"
        "Επαγγελματικοί Τομείς προς Διερεύνηση\n1. Τομέας Ένα\n"
        "Γιατί μπορεί να ταιριάζει: συνδέεται με το Ταλέντο 1.\n"
        "Ενδεικτικά επαγγέλματα: επάγγελμα άλφα, Εντελώς μη εγκεκριμένο επάγγελμα.\n\n"
        "Τελική σύνθεση\n" + " ".join(["λέξη"] * 60) +
        " Η τελική επιλογή παραμένει πάντα δική του, ως έκφραση ελεύθερης βούλησης."
        " Τα μαθήματα και η πραγματική επίδοση θα χρειαστεί αργότερα να επιβεβαιώσουν ή να αναθεωρήσουν αυτό το συμπέρασμα.\n"
    )
    audit = (
        "Παράρτημα τεκμηρίωσης ελέγχου\n"
        "ΤΑΛΕΝΤΟ: Ταλέντο 1\nΔείκτης 1: Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6\n"
        "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Κρόνος | Όψη: Τρίγωνο | Σημείο 2: Ήλιος | Orb: 1°00′ | Βαρύτητα: Στενή/ισχυρή\n"
        "Ιεράρχηση βαρύτητας: Κανονική.\n"
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ\n- Τομέας Ένα\n"
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ\n- επάγγελμα άλφα\n"
        "Τελικός έλεγχος: ολοκληρώθηκε.\n"
    )
    client_bytes = build_orientation_client_docx("Τίτλος", "Test", client)
    audit_bytes = build_orientation_audit_docx("Τεχνικό Δελτίο", "Test", audit)
    import io
    client_rt = docx_text(io.BytesIO(client_bytes))
    audit_rt = docx_text(io.BytesIO(audit_bytes))
    result = validate_orientation(
        CHART, client_rt, {"Όνομα": "Test"},
        presentation_mode="Απλή και πρακτική", audit_text=audit_rt, format_issues=[],
    )
    assert not result.ok
    assert any("Εντελώς μη εγκεκριμένο επάγγελμα" in line and "δεν έχει εγκριθεί" in line for line in result.details_lines())
