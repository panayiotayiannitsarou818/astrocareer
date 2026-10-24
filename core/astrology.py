from __future__ import annotations
from .models import Aspect, Point

SIGNS = [
    "Κριός",
    "Ταύρος",
    "Δίδυμοι",
    "Καρκίνος",
    "Λέων",
    "Παρθένος",
    "Ζυγός",
    "Σκορπιός",
    "Τοξότης",
    "Αιγόκερως",
    "Υδροχόος",
    "Ιχθύες",
]
SIGN_CODES = dict(zip("abcdefghijkl", SIGNS))
RULERS = {
    "Κριός": ("Άρης", None),
    "Ταύρος": ("Αφροδίτη", None),
    "Δίδυμοι": ("Ερμής", None),
    "Καρκίνος": ("Σελήνη", None),
    "Λέων": ("Ήλιος", None),
    "Παρθένος": ("Ερμής", None),
    "Ζυγός": ("Αφροδίτη", None),
    "Σκορπιός": ("Πλούτωνας", "Άρης"),
    "Τοξότης": ("Δίας", None),
    "Αιγόκερως": ("Κρόνος", None),
    "Υδροχόος": ("Ουρανός", "Κρόνος"),
    "Ιχθύες": ("Ποσειδώνας", "Δίας"),
}
DEGREE_QUALITIES = {
    "Κριός": "πρωτοβουλία, τόλμη και αμεσότητα",
    "Ταύρος": "σταθερότητα, ασφάλεια, αισθησιασμός και πρακτικότητα",
    "Δίδυμοι": "περιέργεια, επικοινωνία και πνευματική ευελιξία",
    "Καρκίνος": "ευαισθησία, προστασία και συναισθηματική μνήμη",
    "Λέων": "δημιουργικότητα, περηφάνια και ανάγκη έκφρασης",
    "Παρθένος": "ανάλυση, ακρίβεια και πρακτική βελτίωση",
    "Ζυγός": "συνεργασία, αρμονία και αισθητική",
    "Σκορπιός": "βάθος, διεισδυτικότητα και μεταμόρφωση",
    "Τοξότης": "αναζήτηση νοήματος, ελευθερία και διεύρυνση",
    "Αιγόκερως": "σοβαρότητα, αυτοέλεγχος, φιλοδοξία και αξιοπιστία",
    "Υδροχόος": "ανεξαρτησία, πρωτοτυπία και συλλογική σκέψη",
    "Ιχθύες": "διαίσθηση, φαντασία και συμπόνια",
}


def absolute(sign: str, degree: int, minute: int, second: int) -> float:
    return SIGNS.index(sign) * 30 + degree + minute / 60 + second / 3600


def angular_distance(a: float, b: float) -> float:
    raw = abs(a - b) % 360
    return min(raw, 360 - raw)


def house_of(value: float, cusps: list[Point]) -> int:
    for i in range(12):
        start, end = cusps[i].absolute, cusps[(i + 1) % 12].absolute
        if (start < end and start <= value < end) or (
            start >= end and (value >= start or value < end)
        ):
            return i + 1
    raise ValueError("Δεν ήταν δυνατός ο υπολογισμός του Οίκου.")


def orb_weight(orb: float) -> str:
    if orb < 2:
        return "Στενή/ισχυρή"
    if orb < 4:
        return "Κανονική"
    if orb <= 7:
        return "Πλατιά αλλά έγκυρη"
    return "Πολύ πλατιά/δευτερεύουσα"


def orb_to_text(orb: float) -> str:
    # Astrodienst displays aspect orbs to the nearest arc minute.  Keep the
    # same useful precision throughout the report instead of adding seconds.
    total_minutes = round(abs(orb) * 60)
    d, m = divmod(total_minutes, 60)
    return f"{d}°{m:02d}′"


