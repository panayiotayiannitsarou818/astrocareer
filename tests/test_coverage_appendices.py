"""v19 -- Παραρτήματα κάλυψης θέσεων/συγκεντρώσεων και τομέων.

Αφορμή: σε πραγματική ανάλυση (α) χάθηκε ολόκληρος ο τομέας «Νομική και
δικαιοσύνη», επειδή τίποτα δεν υποχρέωνε ρητή απόφαση για κάθε τομέα του
καταλόγου, και (β) υποτιμήθηκε η «αίσθηση του δίκαιου», παρότι τρεις πλανήτες
ήταν στον Ζυγό -- οι θέσεις και οι συγκεντρώσεις δεν είχαν έλεγχο κάλυψης.
Εδώ ΔΕΝ χρησιμοποιείται το tests/coverage_helper.py: τα παραρτήματα γράφονται
ρητά, όπως θα τα έγραφε το μοντέλο.
"""
import pytest

from core.astrology import planet_concentrations
from core.catalogue import sector_catalogue
from core.models import Aspect, Chart, Point
from core.prompts import build_orientation_source
from core.reference_loader import load_orientation_command
from core.validator import validate_orientation
from tests.test_docx_round_trip import _build_client_text

CHART = Chart(
    name="Test", date="", time="", place="", house_system="Placidus",
    points=[
        Point("A", "Ήλιος", "Κριός", 5, 0, 0, 5.0, house=1),
        Point("E", "Άρης", "Ζυγός", 10, 0, 0, 190.0, house=7),
        Point("G", "Κρόνος", "Ζυγός", 11, 0, 0, 191.0, house=7),
        Point("J", "Πλούτωνας", "Ζυγός", 20, 0, 0, 200.0, house=7),
        Point("N", "Χείρωνας", "Ταύρος", 3, 0, 0, 33.0, house=2),
    ],
    cusps=[],
    aspects=[Aspect("Άρης", "Κρόνος", "Σύνοδος", 1.0, "1°00′", "Στενή/ισχυρή", "test")],
    warnings=[],
)
CATALOGUE = ["Νομική και δικαιοσύνη", "Εκπαίδευση και μάθηση"]

POSITIONS = {
    "Ήλιος": "Σημείο: Ήλιος | Ζώδιο: Κριός | Οίκος: 1 | Απόφαση: ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 2»",
    "Άρης": "Σημείο: Άρης | Ζώδιο: Ζυγός | Οίκος: 7 | Απόφαση: ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 1»",
    "Κρόνος": "Σημείο: Κρόνος | Ζώδιο: Ζυγός | Οίκος: 7 | Απόφαση: ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 2»",
    "Πλούτωνας": "Σημείο: Πλούτωνας | Ζώδιο: Ζυγός | Οίκος: 7 | Απόφαση: ΕΞΑΙΡΕΙΤΑΙ — γενεακός πλανήτης χωρίς όψη με προσωπικό πλανήτη",
    "Χείρωνας": "Σημείο: Χείρωνας | Ζώδιο: Ταύρος | Οίκος: 2 | Απόφαση: ΕΞΑΙΡΕΙΤΑΙ — καμία επιβεβαιωμένη όψη με προσωπικό πλανήτη ή γωνία",
}
CONCENTRATIONS = {
    "Ζώδιο Ζυγός": "Συγκέντρωση: Ζώδιο Ζυγός | Σημεία: Άρης, Κρόνος, Πλούτωνας | Απόφαση: ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 1»",
    "Οίκος 7": "Συγκέντρωση: Οίκος 7 | Σημεία: Άρης, Κρόνος, Πλούτωνας | Απόφαση: ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 1»",
}
SECTORS = [
    "Τομέας: Νομική και δικαιοσύνη | Απόφαση: ΕΠΙΛΕΓΕΤΑΙ ως «Τομέας 1» — ταλέντα «Ταλέντο 1», «Ταλέντο 2»",
    "Τομέας: Εκπαίδευση και μάθηση | Απόφαση: ΑΠΟΡΡΙΠΤΕΤΑΙ — κανένα εγκεκριμένο ταλέντο δεν αφορά διδασκαλία",
    "Τομέας: ΝΕΟΣ | Απόφαση: ΕΠΙΛΕΓΕΤΑΙ ως «Τομέας 2» — ταλέντα «Ταλέντο 1», «Ταλέντο 2»· δεν καλύπτεται από τον κατάλογο",
]


