"""v19.3 -- Συνδυασμοί πλατιών όψεων με κοινό σημείο (Κανόνας 10, εξαίρεση).

Αφορμή (πραγματική εκτέλεση): το μοντέλο απέρριψε την όψη Ήλιος–Πλούτωνας με
«χωρίς δεύτερη πλατιά όψη με κοινό σημείο», ενώ υπήρχε η Ερμής–Πλούτωνας·
χάθηκε έτσι ένα ολόκληρο ταλέντο και ο validator δεν το έπιασε.
"""
from core.astrology import wide_aspect_clusters
from core.models import Aspect, Chart, Point
from core.prompts import build_orientation_source
from core.reference_loader import load_orientation_command
from core.validator import validate_orientation
from tests.test_docx_round_trip import _build_client_text

W = "Πλατιά αλλά έγκυρη"
CHART = Chart(
    name="Test", date="", time="", place="", house_system="Placidus",
    points=[
        Point("A", "Ήλιος", "Υδροχόος", 21, 0, 0, 321.0, house=3),
        Point("C", "Ερμής", "Υδροχόος", 3, 0, 0, 303.0, house=2),
        Point("J", "Πλούτωνας", "Ζυγός", 26, 0, 0, 206.0, house=11),
        Point("I", "Ποσειδώνας", "Τοξότης", 26, 0, 0, 266.0, house=1),
        Point("G", "Κρόνος", "Ζυγός", 22, 0, 0, 202.0, house=11),
    ],
    cusps=[],
    aspects=[
        Aspect("Ήλιος", "Κρόνος", "Τρίγωνο", 0.25, "0°14′", "Στενή/ισχυρή", "test"),
        Aspect("Ήλιος", "Πλούτωνας", "Τρίγωνο", 4.97, "4°58′", W, "test"),
        Aspect("Ερμής", "Πλούτωνας", "Τετράγωνο", 6.37, "6°22′", W, "test"),
        Aspect("Κρόνος", "Ποσειδώνας", "Εξάγωνο", 4.3, "4°18′", W, "test"),   # χωρίς προσωπικό -> δεν μετρά
        Aspect("Κρόνος", "Πλούτωνας", "Σύνοδος", 4.73, "4°44′", W, "test"),   # χωρίς προσωπικό -> δεν μετρά
    ],
    warnings=[],
)
CLUSTER_USED = ("Κοινό σημείο: Πλούτωνας | Όψεις: Ήλιος–Πλούτωνας, Ερμής–Πλούτωνας | "
                "Απόφαση: ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 2»")


def _audit(cluster=CLUSTER_USED, sun_pluto="ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 2» ως δείκτης",
           talent2=None):
    talent2 = talent2 or [
        "Δείκτης 1: Τύπος: Όψη | Σημείο 1: Ήλιος | Όψη: Τρίγωνο | Σημείο 2: Πλούτωνας | Orb: 4°58′ | Βαρύτητα: Πλατιά αλλά έγκυρη",
        "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Ερμής | Όψη: Τετράγωνο | Σημείο 2: Πλούτωνας | Orb: 6°22′ | Βαρύτητα: Πλατιά αλλά έγκυρη",
    ]
    lines = [
        "ΕΣΩΤΕΡΙΚΟ ΤΕΧΝΙΚΟ ΔΕΛΤΙΟ ΕΛΕΓΧΟΥ",
        "ΤΑΛΕΝΤΟ: Ταλέντο 1",
        "Δείκτης 1: Τύπος: Θέση | Σημείο: Ήλιος | Ζώδιο: Υδροχόος | Οίκος: 3",
        "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Ήλιος | Όψη: Τρίγωνο | Σημείο 2: Κρόνος | Orb: 0°14′ | Βαρύτητα: Στενή/ισχυρή",
        "ΤΑΛΕΝΤΟ: Ταλέντο 2", *talent2,
        "Ιεράρχηση βαρύτητας: Στενή/ισχυρή → Κανονική → Πλατιά αλλά έγκυρη → Πολύ πλατιά/δευτερεύουσα.",
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ", "Τομέας 1", "Τομέας 2",
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ", "επάγγελμα 1α", "επάγγελμα 1β", "επάγγελμα 2α", "επάγγελμα 2β",
        "Παράρτημα Επιβεβαιωμένων Όψεων",
        "Ήλιος–Κρόνος | Τρίγωνο | orb 0°14′ | Στενή/ισχυρή | ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 1» ως δείκτης",
        f"Ήλιος–Πλούτωνας | Τρίγωνο | orb 4°58′ | Πλατιά αλλά έγκυρη | {sun_pluto}",
        "Παράρτημα Κάλυψης Θέσεων",
        "Σημείο: Ήλιος | Ζώδιο: Υδροχόος | Οίκος: 3 | Απόφαση: ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 1»",
        "Σημείο: Ερμής | Ζώδιο: Υδροχόος | Οίκος: 2 | Απόφαση: ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 2»",
        "Σημείο: Πλούτωνας | Ζώδιο: Ζυγός | Οίκος: 11 | Απόφαση: ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 2»",
        "Σημείο: Ποσειδώνας | Ζώδιο: Τοξότης | Οίκος: 1 | Απόφαση: ΕΞΑΙΡΕΙΤΑΙ — γενεακός πλανήτης χωρίς προσωπική σύνδεση",
        "Σημείο: Κρόνος | Ζώδιο: Ζυγός | Οίκος: 11 | Απόφαση: ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 1»",
        cluster,
        "Παράρτημα Κάλυψης Τομέων",
        "Τομέας: ΝΕΟΣ | Απόφαση: ΕΠΙΛΕΓΕΤΑΙ ως «Τομέας 1» — ταλέντα «Ταλέντο 1», «Ταλέντο 2»",
        "Τομέας: ΝΕΟΣ | Απόφαση: ΕΠΙΛΕΓΕΤΑΙ ως «Τομέας 2» — ταλέντα «Ταλέντο 1», «Ταλέντο 2»",
        "Τελικός έλεγχος: ολοκληρώθηκε.",
    ]
    return "\n".join(l for l in lines if l)