# Κανόνας 6Β (Odigies): σύνοδοι κάθε πλανήτη/σημείου με Ωροσκόπο και
# Μεσουράνημα ελέγχονται ρητά, ακόμη κι αν λείπουν από τον πίνακα του
# Astrodienst. Ο υπολογισμός γίνεται ΕΔΩ, σε Python -- όχι από το LLM.
# Στα fixtures ο πίνακας καλύπτει ήδη συνόδους με γωνίες έως ~8°, άρα
# πρακτικά συμπληρώνεται μόνο το παράθυρο ~8°–10°.
ANGLE_CONJUNCTION_MAX_ORB = 10.0
POSITION_DERIVED_SOURCE = "Υπολογισμός από τις θέσεις (λείπει από τον πίνακα Astrodienst)"
_ANGLES = ("Ωροσκόπος", "Μεσουράνημα")


def angle_conjunctions_from_positions(
    points: list[Point], aspects: list[Aspect], max_orb: float = ANGLE_CONJUNCTION_MAX_ORB
) -> list[Aspect]:
    """Σύνοδοι με Ωροσκόπο/Μεσουράνημα που προκύπτουν από τις θέσεις αλλά
    ΔΕΝ υπάρχουν ήδη στις όψεις (πίνακας ή παραγόμενες). Δεν αντικαθιστά
    ποτέ όψη του πίνακα· μόνο συμπληρώνει."""
    existing = {
        frozenset((a.first, a.second)) for a in aspects if a.aspect == "Σύνοδος"
    }
    by_name = {p.name: p for p in points}
    result = []
    for angle_name in _ANGLES:
        angle = by_name.get(angle_name)
        if angle is None:
            continue
        for p in points:
            if p.name in _ANGLES:
                continue
            if frozenset((p.name, angle_name)) in existing:
                continue
            orb = angular_distance(p.absolute, angle.absolute)
            if orb <= max_orb:
                result.append(
                    Aspect(
                        p.name,
                        angle_name,
                        "Σύνοδος",
                        orb,
                        orb_to_text(orb),
                        orb_weight(orb),
                        POSITION_DERIVED_SOURCE,
                        None,
                    )
                )
    return result


def south_node_aspects(aspects: list[Aspect]) -> list[Aspect]:
    """Derive South Node aspects from the Astrodienst True Node axis.

    The South Node is exactly opposite the North Node.  Therefore only aspect
    types that remain inside the supported major-aspect set are emitted.
    """
    opposite_map = {
        "Σύνοδος": "Αντίθεση",
        "Αντίθεση": "Σύνοδος",
        "Τετράγωνο": "Τετράγωνο",
        "Τρίγωνο": "Εξάγωνο",
        "Εξάγωνο": "Τρίγωνο",
    }
    result = []
    for aspect in aspects:
        if "Βόρειος Δεσμός" not in (aspect.first, aspect.second):
            continue
        derived_type = opposite_map.get(aspect.aspect)
        if not derived_type:
            continue
        other = aspect.second if aspect.first == "Βόρειος Δεσμός" else aspect.first
        result.append(
            Aspect(
                "Νότιος Δεσμός",
                other,
                derived_type,
                aspect.orb,
                aspect.orb_text,
                aspect.weight,
                "Μαθηματική παραγωγή από τον άξονα Βόρειου/Νότιου Δεσμού",
                aspect.applying,
            )
        )
    return result