def _audit(positions=None, concentrations=None, sectors=None, drop=()):
    positions = dict(POSITIONS, **(positions or {}))
    concentrations = dict(CONCENTRATIONS, **(concentrations or {}))
    sectors = SECTORS if sectors is None else sectors
    pos = "\n".join(v for k, v in positions.items() if k not in drop and v)
    conc = "\n".join(v for k, v in concentrations.items() if k not in drop and v)
    sec = "\n".join(s for s in sectors if s)
    parts = [
        "ΕΣΩΤΕΡΙΚΟ ΤΕΧΝΙΚΟ ΔΕΛΤΙΟ ΕΛΕΓΧΟΥ",
        "ΤΑΛΕΝΤΟ: Ταλέντο 1",
        "Δείκτης 1: Τύπος: Θέση | Σημείο: Άρης | Ζώδιο: Ζυγός | Οίκος: 7",
        "Δείκτης 2: Τύπος: Όψη | Σημείο 1: Άρης | Όψη: Σύνοδος | Σημείο 2: Κρόνος | Orb: 1°00′ | Βαρύτητα: Στενή/ισχυρή",
        "ΤΑΛΕΝΤΟ: Ταλέντο 2",
        "Δείκτης 1: Τύπος: Θέση | Σημείο: Ήλιος | Ζώδιο: Κριός | Οίκος: 1",
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Ζυγός | Οίκος: 7",
        "Ιεράρχηση βαρύτητας: Στενή/ισχυρή → Κανονική → Πλατιά αλλά έγκυρη → Πολύ πλατιά/δευτερεύουσα.",
        "ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ", "Τομέας 1", "Τομέας 2",
        "ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ", "επάγγελμα 1α", "επάγγελμα 1β", "επάγγελμα 2α", "επάγγελμα 2β",
        "Παράρτημα Επιβεβαιωμένων Όψεων",
        "Άρης–Κρόνος | Σύνοδος | orb 1°00′ | Στενή/ισχυρή | ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 1» ως δείκτης",
        "Παράρτημα Κάλυψης Θέσεων", pos, conc,
        "Παράρτημα Κάλυψης Τομέων", sec,
        "Τελικός έλεγχος: ολοκληρώθηκε.",
    ]
    return "\n".join(p for p in parts if p)


BRIEF = "Άλλες κατευθύνσεις που μπορείς επίσης να εξερευνήσεις: Εκπαίδευση και μάθηση."


def _client(brief=None):
    text = _build_client_text(2)
    if brief:
        text = text.replace("Τελική σύνθεση\n", brief + "\n\nΤελική σύνθεση\n", 1)
    return text


def _check(audit, brief=None):
    return validate_orientation(
        CHART, _client(brief), {"Όνομα": "Test"}, presentation_mode="Απλή και πρακτική",
        audit_text=audit, format_issues=[], sector_catalogue=CATALOGUE,
    )


def _errors(audit, brief=None):
    return "\n".join(_check(audit, brief).details_lines())


# ------------------------------------------------------------ υπολογισμός Python
def test_concentrations_found_for_sign_and_house():
    assert planet_concentrations(CHART.points) == [
        ("Ζώδιο Ζυγός", ["Άρης", "Κρόνος", "Πλούτωνας"]),
        ("Οίκος 7", ["Άρης", "Κρόνος", "Πλούτωνας"]),
    ]


def test_concentrations_ignore_chiron_nodes_and_two_planet_groups():
    pts = [
        Point("A", "Ήλιος", "Ταύρος", 1, 0, 0, 31.0, house=2),
        Point("D", "Αφροδίτη", "Ταύρος", 2, 0, 0, 32.0, house=2),
        Point("N", "Χείρωνας", "Ταύρος", 3, 0, 0, 33.0, house=2),
        Point("L", "Βόρειος Δεσμός", "Ταύρος", 4, 0, 0, 34.0, house=2, kind="node"),
    ]
    assert planet_concentrations(pts) == []