def _errors(audit):
    r = validate_orientation(CHART, _build_client_text(2), {"Όνομα": "Test"}, presentation_mode="Απλή και πρακτική",
                             audit_text=audit, format_issues=[], sector_catalogue=[])
    return r, "\n".join(r.details_lines())


def test_clusters_found_only_with_personal_planet_or_angle():
    assert wide_aspect_clusters(CHART.aspects) == [("Πλούτωνας", ["Ήλιος–Πλούτωνας", "Ερμής–Πλούτωνας"])]


def test_nodes_and_non_wide_aspects_never_form_clusters():
    aspects = [
        Aspect("Ήλιος", "Βόρειος Δεσμός", "Τετράγωνο", 5.0, "5°00′", W, "t"),
        Aspect("Ερμής", "Βόρειος Δεσμός", "Τετράγωνο", 5.0, "5°00′", W, "t"),
        Aspect("Ήλιος", "Κρόνος", "Τρίγωνο", 3.0, "3°00′", "Κανονική", "t"),
        Aspect("Ερμής", "Κρόνος", "Τρίγωνο", 7.5, "7°30′", "Πολύ πλατιά/δευτερεύουσα", "t"),
    ]
    assert wide_aspect_clusters(aspects) == []


def test_source_data_lists_clusters_for_the_model():
    src = build_orientation_source(CHART)
    assert "ΣΥΝΔΥΑΣΜΟΙ ΠΛΑΤΙΩΝ ΟΨΕΩΝ ΜΕ ΚΟΙΝΟ ΣΗΜΕΙΟ" in src
    assert "- Κοινό σημείο Πλούτωνας: Ήλιος–Πλούτωνας, Ερμής–Πλούτωνας" in src


def test_used_cluster_passes():
    r, errors = _errors(_audit())
    assert r.ok, errors


def test_missing_cluster_line_is_rejected():
    _, errors = _errors(_audit(cluster=""))
    assert "κοινό σημείο «Πλούτωνας»" in errors and "λείπει γραμμή «Κοινό σημείο:»" in errors


def test_the_real_false_reason_is_rejected_on_the_aspect_line():
    """Η ακριβής φράση της πραγματικής εκτέλεσης."""
    false = ("ΕΞΑΙΡΕΙΤΑΙ — πλατιά όψη χωρίς δεύτερη πλατιά όψη με κοινό σημείο για αυτόνομο ταλέντο· "
             "μόνο απόχρωση βάθους στην έρευνα")
    talent2 = ["Δείκτης 1: Τύπος: Θέση | Σημείο: Ερμής | Ζώδιο: Υδροχόος | Οίκος: 2",
               "Δείκτης 2: Τύπος: Θέση | Σημείο: Πλούτωνας | Ζώδιο: Ζυγός | Οίκος: 11"]
    cluster = ("Κοινό σημείο: Πλούτωνας | Όψεις: Ήλιος–Πλούτωνας, Ερμής–Πλούτωνας | "
               "Απόφαση: ΕΞΑΙΡΕΙΤΑΙ — το θέμα του βάθους καλύπτεται ήδη από άλλο ταλέντο")
    _, errors = _errors(_audit(cluster=cluster, sun_pluto=false, talent2=talent2))
    assert "Η εξαίρεση της όψης Ήλιος–Πλούτωνας" in errors and "Ερμής–Πλούτωνας" in errors