# Απέναντι άκρο κάθε γωνιακού άξονα και σύντομη περιγραφή του άξονα, για τη
# σημείωση ενεργοποίησης -- ΔΕΝ δημιουργεί νέα σημεία ή νέες γραμμές όψεων,
# μόνο επεξηγηματικό κείμενο πάνω στην ήδη υπάρχουσα όψη.
OPPOSITE_ANGLE = {
    "Ωροσκόπος": ("Δύση", "1ου–7ου Οίκου (ταυτότητα–σχέσεις)"),
    "Μεσουράνημα": ("Πυθμένα Ουρανού", "10ου–4ου Οίκου (δημόσια πορεία–ρίζες)"),
}
# Πώς αλλάζει ο τύπος της όψης όταν μετριέται από το απέναντι άκρο του άξονα.
# Η Χιαστί όψη 150° δεν έχει υποστηριζόμενο αντίστοιχο (θα έδινε ημιεξάγωνο 30°),
# οπότε δεν παράγεται σημείωση για αυτήν.
_AXIS_FLIP = {
    "Σύνοδος": "Αντίθεση",
    "Αντίθεση": "Σύνοδος",
    "Τετράγωνο": "Τετράγωνο",
    "Τρίγωνο": "Εξάγωνο",
    "Εξάγωνο": "Τρίγωνο",
}


def axis_activation_note(aspect: Aspect) -> str | None:
    """Αν η όψη αφορά τον Ωροσκόπο ή το Μεσουράνημα, επιστρέφει μια σύντομη
    σημείωση ότι ενεργοποιείται ταυτόχρονα και το απέναντι σημείο του άξονα
    (Δύση/Πυθμένας Ουρανού), με τον σωστό τύπο όψης εκεί. Δεν προτείνει
    δεύτερη, ανεξάρτητη καταχώρηση -- μόνο επεξήγηση πάνω στην υπάρχουσα.
    """
    for point in (aspect.first, aspect.second):
        if point in OPPOSITE_ANGLE:
            opposite_name, axis_desc = OPPOSITE_ANGLE[point]
            flipped = _AXIS_FLIP.get(aspect.aspect)
            if not flipped:
                return None
            return (
                f"ενεργοποιεί ταυτόχρονα, ως {flipped}, και {opposite_name} "
                f"— άξονας {axis_desc}"
            )
    return None


def degree_theory(p: Point) -> str:
    if p.degree == 0:
        return "0°: αρχική, “καθαρή” εκδήλωση του πραγματικού ζωδίου"
    sign = SIGNS[(p.degree - 1) % 12]
    extra = " Παράλληλα μπορεί να εξεταστεί ως κρίσιμη/αναιρετική μοίρα." if p.degree == 29 else ""
    return f"{p.degree}° = συμβολική μοίρα {sign}: {DEGREE_QUALITIES[sign]}.{extra}"