def test_source_data_lists_concentrations_for_the_model():
    src = build_orientation_source(CHART)
    assert "ΣΥΓΚΕΝΤΡΩΣΕΙΣ ΠΛΑΝΗΤΩΝ" in src
    assert "- Ζώδιο Ζυγός: Άρης, Κρόνος, Πλούτωνας" in src
    assert "- Οίκος 7: Άρης, Κρόνος, Πλούτωνας" in src


def test_real_catalogue_is_read_from_the_binding_command():
    cat = sector_catalogue()
    assert len(cat) == 38
    assert "Νομική και δικαιοσύνη" in cat
    assert "Υγεία και θεραπευτικές υπηρεσίες" in cat  # χωρίς το «(*)»
    assert not any("(*)" in c for c in cat)


def test_binding_command_v13_contains_the_new_rules_in_order():
    cmd = load_orientation_command()
    assert "Έκδοση v13" in cmd
    for needle in ("Συγκεντρώσεις:", "Υποχρεωτικός έλεγχος κάλυψης θέσεων",
                   "Υποχρεωτικός έλεγχος κάλυψης τομέων", "16.3 Γραμμές του Παραρτήματος Κάλυψης Θέσεων",
                   "16.4 Γραμμές του Παραρτήματος Κάλυψης Τομέων"):
        assert needle in cmd, needle
    order = [cmd.index(x) for x in ("12. Παράρτημα Επιβεβαιωμένων Όψεων", "13. Παράρτημα Κάλυψης Θέσεων",
                                     "14. Παράρτημα Κάλυψης Τομέων", "15. Τελικός έλεγχος")]
    assert order == sorted(order)


# ------------------------------------------------------------ έγκυρο σενάριο
def test_complete_appendices_pass():
    result = _check(_audit())
    assert result.ok, result.details_lines()


# ------------------------------------------------------------ θέσεις
def test_missing_positions_appendix_is_rejected():
    audit = _audit().replace("Παράρτημα Κάλυψης Θέσεων", "Κάτι άλλο")
    assert "Λείπει το «Παράρτημα Κάλυψης Θέσεων»" in _errors(audit)


def test_missing_point_line_is_rejected():
    assert "Θέση «Χείρωνας»: λείπει γραμμή" in _errors(_audit(drop=("Χείρωνας",)))


def test_wrong_sign_in_position_line_is_rejected():
    bad = POSITIONS["Χείρωνας"].replace("Ταύρος", "Κριός")
    assert "το ζώδιο πρέπει να είναι «Ταύρος»" in _errors(_audit(positions={"Χείρωνας": bad}))


def test_wrong_house_in_position_line_is_rejected():
    bad = POSITIONS["Χείρωνας"].replace("Οίκος: 2", "Οίκος: 9")
    assert "ο Οίκος πρέπει να είναι 2" in _errors(_audit(positions={"Χείρωνας": bad}))


def test_exclusion_without_reason_is_rejected():
    bad = "Σημείο: Χείρωνας | Ζώδιο: Ταύρος | Οίκος: 2 | Απόφαση: ΕΞΑΙΡΕΙΤΑΙ"
    assert "χρειάζεται ρητή αιτιολόγηση" in _errors(_audit(positions={"Χείρωνας": bad}))


def test_both_decision_words_is_rejected():
    bad = POSITIONS["Χείρωνας"].replace("ΕΞΑΙΡΕΙΤΑΙ", "ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ ή ΕΞΑΙΡΕΙΤΑΙ")
    assert "ΑΚΡΙΒΩΣ μία" in _errors(_audit(positions={"Χείρωνας": bad}))


def test_position_indicator_cannot_be_declared_excluded():
    bad = "Σημείο: Ήλιος | Ζώδιο: Κριός | Οίκος: 1 | Απόφαση: ΕΞΑΙΡΕΙΤΑΙ — δεν θεωρήθηκε σημαντικός"
    assert "χρησιμοποιείται ως δείκτης Θέσης" in _errors(_audit(positions={"Ήλιος": bad}))