def test_false_reason_on_the_cluster_line_is_rejected():
    cluster = ("Κοινό σημείο: Πλούτωνας | Όψεις: Ήλιος–Πλούτωνας, Ερμής–Πλούτωνας | "
               "Απόφαση: ΕΞΑΙΡΕΙΤΑΙ — δεν υπάρχει κοινό σημείο ανάμεσά τους")
    _, errors = _errors(_audit(cluster=cluster))
    assert "το λογισμικό βρήκε αυτόν τον συνδυασμό" in errors


def test_true_exclusion_reason_is_accepted():
    talent2 = ["Δείκτης 1: Τύπος: Θέση | Σημείο: Ερμής | Ζώδιο: Υδροχόος | Οίκος: 2",
               "Δείκτης 2: Τύπος: Θέση | Σημείο: Πλούτωνας | Ζώδιο: Ζυγός | Οίκος: 11"]
    cluster = ("Κοινό σημείο: Πλούτωνας | Όψεις: Ήλιος–Πλούτωνας, Ερμής–Πλούτωνας | "
               "Απόφαση: ΕΞΑΙΡΕΙΤΑΙ — το θέμα του βάθους ενοποιείται με άλλο ταλέντο που ήδη το καλύπτει")
    aspect = "ΕΞΑΙΡΕΙΤΑΙ — λειτουργεί μόνο ως υποστηρικτική απόχρωση"
    r, errors = _errors(_audit(cluster=cluster, sun_pluto=aspect, talent2=talent2))
    assert r.ok, errors


def test_claimed_cluster_usage_needs_one_of_its_aspects_in_the_talent():
    cluster = CLUSTER_USED.replace("«Ταλέντο 2»", "«Ταλέντο 1»")
    _, errors = _errors(_audit(cluster=cluster))
    assert "καμία από αυτές τις όψεις δεν είναι δείκτης" in errors


def test_invented_cluster_is_rejected():
    extra = CLUSTER_USED + "\nΚοινό σημείο: Ήλιος | Όψεις: Ήλιος–Πλούτωνας | Απόφαση: ΕΞΑΙΡΕΙΤΑΙ — μία μόνο όψη"
    _, errors = _errors(_audit(cluster=extra))
    assert "δεν υπάρχει στους συνδυασμούς που υπολόγισε το λογισμικό" in errors


def test_binding_command_explains_clusters_and_chiron():
    cmd = load_orientation_command()
    assert "ΣΥΝΔΥΑΣΜΟΙ ΠΛΑΤΙΩΝ ΟΨΕΩΝ ΜΕ ΚΟΙΝΟ ΣΗΜΕΙΟ" in cmd
    assert "Κοινό σημείο: Πλούτωνας | Όψεις:" in cmd
    assert "ο Χείρωνας δεν υποβαθμίζεται" in cmd



def test_cluster_aspects_must_match_the_software():
    bad = CLUSTER_USED.replace("Όψεις: Ήλιος–Πλούτωνας, Ερμής–Πλούτωνας", "Όψεις: Ήλιος–Πλούτωνας")
    _, errors = _errors(_audit(cluster=bad))
    assert "το πεδίο «Όψεις:» πρέπει να γράφει ακριβώς" in errors


def test_duplicate_cluster_lines_are_rejected():
    extra = CLUSTER_USED + "\n" + CLUSTER_USED.replace("ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 2»", "ΕΞΑΙΡΕΙΤΑΙ — δεν ταιριάζει")
    _, errors = _errors(_audit(cluster=extra))
    assert "εμφανίζεται 2 φορές" in errors



def test_repeated_field_inside_one_cluster_line_is_rejected():
    bad = CLUSTER_USED.replace("Όψεις: Ήλιος–Πλούτωνας, Ερμής–Πλούτωνας",
                               "Όψεις: Ήλιος–Σελήνη | Όψεις: Ήλιος–Πλούτωνας, Ερμής–Πλούτωνας")
    _, errors = _errors(_audit(cluster=bad))
    assert "επαναλαμβάνει το πεδίο «Όψεις»" in errors