def opposite_node(node: Point) -> Point:
    value = (node.absolute + 180) % 360
    si = int(value // 30)
    rem = value - si * 30
    degree = int(rem)
    minute = int((rem - degree) * 60)
    second = round((((rem - degree) * 60) - minute) * 60)
    return Point(
        "SN",
        "Νότιος Δεσμός",
        SIGNS[si],
        degree,
        minute,
        second,
        value,
        retrograde=node.retrograde,
        kind="node",
    )


def movement_text(point: Point) -> str:
    """Human-readable movement without treating angles like planets."""
    if point.kind in ("angle", "cusp"):
        return "Δεν εφαρμόζεται"
    if point.kind == "node":
        return "Ανάδρομη κίνηση" if point.retrograde else "Ορθόδρομη κίνηση"
    return "Ανάδρομος" if point.retrograde else "Ορθόδρομος"


# ---------------------------------------------------------------------------
# v19 -- Συγκεντρώσεις πλανητών (Κανόνας 6, «Συγκεντρώσεις»).
# Υπολογίζονται ΕΔΩ, σε Python, και δίνονται στο μοντέλο ως ελεγμένο δεδομένο.
# Αφορμή: σε πραγματική ανάλυση χάθηκε η «αίσθηση του δίκαιου», παρότι τρεις
# πλανήτες βρίσκονταν στον Ζυγό -- η εντολή εξέταζε κάθε πλανήτη χωριστά και
# τα τέσσερα στοιχεία συνολικά, αλλά όχι τη συγκέντρωση σε ένα ζώδιο/Οίκο.
# ---------------------------------------------------------------------------
CONCENTRATION_PLANETS = (
    "Ήλιος", "Σελήνη", "Ερμής", "Αφροδίτη", "Άρης",
    "Δίας", "Κρόνος", "Ουρανός", "Ποσειδώνας", "Πλούτωνας",
)
CONCENTRATION_MIN = 3


def planet_concentrations(points, min_count: int = CONCENTRATION_MIN) -> list[tuple[str, list[str]]]:
    """Ζώδια και Οίκοι με τουλάχιστον `min_count` από τους δέκα πλανήτες.

    Επιστρέφει λίστα (ετικέτα, ονόματα πλανητών), π.χ.
    [("Ζώδιο Ζυγός", ["Άρης", "Κρόνος", "Πλούτωνας"]), ("Οίκος 11", [...])],
    πρώτα τα ζώδια (με τη σειρά του ζωδιακού) και μετά οι Οίκοι (1-12).
    Δεσμοί, Χείρωνας και γωνίες δεν μετρούν."""
    planets = [p for p in points if p.name in CONCENTRATION_PLANETS]
    order = {name: i for i, name in enumerate(CONCENTRATION_PLANETS)}
    result: list[tuple[str, list[str]]] = []
    for sign in SIGNS:
        names = sorted((p.name for p in planets if p.sign == sign), key=order.get)
        if len(names) >= min_count:
            result.append((f"Ζώδιο {sign}", names))
    for house in range(1, 13):
        names = sorted((p.name for p in planets if p.house == house), key=order.get)
        if len(names) >= min_count:
            result.append((f"Οίκος {house}", names))
    return result


# ---------------------------------------------------------------------------
# v19.3 -- Συνδυασμοί πλατιών όψεων με κοινό σημείο (Κανόνας 10, εξαίρεση).
# Αφορμή: σε πραγματική εκτέλεση το μοντέλο απέρριψε την όψη Ήλιου–Πλούτωνα
# γράφοντας «χωρίς δεύτερη πλατιά όψη με κοινό σημείο», ενώ υπήρχε η
# Ερμή–Πλούτωνα. Ο υπολογισμός γίνεται εδώ, ώστε το μοντέλο να τους βλέπει
# γραμμένους και να μη χρειάζεται να τους «θυμηθεί».
# ---------------------------------------------------------------------------
WIDE_VALID = "Πλατιά αλλά έγκυρη"
PERSONAL_OR_ANGLE = ("Ήλιος", "Σελήνη", "Ερμής", "Αφροδίτη", "Άρης", "Ωροσκόπος", "Μεσουράνημα")
_NODES = ("Βόρειος Δεσμός", "Νότιος Δεσμός")
_POINT_ORDER = CONCENTRATION_PLANETS + ("Χείρωνας", "Ωροσκόπος", "Μεσουράνημα")


def wide_aspect_clusters(aspects) -> list[tuple[str, list[str]]]:
    """Σημεία που συμμετέχουν σε 2+ όψεις «Πλατιά αλλά έγκυρη».

    Μετρούν μόνο όψεις με προσωπικό πλανήτη ή γωνία (Κανόνας 5) και χωρίς
    Δεσμούς (Κανόνας 10). Επιστρέφει [(κοινό σημείο, ["Α–Β", ...]), ...]."""
    qualifying = [
        a for a in aspects
        if a.weight == WIDE_VALID
        and a.first not in _NODES and a.second not in _NODES
        and (a.first in PERSONAL_OR_ANGLE or a.second in PERSONAL_OR_ANGLE)
    ]
    order = {name: i for i, name in enumerate(_POINT_ORDER)}
    points = sorted({p for a in qualifying for p in (a.first, a.second)}, key=lambda n: order.get(n, 99))
    result = []
    for point in points:
        members = [f"{a.first}–{a.second}" for a in qualifying if point in (a.first, a.second)]
        if len(members) >= 2:
            result.append((point, members))
    return result