def test_claimed_usage_must_match_the_named_talent_block():
    bad = POSITIONS["Ήλιος"].replace("«Ταλέντο 2»", "«Ταλέντο 1»")
    assert "δεν εμφανίζεται σε κανέναν δείκτη αυτού του μπλοκ" in _errors(_audit(positions={"Ήλιος": bad}))


def test_claimed_usage_must_name_an_approved_talent():
    bad = POSITIONS["Ήλιος"].replace("«Ταλέντο 2»", "«Φανταστικό ταλέντο»")
    assert "εγκεκριμένο ταλέντο" in _errors(_audit(positions={"Ήλιος": bad}))


def test_duplicate_point_line_is_rejected():
    audit = _audit().replace(POSITIONS["Χείρωνας"], POSITIONS["Χείρωνας"] + "\n" + POSITIONS["Χείρωνας"])
    assert "εμφανίζεται 2 φορές" in _errors(audit)


# ------------------------------------------------------------ συγκεντρώσεις
def test_missing_concentration_line_is_rejected():
    """Το ακριβές σενάριο: τρεις πλανήτες στον Ζυγό χωρίς καμία απόφαση."""
    assert "Συγκέντρωση «Ζώδιο Ζυγός»" in _errors(_audit(drop=("Ζώδιο Ζυγός",)))


def test_concentration_exclusion_with_reason_is_accepted():
    ok = "Συγκέντρωση: Οίκος 7 | Σημεία: Άρης, Κρόνος, Πλούτωνας | Απόφαση: ΕΞΑΙΡΕΙΤΑΙ — το θέμα καλύπτεται ήδη από τη συγκέντρωση στο ζώδιο"
    result = _check(_audit(concentrations={"Οίκος 7": ok}))
    assert result.ok, result.details_lines()


def test_concentration_usage_needs_one_of_its_planets_in_the_talent():
    bad = CONCENTRATIONS["Ζώδιο Ζυγός"].replace("«Ταλέντο 1»", "«Ταλέντο 2»").replace("Άρης, ", "")
    # Ταλέντο 2 έχει τον Κρόνο -> επιτρέπεται· αλλάζουμε σε ταλέντο χωρίς κανέναν από τους πλανήτες
    audit = _audit(concentrations={"Ζώδιο Ζυγός": bad}).replace(
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Κρόνος | Ζώδιο: Ζυγός | Οίκος: 7",
        "Δείκτης 2: Τύπος: Θέση | Σημείο: Χείρωνας | Ζώδιο: Ταύρος | Οίκος: 2",
    ).replace(POSITIONS["Κρόνος"], POSITIONS["Κρόνος"].replace("«Ταλέντο 2»", "«Ταλέντο 1»")).replace(
        POSITIONS["Χείρωνας"], "Σημείο: Χείρωνας | Ζώδιο: Ταύρος | Οίκος: 2 | Απόφαση: ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ — Ταλέντο «Ταλέντο 2»")
    assert "κανένας από αυτούς τους πλανήτες" in _errors(audit)


def test_invented_concentration_is_rejected():
    extra = "Συγκέντρωση: Ζώδιο Κριός | Σημεία: Ήλιος | Απόφαση: ΕΞΑΙΡΕΙΤΑΙ — μόνο ένας πλανήτης"
    audit = _audit().replace(CONCENTRATIONS["Οίκος 7"], CONCENTRATIONS["Οίκος 7"] + "\n" + extra)
    assert "δεν υπάρχει στις συγκεντρώσεις που υπολόγισε το λογισμικό" in _errors(audit)


# ------------------------------------------------------------ τομείς
def test_missing_sectors_appendix_is_rejected():
    audit = _audit().replace("Παράρτημα Κάλυψης Τομέων", "Κάτι άλλο")
    assert "Λείπει το «Παράρτημα Κάλυψης Τομέων»" in _errors(audit)


def test_forgotten_catalogue_sector_is_rejected():
    """Το ακριβές σενάριο της αφορμής: ο τομέας «Νομική» απλώς δεν εξετάστηκε."""
    sectors = [s for s in SECTORS if "Νομική" not in s] + [
        "Τομέας: ΝΕΟΣ | Απόφαση: ΕΠΙΛΕΓΕΤΑΙ ως «Τομέας 1» — ταλέντα «Ταλέντο 1», «Ταλέντο 2»· νέος"]
    assert "Τομέας καταλόγου «Νομική και δικαιοσύνη»: λείπει γραμμή" in _errors(_audit(sectors=sectors))


def test_rejection_without_reason_is_rejected():
    sectors = [SECTORS[0], "Τομέας: Εκπαίδευση και μάθηση | Απόφαση: ΑΠΟΡΡΙΠΤΕΤΑΙ", SECTORS[2]]
    assert "χρειάζεται ρητή αιτιολόγηση" in _errors(_audit(sectors=sectors))


def test_selected_title_must_be_an_approved_field():
    sectors = [SECTORS[0].replace("«Τομέας 1»", "«Τομέας 9»"), SECTORS[1], SECTORS[2]]
    errors = _errors(_audit(sectors=sectors))
    assert "δεν υπάρχει στους ΕΓΚΕΚΡΙΜΕΝΟΥΣ" in errors
    assert "Ο εγκεκριμένος τομέας «Τομέας 1» δεν προκύπτει" in errors


def test_selected_sector_must_name_an_approved_talent():
    sectors = [SECTORS[0].replace("«Ταλέντο 1», «Ταλέντο 2»", "«Άγνωστο»"), SECTORS[1], SECTORS[2]]
    assert "τουλάχιστον ένα εγκεκριμένο ταλέντο" in _errors(_audit(sectors=sectors))


def test_unknown_sector_name_is_rejected():
    sectors = SECTORS + ["Τομέας: Αστροναυτική | Απόφαση: ΑΠΟΡΡΙΠΤΕΤΑΙ — δεν σχετίζεται"]
    assert "δεν υπάρχει στον κατάλογο" in _errors(_audit(sectors=sectors))


def test_two_catalogue_sectors_may_merge_into_one_title():
    cat = CATALOGUE + ["Δημόσια διοίκηση"]
    audit = _audit(sectors=SECTORS + [
        "Τομέας: Δημόσια διοίκηση | Απόφαση: ΕΠΙΛΕΓΕΤΑΙ ως «Τομέας 1» — ταλέντα «Ταλέντο 1», «Ταλέντο 2»· ενοποιείται"])
    result = validate_orientation(
        CHART, _build_client_text(2), {"Όνομα": "Test"}, presentation_mode="Απλή και πρακτική",
        audit_text=audit, format_issues=[], sector_catalogue=cat,
    )
    assert result.ok, result.details_lines()


def test_english_instructions_list_the_new_greek_labels():
    from core.pipeline import reinforcement_instructions
    text = reinforcement_instructions("Test", "en")
    for label in ("Παράρτημα Κάλυψης Θέσεων", "Παράρτημα Κάλυψης Τομέων", "Τομέας:", "ΕΠΙΛΕΓΕΤΑΙ ως"):
        assert label in text


# ------------------------------------------------------------ v19.1: κύριοι τομείς / σύντομη αναφορά
BRIEF_SECTOR = ("Τομέας: Εκπαίδευση και μάθηση | Απόφαση: ΣΥΝΤΟΜΗ ΑΝΑΦΟΡΑ ως «Εκπαίδευση και μάθηση» "
                "— ταλέντο «Ταλέντο 2»")


def test_brief_mention_line_with_matching_decision_passes():
    result = _check(_audit(sectors=[SECTORS[0], BRIEF_SECTOR, SECTORS[2]]), brief=BRIEF)
    assert result.ok, result.details_lines()


def test_brief_line_is_not_misread_as_an_unapproved_main_field():
    errors = _errors(_audit(sectors=[SECTORS[0], BRIEF_SECTOR, SECTORS[2]]), brief=BRIEF)
    assert "δεν έχει εγκριθεί" not in errors


def test_brief_decision_missing_from_client_text_is_rejected():
    errors = _errors(_audit(sectors=[SECTORS[0], BRIEF_SECTOR, SECTORS[2]]))
    assert "λείπει από τη γραμμή «Άλλες κατευθύνσεις" in errors


def test_brief_name_in_client_without_decision_is_rejected():
    errors = _errors(_audit(), brief=BRIEF)
    assert "δεν έχει απόφαση «ΣΥΝΤΟΜΗ ΑΝΑΦΟΡΑ»" in errors


def test_brief_line_twice_is_rejected():
    two = BRIEF + "\n" + BRIEF
    errors = _errors(_audit(sectors=[SECTORS[0], BRIEF_SECTOR, SECTORS[2]]), brief=two)
    assert "μία μόνο φορά" in errors


def test_main_field_with_single_talent_needs_guarantee():
    one = SECTORS[2].replace("«Ταλέντο 1», «Ταλέντο 2»", "«Ταλέντο 2»")
    assert "ως «εγγύηση»" in _errors(_audit(sectors=[SECTORS[0], SECTORS[1], one]))


def test_main_field_with_single_talent_and_guarantee_passes():
    one = SECTORS[2].replace("«Ταλέντο 1», «Ταλέντο 2»·", "«Ταλέντο 2»· εγγύηση για το ταλέντο·")
    result = _check(_audit(sectors=[SECTORS[0], SECTORS[1], one]))
    assert result.ok, result.details_lines()


def test_talent_without_any_main_field_is_rejected():
    """Η εγγύηση της ιδιοκτήτριας: κανένα ταλέντο δεν μένει χωρίς κύριο τομέα."""
    a = SECTORS[0].replace("«Ταλέντο 1», «Ταλέντο 2»", "«Ταλέντο 1»· εγγύηση")
    b = SECTORS[2].replace("«Ταλέντο 1», «Ταλέντο 2»", "«Ταλέντο 1»· εγγύηση")
    assert "Το ταλέντο «Ταλέντο 2» δεν συνδέεται με κανέναν κύριο τομέα" in _errors(_audit(sectors=[a, SECTORS[1], b]))


def test_same_title_cannot_be_main_and_brief():
    brief = "Τομέας: Εκπαίδευση και μάθηση | Απόφαση: ΣΥΝΤΟΜΗ ΑΝΑΦΟΡΑ ως «Τομέας 1» — ταλέντο «Ταλέντο 2»"
    errors = _errors(_audit(sectors=[SECTORS[0], brief, SECTORS[2]]),
                     brief="Άλλες κατευθύνσεις που μπορείς επίσης να εξερευνήσεις: Τομέας 1.")
    assert "ταυτόχρονα κύριος τομέας και σύντομη αναφορά" in errors


def test_english_brief_label_is_recognised():
    from core.validator import _client_brief_fields
    names, count = _client_brief_fields(
        "Career Fields to Explore\nOther directions you may also explore: Law and justice, Education.\nFinal Synthesis\n")
    assert count == 1 and names == ["Law and justice", "Education"]


def test_binding_command_describes_brief_mentions_and_guarantee():
    cmd = load_orientation_command()
    for needle in ("Άλλες κατευθύνσεις που μπορείς επίσης να εξερευνήσεις:", "ΣΥΝΤΟΜΗ ΑΝΑΦΟΡΑ ως",
                   "Εγγύηση για τα ταλέντα", "η ποιότητα της εξήγησης δεν θυσιάζεται"):
        assert needle in cmd, needle


def test_command_examples_pass_the_validator_format():
    """Τα παραδείγματα 16.4 της εντολής πρέπει να είναι γραμμές που ο validator διαβάζει σωστά."""
    from core.validator import _key_fields
    cmd = load_orientation_command()
    examples = [l for l in cmd.split("\n") if l.startswith("Τομέας: ")]
    assert len(examples) >= 4
    for line in examples:
        f = _key_fields(line)
        assert "τομεας" in f and "αποφαση" in f, line


def test_brief_line_survives_the_real_docx_round_trip():
    import io
    from core.docx_builder import build_orientation_audit_docx, build_orientation_client_docx
    from core.reference_loader import docx_text
    client = _client("**Άλλες κατευθύνσεις που μπορείς επίσης να εξερευνήσεις:** Εκπαίδευση και μάθηση.")
    audit = _audit(sectors=[SECTORS[0], BRIEF_SECTOR, SECTORS[2]])
    c = docx_text(io.BytesIO(build_orientation_client_docx("Τίτλος", "Test", client)))
    a = docx_text(io.BytesIO(build_orientation_audit_docx("Δελτίο", "Test", audit)))
    result = validate_orientation(CHART, c, {"Όνομα": "Test"}, presentation_mode="Απλή και πρακτική",
                                  audit_text=a, format_issues=[], sector_catalogue=CATALOGUE)
    assert result.ok, result.details_lines()



@pytest.mark.parametrize("value", ["Οίκος:", "Οίκος: λάθος", "Οίκος: —"])
def test_empty_or_non_numeric_house_is_rejected(value):
    """v19.5 (εξωτερικός έλεγχος): κενό/μη αριθμητικό «Οίκος:» εγκρινόταν σιωπηλά."""
    bad = POSITIONS["Χείρωνας"].replace("Οίκος: 2", value)
    assert "ο Οίκος πρέπει να είναι 2" in _errors(_audit(positions={"Χείρωνας": bad}))



@pytest.mark.parametrize("members", ["Σημεία: Ήλιος, Σελήνη", "", "Σημεία: Άρης, Κρόνος"])
def test_concentration_members_must_match_the_software(members):
    """v19.6 (εξωτερικός έλεγχος): λάθος/ελλιπή μέλη εγκρίνονταν."""
    line = CONCENTRATIONS["Ζώδιο Ζυγός"].replace("Σημεία: Άρης, Κρόνος, Πλούτωνας", members).replace("|  |", "|")
    assert "το πεδίο «Σημεία:» πρέπει να γράφει ακριβώς" in _errors(_audit(concentrations={"Ζώδιο Ζυγός": line}))


def test_conflicting_duplicate_concentration_lines_are_rejected():
    """v19.6 (εξωτερικός έλεγχος): ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ + ΕΞΑΙΡΕΙΤΑΙ για την ίδια συγκέντρωση εγκρινόταν."""
    second = "Συγκέντρωση: Ζώδιο Ζυγός | Σημεία: Άρης, Κρόνος, Πλούτωνας | Απόφαση: ΕΞΑΙΡΕΙΤΑΙ — δεν σχετίζεται"
    line = CONCENTRATIONS["Ζώδιο Ζυγός"] + "\n" + second
    assert "εμφανίζεται 2 φορές" in _errors(_audit(concentrations={"Ζώδιο Ζυγός": line}))



def test_repeated_field_inside_one_concentration_line_is_rejected():
    """v19.8 (εξωτερικός έλεγχος): «Σημεία: Ήλιος, Σελήνη | Σημεία: Άρης, …» εγκρινόταν."""
    line = CONCENTRATIONS["Ζώδιο Ζυγός"].replace(
        "Σημεία: Άρης, Κρόνος, Πλούτωνας", "Σημεία: Ήλιος, Σελήνη | Σημεία: Άρης, Κρόνος, Πλούτωνας")
    assert "επαναλαμβάνει το πεδίο «Σημεία»" in _errors(_audit(concentrations={"Ζώδιο Ζυγός": line}))


def test_repeated_field_inside_one_sector_line_is_rejected():
    bad = "Τομέας: Εκπαίδευση και μάθηση | Τομέας: Νομική και δικαιοσύνη | Απόφαση: ΑΠΟΡΡΙΠΤΕΤΑΙ — δεν σχετίζεται"
    assert "επαναλαμβάνει το πεδίο «Τομέας»" in _errors(_audit(sectors=[SECTORS[0], bad, SECTORS[2]]))
