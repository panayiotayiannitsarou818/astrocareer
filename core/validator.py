"""
validator.py
=============
Ελέγχει το ΤΕΛΙΚΟ κείμενο ανάλυσης (πριν γίνει Word) ενάντια στο ελεγμένο
Chart -- δεν εμπιστεύεται ότι το μοντέλο ακολούθησε τις οδηγίες, το
επαληθεύει μηχανικά. Αυτό είναι το ίδιο ακριβώς λάθος που παρατηρήθηκε
χειροκίνητα (παρέλειψη όψεων παρά τις ρητές οδηγίες) -- ο σκοπός αυτού του
module είναι να μην ξαναπεράσει αθόρυβα.

v2: δύο προσθήκες, ύστερα από δύο συγκεκριμένα περιστατικά που η v1 δεν θα
είχε πιάσει:
  1. Ο μηχανικός έλεγχος κάλυπτε μόνο "Τετράγωνο"/"Αντίθεση". Μια σύνοδος με
     τον Ωροσκόπο ή το Μεσουράνημα (π.χ. Χείρωνας–Ωροσκόπος) δεν ελεγχόταν
     καθόλου, άρα η απουσία της δεν θα εμφανιζόταν ποτέ ως σφάλμα. Τώρα ο
     ορισμός του "mandatory" περιλαμβάνει και κάθε σύνοδο όπου συμμετέχει
     γωνία (astrology.OPPOSITE_ANGLE).
  2. Ο παλιός έλεγχος co-occurrence δεχόταν μια όψη ως "καλυμμένη" αν
     εμφανιζόταν ΟΠΟΥΔΗΠΟΤΕ στο κείμενο -- π.χ. μια όψη του κυβερνήτη ενός
     Οίκου που αναφέρεται μόνο στον Οίκο όπου φυσικά βρίσκεται ο πλανήτης,
     αλλά ποτέ στον Οίκο που ο ίδιος πλανήτης κυβερνά, περνούσε ως OK. Τώρα
     γίνεται ξεχωριστός έλεγχος ανά Οίκο (κανόνας 6Β): κάθε mandatory όψη
     πρέπει να εμφανίζεται μέσα στο τμήμα κειμένου κάθε Οίκου όπου το σημείο
     της είναι "involved" -- Οίκος-κατοικίας ΚΑΙ κάθε Οίκος που κυβερνά.

v3: νέος έλεγχος, ύστερα από συγκεκριμένο περιστατικό (ΠΑΝΑΓΙΩΤΑ, 9ος Οίκος)
που κανένας από τους παραπάνω ελέγχους δεν θα είχε πιάσει: το πλαίσιο
σύνοψης ("Κυβερνήτης: ...") ενός Οίκου είχε αντιγραφεί αυτούσιο από άλλον
Οίκο, ενώ το κυρίως κείμενο του ίδιου Οίκου ονόμαζε σωστά διαφορετικό
πλανήτη ως κυβερνήτη. Ούτε ο έλεγχος όψεων ούτε ο έλεγχος ενοτήτων το
εντοπίζουν, γιατί το λάθος όνομα είναι έγκυρο αστρολογικό όνομα, απλώς για
λάθος Οίκο. Τώρα, για κάθε Οίκο, εξάγεται ο κυβερνήτης (ή οι κυβερνήτες,
όταν δηλώνονται και σύγχρονος και παραδοσιακός) από την εισαγωγική πρόταση
του κυρίως κειμένου, και ελέγχεται ότι το ίδιο όνομα εμφανίζεται μέσα στη
γραμμή "Κυβερνήτης:" του πλαισίου σύνοψης του ΙΔΙΟΥ Οίκου.

Η λήψη του τελικού Word πρέπει να παραμένει κλειδωμένη όσο
ValidationResult.ok είναι False.
"""

from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field

from .astrology import SIGNS

# Κανονικοποίηση των συνηθέστερων ελληνικών πτώσεων. Ο παλιός validator
# έψαχνε μόνο την ονομαστική (π.χ. «Πλούτωνας») και απέρριπτε σωστές φράσεις
# όπως «με τον Πλούτωνα» ή «του Κρόνου».
_NAME_FORMS = {
    "Ήλιος": r"Ήλι(?:ος|ο|ου)",
    "Σελήνη": r"Σελήν(?:η|ης)",
    "Ερμής": r"Ερμ(?:ής|ή)",
    "Αφροδίτη": r"Αφροδίτ(?:η|ης)",
    "Άρης": r"Άρ(?:ης|η)",
    "Δίας": r"Δί(?:ας|α)",
    "Κρόνος": r"Κρόν(?:ος|ο|ου)",
    "Ουρανός": r"Ουραν(?:ός|ό|ού)",
    "Ποσειδώνας": r"Ποσειδών(?:ας|α)",
    "Πλούτωνας": r"Πλούτων(?:ας|α)",
    "Βόρειος Δεσμός": r"Βόρει(?:ος|ο|ου)\s+Δεσμ(?:ός|ό|ού)",
    "Νότιος Δεσμός": r"Νότι(?:ος|ο|ου)\s+Δεσμ(?:ός|ό|ού)",
    "Χείρωνας": r"Χείρων(?:ας|α)",
    "Ωροσκόπος": r"Ωροσκόπ(?:ος|ο|ου)",
    "Μεσουράνημα": r"Μεσουρ(?:άνημα|ανήματος)",
}

# Fix (deep review κριτική, 2ος γύρος): χρειάζεται και για _mentioned_point_names(),
# ώστε ένας δείκτης γραμμένος με αγγλικά ονόματα πλανητών (π.χ. "Mercury")
# να αναγνωρίζεται και να ελέγχεται έναντι των πραγματικών σημείων του χάρτη.
_EL_TO_EN_POINT = {
    "Ήλιος": "Sun", "Σελήνη": "Moon", "Ερμής": "Mercury", "Αφροδίτη": "Venus",
    "Άρης": "Mars", "Δίας": "Jupiter", "Κρόνος": "Saturn", "Ουρανός": "Uranus",
    "Ποσειδώνας": "Neptune", "Πλούτωνας": "Pluto", "Χείρωνας": "Chiron",
    "Βόρειος Δεσμός": "North Node", "Νότιος Δεσμός": "South Node",
    "Ωροσκόπος": "Ascendant", "Μεσουράνημα": "Midheaven",
}

_ASPECT_FORMS = {
    "Σύνοδος": r"σύνοδ(?:ος|ο|ου)",
    "Εξάγωνο": r"εξάγων(?:ο|ου)",
    "Τετράγωνο": r"τετράγων(?:ο|ου)",
    "Τρίγωνο": r"τρίγων(?:ο|ου)",
    "Αντίθεση": r"αντίθεσ(?:η|ης)",
    "Χιαστί όψη 150°": r"χιαστί(?:\s+όψη)?(?:\s+150°)?",
}

_WEIGHT_FORMS = {
    "Στενή/ισχυρή": r"στεν(?:ή|ό)\s*/\s*ισχυρ(?:ή|ό)",
    "Κανονική": r"κανονικ(?:ή|ό)",
    "Πλατιά αλλά έγκυρη": r"πλατ(?:ιά|ύ)\s+αλλά\s+έγκυρ(?:η|ο)",
    "Πολύ πλατιά/δευτερεύουσα": r"πολύ\s+πλατ(?:ιά|ύ)\s*/\s*δευτερεύ(?:ουσα|ον)",
}

_WINDOW = 350  # χαρακτήρες γύρω από κάθε εμφάνιση ονόματος, για αναζήτηση ταιριάσματος

def _normalize_prime_marks(text: str) -> str:
    """Κανονικοποιεί το πρόχειρο ' (ASCII apostrophe, U+0027) και το
    τυπογραφικό ' (right single quote, U+2019) σε ′ (πραγματικό σύμβολο
    πρώτου λεπτού τόξου, U+2032) όταν ακολουθεί ψηφίο -- π.χ. "3°30'" ή
    "3°30'" γίνονται "3°30′".

    Γιατί χρειάζεται: κάθε aspect.orb_text (astrology.orb_to_text) και
    κάθε _NAME_FORMS/regex σε αυτό το module χρησιμοποιεί αποκλειστικά το
    ′. Ένα Word που παράγεται από μοντέλο (ή περνάει από αυτόματο smart-
    quote του Word/ChatGPT) μπορεί να γράψει το πρόχειρο απόστροφο αντ'
    αυτού. Χωρίς αυτή την κανονικοποίηση, το ίδιο ακριβώς, σωστό orb
    χαρακτηρίζεται ψευδώς "ύποπτο/απόν" επειδή η αναζήτηση συμβολοσειράς
    (`orb_text in window`, `re.escape(orb_text)` κ.λπ.) απαιτεί ΑΚΡΙΒΩΣ
    το χαρακτήρα ′. Καλείται μία φορά, στην είσοδο κάθε δημόσιας
    validate_*() συνάρτησης -- όλες οι εσωτερικές κλήσεις (per-house
    τμήματα, Παράρτημα κ.λπ.) προέρχονται από ήδη κανονικοποιημένο κείμενο.
    """
    return re.sub(r"(?<=\d)['’]", "′", text)


def _name_pattern(name: str) -> str:
    return _NAME_FORMS.get(name, re.escape(name))


_USAGE_KEYWORDS_RE = re.compile(r"ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ|χρησιμοποιείται|χρησιμοποιήθηκε|\bused\b", re.IGNORECASE)
_EXCLUSION_KEYWORDS_RE = re.compile(
    r"ΕΞΑΙΡΕΙΤΑΙ|εξαιρείται|εξαιρέθηκε|αγνοείται|αγνοήθηκε|αποκλείστηκε|αποκλείεται|excluded|unused",
    re.IGNORECASE,
)
# Fix (κριτική chat, πραγματικά κενά): "never"/"ουδέποτε"/"χωρίς" (without)
# δεν αναγνωρίζονταν καθόλου ως άρνηση -- "never used"/"ουδέποτε
# χρησιμοποιείται"/"χωρίς να χρησιμοποιείται" περνούσαν σαν θετική δήλωση
# χρήσης. Το "unused" (μία λέξη, όχι "not used") δεν έχει τη δομή
# "άρνηση+used" καθόλου -- προστέθηκε απευθείας στο _EXCLUSION_KEYWORDS_RE
# ως ισοδύναμο του "excluded", αφού λειτουργικά σημαίνει ακριβώς αυτό.
_NEGATION_RE = re.compile(
    r"δεν|μη(?:ν)?\b|not\b|isn'?t\b|doesn'?t\b|never\b|ουδέποτε|χωρίς\b",
    re.IGNORECASE,
)
# Επικεφαλίδες που σηματοδοτούν ότι βγήκαμε πλέον από την ενότητα ελέγχου
# τεκμηρίωσης ταλέντων (άρα ένα «Δείκτης» μετά από αυτές δεν είναι πια
# μέσα σε ΤΑΛΕΝΤΟ: μπλοκ, ό,τι κι αν λέει).
_TALENT_BLOCK_END_RE = re.compile(
    r"^\s*(?:ΕΓΚΕΚΡΙΜΕΝΟΙ|ΕΓΚΕΚΡΙΜΕΝΑ|Κάλυψη\s+όψ|Κάλυψη\s+στεν|Παράρτημα|Τελικός\s+έλεγχος|ΑΥΤΟΕΛΕΓΧΟΣ)",
    re.IGNORECASE,
)
_TALENT_BLOCK_START_RE = re.compile(r"^\s*ΤΑΛΕΝΤΟ\s*:\s*(.*)$", re.IGNORECASE)


def _norm_title(t: str) -> str:
    """Κανονικοποίηση τίτλου ταλέντου για ανεκτική σύγκριση (πεζά/κενά/
    τελική στίξη) -- κοινή βάση χρησιμοποιούμενη σε πολλαπλά σημεία ελέγχου."""
    return re.sub(r"\s+", " ", t.strip().lower()).rstrip(".·")


def _talent_block_membership(text: str) -> list[str | None]:
    """Για κάθε γραμμή (με τη σειρά του text.split("\\n")), ο (ωμός) τίτλος
    του ΤΑΛΕΝΤΟ: μπλοκ μέσα στο οποίο βρίσκεται η γραμμή, ή None αν δεν
    είναι μέσα σε κανένα.

    Fix (κριτική chat, ακριβής, επιβεβαιωμένη -- τρίτο εύρημα): πριν, ΚΑΘΕ
    γραμμή που ξεκινούσε με «Δείκτης» μετρούσε αυτόματα ως έμμεση δήλωση
    χρήσης, ΑΚΟΜΗ κι αν βρισκόταν έξω από οποιοδήποτε ΤΑΛΕΝΤΟ: μπλοκ.
    Fix (κριτική chat, ακριβής -- πέμπτος γύρος): αυτό δεν αρκούσε --
    επιστρέφει τώρα τον ΙΔΙΟ τον τίτλο (όχι απλό bool), ώστε ο καλών να
    μπορεί να ελέγξει αν το μπλοκ αντιστοιχεί σε πραγματικό, εγκεκριμένο
    ταλέντο του καθαρού παραδοτέου -- όχι σε ένα «φανταστικό» ΤΑΛΕΝΤΟ:
    μπλοκ που δεν εμφανίζεται πουθενά στον πελάτη."""
    current_title: str | None = None
    membership: list[str | None] = []
    for line in text.split("\n"):
        m = _TALENT_BLOCK_START_RE.match(line)
        if m:
            current_title = m.group(1).strip()
        elif _TALENT_BLOCK_END_RE.match(line):
            current_title = None
        membership.append(current_title)
    return membership


def _line_declares_indicator(line: str, name_a: str, name_b: str, aspect_type: str | None) -> bool:
    """Ελέγχει αν μια γραμμή «Δείκτης...» είναι ΠΡΑΓΜΑΤΙΚΑ ένας δομημένος
    δείκτης Όψης για το συγκεκριμένο ζεύγος+τύπο -- με πλήρη ανάλυση
    πεδίων (Τύπος:/Σημείο 1:/Όψη:/Σημείο 2:), όχι απλή αναζήτηση υπο-
    αλφαβητισμού.

    Fix (κριτική chat, ακριβής -- πέμπτος γύρος, δεύτερο μέρος): μια μη
    δομημένη, ακόμη και αρνητική γραμμή («Δείκτης 99: Η όψη Σελήνη–Ήλιος
    Τετράγωνο δεν χρησιμοποιείται») περνούσε ως «δηλωμένος δείκτης» επειδή
    ο παλιός έλεγχος έψαχνε απλώς αν τα ονόματα+τύπος εμφανίζονται
    ΟΠΟΥΔΗΠΟΤΕ στη γραμμή. Τώρα η γραμμή πρέπει να αναλύεται σε πραγματικά
    δομημένα πεδία Τύπος: Όψη με ακριβές Σημείο 1/Σημείο 2/Όψη.

    Fix (κριτική chat, ακριβής -- έβδομος γύρος): ακόμη κι όταν η γραμμή
    ΕΙΝΑΙ πλήρως δομημένη, ένα πρόσθετο, ελεύθερο κείμενο στο τέλος («|
    δεν χρησιμοποιείται») περνούσε απαρατήρητο -- η _parse_indicator_fields()
    απλώς αγνοεί ένα τελευταίο κομμάτι χωρίς «:» αντί να το εξετάσει.
    Τώρα ελέγχεται ρητά ολόκληρη η γραμμή για άρνηση («δεν», «μη», «not»)
    πριν θεωρηθεί έγκυρη δήλωση χρήσης.

    Fix (κριτική chat, ακριβής -- όγδοος γύρος): η άρνηση δεν ήταν το μόνο
    σήμα εξαίρεσης -- ένα δομημένο «Δείκτης» με ρητή λέξη ΕΞΑΙΡΕΙΤΑΙ/
    αγνοείται/αποκλείεται στο τέλος («| ΕΞΑΙΡΕΙΤΑΙ: θεματικά ασύνδετη»)
    επίσης περνούσε, αφού ελεγχόταν μόνο η _NEGATION_RE, όχι η
    _EXCLUSION_KEYWORDS_RE. Τώρα απορρίπτεται και για τους δύο λόγους."""
    if _NEGATION_RE.search(line) or _EXCLUSION_KEYWORDS_RE.search(line):
        return False
    m = re.match(r"\s*Δείκτης\s*\d*\s*:\s*(.*)$", line, re.IGNORECASE)
    indicator_text = m.group(1) if m else line
    if _indicator_kind(indicator_text) != "οψη":
        return False
    fields = _parse_indicator_fields(indicator_text)
    p1 = _exact_point_name(fields.get("σημειο 1", ""))
    p2 = _exact_point_name(fields.get("σημειο 2", ""))
    if p1 is None or p2 is None or {p1, p2} != {name_a, name_b}:
        return False
    if not aspect_type:
        return True
    found_type = _exact_aspect_type(fields.get("οψη", ""))
    return found_type == aspect_type


def _aspect_declared_as_indicator_in_talent(text: str, membership: list[str | None],
                                             name_a: str, name_b: str,
                                             aspect_type: str | None,
                                             approved_titles: set[str]) -> bool:
    """Ελέγχει αν το ζεύγος+τύπος όψης εμφανίζεται ΠΡΑΓΜΑΤΙΚΑ ως δομημένος
    δείκτης μέσα σε ΤΑΛΕΝΤΟ: μπλοκ που αντιστοιχεί σε πραγματικό,
    εγκεκριμένο ταλέντο -- όχι απλώς μέσα σε ΟΠΟΙΟΔΗΠΟΤΕ μπλοκ.

    Fix (κριτική chat, ακριβής, επιβεβαιωμένη -- τέταρτο εύρημα): πριν, μια
    γραμμή κάλυψης που έλεγε απλώς «ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ» γινόταν αποδεκτή χωρίς
    καμία επαλήθευση ότι η όψη ΟΝΤΩΣ εμφανίζεται ως δείκτης σε κάποιο
    ταλέντο. Fix (πέμπτος γύρος): δεν αρκεί καν αυτό -- το ΤΑΛΕΝΤΟ: μπλοκ
    μπορούσε να είναι «φανταστικό» (τίτλος που δεν υπάρχει καθόλου στο
    καθαρό παραδοτέο). Τώρα απαιτείται ο τίτλος του μπλοκ να ταιριάζει
    (κανονικοποιημένα) με κάποιον από τους πραγματικά εγκεκριμένους
    τίτλους ταλέντων."""
    for line, block_title in zip(text.split("\n"), membership):
        if block_title is None or _norm_title(block_title) not in approved_titles:
            continue
        if not re.match(r"\s*Δείκτης", line, re.IGNORECASE):
            continue
        if _line_declares_indicator(line, name_a, name_b, aspect_type):
            return True
    return False


_FILLER_JUSTIFICATION_RE = re.compile(
    r"^(?:ναι|όχι|οχι|κάτι|κατι|τίποτα|τιποτα|άγνωστο|αγνωστο|n/?a|abc|xx?x?)$",
    re.IGNORECASE,
)


def _has_real_justification(trailing: str) -> bool:
    """Fix (κριτική chat, δευτερεύον εύρημα): το «τουλάχιστον μία λέξη 3+
    γραμμάτων» δεχόταν ανούσιες λέξεις-γέμισμα («ναι», «όχι», «κάτι»,
    «abc») που δεν αποτελούν πραγματική αιτιολόγηση. Χωρίς να απαιτείται
    πλήρης δομημένη ανασχεδίαση (η ασφαλέστερη αλλά πιο ριζική πρόταση
    της κριτικής), απορρίπτεται τουλάχιστον το προφανές μπλοκ γεμίσματος."""
    words = re.findall(r"[Α-ώΆ-Ωα-ωA-Za-z]{3,}", trailing)
    return any(not _FILLER_JUSTIFICATION_RE.match(w) for w in words)


def _decision_ok_on_line(line: str, block_title: str | None = "", approved_titles: set[str] | None = None,
                          verified_usage_elsewhere: bool = True,
                          name_a: str | None = None, name_b: str | None = None,
                          aspect_type: str | None = None) -> bool:
    """Ελέγχει αν μία γραμμή έχει έγκυρη δήλωση χρήσης/απόφασης.

    Fix (κριτική chat, ακριβής): η δεσμευτική εντολή απαιτεί «ΕΞΑΙΡΕΙΤΑΙ» ΜΕ
    ρητή αιτιολόγηση -- πριν, ο έλεγχος δεχόταν την ψιλή λέξη «ΕΞΑΙΡΕΙΤΑΙ»
    χωρίς καμία εξήγηση μετά. Τώρα, αν η λέξη είναι εξαίρεση (όχι έμμεση
    χρήση μέσω γραμμής «Δείκτης» μέσα σε ΤΑΛΕΝΤΟ: μπλοκ), απαιτείται
    τουλάχιστον μία πραγματική λέξη (όχι μόνο στίξη/κενά) ΜΕΤΑ τη λέξη
    στην ίδια γραμμή.

    Fix (κριτική chat, ακριβής -- δεύτερος γύρος, δύο ευρήματα): (α) «δεν
    χρησιμοποιείται» περνούσε σαν να ήταν θετική δήλωση χρήσης· τώρα μια
    αρνημένη «χρησιμοποιείται» αντιμετωπίζεται σαν εξαίρεση. (β) το όριο
    «len(trailing) >= 8» ήταν αυθαίρετο· αντικαταστάθηκε με έλεγχο για
    τουλάχιστον μία πραγματική λέξη.

    Fix (κριτική chat, ακριβής -- τρίτος γύρος): μια bare «ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ»
    (όχι η ίδια γραμμή «Δείκτης» μέσα σε ΤΑΛΕΝΤΟ:) πρέπει επιπλέον να
    επαληθεύεται (verified_usage_elsewhere).

    Fix (κριτική chat, ακριβής -- πέμπτος γύρος): η γραμμή «Δείκτης» μέσα
    σε ΤΑΛΕΝΤΟ: μπλοκ μετράει ως έμμεση χρήση ΜΟΝΟ όταν ο τίτλος του
    μπλοκ είναι πραγματικά εγκεκριμένος τίτλος.

    Fix (κριτική chat, ακριβής -- έκτος γύρος): ακόμη κι ΜΕΣΑ σε εγκεκριμένο
    μπλοκ, η «συντόμευση Δείκτης» δεχόταν ΟΠΟΙΑΔΗΠΟΤΕ γραμμή που απλώς
    ΞΕΚΙΝΟΥΣΕ με τη λέξη «Δείκτης» -- ακόμη και μη δομημένη, αρνητική
    πρόταση («Δείκτης 99: Η όψη ... δεν χρησιμοποιείται»). Τώρα η
    συντόμευση απαιτεί η γραμμή να είναι ΠΡΑΓΜΑΤΙΚΑ δομημένος δείκτης για
    το ΣΥΓΚΕΚΡΙΜΕΝΟ ζεύγος+τύπο που ελέγχεται (μέσω _line_declares_indicator),
    όχι απλώς να ξεκινάει με τη λέξη."""
    inside_approved_block = block_title is not None and approved_titles is not None and _norm_title(block_title) in approved_titles
    if inside_approved_block and re.match(r"\s*Δείκτης", line, re.IGNORECASE):
        if name_a is not None and name_b is not None:
            if _line_declares_indicator(line, name_a, name_b, aspect_type):
                return True
        else:
            return True  # παλιά κλήση χωρίς πλαίσιο ζεύγους -- διατηρεί προηγούμενη συμπεριφορά
    m = _USAGE_KEYWORDS_RE.search(line)
    if m:
        preceding = line[max(0, m.start() - 15):m.start()]
        if not _NEGATION_RE.search(preceding):
            return verified_usage_elsewhere
        # Αρνημένη χρήση («δεν χρησιμοποιείται») -- λειτουργικά είναι
        # εξαίρεση, άρα χρειάζεται τη δική της αιτιολόγηση παρακάτω.
        trailing = line[m.end():]
        return _has_real_justification(trailing)
    m = _EXCLUSION_KEYWORDS_RE.search(line)
    if not m:
        return False
    trailing = line[m.end():]
    return _has_real_justification(trailing)


def _co_occurs_with_orb(text: str, name_a: str, name_b: str, orb_text: str,
                        aspect_type: str | None = None,
                        weight: str | None = None,
                        approved_titles: set[str] | None = None) -> tuple[bool, bool, bool, bool, bool]:
    """Επιστρέφει παρουσία ζεύγους, orb, σωστού τύπου, σωστής βαρύτητας, και
    έγκυρης δήλωσης χρήσης/απόφασης -- όλα ελεγμένα ΜΑΖΙ στην ΙΔΙΑ γραμμή.

    Fix (κριτική chat, ακριβής, επιβεβαιωμένη -- δεύτερο εύρημα): η
    προηγούμενη εκδοχή έλεγχε ανά γραμμή αλλά συσσώρευε κάθε σημαία
    (τύπος/βαρύτητα/απόφαση) ανεξάρτητα σε όλες τις γραμμές με το ίδιο
    ζεύγος+orb -- δύο ΔΙΑΦΟΡΕΤΙΚΕΣ λανθασμένες γραμμές μπορούσαν μαζί να
    δώσουν «επιτυχία», παρότι καμία γραμμή δεν είχε όλα τα στοιχεία μαζί
    (π.χ. μία γραμμή με λάθος βαρύτητα αλλά σωστό τύπο, μια άλλη με λάθος
    τύπο αλλά σωστή βαρύτητα). Τώρα κρατιέται η γραμμή που ικανοποιεί τα
    ΠΕΡΙΣΣΟΤΕΡΑ κριτήρια ΜΑΖΙ (για ενημερωτική αναφορά σε μερική αποτυχία),
    και η επιτυχία σημαίνει ρητά ότι ΜΙΑ γραμμή είχε τα πάντα μαζί.

    Fix (κριτική chat, ακριβής -- πέμπτος γύρος): approved_titles (τίτλοι
    ταλέντων από το καθαρό παραδοτέο) περνάει τώρα μέχρι κάθε γραμμή, ώστε
    ένα ΤΑΛΕΝΤΟ: μπλοκ με «φανταστικό» τίτλο (που δεν υπάρχει στον
    πελάτη) να μην μετράει ως έγκυρη χρήση -- χωρίς approved_titles
    (None), κανένα μπλοκ δεν θεωρείται εγκεκριμένο (ασφαλές εξ ορισμού).
    """
    co_occurs = False
    best = (False, False, False, False)  # orb, type, weight, decision -- από τη ΜΙΑ καλύτερη γραμμή
    pa, pb = _name_pattern(name_a), _name_pattern(name_b)
    membership = _talent_block_membership(text)
    norm_approved = {_norm_title(t) for t in approved_titles} if approved_titles else set()
    verified_elsewhere = _aspect_declared_as_indicator_in_talent(text, membership, name_a, name_b, aspect_type, norm_approved)
    for line, block_title in zip(text.split("\n"), membership):
        if not (re.search(pa, line, re.IGNORECASE) and re.search(pb, line, re.IGNORECASE)):
            continue
        co_occurs = True
        orb_ok = orb_text in line
        if not orb_ok:
            continue
        t_ok = bool(re.search(_ASPECT_FORMS.get(aspect_type, re.escape(aspect_type)), line, re.IGNORECASE)) if aspect_type else True
        w_ok = bool(re.search(_WEIGHT_FORMS.get(weight, re.escape(weight)), line, re.IGNORECASE)) if weight else True
        d_ok = _decision_ok_on_line(line, block_title, norm_approved, verified_elsewhere, name_a, name_b, aspect_type)
        this_line = (orb_ok, t_ok, w_ok, d_ok)
        if sum(this_line) > sum(best):
            best = this_line
        if all(this_line):
            best = this_line
            break
    return (co_occurs,) + best


def _location_claim_errors(chart, text: str) -> list[tuple[str, int, int, str]]:
    """Detect only affirmative location statements, avoiding thematic links.

    The check intentionally targets phrases such as "ο Άρης βρίσκεται στον 7ο"
    or "ο Άρης βρίσκεται στο πεδίο των σχέσεων".  It does not reject a valid
    sentence saying that a planet in one house *connects* with another field.
    """
    theme_houses = {
        1: r"ταυτότητ|προσωπικ(?:ή|ης)\s+παρουσ",
        2: r"προσωπικ(?:ή|ης)\s+αξί|πόρ(?:ων|ους)",
        3: r"επικοινωνί|μάθησ",
        4: r"οικογένει|ριζ(?:ών|ες)|σπιτ",
        5: r"δημιουργικότητ|παιδι(?:ών|ά)|χαρά",
        6: r"καθημεριν(?:ή|ης)\s+εργασ|ρουτίν|υγεί",
        7: r"σχέσε(?:ων|ών|ις)|γάμ(?:ου|ος)|συνεργασ",
        8: r"κοιν(?:ών|ά)\s+οικονομ|εμπιστοσύν|μεταμόρφωσ",
        9: r"νοήματ|ανώτερ(?:η|ης)\s+παιδε|φιλοσοφ",
        10: r"καριέρα|δημόσια(?:ς|\s+)\s*(?:σου\s+)?πορεία|επαγγελματικ(?:ή|ης)\s+πορεία",
        11: r"οραμάτων|κοινότητ|ομάδ|φίλ",
        12: r"εσωτερικ(?:ό|ού)\s+κόσμ|παρασκήν|ασυνείδητ",
    }
    errors = []
    for point in chart.points:
        if point.house is None or point.kind not in ("planet", "node"):
            continue
        name = _name_pattern(point.name)
        # Explicit numeric placement.
        numeric = re.compile(
            rf"{name}[^.!?\n]{{0,90}}?(?:βρίσκεται|είναι|τοποθετείται|κατοικεί|Θέση\s*:)[^.!?\n]{{0,45}}?(\d{{1,2}})\s*(?:ος|ο|ου)?\s*Οίκ",
            re.IGNORECASE,
        )
        # Symbolic house label used as if it were a physical placement.
        thematic = re.compile(
            rf"{name}[^.!?\n]{{0,70}}?(?:βρίσκεται|είναι|τοποθετείται|κατοικεί)\s+(?:μέσα\s+)?στο\s+πεδίο\s+(?:της|των)\s+([^—.!?\n]{{2,55}})",
            re.IGNORECASE,
        )
        for match in numeric.finditer(text):
            claimed = int(match.group(1))
            if 1 <= claimed <= 12 and claimed != point.house:
                errors.append((point.name, claimed, point.house, match.group(0).strip()))
        for match in thematic.finditer(text):
            label = match.group(1)
            claimed = next((n for n, pat in theme_houses.items() if re.search(pat, label, re.IGNORECASE)), None)
            if claimed and claimed != point.house:
                errors.append((point.name, claimed, point.house, match.group(0).strip()))
    return errors


def _unauthorized_personal_claims(personal: dict | None, text: str) -> list[tuple[str, str]]:
    """Εντοπίζει επινοημένα προσωπικά στοιχεία που ΔΕΝ δηλώθηκαν στο
    ΠΡΟΣΩΠΙΚΟ ΠΛΑΙΣΙΟ.

    ΠΡΟΣΟΧΗ -- γνωστός περιορισμός: αυτή η λίστα είναι αναγκαστικά μια
    allowlist συγκεκριμένων φράσεων, όχι γενικός σημασιολογικός έλεγχος.
    Καλύπτει τις κατηγορίες που αντιστοιχούν σε πεδία του ΠΡΟΣΩΠΙΚΟΥ
    ΠΛΑΙΣΙΟΥ (tab3 του app.py), αλλά μια αρκετά διαφορετική διατύπωση από
    αυτή που ήδη περιμένουν τα regex θα περάσει απαρατήρητη. Δεν
    αντικαθιστά την ανθρώπινη ανάγνωση της τελικής ανάλυσης.
    """
    personal = personal or {}
    checks = []
    if not (personal.get("Επάγγελμα και σπουδές") or "").strip():
        checks.append(("επάγγελμα/σπουδές", r"[^.!?\n]{0,45}(?:καθηγήτρια|καθηγητής|διδασκαλία\s+(?:της\s+)?φυσικής|στο\s+επάγγελμά\s+σου|εργάζεσαι\s+σε\s+σχολ|έχεις\s+μεταπτυχιακό|το\s+πτυχίο\s+σου)[^.!?\n]{0,70}"))
    if not (personal.get("Οικογενειακή κατάσταση") or "").strip():
        checks.append(("οικογενειακή κατάσταση", r"[^.!?\n]{0,45}(?:με\s+(?:τα\s+)?δύο\s+(?:σου\s+)?παιδιά|έχεις\s+δύο\s+παιδιά|ως\s+μητέρα|ως\s+πατέρας|ο\s+σύζυγός\s+σου|η\s+σύζυγός\s+σου)[^.!?\n]{0,70}"))
    if not (personal.get("Εργασιακές συνήθειες") or "").strip():
        checks.append(("εργασιακές συνήθειες", r"[^.!?\n]{0,45}(?:επαγγελματική\s+κόπωση|επαγγελματική\s+εξουθένωση|burnout)[^.!?\n]{0,70}"))
    if not (personal.get("Έργα/ενδιαφέροντα") or "").strip():
        checks.append(("έργα/στόχοι", r"[^.!?\n]{0,45}(?:θέλεις\s+να\s+αλλάξεις\s+καριέρα|το\s+έργο\s+σου\s+(?:στο|στην|με))[^.!?\n]{0,70}"))
    found = []
    for category, pattern in checks:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            found.append((category, match.group(0).strip()))
    return found


@dataclass
class OrientationValidationResult:
    ok: bool
    wrong_house_claims: list = field(default_factory=list)
    unauthorized_personal_claims: list = field(default_factory=list)
    missing_core_topics: list = field(default_factory=list)
    technical_mismatches: list = field(default_factory=list)
    name_issues: list = field(default_factory=list)
    # Fix (spec: νέα λογική τεκμηρίωσης ταλέντων): προαιρετικές, μη
    # αποκλειστικές σημειώσεις -- ΔΕΝ επηρεάζουν το ok. Π.χ. παράγραφος
    # ταλέντου εκτός του ~70-110 λέξεων στόχου. Μη δεσμευτική υπενθύμιση,
    # όχι λόγος απόρριψης.
    warnings: list = field(default_factory=list)
    # Fix (ετικέτα απόρριψης): το technical_mismatches μαζεύει μηνύματα από
    # πολλούς διαφορετικούς ελέγχους (όψεις/orb, τεχνικό δελτίο, τομείς/
    # επαγγέλματα, δομή/μορφή). Πριν, το summary() τα μετρούσε ΟΛΑ ως
    # «ασυμφωνίες όψης/orb/βαρύτητας», π.χ. 33 σφάλματα τομέων εμφανίζονταν
    # ως σφάλματα όψεων. Εδώ κρατιέται το πλήθος ανά κατηγορία, ώστε η
    # σύνοψη να ονομάζει σωστά την πηγή. Το technical_mismatches μένει
    # αμετάβλητο (όλα τα μηνύματα), για συμβατότητα με όσους το διαβάζουν.
    technical_breakdown: dict = field(default_factory=dict)

    def summary(self):
        if self.ok:
            if self.warnings:
                return (
                    f"✓ Το παραδοτέο εγκρίθηκε με {len(self.warnings)} μη δεσμευτικές παρατηρήσεις "
                    "(δες τις λεπτομέρειες)."
                )
            return "✓ Ο προαιρετικός επαγγελματικός προσανατολισμός πέρασε τον βασικό έλεγχο πηγών και αμετάβλητων δεδομένων."
        parts=[]
        if self.wrong_house_claims: parts.append(f"{len(self.wrong_house_claims)} λανθασμένες τοποθετήσεις")
        if self.unauthorized_personal_claims: parts.append(f"{len(self.unauthorized_personal_claims)} μη δηλωμένα προσωπικά στοιχεία")
        if self.missing_core_topics: parts.append("λείπουν: " + ", ".join(self.missing_core_topics))
        if self.technical_mismatches:
            breakdown = {k: v for k, v in (self.technical_breakdown or {}).items() if v}
            if breakdown:
                for key, (singular, plural) in _TECHNICAL_CATEGORY_LABELS:
                    n = breakdown.get(key)
                    if n:
                        parts.append(f"{n} {singular if n == 1 else plural}")
            else:
                # Χωρίς ανάλυση (π.χ. αποτέλεσμα φτιαγμένο αλλού): ουδέτερη
                # διατύπωση αντί για τον παραπλανητικό χαρακτηρισμό «όψης/orb».
                n = len(self.technical_mismatches)
                parts.append(f"{n} τεχνικό ζήτημα" if n == 1 else f"{n} τεχνικά ζητήματα")
        if self.name_issues: parts.append(f"{len(self.name_issues)} πρόβλημα/προβλήματα ονόματος")
        return "Ο προσανατολισμός απορρίφθηκε: " + "· ".join(parts) + "."

    def details_lines(self):
        lines=[]
        for point,claimed,expected,snippet in self.wrong_house_claims:
            lines.append(f"{point}: δηλώνεται στον {claimed}ο αντί στον {expected}ο Οίκο: «{snippet}»")
        for category,snippet in self.unauthorized_personal_claims:
            lines.append(f"Μη δηλωμένο προσωπικό στοιχείο ({category}): «{snippet}»")
        for topic in self.missing_core_topics: lines.append(f"Δεν εντοπίστηκε βασικό μέρος: {topic}.")
        for message in self.technical_mismatches: lines.append(message)
        for message in self.name_issues: lines.append(message)
        for message in self.warnings: lines.append(f"[Μη δεσμευτική σημείωση] {message}")
        return lines


# Σειρά και ετικέτες των κατηγοριών στη σύνοψη απόρριψης.
_TECHNICAL_CATEGORY_LABELS = (
    ("aspect", ("ασυμφωνία όψης/orb/βαρύτητας", "ασυμφωνίες όψης/orb/βαρύτητας")),
    ("audit", ("σφάλμα στο τεχνικό δελτίο", "σφάλματα στο τεχνικό δελτίο")),
    ("career", ("ασυμφωνία τομέων/επαγγελμάτων με το τεχνικό δελτίο", "ασυμφωνίες τομέων/επαγγελμάτων με το τεχνικό δελτίο")),
    ("structure", ("ζήτημα δομής/μορφής/περιεχομένου", "ζητήματα δομής/μορφής/περιεχομένου")),
)


def _orientation_technical_mismatches(chart, text: str) -> list[str]:
    """Ελέγχει κάθε ρητά δηλωμένο orb που επέλεξε να γράψει το μοντέλο.

    Δεν απαιτεί να χρησιμοποιηθούν όλες οι όψεις του χάρτη. Αν όμως εμφανιστεί
    orb, πρέπει στο ίδιο τοπικό τμήμα να υπάρχει το σωστό ζεύγος, ο σωστός
    τύπος και η σωστή κατηγορία βαρύτητας από το registry του Chart.

    v2 (διόρθωση, ίδια αιτία με το _invented_orbs): αγκυρωμένο στη λέξη
    "orb" ώστε να μην πιάνει θέσεις πλανητών (π.χ. "Παρθένος 8°47′33″",
    astrology.fmt) που επίσης περιέχουν "μοίρα°λεπτό′" -- το build_orientation_source
    περιλαμβάνει τέτοιες θέσεις στην ενότητα "ΠΛΑΝΗΤΕΣ ΚΑΙ ΣΗΜΕΙΑ".
    """
    mismatches = []
    orb_re = re.compile(r"\borb\b\s*[:\-]?\s*(\d{1,2}°\d{1,2}[′'])", re.IGNORECASE)
    for match in orb_re.finditer(text):
        raw_orb = match.group(1).replace("'", "′")
        candidates = [a for a in chart.aspects if a.orb_text == raw_orb]
        start, end = max(0, match.start() - 230), min(len(text), match.end() + 180)
        fragment = text[start:end]
        if not candidates:
            mismatches.append(f"Orb {raw_orb}: δεν υπάρχει στα ελεγμένα δεδομένα του χάρτη.")
            continue
        valid = False
        for a in candidates:
            if not (re.search(_name_pattern(a.first), fragment, re.IGNORECASE)
                    and re.search(_name_pattern(a.second), fragment, re.IGNORECASE)):
                continue
            type_ok = bool(re.search(_ASPECT_FORMS[a.aspect], fragment, re.IGNORECASE))
            weight_ok = bool(re.search(_WEIGHT_FORMS[a.weight], fragment, re.IGNORECASE))
            if type_ok and weight_ok:
                valid = True
                break
        if not valid:
            mismatches.append(
                f"Orb {raw_orb}: δεν συνδέεται τοπικά με το σωστό ζεύγος, τύπο όψης και κατηγορία βαρύτητας."
            )
    return list(dict.fromkeys(mismatches))


def _mentioned_point_names(text: str) -> set[str]:
    """Επιστρέφει τα κανονικά ελληνικά ονόματα σημείων/πλανητών που
    αναφέρονται μέσα στο κείμενο -- αναγνωρίζει και τις δύο γλώσσες
    (ελληνικά μέσω _NAME_FORMS, αγγλικά μέσω _EL_TO_EN_POINT), ώστε να
    δουλεύει είτε ο δείκτης είναι γραμμένος στα ελληνικά είτε σε αγγλικό
    επεξηγηματικό κείμενο μέσα στο τεχνικό δελτίο.

    Fix (deep review, 4ος γύρος, σοβαρό): τα αγγλικά ονόματα ψάχνονταν
    ΧΩΡΙΣ όρια λέξης -- "Sunday planning ability" αναγνωριζόταν λανθασμένα
    ως αναφορά στον Sun, "Marshall-style approach" ως αναφορά στον Mars.
    Τώρα κάθε αγγλικό όνομα έχει \\b όρια λέξης και στις δύο άκρες.
    """
    found = set()
    for name, pattern in _NAME_FORMS.items():
        if re.search(pattern, text, re.IGNORECASE):
            found.add(name)
    for el_name, en_name in _EL_TO_EN_POINT.items():
        if re.search(rf"\b{re.escape(en_name)}\b", text, re.IGNORECASE):
            found.add(el_name)
    return found


_EL_TO_EN_SIGN = dict(zip(SIGNS, (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)))

# Fix (deep review, 10ος γύρος, σοβαρό): πριν το «στέλεχος» κάθε ζωδίου
# ακολουθούνταν από \w* (οποιαδήποτε συνέχεια χαρακτήρων), οπότε "Ζώδιο:
# ΑιγόκερωςΜπανανία" ή "Αιγόκερωxyz" γίνονταν δεκτά ως "Αιγόκερως" -- το
# \w* δεν αγκυρώνει το τέλος της λέξης, απλώς επιτρέπει ό,τι ακολουθεί.
# Τώρα κάθε ζώδιο έχει ρητή, κλειστή λίστα αποδεκτών κλίσεων.
_SIGN_FORMS = {
    "Κριός": r"Κρι(?:ός|ού|ό)",
    "Ταύρος": r"Ταύρ(?:ος|ου|ο)",
    "Δίδυμοι": r"Δίδυμοι|Διδύμων",
    "Καρκίνος": r"Καρκίν(?:ος|ου|ο)",
    "Λέων": r"Λέων|Λέοντ(?:ος|α)",
    "Παρθένος": r"Παρθέν(?:ος|ου|ο)",
    "Ζυγός": r"Ζυγ(?:ός|ού|ό)",
    "Σκορπιός": r"Σκορπι(?:ός|ού|ό)",
    "Τοξότης": r"Τοξότ(?:ης|η)",
    "Αιγόκερως": r"Αιγόκερ(?:ως|ω|ου)",
    "Υδροχόος": r"Υδροχό(?:ος|ου|ο)",
    "Ιχθύες": r"Ιχθύ(?:ες|ων)",
}

_EL_TO_EN_ASPECT = {
    "Σύνοδος": "conjunction", "Εξάγωνο": "sextile", "Τετράγωνο": "square",
    "Τρίγωνο": "trine", "Αντίθεση": "opposition", "Χιαστί όψη 150°": "quincunx",
}


def _exact_sign(value: str) -> str | None:
    """Fix (deep review, 9ος & 10ος γύρος, σοβαρό): για δομημένα πεδία
    (π.χ. το «Ζώδιο» ενός δείκτη) δεν αρκεί το ζώδιο να υπάρχει ΚΑΠΟΥ μέσα
    στην τιμή, ούτε αρκεί ένα "στέλεχος+οτιδήποτε" -- χρειάζεται ΑΚΡΙΒΗΣ
    ισότητα της ΟΛΟΚΛΗΡΗΣ τιμής, μετά την αφαίρεση περιθωριακών κενών, με
    μία από τις ρητά καταγεγραμμένες κλίσεις ενός γνωστού ζωδίου."""
    value = value.strip()
    for el_sign, pattern in _SIGN_FORMS.items():
        if re.fullmatch(pattern, value, re.IGNORECASE):
            return el_sign
    for el_sign, en_sign in _EL_TO_EN_SIGN.items():
        if value.lower() == en_sign.lower():
            return el_sign
    return None


def _exact_point_name(value: str) -> str | None:
    """Ανάλογο του _exact_sign(), για το πεδίο «Σημείο»/«Σημείο 1»/«Σημείο
    2»: ΟΛΟΚΛΗΡΗ η τιμή πρέπει να είναι ένα γνωστό σημείο/πλανήτης, όχι απλώς
    να το περιέχει -- "Σημείο: ΚρόνοςΜπανανία" δεν πρέπει να ταυτοποιείται
    ως "Κρόνος". Τα μοτίβα του _NAME_FORMS έχουν ήδη κλειστή εναλλαγή
    καταλήξεων (όχι \\w*), άρα το re.fullmatch αρκεί για να τα κάνει
    αυστηρά ακριβή."""
    value = value.strip()
    for name, pattern in _NAME_FORMS.items():
        if re.fullmatch(pattern, value, re.IGNORECASE):
            return name
    for el_name, en_name in _EL_TO_EN_POINT.items():
        if value.lower() == en_name.lower():
            return el_name
    return None


def _mentioned_house_number(text: str) -> int | None:
    m = re.search(r"(\d{1,2})\s*(?:ος|η|ο|ου)?\s*Οίκ", text, re.IGNORECASE)
    if not m:
        m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+house", text, re.IGNORECASE)
    if not m:
        m = re.search(r"house\s*(\d{1,2})", text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _mentioned_aspect_type(text: str) -> str | None:
    for el_aspect, pattern in _ASPECT_FORMS.items():
        if el_aspect == "Χιαστί όψη 150°":
            continue
        if re.search(pattern, text, re.IGNORECASE):
            return el_aspect
    for el_aspect, en_aspect in _EL_TO_EN_ASPECT.items():
        if re.search(rf"\b{en_aspect}\b", text, re.IGNORECASE):
            return el_aspect
    return None


def _exact_aspect_type(value: str) -> str | None:
    """Fix (deep review, 11ος γύρος, σοβαρό): ίδιο μοτίβο με _exact_sign()/
    _exact_point_name() -- το πεδίο «Όψη» δεν πρέπει απλώς να ΠΕΡΙΕΧΕΙ έναν
    γνωστό τύπο όψης («Τρίγωνο Μπανανία», «ΤρίγωνοΜπανανία», «trine junk»
    όλα ταυτοποιούνταν λανθασμένα ως «Τρίγωνο» μέσω substring search). Η
    ΟΛΟΚΛΗΡΗ τιμή, μετά την αφαίρεση περιθωριακών κενών, πρέπει να είναι
    ακριβώς ένας γνωστός τύπος όψης.

    Fix (deep review, 12ος γύρος): η «Χιαστί όψη 150°» εξαιρούνταν εδώ
    (κληρονομιά από την παλιά _mentioned_aspect_type, όπου η εξαίρεση
    είχε νόημα -- το μοτίβο της έχει ΟΛΑ τα τμήματα προαιρετικά, άρα σε
    ελεύθερη σάρωση κειμένου το ίδιο το «Χιαστί» θα ταίριαζε πολύ εύκολα
    τυχαία). Με fullmatch πάνω σε ΟΛΟΚΛΗΡΗ την τιμή του πεδίου αυτός ο
    κίνδυνος δεν υπάρχει -- η εξαίρεση εδώ απλώς εμπόδιζε έναν πραγματικό,
    αναγνωρισμένο από τον parser τύπο όψης (ο Astrodienst το επισημαίνει
    ως "s") να περάσει ποτέ τον έλεγχο.
    """
    value = value.strip()
    for el_aspect, pattern in _ASPECT_FORMS.items():
        if re.fullmatch(pattern, value, re.IGNORECASE):
            return el_aspect
    for el_aspect, en_aspect in _EL_TO_EN_ASPECT.items():
        if value.lower() == en_aspect.lower():
            return el_aspect
    return None


def _parse_indicator_fields(text: str) -> dict[str, str]:
    """Δομημένος parser: χωρίζει το κείμενο ενός δείκτη σε υπο-πεδία στην
    ίδια γραμμή, χωρισμένα με «|» (π.χ. «Τύπος: Θέση | Σημείο: Κρόνος |
    Ζώδιο: Αιγόκερως | Οίκος: 6»). Επιστρέφει dict με πεζά, χωρίς τόνους
    κλειδιά -> τιμή.

    Fix (deep review, 9ος γύρος, σοβαρό): ένα πεδίο με ΚΕΝΗ τιμή (π.χ.
    «Ζώδιο: |») παραλείπεται εντελώς εδώ -- πριν το κλειδί έμπαινε στο
    dict με κενή τιμή, οπότε "ζωδιο" in fields ήταν True παρότι δεν
    δόθηκε καμία πραγματική τιμή, κάνοντας τον επόμενο έλεγχο να μην
    εκτελείται καθόλου (if fields["ζωδιο"]: ήταν False, άρα παρακαμπτόταν).
    """
    fields: dict[str, str] = {}
    for segment in text.split("|"):
        if ":" not in segment:
            continue
        key, _, value = segment.partition(":")
        value = value.strip()
        if not value:
            continue
        fields[_strip_greek_diacritics(key.strip().lower())] = value
    return fields


def _indicator_grounding_error(indicator_text: str, chart) -> str | None:
    """Fix (deep review, 7ος γύρος, ΟΡΙΣΤΙΚΗ ΔΙΟΡΘΩΣΗ): οι προηγούμενες
    εκδοχές προσπαθούσαν να μαντέψουν ΣΕ ΠΟΙΟ σημείο αναφέρεται ένας
    δηλωμένος Οίκος/ζώδιο μέσω "παραθύρου εγγύτητας" γύρω από κάθε όνομα.
    Αυτό αποδείχθηκε αναξιόπιστο προς ΚΑΙ τις δύο κατευθύνσεις:
    - "Saturn trine Sun in the 1st house" (ο Ήλιος -- όχι ο Κρόνος -- είναι
      στον 1ο) απορριπτόταν λανθασμένα, γιατί το παράθυρο γύρω από τον
      Κρόνο έφτανε αρκετά μακριά να "δει" το "1st house" του Ήλιου.
    - "Saturn ... in the 3rd house, trine Sun" με τον αριθμό Οίκου πιο
      μακριά από το όριο του παραθύρου περνούσε χωρίς έλεγχο.
    Καμία απόσταση παραθύρου δεν λύνει αυτό αξιόπιστα -- το πρόβλημα είναι
    δομικό: το ελεύθερο κείμενο δεν δηλώνει ρητά ΣΕ ΠΟΙΟ σημείο ανήκει
    κάθε ισχυρισμός.

    Λύση: αντί να μαντεύει, ο validator απαιτεί ΡΗΤΗ δομή ανά δείκτη
    (βλ. _parse_indicator_fields) -- «Τύπος: Θέση | Σημείο: ... | Ζώδιο: ... |
    Οίκος: ...» ή «Τύπος: Όψη | Σημείο 1: ... | Όψη: ... | Σημείο 2: ...».
    Ένας δείκτης χωρίς αυτή τη δομή δεν μπορεί να επαληθευτεί μηχανικά και
    απορρίπτεται ρητά ως τέτοιος -- καμία εικασία, καμία απόσταση χαρακτήρων.
    """
    real_points = {p.name: p for p in chart.points}
    fields = _parse_indicator_fields(indicator_text)
    kind = _strip_greek_diacritics(fields.get("τυπος", "").strip().lower())

    if kind not in ("θεση", "οψη"):
        return (
            "δεν χρησιμοποιεί τη δομημένη μορφή -- αναμένεται «Τύπος: Θέση | Σημείο: ... | "
            "Ζώδιο/Οίκος: ...» ή «Τύπος: Όψη | Σημείο 1: ... | Όψη: ... | Σημείο 2: ...»"
        )

    if kind == "θεση":
        # Fix (deep review, 10ος γύρος, σοβαρό): _mentioned_point_names()
        # κάνει substring search -- "Σημείο: ΚρόνοςΜπανανία" ταυτοποιούνταν
        # ως "Κρόνος". Το πεδίο «Σημείο» πρέπει να ΕΙΝΑΙ ένα σημείο, όχι απλώς
        # να το περιέχει -- _exact_point_name() απαιτεί πλήρες ταίριασμα.
        name = _exact_point_name(fields.get("σημειο", ""))
        if name is None:
            return "το πεδίο «Σημείο» δεν είναι ακριβώς ένα αναγνωρίσιμο σημείο του χάρτη"
        if name not in real_points:
            return f"αναφέρεται σε «{name}», που δεν υπάρχει στα σημεία αυτού του χάρτη"
        point = real_points[name]
        # Fix (deep review, 8ος & 9ος γύρος, σοβαρό): πριν, ένα ΑΓΝΩΣΤΟ
        # ζώδιο ή μη αριθμητικός Οίκος έκανε το sign/house_m να είναι
        # None, οπότε το if απλώς δεν εκτελούνταν -- «Ζώδιο: Μπανανία» ή
        # «Οίκος: άγνωστος» περνούσαν σιωπηλά. Επίσης, το re.search
        # δεχόταν πρόσθετα σκουπίδια γύρω από μια έγκυρη τιμή («Οίκος:
        # abc6xyz» έβρισκε το «6»· «Ζώδιο: Αιγόκερως Μπανανία» έβρισκε το
        # «Αιγόκερως»). Τώρα απαιτείται η ΟΛΟΚΛΗΡΗ τιμή του πεδίου να
        # είναι, μετά την αφαίρεση κενών, ΑΚΡΙΒΩΣ ένα αναγνωρίσιμο ζώδιο ή
        # έναν ακέραιο 1–12 -- τίποτα άλλο.
        if "ζωδιο" in fields:
            raw_sign = fields["ζωδιο"]
            sign = _exact_sign(raw_sign)
            if sign is None:
                return f"το πεδίο «Ζώδιο» («{raw_sign}») δεν είναι ακριβώς ένα αναγνωρίσιμο ζώδιο"
            if sign != point.sign:
                return f"λέει ότι ο/η {point.name} είναι σε {sign}, ενώ στον χάρτη είναι σε {point.sign}"
        if "οικος" in fields:
            raw_house = fields["οικος"]
            house_m = re.fullmatch(r"\d{1,2}", raw_house)
            if not house_m:
                return f"το πεδίο «Οίκος» («{raw_house}») πρέπει να είναι ακριβώς ένας ακέραιος 1–12, χωρίς άλλο κείμενο"
            house = int(house_m.group())
            if not 1 <= house <= 12:
                return f"το πεδίο «Οίκος» δηλώνει {house}, εκτός του έγκυρου εύρους 1–12"
            if house != point.house:
                return (
                    f"λέει ότι ο/η {point.name} είναι στον {house}ο Οίκο, "
                    f"ενώ στον χάρτη είναι στον {point.house}ο"
                )
        if "ζωδιο" not in fields and "οικος" not in fields:
            return "έχει Τύπος: Θέση αλλά δεν δηλώνει ούτε Ζώδιο ούτε Οίκο -- δεν υπάρχει τίποτα να επαληθευτεί"
        return None

    # kind == "οψη"
    p1, p2 = _exact_point_name(fields.get("σημειο 1", "")), _exact_point_name(fields.get("σημειο 2", ""))
    if p1 is None or p2 is None:
        return "τα πεδία «Σημείο 1»/«Σημείο 2» δεν αναφέρουν ακριβώς από ένα αναγνωρίσιμο σημείο το καθένα"
    fake = {p1, p2} - set(real_points)
    if fake:
        return f"αναφέρεται σε «{', '.join(sorted(fake))}», που δεν υπάρχει στα σημεία αυτού του χάρτη"
    aspect_type = _exact_aspect_type(fields.get("οψη", ""))
    if aspect_type is None:
        return "το πεδίο «Όψη» δεν αναφέρει αναγνωρίσιμο τύπο όψης"
    for a in chart.aspects:
        if {a.first, a.second} == {p1, p2} and a.aspect == aspect_type:
            return None
    return f"δηλώνει όψη «{aspect_type}» μεταξύ {p1} και {p2}, που δεν υπάρχει στο Παράρτημα Όψεων του χάρτη"


def _indicator_kind(indicator_text: str) -> str:
    """Επιστρέφει «θεση», «οψη», ή «» (κενό αν δεν αναγνωρίζεται) από το
    πεδίο «Τύπος:» ενός δείκτη -- κοινή βάση για τα νέα _real_aspect_weight()
    και _indicator_points()."""
    fields = _parse_indicator_fields(indicator_text)
    return _strip_greek_diacritics(fields.get("τυπος", "").strip().lower())


def _real_aspect_weight(indicator_text: str, chart) -> str | None:
    """Fix (πραγματικό αίτημα χρήστη, μετά από συζήτηση): επιστρέφει την
    ΠΡΑΓΜΑΤΙΚΗ κατηγορία βαρύτητας μιας όψης από το chart.aspects -- όχι
    ό,τι δηλώθηκε στο πεδίο «Βαρύτητα:» του δείκτη (που θα μπορούσε να
    είναι λάθος ή απλώς αντιγραμμένο χωρίς έλεγχο). Πριν, ο validator δεν
    ήλεγχε ΚΑΘΟΛΟΥ τη βαρύτητα ενός δείκτη -- μία μεμονωμένη «Πλατιά αλλά
    έγκυρη» όψη περνούσε σιωπηλά σαν πλήρης τεκμηρίωση, αντίθετα με τον
    ρητό κανόνα ιεράρχησης βαρύτητας. Επιστρέφει None για δείκτη Θέσης
    (δεν έχει βαρύτητα) ή αν η όψη δεν είναι έγκυρη/υπαρκτή."""
    if _indicator_kind(indicator_text) != "οψη":
        return None
    fields = _parse_indicator_fields(indicator_text)
    p1 = _exact_point_name(fields.get("σημειο 1", ""))
    p2 = _exact_point_name(fields.get("σημειο 2", ""))
    aspect_type = _exact_aspect_type(fields.get("οψη", ""))
    if not (p1 and p2 and aspect_type):
        return None
    for a in chart.aspects:
        if {a.first, a.second} == {p1, p2} and a.aspect == aspect_type:
            return a.weight
    return None


def _indicator_points(indicator_text: str) -> set[str]:
    """Τα σημεία που εμπλέκονται σε έναν δείκτη όψης (Σημείο 1/Σημείο 2) --
    χρησιμοποιείται για τη νέα εξαίρεση «δύο όψεις Πλατιά αλλά έγκυρη με
    κοινό σημείο» (μηχανική προσέγγιση του "ίδιο θέμα", όχι σημασιολογική
    εικασία)."""
    fields = _parse_indicator_fields(indicator_text)
    points = {_exact_point_name(fields.get("σημειο 1", "")), _exact_point_name(fields.get("σημειο 2", ""))}
    points.discard(None)
    return points


def _indicator_fingerprint(indicator_text: str, chart):
    """Fix (deep review, 5ος γύρος, ξαναγράφτηκε στον 7ο γύρο για να
    χρησιμοποιεί τη δομημένη μορφή αντί για εικασία): το ίδιο τεχνικό
    στοιχείο μπορούσε να γραφτεί με δύο διαφορετικές διατυπώσεις και να
    μετρήσει ως δύο ΔΙΑΚΡΙΤΟΙ δείκτες. Επιστρέφει ένα hashable "αποτύπωμα"
    του ΣΥΓΚΕΚΡΙΜΕΝΟΥ τεχνικού ισχυρισμού, διαβασμένο απευθείας από τα
    δομημένα πεδία -- δύο δείκτες με το ίδιο αποτύπωμα είναι το ίδιο
    στοιχείο, όσο διαφορετικό κι αν είναι το ελεύθερο κείμενο γύρω τους."""
    fields = _parse_indicator_fields(indicator_text)
    kind = _strip_greek_diacritics(fields.get("τυπος", "").strip().lower())
    if kind == "θεση":
        name = _exact_point_name(fields.get("σημειο", ""))
        if name is None:
            return None
        if fields.get("οικος"):
            m = re.fullmatch(r"\d{1,2}", fields["οικος"])
            if m:
                return ("position_house", name, int(m.group()))
        if fields.get("ζωδιο"):
            sign = _exact_sign(fields["ζωδιο"])
            if sign:
                return ("position_sign", name, sign)
        return ("point_only", name)
    if kind == "οψη":
        p1, p2 = _exact_point_name(fields.get("σημειο 1", "")), _exact_point_name(fields.get("σημειο 2", ""))
        aspect_type = _exact_aspect_type(fields.get("οψη", ""))
        if p1 is not None and p2 is not None and aspect_type:
            return ("aspect", frozenset({p1, p2}), aspect_type)
    return None


def _talent_documentation_block_errors(audit_text: str, talent_titles: list[str], chart=None) -> list[str]:
    """Πραγματικός έλεγχος τεκμηρίωσης ανά ταλέντο (fix μετά από 2ο γύρο
    chat κριτικής, σημείο #4). Η προηγούμενη εκδοχή:
    - έψαχνε μέσα σε σταθερό παράθυρο 400 χαρακτήρων μετά το όνομα του
      ταλέντου, οπότε οι δείκτες του ΕΠΟΜΕΝΟΥ ταλέντου μπορούσαν λανθασμένα
      να μετρήσουν ως τεκμηρίωση του προηγούμενου·
    - δεχόταν την ίδια την ΛΕΞΗ «Δείκτης 1» χωρίς περιεχόμενο μετά.

    Τώρα: χωρίζει το τεχνικό δελτίο σε πραγματικά μπλοκ ανά «ΤΑΛΕΝΤΟ: <τίτλος>»
    (κάθε μπλοκ σταματά ακριβώς στο επόμενο «ΤΑΛΕΝΤΟ:» ή σε γνωστή επόμενη
    ενότητα), και μέσα σε κάθε μπλοκ απαιτεί είτε (α) δύο μη κενούς και μη
    πανομοιότυπους δείκτες, είτε (β) έναν μοναδικό ισχυρό δείκτη ΜΑΖΙ με
    αιτιολόγηση ισχύος/συνάφειας -- και τα δύο με πραγματικό περιεχόμενο.
    """
    if not talent_titles:
        return []

    markers = list(re.finditer(r"ΤΑΛΕΝΤΟ\s*:\s*(?P<title>[^\r\n]+)", audit_text, re.IGNORECASE))
    if not markers:
        return [
            "Το τεχνικό δελτίο δεν χρησιμοποιεί καθόλου δομημένα μπλοκ «ΤΑΛΕΝΤΟ: <τίτλος>» "
            "για την τεκμηρίωση κάθε ταλέντου ξεχωριστά."
        ]

    boundary = re.compile(r"^(?:Ιεράρχηση|Τελικός\s+έλεγχος|ΕΓΚΕΚΡΙΜΕΝ)", re.IGNORECASE)

    def block_for(idx: int) -> str:
        start = markers[idx].end()
        end = markers[idx + 1].start() if idx + 1 < len(markers) else len(audit_text)
        block = audit_text[start:end]
        # Επιπλέον ασφάλεια: αν μέσα στο (θεωρητικά τελευταίο) μπλοκ υπάρχει
        # γνωστή επόμενη ενότητα, κόψε εκεί -- δεν πρέπει ποτέ να "διαρρεύσει"
        # τεκμηρίωση άλλου ταλέντου ή του παραρτήματος όψεων.
        for line in block.splitlines():
            if boundary.match(line.strip()):
                block = block[:block.find(line)]
                break
        return block

    def nonempty(value: str | None) -> bool:
        return bool(value) and len(re.sub(r"[\s.·-]+", "", value)) >= 3

    def normalize(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().lower()).rstrip(".·")

    check_grounding = chart is not None

    errors = []
    for title in talent_titles:
        title = title.strip().rstrip(".·")
        if not title:
            continue
        # Fix (deep review): πριν χρησιμοποιούσε .startswith(), που έκανε
        # π.χ. «Ταλέντο 1» να ταιριάζει λανθασμένα με το μπλοκ του «Ταλέντο
        # 10» (αφού "ταλέντο 10".startswith("ταλέντο 1") == True) -- ένα
        # ταλέντο χωρίς καθόλου τεκμηρίωση περνούσε σιωπηλά "δανειζόμενο"
        # τους δείκτες ενός άλλου. Τώρα απαιτείται ΑΚΡΙΒΕΣ ταίριασμα τίτλου
        # (μετά από κανονικοποίηση κεφαλαίων/κενών/τελικής στίξης).
        norm_title = normalize(title)
        match_idx = next(
            (i for i, m in enumerate(markers) if normalize(m.group("title")) == norm_title),
            None,
        )
        if match_idx is None:
            errors.append(f"Δεν βρέθηκε δομημένο μπλοκ «ΤΑΛΕΝΤΟ: {title}» στο τεχνικό δελτίο.")
            continue
        block = block_for(match_idx)
        d1 = re.search(r"Δείκτης\s*1\s*:\s*([^\r\n]*)", block, re.IGNORECASE)
        d2 = re.search(r"Δείκτης\s*2\s*:\s*([^\r\n]*)", block, re.IGNORECASE)
        two_ok = nonempty(d1.group(1) if d1 else None) and nonempty(d2.group(1) if d2 else None)
        if two_ok and re.sub(r"\s+", " ", d1.group(1).strip().lower()) == re.sub(r"\s+", " ", d2.group(1).strip().lower()):
            two_ok = False  # ίδιο περιεχόμενο -- δεν μετράει ως δύο διακριτοί δείκτες
        if two_ok and check_grounding:
            # Fix (deep review, 5ος γύρος): ίδιο κείμενο ήδη πιάνεται πάνω,
            # αλλά «Κρόνος, πειθαρχία» και «Κρόνος, οργάνωση» έχουν
            # διαφορετικό ωμό κείμενο ενώ είναι το ΙΔΙΟ τεχνικό στοιχείο
            # (ίδιο fingerprint) -- πιάνεται εδώ.
            fp1 = _indicator_fingerprint(d1.group(1), chart)
            fp2 = _indicator_fingerprint(d2.group(1), chart)
            if fp1 is not None and fp1 == fp2:
                two_ok = False
            else:
                # Fix (πραγματικό αίτημα χρήστη): ο validator ΔΕΝ έλεγχε ποτέ
                # την πραγματική βαρύτητα ενός δείκτη -- μία "Πλατιά αλλά
                # έγκυρη" όψη περνούσε σιωπηλά σαν να ήταν πλήρης τεκμηρίωση,
                # αντίθετα με τον ρητό κανόνα "οι Πλατιές χρησιμοποιούνται
                # μόνο υποστηρικτικά, ποτέ ως αυτοτελής δείκτης". Τώρα
                # απαιτείται τουλάχιστον ΕΝΑΣ δείκτης πρωτεύουσας βαρύτητας
                # (Θέση, ή Όψη με πραγματική βαρύτητα Στενή/ισχυρή ή
                # Κανονική) -- με μία ρητή, στενή εξαίρεση: δύο ΔΙΑΚΡΙΤΕΣ
                # όψεις «Πλατιά αλλά έγκυρη» που μοιράζονται ένα κοινό σημείο
                # (μηχανική προσέγγιση του "ίδιο θέμα", χωρίς σημασιολογική
                # εικασία -- αν αξίζει ή όχι δεν αποφασίζεται με μάντεμα).
                w1, w2 = _real_aspect_weight(d1.group(1), chart), _real_aspect_weight(d2.group(1), chart)
                kind1 = _indicator_kind(d1.group(1))
                kind2 = _indicator_kind(d2.group(1))
                if kind1 in ("θεση", "οψη") and kind2 in ("θεση", "οψη"):
                    primary1 = kind1 == "θεση" or w1 in ("Στενή/ισχυρή", "Κανονική")
                    primary2 = kind2 == "θεση" or w2 in ("Στενή/ισχυρή", "Κανονική")
                    if not (primary1 or primary2):
                        both_wide = w1 == "Πλατιά αλλά έγκυρη" and w2 == "Πλατιά αλλά έγκυρη"
                        shared_point = both_wide and (_indicator_points(d1.group(1)) & _indicator_points(d2.group(1)))
                        if not shared_point:
                            two_ok = False
                # Αν κάποιος από τους δύο δεν είναι καν δομημένος (kind == ""),
                # ΔΕΝ ακυρώνουμε εδώ -- αφήνουμε το two_ok όπως είναι, ώστε να
                # φτάσει στο grounding-check παρακάτω και να πάρει το πιο
                # συγκεκριμένο μήνυμα "δεν χρησιμοποιεί τη δομημένη μορφή".
        single = re.search(r"Μοναδικός\s+ισχυρός\s+δείκτης\s*:\s*([^\r\n]*)", block, re.IGNORECASE)
        justification = re.search(r"Αιτιολόγηση\s+ισχύος[^\r\n:]*:\s*([^\r\n]*)", block, re.IGNORECASE)
        single_ok = nonempty(single.group(1) if single else None) and nonempty(justification.group(1) if justification else None)
        if single_ok and check_grounding:
            # Fix (κριτική chat, ακριβής): η δεσμευτική εντολή λέει ρητά ότι ο
            # «Μοναδικός ισχυρός δείκτης» ΠΡΕΠΕΙ να είναι όψη πραγματικής
            # βαρύτητας Στενής/ισχυρής -- ΟΧΙ απλώς "αν τυχαίνει να είναι
            # όψη, τότε ελέγξου τη βαρύτητα". Πριν, ένας δείκτης Θέσης
            # (π.χ. «Τύπος: Θέση | Σημείο: Κρόνος | Οίκος: 6») περνούσε
            # ασύγκριτα ως "μοναδικός ισχυρός", αφού η συνθήκη απόρριψης
            # ενεργοποιούνταν ΜΟΝΟ όταν kind=="οψη" -- ποτέ δεν απαιτούσε
            # ρητά να ΕΙΝΑΙ "οψη". Τώρα η θετική συνθήκη είναι ρητή: πρέπει
            # να είναι όψη ΚΑΙ η πραγματική βαρύτητά της να είναι Στενή/ισχυρή.
            if not (_indicator_kind(single.group(1)) == "οψη" and _real_aspect_weight(single.group(1), chart) == "Στενή/ισχυρή"):
                single_ok = False
        if not (two_ok or single_ok):
            errors.append(
                f"Το ταλέντο «{title}» δεν έχει πλήρη τεκμηρίωση στο μπλοκ του: χρειάζεται είτε δύο μη κενούς "
                "και διαφορετικούς «Δείκτης 1»/«Δείκτης 2» -- τουλάχιστον έναν εκ των οποίων πρωτεύουσας "
                "βαρύτητας (Θέση, ή Όψη Στενής/ισχυρής ή Κανονικής βαρύτητας), ή δύο όψεις «Πλατιά αλλά "
                "έγκυρη» με κοινό σημείο -- είτε «Μοναδικός ισχυρός δείκτης» πραγματικά Στενής/ισχυρής "
                "βαρύτητας ΜΑΖΙ με «Αιτιολόγηση ισχύος και άμεσης συνάφειας»."
            )
        elif check_grounding:
            # Fix (deep review, 3ος & 4ος γύρος): ο έλεγχος πάνω περνάει με
            # ΟΠΟΙΟΔΗΠΟΤΕ μη κενό κείμενο -- εδώ επιβεβαιώνεται ότι κάθε
            # δείκτης πράγματι αντιστοιχεί σε πραγματική θέση ή όψη ΑΥΤΟΥ
            # του χάρτη (βλ. _indicator_grounding_error για τι ακριβώς
            # ελέγχεται και τι σκόπιμα όχι).
            bad_bits = []
            for label, indicator_match in (("Δείκτης 1", d1), ("Δείκτης 2", d2), ("Μοναδικός ισχυρός δείκτης", single)):
                if indicator_match:
                    problem = _indicator_grounding_error(indicator_match.group(1), chart)
                    if problem:
                        bad_bits.append(f"{label} {problem}")
            if bad_bits:
                errors.append(
                    f"Το ταλέντο «{title}» έχει δείκτη(-ες) που δεν επαληθεύονται έναντι του χάρτη: "
                    + "· ".join(bad_bits) + "."
                )
    return errors


def _orientation_audit_errors(chart, audit_text: str, client_text: str = "") -> list[str]:
    """Ελέγχει το τεχνικό δελτίο της απλής παρουσίασης ή το παράρτημα
    της αναλυτικής: ακριβή τοπική αντιστοίχιση και κάλυψη των 5 στενότερων.
    """
    errors = []
    if not audit_text.strip():
        return ["Λείπει το εσωτερικό τεχνικό δελτίο ελέγχου."]
    # Fix (ίδιο πραγματικό bug με το _between_headings, βλ. εκεί για πλήρη
    # εξήγηση): το IGNORECASE δεν εξισώνει τονισμένους/άτονους χαρακτήρες,
    # και το "ΕΣΩΤΕΡΙΚΟ ΤΕΧΝΙΚΟ ΔΕΛΤΙΟ ΕΛΕΓΧΟΥ" (κεφαλαία, χωρίς τόνους)
    # δεν ταίριαζε ποτέ με το τονισμένο "τεχνικ...δελτί".
    if not re.search(
        _strip_greek_diacritics(r"Παράρτημα[^\r\n]{0,100}(?:τεκμηρίωσ|ελέγχ)|τεχνικ[^\r\n]{0,80}δελτί"),
        _strip_greek_diacritics(audit_text), re.IGNORECASE,
    ):
        errors.append("Το τεχνικό δελτίο δεν έχει αναγνωρίσιμη ενότητα ελέγχου τεκμηρίωσης.")
    # Fix (chat κριτική #5, βελτιώθηκε ξανά στο 2ο γύρο #4): ανά-ταλέντο
    # έλεγχος με πραγματικά όρια μπλοκ -- βλ. _talent_documentation_block_errors().
    talent_titles = _extract_talent_titles(client_text) if client_text else []
    if talent_titles:
        errors.extend(_talent_documentation_block_errors(audit_text, talent_titles, chart))
        # Fix (κριτική chat, ακριβής -- έκτος γύρος, δεύτερο εύρημα): πριν
        # ελεγχόταν μόνο η ΜΙΑ κατεύθυνση (κάθε εγκεκριμένος τίτλος έχει
        # μπλοκ στο τεχνικό δελτίο) -- όχι το αντίστροφο. Ένα ΕΠΙΠΛΕΟΝ
        # ΤΑΛΕΝΤΟ: μπλοκ στο τεχνικό δελτίο, με τίτλο που δεν υπάρχει καν
        # στο καθαρό παραδοτέο, περνούσε εντελώς απαρατήρητο -- ασυνέπεια
        # ανάμεσα στα δύο Word χωρίς κανένα μήνυμα. Τώρα ελέγχεται και η
        # αντίστροφη κατεύθυνση.
        approved_norm = {_norm_title(t) for t in talent_titles}
        audit_titles = re.findall(r"^\s*ΤΑΛΕΝΤΟ\s*:\s*(.+?)\s*$", audit_text, re.MULTILINE | re.IGNORECASE)
        for raw_title in audit_titles:
            if _norm_title(raw_title) not in approved_norm:
                errors.append(
                    f"Το τεχνικό δελτίο περιέχει το ταλέντο «{raw_title}», το οποίο δεν εμφανίζεται "
                    "στο καθαρό παραδοτέο."
                )
    elif not re.search(
        r"Δείκτης\s*\d|Μοναδικός\s+ισχυρός\s+δείκτης"
        r"|(?:τουλάχιστον\s+δύο|δύο\s+ή\s+περισσότερους)\s+διακριτ"
        r"|ιδιαίτερα\s+ισχυρ[όή][^\r\n]{0,40}(?:άμεσ|δείκτ)",
        audit_text, re.IGNORECASE,
    ):
        # Fallback όταν δεν έχουμε τίτλους ταλέντων από το καθαρό κείμενο
        # (π.χ. η "Αναλυτική" λειτουργία, όπου client_text δεν δίνεται
        # ξεχωριστά) -- γενικός έλεγχος όπως πριν, καλύτερο από τίποτα.
        errors.append(
            "Το τεχνικό δελτίο δεν δηλώνει ότι κάθε ταλέντο στηρίχθηκε είτε σε δύο ή περισσότερους "
            "διακριτούς δείκτες είτε σε έναν ιδιαίτερα ισχυρό και άμεσο δείκτη."
        )
    if not re.search(r"(?:ιεράρχηση|βαρύτητα).{0,120}(?:Στεν|Ισχυρ|Κανονικ|Πλατι)", audit_text, re.IGNORECASE | re.DOTALL):
        errors.append("Το τεχνικό δελτίο δεν δηλώνει καθαρά την ιεράρχηση βαρύτητας των όψεων.")
    # Fix (πραγματικό bug, εντοπίστηκε με πραγματικό ανέβασμα .docx): εδώ
    # καλούνταν _orientation_technical_mismatches(), μια ΠΑΛΙΟΤΕΡΗ συνάρτηση
    # από πριν τη δομημένη μορφή Τύπος:/Σημείο: -- σαρώνει ΟΛΟ το ελεύθερο
    # κείμενο του τεχνικού δελτίου για οποιαδήποτε αναφορά "orb X°Y′" και
    # ελέγχει με "παράθυρο εγγύτητας" αν εκεί κοντά αναφέρεται το σωστό
    # ζεύγος/τύπος/βαρύτητα. Το πρόβλημα: η δεσμευτική εντολή μας ΖΗΤΑΕΙ
    # ρητά αφηγηματικές επαναλήψεις ενός orb σε φυσική γλώσσα αλλού στο
    # δελτίο (π.χ. «Δείκτης 1 είναι από μόνος του "Μοναδικός ισχυρός
    # δείκτης" (Στενή/Ισχυρή τριγωνική όψη Ήλιου–Κρόνου, orb 0°14′)» --
    # εδώ το "τριγωνική" δεν ταιριάζει με το μοτίβο "Τρίγωνο", παράγοντας
    # ΨΕΥΔΕΣ σφάλμα ασυμφωνίας, ΠΑΡΟΛΟ που το ίδιο orb ήταν ήδη πλήρως και
    # σωστά τεκμηριωμένο στο δομημένο πεδίο Δείκτης 1. Η δομημένη
    # επαλήθευση (_indicator_grounding_error, παρακάτω μέσω
    # _talent_documentation_block_errors) καλύπτει ήδη πλήρως κάθε
    # δηλωμένο δείκτη -- αυτός ο παλιός, ελεύθερου-κειμένου έλεγχος είναι
    # πλέον περιττός και μόνο προσθέτει ψευδή θετικά σε φυσιολογικό
    # αφηγηματικό κείμενο. Αφαιρέθηκε από τη ροή (η συνάρτηση παραμένει
    # ορισμένη, χωρίς πλέον να καλείται).
    #
    # Fix (deep review, προηγούμενος γύρος): πριν ελεγχόταν μηχανικά μόνο η
    # κάλυψη των 5 στενότερων όψεων -- σε πυκνό χάρτη μπορεί να υπάρχουν
    # 15-20+ ακόμη όψεις με έγκυρη βαρύτητα (Στενή/ισχυρή ή Κανονική) που
    # έμεναν εντελώς εκτός ελέγχου, αφήνοντας τον αριθμό ταλέντων στην τύχη
    # της εξαντλητικότητας της συγκεκριμένης συνεδρίας παραγωγής. Τώρα
    # ελέγχεται η πλήρης κάλυψη κάθε όψης αυτής της κατηγορίας βαρύτητας,
    # όχι μόνο των 5 στενότερων -- συμμετρικό με την ενημερωμένη οδηγία στη
    # δεσμευτική εντολή.
    covered_weights = ("Στενή/ισχυρή", "Κανονική")
    for aspect in sorted(chart.aspects, key=lambda item: item.orb):
        if aspect.weight not in covered_weights:
            continue
        co, orb_ok, type_ok, weight_ok, decision_ok = _co_occurs_with_orb(
            audit_text, aspect.first, aspect.second, aspect.orb_text,
            aspect.aspect, aspect.weight, set(talent_titles),
        )
        if not (co and orb_ok and type_ok and weight_ok and decision_ok):
            errors.append(
                f"Η όψη {aspect.first}–{aspect.second} ({aspect.aspect}, orb {aspect.orb_text}, {aspect.weight}) "
                "δεν τεκμηριώνεται πλήρως στο τεχνικό δελτίο -- πρέπει να δηλώνεται ρητά αν χρησιμοποιείται "
                "ή γιατί εξαιρείται, όχι μόνο να αναφέρεται."
            )
    return list(dict.fromkeys(errors))


def _simple_presentation_technical_terms(text: str) -> list[str]:
    """Η απλή έκδοση πελάτη δεν πρέπει να εκθέτει τεχνική αστρολογική γλώσσα."""
    # Fix (English mode, κριτική): οι λίστες πιάνουν πλέον και τα αγγλικά
    # τεχνικά ονόματα -- πριν, ένα αγγλικό παραδοτέο μπορούσε να διαρρεύσει
    # π.χ. "Saturn" ή "square aspect" χωρίς να το εντοπίσει κανένα μοτίβο,
    # γιατί όλα ήταν αποκλειστικά ελληνικά.
    patterns = {
        "αριθμητικό orb": r"\d{1,2}°\d{1,2}[′']|\borb\b",
        "πλανήτες/σημεία": r"\b(?:Ήλιος|Σελήνη|Ερμής|Αφροδίτη|Άρης|Δίας|Κρόνος|Ουρανός|Ποσειδώνας|Πλούτωνας|Χείρωνας|Βόρειος\s+Δεσμός|Νότιος\s+Δεσμός|Μεσουράνημα|Ωροσκόπος"
                        r"|Sun|Moon|Mercury|Venus|Mars|Jupiter|Saturn|Uranus|Neptune|Pluto|Chiron|North\s+Node|South\s+Node|Midheaven|Ascendant)\b",
        "Οίκοι/κυβερνήτες": r"\b(?:\d{1,2}(?:ο|ος|ου)\s+)?Ο[ίι]κ(?:ος|ου|οι|ων)|\bκυβερνήτ|\b(?:\d{1,2}(?:st|nd|rd|th)\s+)?House\b|\bruler(?:s)?\b",
        "τεχνικοί τύποι όψεων": r"\b(?:σύνοδος|τρίγωνο|εξάγωνο|τετράγωνο|αντίθεση|χιαστί\s+όψη|conjunction|trine|sextile|square|opposition|quincunx)\b",
        "κατηγορίες βαρύτητας": r"Στεν(?:ή|ης)/Ισχυρ|Πλατιά\s+αλλά\s+έγκυρη|Πολύ\s+πλατιά/Δευτερεύουσα|Narrow/Strong|Wide\s+but\s+valid|Very\s+wide/Secondary",
    }
    return [label for label, pattern in patterns.items() if re.search(pattern, text, re.IGNORECASE)]


_GREEK_TO_LATIN = {
    "α": "a", "β": "v", "γ": "g", "δ": "d", "ε": "e", "ζ": "z", "η": "i",
    "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m", "ν": "n", "ξ": "x",
    "ο": "o", "π": "p", "ρ": "r", "σ": "s", "ς": "s", "τ": "t", "υ": "y",
    "φ": "f", "χ": "ch", "ψ": "ps", "ω": "o",
}


def _strip_greek_diacritics(text: str) -> str:
    """Αφαιρεί τόνους/διαλυτικά (π.χ. «Γαβριέλα» -> «Γαβριελα») για χαλαρή
    σύγκριση, χωρίς να αγγίζει τα ίδια τα γράμματα."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def _rough_transliterate(text: str) -> str:
    """Πρόχειρη μεταγραφή ελληνικών σε λατινικά, μόνο για να εντοπίσει αν το
    μοντέλο έγραψε ένα ελληνικό όνομα με λατινικούς χαρακτήρες (π.χ. "GAVRIELA")."""
    stripped = _strip_greek_diacritics(text).lower()
    return "".join(_GREEK_TO_LATIN.get(ch, ch) for ch in stripped)


def _name_consistency_issue(personal: dict | None, text: str) -> str | None:
    """Ελέγχει ότι το δηλωμένο όνομα εμφανίζεται στο παραδοτέο ακριβώς όπως
    δόθηκε (με τόνους, με ελληνικούς χαρακτήρες) -- όχι μόνο ότι *κάποιο*
    όνομα υπάρχει. Πραγματικό περιστατικό: το μοντέλο έγραψε "GAVRIELA" ή
    "Γαβριελα" (χωρίς τόνο) αντί για το δηλωμένο "Γαβριέλα"· ο validator δεν
    το έπιανε καθόλου πριν, οπότε χρειαζόταν πάντα τελευταίο ανθρώπινο έλεγχο.
    """
    if not personal:
        return None
    expected = (personal.get("Όνομα") or "").strip()
    if not expected:
        return None
    if expected in text:
        return None
    stripped_expected = _strip_greek_diacritics(expected)
    stripped_text = _strip_greek_diacritics(text)
    if stripped_expected and stripped_expected in stripped_text:
        return (
            f"Το όνομα εμφανίζεται στο έγγραφο χωρίς τους σωστούς τόνους/διαλυτικά "
            f"(αναμενόταν «{expected}»)."
        )
    translit_expected = _rough_transliterate(expected)
    translit_text = _rough_transliterate(text)
    if translit_expected and len(translit_expected) >= 3 and translit_expected in translit_text:
        return f"Το όνομα «{expected}» φαίνεται να γράφτηκε με λατινικούς χαρακτήρες αντί για ελληνικούς."
    return f"Το δηλωμένο όνομα «{expected}» δεν εντοπίστηκε καθόλου μέσα στο έγγραφο."


# Fix (2), critique: η γενική λέξη «υγεία/υγείας» έμπαινε στο ίδιο μοτίβο με
# τα κλινικά επαγγέλματα, οπότε κάτι σαν "τεχνολογία υγείας" ενεργοποιούσε
# τον αυστηρό ιατρικό έλεγχο σαν να ήταν "γιατρός". Ο κανόνας πρέπει να
# ενεργοποιείται μόνο από συγκεκριμένα κλινικά επαγγέλματα, όχι από το γενικό θέμα.
# Fix (deep review κριτική #3, σοβαρό): πριν το μοτίβο ήταν αμιγώς ελληνικό
# -- ένα αγγλικό παραδοτέο που πρότεινε "doctor" ή "surgeon" περνούσε χωρίς
# να ενεργοποιήσει καθόλου τον αυστηρό έλεγχο τεκμηρίωσης Υγείας.
_HEALTH_CAREER_RE = re.compile(
    r"\b(?:ιατρ(?:ός|ού|ική|ικής)|γιατρ(?:ός|ού)|νοσηλευτ\w*|φαρμακοποι\w*|"
    r"ψυχολόγ\w*|εργοθεραπευτ\w*|διατροφολόγ\w*|φυσικοθεραπευτ\w*|"
    r"οδοντίατρ\w*|κτηνίατρ\w*|μαία|μαιευτ\w*"
    r"|doctors?|physicians?|surgeons?|nurses?|pharmacists?|psychologists?|"
    r"dietitians?|nutritionists?|occupational\s+therapists?|physiotherapists?|"
    r"dentists?|veterinarians?|midwi(?:fe|ves))\b",
    re.IGNORECASE,
)


def _career_norm(value: str) -> str:
    value = _strip_greek_diacritics(value).casefold()
    value = re.sub(r"[^a-zα-ω0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _between_headings(text: str, start: str, ends: tuple[str, ...]) -> str:
    """Fix (πραγματικό bug, εντοπίστηκε με πραγματικό ανέβασμα .docx): το
    re.IGNORECASE αλλάζει πεζά/κεφαλαία αλλά ΔΕΝ εξισώνει τονισμένους με
    άτονους χαρακτήρες -- "Ο" (χωρίς τόνο) και "Ό" (με τόνο) παραμένουν
    διαφορετικοί χαρακτήρες ακόμη και με IGNORECASE. Πολλά πραγματικά
    τεχνικά δελτία γράφουν τις κύριες επικεφαλίδες σε ΚΕΦΑΛΑΙΑ ΧΩΡΙΣ
    τόνους (τυπική, αποδεκτή ελληνική σύμβαση για τίτλους) -- π.χ.
    "ΠΑΡΑΡΤΗΜΑ ΕΠΙΒΕΒΑΙΩΜΕΝΩΝ ΟΨΕΩΝ", ενώ το μοτίβο ήταν γραμμένο
    τονισμένο ("Παράρτημα Επιβεβαιωμένων Όψεων") -- αποτέλεσμα: η
    ενότητα θεωρούνταν εντελώς ανύπαρκτη, παρότι ήταν εκεί, ολόκληρη και
    σωστή. Το ταίριασμα γίνεται τώρα πάνω σε αντίγραφα ΧΩΡΙΣ τόνους και
    από τις δύο πλευρές (μοτίβο ΚΑΙ κείμενο) -- η _strip_greek_diacritics
    διατηρεί το μήκος χαρακτήρα-προς-χαρακτήρα, άρα οι θέσεις που
    βρίσκονται εκεί αντιστοιχούν ακριβώς στις θέσεις του αρχικού
    κειμένου, οπότε η επιστροφή παραμένει το αυθεντικό (τονισμένο) τμήμα.
    Αυτό διορθώνει ταυτόχρονα ΚΑΘΕ κλήση της _between_headings() σε όλο
    το αρχείο, όχι μόνο το ένα σημείο που το αποκάλυψε.
    """
    stripped_text = _strip_greek_diacritics(text)
    stripped_start = _strip_greek_diacritics(start)
    start_match = re.search(r"(?:^|\n)\s*(?:" + stripped_start + ")", stripped_text, re.IGNORECASE)
    if not start_match:
        return ""
    tail = text[start_match.end():]
    stripped_tail = stripped_text[start_match.end():]
    end_positions = []
    for pattern in ends:
        # Fix (πραγματικό bug, εντοπίστηκε με πραγματικό ανέβασμα .docx): το
        # όριο τέλους έψαχνε την επικεφαλίδα ΟΠΟΥΔΗΠΟΤΕ στο υπόλοιπο κείμενο --
        # αν το μοντέλο αναφέρει παρενθετικά το όνομα μιας επόμενης ενότητας
        # ΜΕΣΑ σε πρόταση (π.χ. "(βλ. Ρητή Τεκμηρίωση Τομέα Υγείας)" μέσα στη
        # λίστα εγκεκριμένων τομέων, ως διασταυρούμενη παραπομπή, όχι ως η
        # ίδια η επικεφαλίδα), το όριο έκοβε το μπλοκ εκεί -- πολύ νωρίς,
        # χάνοντας τις τελευταίες καταχωρήσεις. Μια πραγματική επικεφαλίδα
        # είναι πάντα η ΑΡΧΗ της δικής της παραγράφου/γραμμής· μια
        # παρενθετική αναφορά είναι ενσωματωμένη μέσα σε πρόταση. Απαιτείται
        # τώρα η αντιστοιχία να ξεκινάει στην αρχή γραμμής.
        match = re.search(r"(?:^|\n)\s*(?:" + _strip_greek_diacritics(pattern) + ")", stripped_tail, re.IGNORECASE)
        if match:
            end_positions.append(match.start())
    return tail[:min(end_positions)] if end_positions else tail


def _career_consistency_errors(client_text: str, audit_text: str) -> list[str]:
    """Cross-check the client career choices against an explicit audit manifest.

    This is deliberately lexical, not an astrological interpretation engine: the
    model must first commit to approved fields/jobs in the technical audit, and
    the clean version may only reuse that set. Health careers receive an extra
    fail-closed gate because generic words such as care/precision previously
    produced an unsupported doctor recommendation.
    """
    errors: list[str] = []
    approved_fields = _between_headings(
        audit_text,
        r"ΕΓΚΕΚΡΙΜΕΝΟΙ\s+ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ\s+ΤΟΜΕΙΣ",
        (r"ΕΓΚΕΚΡΙΜΕΝΑ\s+ΕΠΑΓΓΕΛΜΑΤΑ", r"ΡΗΤΗ\s+ΤΕΚΜΗΡΙΩΣΗ\s+ΤΟΜΕΑ\s+ΥΓΕΙΑΣ"),
    )
    approved_jobs = _between_headings(
        audit_text,
        r"ΕΓΚΕΚΡΙΜΕΝΑ\s+ΕΠΑΓΓΕΛΜΑΤΑ",
        (r"ΡΗΤΗ\s+ΤΕΚΜΗΡΙΩΣΗ\s+ΤΟΜΕΑ\s+ΥΓΕΙΑΣ", r"Παράρτημα", r"Τελικός\s+έλεγχος"),
    )
    if not approved_fields.strip():
        errors.append("Το τεχνικό δελτίο δεν περιέχει την ενότητα «ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ».")
    if not approved_jobs.strip():
        errors.append("Το τεχνικό δελτίο δεν περιέχει την ενότητα «ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ».")

    # Fix (English mode, κριτική): το ΚΑΘΑΡΟ κείμενο πελάτη μπορεί πλέον να
    # είναι Αγγλικά (βλ. common_topics EN patterns παραπάνω) -- οι ίδιες
    # επικεφαλίδες πρέπει να αναγνωρίζονται και εδώ, αλλιώς κάθε αγγλικό
    # παραδοτέο θα φαινόταν σαν να μην έχει καθόλου δηλωμένους τομείς.
    client_fields = _between_headings(
        client_text,
        r"Επαγγελματικ(?:οί|ούς)\s+Τομ(?:είς|έα)(?:\s+προς\s+Διερεύνηση)?|Career\s+Fields(?:\s+to\s+Explore)?",
        (r"Τελική\s+Σύνθεση", r"Σύνοψη", r"Πλαίσιο\s+Εκπαιδευτικ", r"Final\s+Synthesis"),
    )
    # Fix (deep review κριτική #6, σοβαρό): πριν το approved_fields_norm ήταν
    # ΕΝΑ ενιαίο normalized string (ολόκληρο το μπλοκ κειμένου), και ο έλεγχος
    # ήταν ουσιαστικά "x in ολόκληρο-το-κείμενο" -- δηλαδή substring match.
    # Ένας σύντομος τομέας όπως «Τέχνη» περνούσε επειδή είναι υποσυμβολοσειρά
    # μέσα σε κάτι εντελώς διαφορετικό όπως «Βιοτεχνολογία και τέχνη δεδομένων».
    # Τώρα χτίζεται πραγματικό ΣΥΝΟΛΟ ξεχωριστών, ολόκληρων ονομάτων τομέων
    # (μία γραμμή/bullet ανά τομέα) και ο έλεγχος είναι ακριβής ισότητα.
    approved_fields_norm = {
        _career_norm(re.sub(r"^\s*(?:[-•*]|\d+[.)])\s*", "", line))
        for line in approved_fields.splitlines() if line.strip()
    }
    approved_fields_norm.discard("")
    for raw_line in client_fields.splitlines():
        line = re.sub(r"^[\s#*•-]*", "", raw_line).strip()
        if not line:
            continue
        # Fix (πραγματικό round-trip bug, εντοπίστηκε με πραγματικό ανέβασμα
        # .docx): η αρίθμηση "1." μετατρέπεται σε ΕΓΓΕΝΗ Word λίστα όταν
        # φτιάχνεται το .docx -- ο χαρακτήρας δεν επιβιώνει σαν literal
        # κείμενο στην επαναφόρτωση, οπότε η απαίτηση αριθμού/bullet δεν
        # έβρισκε ΠΟΤΕ αντιστοιχία και ΚΑΝΕΝΑΣ τομέας δεν ελεγχόταν.
        # Τώρα αναγνωρίζεται ο τίτλος τομέα αποκλείοντας τις γνωστές
        # υπο-γραμμές (Γιατί/Ενδεικτικά), αντί να απαιτείται ο δείκτης.
        m = re.match(r"\d+[.)]\s*(.+)", line) or re.match(r"[-•*]\s*(.+)", raw_line.strip())
        field = m.group(1) if m else line
        if re.match(r"Γιατί\s+μπορεί\s+να\s+ταιριάζει|Ενδεικτικά\s+επαγγέλματα|Why\s+it\s+may\s+fit|Example\s+Careers", field, re.IGNORECASE):
            continue
        field = re.sub(r"\*+", "", field).strip()
        if field and _career_norm(field) not in approved_fields_norm:
            errors.append(f"Ο επαγγελματικός τομέας «{field}» δεν έχει εγκριθεί στο τεχνικό δελτίο.")

    # Fix (3), κριτική: το προηγούμενο re.split(r"[,;]", ...) έσπαγε λανθασμένα
    # μέσα σε παρενθετικές επεξηγήσεις (π.χ. "ειδική καινοτομίας (ρόλος που
    # αναζητά νέες, μη συμβατικές λύσεις)" γινόταν δύο ψευδο-επαγγέλματα).
    # Τώρα ο διαχωρισμός σέβεται τις παρενθέσεις, και η σύγκριση γίνεται στο
    # βασικό όνομα του επαγγέλματος (πριν την πρώτη παρένθεση) -- η παρενθετική
    # επεξήγηση είναι ελεύθερο επεξηγηματικό κείμενο, όχι μέρος του εγκεκριμένου
    # ονόματος.
    # Οριοθέτες λίστας: κόμμα, ελληνικό/λατινικό ερωτηματικό, και η άνω τελεία
    # (·, U+00B7 ή U+0387) που χρησιμοποιείται στο τεχνικό δελτίο ανάμεσα σε
    # κατηγορίες επαγγελμάτων -- η απουσία της προηγουμένως ένωνε λανθασμένα
    # το τελευταίο επάγγελμα μιας κατηγορίας με το πρώτο της επόμενης.
    _JOB_DELIMITERS = ",;··"

    def _split_job_list(job_line: str) -> list[str]:
        jobs: list[str] = []
        depth = 0
        current = []
        for ch in job_line:
            if ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth = max(0, depth - 1)
                current.append(ch)
            elif ch in _JOB_DELIMITERS and depth == 0:
                jobs.append("".join(current))
                current = []
            else:
                current.append(ch)
        if current:
            jobs.append("".join(current))
        return jobs

    def _base_job_name(job: str) -> str:
        # αφαιρεί τελική παρενθετική επεξήγηση, και οτιδήποτε προηγείται μιας
        # ετικέτας αρίθμησης κατηγορίας όπως "(2)" (π.χ. "ανά τομέα: (1) " πριν
        # το πρώτο επάγγελμα μιας λίστας) -- η ετικέτα δεν είναι μέρος του ονόματος.
        job = re.sub(r"^.*\(\d+\)\s*", "", job)
        return re.sub(r"\s*\([^)]*\)\s*$", "", job).strip()

    approved_jobs_norm = {
        _career_norm(_base_job_name(j)) for j in _split_job_list(approved_jobs.replace("\n", ","))
    }
    approved_jobs_norm.discard("")
    for match in re.finditer(
        r"(?:Ενδεικτικά\s+επαγγέλματα|Example\s+Careers(?:\s+per\s+Field)?)\s*:\s*([^\r\n]+)",
        client_text, re.IGNORECASE,
    ):
        job_line = re.sub(r"\*+", "", match.group(1))
        for job in _split_job_list(job_line):
            job = job.strip().rstrip(".")
            base = _base_job_name(job)
            if len(base) >= 3 and _career_norm(base) not in approved_jobs_norm:
                errors.append(f"Το επάγγελμα «{job}» δεν έχει εγκριθεί στο τεχνικό δελτίο.")

    if _HEALTH_CAREER_RE.search(client_text):
        health_block = _between_headings(
            audit_text,
            r"ΡΗΤΗ\s+ΤΕΚΜΗΡΙΩΣΗ\s+ΤΟΜΕΑ\s+ΥΓΕΙΑΣ",
            (r"Παράρτημα", r"Τελικός\s+έλεγχος", r"ΕΓΚΕΚΡΙΜΕΝΟΙ\s+ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ"),
        )
        # Fix (1), κριτική: πριν ελεγχόταν μόνο αν οι λέξεις "Δείκτης 1"/"Δείκτης 2"
        # υπήρχαν -- το μοντέλο μπορούσε να γράψει δύο ασήμαντους "δείκτες" και να
        # περάσει. Τώρα εξάγεται το περιεχόμενο μετά από κάθε ετικέτα και ελέγχεται
        # ότι (α) οι δύο δείκτες δεν είναι κενοί, (β) δεν είναι ουσιαστικά ο ίδιος
        # δείκτης γραμμένος δύο φορές, και (γ) το περιεχόμενο κάθε δείκτη εμφανίζεται
        # πραγματικά μέσα στο Παράρτημα Επιβεβαιωμένων Όψεων του ίδιου τεχνικού
        # δελτίου -- όχι απλώς κάπου στο ελεύθερο κείμενο.
        appendix_block = _between_headings(
            audit_text,
            r"Παράρτημα\s+Επιβεβαιωμένων\s+Όψεων",
            (r"Τελικός\s+έλεγχος",),
        )
        appendix_norm = _career_norm(appendix_block)

        def _indicator_text(label: str) -> str | None:
            match = re.search(rf"Δείκτης\s*{label}\s*[:\-]?\s*([^\n\r]+)", health_block, re.IGNORECASE)
            if not match:
                return None
            return re.sub(r"\*+", "", match.group(1)).strip().rstrip(".")

        indicator_1 = _indicator_text("1")
        indicator_2 = _indicator_text("2")

        if not health_block.strip() or not indicator_1 or not indicator_2:
            errors.append(
                "Ο τομέας/επάγγελμα Υγείας απαιτεί χωριστή «ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ ΤΟΜΕΑ ΥΓΕΙΑΣ» "
                "με το πλήρες περιεχόμενο των «Δείκτης 1» και «Δείκτης 2»· γενικές έννοιες "
                "φροντίδας, ενσυναίσθησης, ακρίβειας ή βελτίωσης δεν αρκούν."
            )
        else:
            norm_1 = _career_norm(indicator_1)
            norm_2 = _career_norm(indicator_2)
            if norm_1 == norm_2:
                errors.append(
                    "Ο «Δείκτης 1» και ο «Δείκτης 2» της τεκμηρίωσης Υγείας είναι ουσιαστικά "
                    "ο ίδιος δείκτης γραμμένος δύο φορές — χρειάζονται δύο πραγματικά διαφορετικοί δείκτες."
                )
            if appendix_norm:
                # Κάθε δείκτης πρέπει να έχει ουσιαστική αντιστοιχία (τουλάχιστον ένα
                # κοινό ζεύγος λέξεων 4+ χαρακτήρων, π.χ. τα δύο ονόματα πλανητών/σημείων
                # και τον τύπο όψης) μέσα στο πραγματικό Παράρτημα Όψεων.
                def _grounded(indicator_norm: str) -> bool:
                    tokens = [t for t in indicator_norm.split() if len(t) >= 4]
                    hits = sum(1 for t in tokens if t in appendix_norm)
                    return hits >= 2 if tokens else False

                if not _grounded(norm_1):
                    errors.append(
                        f"Ο «Δείκτης 1» της τεκμηρίωσης Υγείας («{indicator_1}») δεν εντοπίστηκε "
                        "μέσα στο Παράρτημα Επιβεβαιωμένων Όψεων του τεχνικού δελτίου."
                    )
                if not _grounded(norm_2):
                    errors.append(
                        f"Ο «Δείκτης 2» της τεκμηρίωσης Υγείας («{indicator_2}») δεν εντοπίστηκε "
                        "μέσα στο Παράρτημα Επιβεβαιωμένων Όψεων του τεχνικού δελτίου."
                    )
            else:
                errors.append(
                    "Δεν βρέθηκε «Παράρτημα Επιβεβαιωμένων Όψεων» στο τεχνικό δελτίο, οπότε οι "
                    "δείκτες Υγείας δεν μπορούν να επαληθευτούν έναντι πραγματικών όψεων."
                )
    return errors


def _extract_talent_titles(text: str) -> list[str]:
    """Εξάγει τους τίτλους ταλέντων από τη συνοπτική λίστα που απαιτεί η
    δεσμευτική εντολή («Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:» /
    "In summary, the talents to explore are:"). Κοινή βάση για
    _duplicate_talent_titles() και τον ανά-ταλέντο έλεγχο τεκμηρίωσης στο
    _orientation_audit_errors().

    Fix (πραγματικό round-trip bug, εντοπίστηκε με πραγματικό ανέβασμα
    .docx): (1) το παλιό όριο περίμενε κενή γραμμή πριν την επόμενη
    ενότητα -- αλλά το docx_text() ΠΟΤΕ δεν διατηρεί κενές γραμμές (τις
    φιλτράρει), οπότε το όριο δεν έβρισκε ποτέ σημείο να σταματήσει και
    "κατάπινε" όλο το υπόλοιπο έγγραφο. Τώρα το όριο είναι η επόμενη
    γνωστή επικεφαλίδα (Επαγγελματικοί Τομείς/Career Fields). (2) τα
    bullet markers («-») που γράφτηκαν στο αρχικό κείμενο μετατρέπονται
    σε ΕΓΓΕΝΗ μορφοποίηση λίστας Word όταν φτιάχνεται το .docx -- ο
    χαρακτήρας «-» δεν επιβιώνει σαν literal κείμενο στην επαναφόρτωση.
    Το marker είναι τώρα προαιρετικό: κάθε μη κενή γραμμή μέσα στα όρια
    της ενότητας μετράει ως τίτλος.
    """
    m = re.search(
        r"(?:Συνοπτικά,\s*τα\s+ταλέντα\s+προς\s+διερεύνηση\s+είναι|In\s+summary,\s*the\s+talents\s+to\s+explore\s+are)\s*:",
        text, re.IGNORECASE,
    )
    if not m:
        return []
    end_m = re.search(
        r"Επαγγελματικ(?:οί|ούς)\s+Τομ(?:είς|έα)|Career\s+Fields",
        text[m.end():], re.IGNORECASE,
    )
    body = text[m.end():m.end() + end_m.start()] if end_m else text[m.end():m.end() + 2000]
    return [
        re.sub(r"^\s*(?:[-•*]|\d+[.)])\s*", "", line).strip()
        for line in body.splitlines() if line.strip()
    ]


def _duplicate_talent_titles(text: str) -> list[str]:
    """Εντοπίζει ταλέντα με ίδιο ή σχεδόν ίδιο τίτλο (case/whitespace-
    insensitive) στη συνοπτική λίστα τίτλων ταλέντων.

    Fix (chat κριτική #6, τεκμηρίωση): αυτό είναι αμιγώς ΣΥΝΤΑΚΤΙΚΟΣ
    έλεγχος πάνω στον τίτλο -- ΔΕΝ κρίνει σημασιολογικά αν δύο
    διαφορετικά διατυπωμένοι τίτλοι (π.χ. «Αναλυτική σκέψη και ακρίβεια»
    vs. «Ικανότητα ανάλυσης με προσοχή στη λεπτομέρεια») περιγράφουν στην
    ουσία το ίδιο ταλέντο· ένα regex δεν μπορεί να το κρίνει αξιόπιστα.
    Πιάνει μόνο πανομοιότυπους ή σχεδόν πανομοιότυπους τίτλους.
    """
    items = _extract_talent_titles(text)
    seen: dict[str, bool] = {}
    dups = []
    for item in items:
        key = re.sub(r"\s+", " ", item.strip().lower()).rstrip(".·")
        if not key:
            continue
        if key in seen:
            dups.append(item.strip())
        seen[key] = True
    return list(dict.fromkeys(dups))


def _split_talent_paragraphs(talents_block: str) -> list[str]:
    """Ομαδοποιεί τις γραμμές της ενότητας «Ταλέντα προς διερεύνηση» σε μία
    ομάδα (τίτλος+παράγραφος) ανά ταλέντο.

    Fix (ΠΡΑΓΜΑΤΙΚΟ round-trip bug, εντοπίστηκε με πραγματικό ανέβασμα ενός
    δικού μας παραγόμενου .docx στην ίδια την εφαρμογή): ο παλιός
    διαχωρισμός βασιζόταν αποκλειστικά σε κενή γραμμή (`\\n\\s*\\n`) ανάμεσα
    σε ταλέντα. Όμως το docx_text() -- η συνάρτηση που διαβάζει ΚΑΘΕ
    πραγματικό .docx πίσω σε κείμενο για έλεγχο -- ΔΕΝ διατηρεί ΠΟΤΕ κενές
    γραμμές (τις φιλτράρει ρητά). Αποτέλεσμα: ένα τέλεια σωστό, πραγματικό
    Word deliverable έδειχνε ΟΛΑ τα ταλέντα σαν ΜΙΑ γιγάντια "παράγραφο"
    εκατοντάδων λέξεων μόλις ανέβαινε για έλεγχο -- ενώ το ίδιο ακριβώς
    κείμενο σε ωμή μορφή περνούσε κανονικά. Τώρα η ομαδοποίηση δεν
    εξαρτάται καθόλου από κενές γραμμές: κάθε νέα ΚΟΝΤΗ γραμμή (<20 λέξεις)
    που εμφανίζεται μετά από μια ήδη «σωματώδη» ομάδα (δηλαδή μετά από μια
    γραμμή με ≥20 λέξεις) θεωρείται νέος τίτλος ταλέντου -- λειτουργεί
    εξίσου καλά είτε επιβιώσουν κενές γραμμές είτε όχι.
    """
    def word_count(s: str) -> int:
        return len(re.findall(r"\b[\wΆ-ώ]+\b", s, re.UNICODE))

    groups: list[str] = []
    current: list[str] = []
    for line in talents_block.split("\n"):
        if not line.strip():
            if current:
                groups.append("\n".join(current))
                current = []
            continue
        if current and any(word_count(l) >= 20 for l in current) and word_count(line) < 20:
            groups.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        groups.append("\n".join(current))
    return groups


def _strip_dense_chart_note(talents_block: str) -> str:
    """Αφαιρεί την υποχρεωτική σημείωση πριν τις κάρτες ταλέντων (Κανόνας
    8Α, για πυκνά διασυνδεδεμένους χάρτες) πριν τον διαχωρισμό παραγράφων.

    Fix (πραγματικό bug, εντοπίστηκε με πραγματικό ανέβασμα .docx): η
    σημείωση είναι μία ΜΑΚΡΙΑ παράγραφος (>=20 λέξεις) που εμφανίζεται
    ΠΡΩΤΗ μέσα στην ενότητα, πριν από οποιονδήποτε πραγματικό τίτλο
    ταλέντου -- το _split_talent_paragraphs() δεν είχε τρόπο να ξέρει ότι
    δεν είναι η ίδια ένα ταλέντο, αφού δεν υπάρχει προηγούμενη σύντομη
    γραμμή-τίτλος να τη διακρίνει. Αποτέλεσμα: η σημείωση μετρούνταν σαν
    7ο/8ο "ταλέντο", προκαλώντας ψευδές σφάλμα αναντιστοιχίας στη
    συνοπτική λίστα και ψευδή προειδοποίηση έκτασης."""
    return re.sub(
        r"(?:^|\n)[^\n]*Σημείωση\s+πριν\s+διαβάσεις\s+τις\s+κάρτες[^\n]*",
        "", talents_block, count=1, flags=re.IGNORECASE,
    )


def _talents_block_body(text: str) -> str:
    """Κοινή βάση για _talent_paragraph_titles()/_talent_paragraph_length_issues():
    εξάγει την ενότητα «Ταλέντα προς διερεύνηση», αφαιρεί τη σημείωση
    πυκνής διασύνδεσης (αν υπάρχει) και κόβει πριν τη συνοπτική λίστα."""
    talents_block = _between_headings(
        text,
        r"Ταλέντα\s+προς\s+διερεύνηση|Talents\s+to\s+Explore",
        (r"Επαγγελματικ(?:οί|ούς)\s+Τομ(?:είς|έα)", r"Career\s+Fields"),
    )
    if not talents_block:
        return ""
    talents_block = _strip_dense_chart_note(talents_block)
    return re.split(
        r"Συνοπτικά,\s*τα\s+ταλέντα|In\s+summary,\s*the\s+talents",
        talents_block, maxsplit=1, flags=re.IGNORECASE,
    )[0]


def _talent_paragraph_titles(text: str) -> list[str]:
    """Μετράει πόσες πραγματικές παράγραφοι ταλέντου παρουσιάστηκαν στην
    ενότητα «Ταλέντα προς διερεύνηση» (χρησιμοποιεί το ίδιο κατώφλι >=20
    λέξεων με το _talent_paragraph_length_issues, για να ξεχωρίζει μια
    πραγματική παράγραφο από έναν σκέτο τίτλο). Χρησιμοποιείται για να
    επιβεβαιωθεί ότι ο αριθμός τίτλων στη συνοπτική λίστα ταιριάζει με τον
    αριθμό ταλέντων που όντως γράφτηκαν."""
    talents_block = _talents_block_body(text)
    if not talents_block:
        return []
    titles = []
    for p in _split_talent_paragraphs(talents_block):
        words = re.findall(r"\b[\wΆ-ώ]+\b", p, re.UNICODE)
        if len(words) < 20:
            continue
        title_guess = p.split("\n", 1)[0][:80].strip()
        # Fix (πραγματικό αίτημα χρήστη): αν ο τίτλος ταλέντου είναι αριθμημένος
        # («1. Τίτλος», για εύκολη αναφορά σε πελάτη/επαγγελματία), το «1. »
        # είναι διακοσμητικό, όχι μέρος του σημασιολογικού τίτλου -- η συνοπτική
        # λίστα ήδη αφαιρεί τέτοιους δείκτες (_extract_talent_titles). Χωρίς
        # αυτό, ένας αριθμημένος τίτλος δεν θα ταίριαζε ΠΟΤΕ με τη μη αριθμημένη
        # εκδοχή του στη λίστα, σπάζοντας σιωπηλά τον έλεγχο αντιστοίχισης.
        titles.append(re.sub(r"^\s*(?:[-•*]|\d+[.)])\s*", "", title_guess))
    return titles


def _talent_paragraph_length_issues(text: str) -> tuple[list[str], list[str]]:
    """Δύο επίπεδα ελέγχου έκτασης ανά παράγραφο ταλέντου (spec στόχος:
    70-110 λέξεις / έως 10 γραμμές· fix μετά από chat κριτική #4 -- πριν το
    εύρος ανοχής χωρίς προειδοποίηση ήταν 50-160, πολύ πιο χαλαρό από τον
    συμφωνημένο στόχο 70-110):

    - (warnings) εκτός 70-110 λέξεων -> μη δεσμευτική σημείωση, δεν
      μπλοκάρει (ο στόχος είναι ενδεικτικός, όχι απόλυτος).
    - (hard_errors) κάτω από 40 ή πάνω από 160 λέξεων -> πραγματικό σφάλμα
      που μπλοκάρει, γιατί σε τέτοιο βαθμό απόκλισης δεν πρόκειται πια για
      μικρή διακύμανση αλλά για παραβίαση της μορφής (πολύ κοντό απόσπασμα
      χωρίς ουσιαστική εξήγηση, ή de facto πολυπαραγραφική ενότητα).

    Επιστρέφει (warnings, hard_errors)· ο καλών αποφασίζει πού τα βάζει.
    """
    talents_block = _talents_block_body(text)
    if not talents_block:
        return [], []
    warnings, hard_errors = [], []
    for p in _split_talent_paragraphs(talents_block):
        words = re.findall(r"\b[\wΆ-ώ]+\b", p, re.UNICODE)
        n = len(words)
        if n < 20:
            continue  # πιθανώς μόνο τίτλος, όχι παράγραφος ταλέντου
        title_guess = p.split("\n", 1)[0][:60].strip()
        if n < 40 or n > 160:
            hard_errors.append(
                f"Παράγραφος ταλέντου («{title_guess}…») έχει {n} λέξεις -- πολύ εκτός του στόχου "
                f"70–110 (αποδεκτό εύρος 40–160). Χρειάζεται διόρθωση."
            )
        elif n < 70 or n > 110:
            warnings.append(f"Παράγραφος ταλέντου («{title_guess}…») έχει {n} λέξεις -- στόχος 70–110.")
    return warnings, hard_errors


def validate_orientation(chart, text: str, personal: dict | None = None,
                         service: str = "", presentation_mode: str = "Αναλυτική με αστρολογική τεκμηρίωση",
                         audit_text: str | None = None,
                         cyprus_education: bool = False,  # DEPRECATED: το χαρακτηριστικό Κύπρου/ΟΜΠ καταργήθηκε· η παράμετρος
                         # μένει εδώ μόνο για να μη σπάσουν clients που ακόμα το περνούν ρητά (π.χ. το entry-point
                         # πριν ενημερωθεί) -- δεν επηρεάζει πλέον καμία λογική ελέγχου. Αφαίρεσέ την εντελώς
                         # μόλις κανένας caller δεν την περνάει πια.
                         format_issues: list[str] | None = None) -> OrientationValidationResult:
    # Ίδια κανονικοποίηση ' -> ′ με τα validate_analysis()/validate_rewrite()
    # -- βλ. docstring της _normalize_prime_marks.
    text = _normalize_prime_marks(text)
    if audit_text is not None:
        audit_text = _normalize_prime_marks(audit_text)
    # Η υπηρεσία ενοποιήθηκε σε ένα μόνο "απλή" mode -- δεν υπάρχει πια
    # διάκριση short_adult/short_child (πρώην βασισμένη στο service string,
    # που το app.py δεν στέλνει πια). short_simple = η ενοποιημένη σύντομη
    # έκδοση, ανεξάρτητα ποιος είναι ο πελάτης.
    short_simple = presentation_mode == "Απλή και πρακτική"
    common_topics={
        "προφίλ": r"\bπροφίλ\b",
        "ταλέντα": r"ταλέντ|ικανότητ|δυνατότητ",
        "Επαγγελματικοί Τομείς προς Διερεύνηση": r"επαγγελματικ(?:οί|ούς)\s+τομ(?:είς|έα)(?:\s+προς\s+διερεύνηση)?",
        "ενδεικτικά επαγγέλματα ανά τομέα": r"ενδεικτικ(?:ά|ών)\s+επαγγέλματ",
        "πρακτική διερεύνηση": r"δραστηριότητ|πείραμα|δοκιμ|επόμενο\s+βήμα",
        "σχέδιο 8–12 εβδομάδων": r"8\s*[–-]\s*12\s+εβδομάδ|σχέδιο\s+(?:δοκιμής|διερεύνησης)",
        "τελική σύνθεση": r"τελική\s+σύνθεση",
        "τεκμηρίωση κάθε ταλέντου": r"πώς\s+τεκμηριώνεται",
        "εμφάνιση κάθε ταλέντου": r"πώς\s+μπορεί\s+να\s+εμφανίζεται",
        "καλλιέργεια κάθε ταλέντου": r"πώς\s+μπορεί\s+να\s+καλλιεργηθεί",
        "δραστηριότητα δοκιμής": r"δραστηριότητα\s+δοκιμής",
        "τρόπος μάθησης και δημιουργίας": r"τρόπος\s+μάθησης|μάθηση\s+και\s+δημιουργία",
        "δυνατά σημεία που χρειάζονται καλλιέργεια": r"δυνατ(?:ά|ών)\s+σημε(?:ία|ίων)[^\r\n]{0,80}καλλιέργ",
        "πιθανά εμπόδια": r"πιθαν(?:ά|ών)\s+εμπόδι",
    }
    if short_simple:
        # Η σύντομη έκδοση είναι σκόπιμα λιτή. Δεν απαιτούμε τους αναλυτικούς
        # πίνακες ταλέντων ούτε πλήρες εβδομαδιαίο πλάνο, γιατί αυτά ήταν η
        # βασική αιτία που το καθαρό παραδοτέο μεγάλωνε υπερβολικά.
        # Fix (English mode, κριτική): οι ενότητες αυτές αφορούν αποκλειστικά
        # το ΚΑΘΑΡΟ ΠΑΡΑΔΟΤΕΟ ΠΕΛΑΤΗ, που πλέον μπορεί να είναι Ελληνικά ή
        # Αγγλικά (βλ. app.py reinforcement_instructions -- εκεί ορίζονται οι
        # ίδιες ακριβώς αγγλικές επικεφαλίδες που ζητούνται από το μοντέλο).
        # Το εσωτερικό τεχνικό δελτίο παραμένει σκόπιμα πάντα ελληνικό (βλ.
        # CAREER_CONSISTENCY_RULE_EN στο prompts.py) και δεν χρειάζεται εδώ
        # αγγλικά μοτίβα -- ελέγχεται ξεχωριστά από το _orientation_audit_errors.
        common_topics = {
            "σύντομο προφίλ / brief profile": r"σύντομο\s+προφίλ|brief\s+profile",
            "ταλέντα προς διερεύνηση / talents to explore": r"ταλέντα\s+προς\s+διερεύνηση|talents\s+to\s+explore",
            "Επαγγελματικοί Τομείς / Career Fields to Explore": r"επαγγελματικ(?:οί|ούς)\s+τομ(?:είς|έα)(?:\s+προς\s+διερεύνηση)?|career\s+fields\s+to\s+explore",
            "ενδεικτικά επαγγέλματα / Example Careers per Field": r"ενδεικτικ(?:ά|ών)\s+επαγγέλματ|παραδείγματα\s+δουλει(?:ών|άς)|example\s+careers(?:\s+per\s+field)?",
            "τελική σύνθεση / Final Synthesis": r"τελική\s+σύνθεση|σύνοψη|final\s+synthesis",
        }
    elif presentation_mode == "Αναλυτική με αστρολογική τεκμηρίωση":
        common_topics["Παράρτημα τεκμηρίωσης"] = r"Παράρτημα[^\r\n]{0,80}(?:τεκμηρίωσ|ελέγχ)"
    if short_simple:
        topics = dict(common_topics)
        # Η υπενθύμιση πραγματικών κριτηρίων εμφανίζεται πάντα στην Τελική
        # Σύνθεση της ενοποιημένης σύντομης έκδοσης, ανεξάρτητα από το
        # πλέον ανύπαρκτο cyprus_education/service.
        topics["υπενθύμιση πραγματικών κριτηρίων / What to Remember"] = (
            r"Τι\s+χρειάζεται\s+να\s+θυμάσαι|What\s+to\s+Remember"
            r"|μαθήματα[\s\S]{0,200}επίδοσ[\s\S]{0,200}(?:επιβεβαιώσ|αναθεωρήσ)"
        )
    elif service == "Παιδί/έφηβος":
        topics = {
            **common_topics,
            "οδηγίες προς γονείς/εκπαιδευτικούς": r"γον(?:είς|έα)|εκπαιδευτικ",
            "ερωτήσεις συζήτησης": r"ερωτήσεις\s+(?:για\s+)?συζήτηση",
        }
        # Το χαρακτηριστικό Κύπρου/ΟΜΠ (και το αντίστοιχο πλήρες υποσύνολο με
        # ενδεικτικές πανεπιστημιακές σπουδές ανά τομέα) καταργήθηκε εντελώς
        # από την υπηρεσία -- σε καμία έκδοση (σύντομη ή αναλυτική) δεν πρέπει
        # πλέον να ζητείται ή να ελέγχεται τέτοιο περιεχόμενο.
    else:
        topics = {
            **common_topics,
            "εργασιακά περιβάλλοντα": r"εργασιακ(?:ά|ό)\s+περιβάλλον",
        }
    missing=[label for label,pattern in topics.items() if not re.search(pattern,text,re.IGNORECASE)]
    wrong=_location_claim_errors(chart,text)
    unauthorized=_unauthorized_personal_claims(personal,text)
    technical=_orientation_technical_mismatches(chart,text)
    breakdown = {"aspect": len(technical), "audit": 0, "career": 0}
    name_issue = _name_consistency_issue(personal, text)
    if presentation_mode == "Απλή και πρακτική":
        if format_issues:
            technical.append(
                "Η απλή παρουσίαση πρέπει να είναι ασπρόμαυρη χωρίς highlights: "
                + ", ".join(format_issues) + "."
            )
        exposed = _simple_presentation_technical_terms(text)
        if exposed:
            technical.append("Η απλή παρουσίαση περιέχει τεχνικά αστρολογικά δεδομένα: " + ", ".join(exposed) + ".")
        _audit = _orientation_audit_errors(chart, audit_text or "", text)
        technical.extend(_audit)
        breakdown["audit"] += len(_audit)
        _career = _career_consistency_errors(text, audit_text or "")
        technical.extend(_career)
        breakdown["career"] += len(_career)
        if short_simple:
            # Fix (spec, νέα λογική έκτασης): αφαιρέθηκε η αυτόματη απόρριψη
            # πάνω από 1.800 λέξεις -- ο αριθμός τεκμηριωμένων ταλέντων δεν
            # είναι πλέον σταθερός, άρα ούτε η συνολική έκταση. Η συντομία
            # επιτυγχάνεται πλέον ανά ταλέντο/τομέα, όχι με συνολικό όριο.
            summary_titles = _extract_talent_titles(text)
            if not summary_titles:
                technical.append(
                    "Λείπει η υποχρεωτική συνοπτική λίστα τίτλων ταλέντων (\"Συνοπτικά, τα ταλέντα "
                    "προς διερεύνηση είναι:\" / \"In summary, the talents to explore are:\") -- χωρίς αυτήν "
                    "δεν μπορεί να επαληθευτεί η τεκμηρίωση κάθε ταλέντου ξεχωριστά."
                )
            else:
                presented_titles = _talent_paragraph_titles(text)
                # Fix (deep review κριτική #3, 2ος γύρος, σοβαρό): πριν
                # συγκρινόταν μόνο ο ΑΡΙΘΜΟΣ τίτλων -- η συνοπτική λίστα
                # μπορούσε να αναφέρει εντελώς διαφορετικούς τίτλους από
                # αυτούς που όντως παρουσιάστηκαν (π.χ. παρουσίαση
                # "Analytical thinking" αλλά συνοπτική λίστα/τεχνικό δελτίο
                # για "Creative writing") και να περάσει, αφού ο αριθμός
                # ταίριαζε. Τώρα απαιτείται ακριβής αντιστοιχία ΣΥΝΟΛΩΝ
                # τίτλων, κανονικοποιημένων (πεζά/κενά/τελική στίξη), όχι
                # μόνο ίδιο πλήθος.
                def _norm_title(t: str) -> str:
                    return re.sub(r"\s+", " ", t.strip().lower()).rstrip(".·")

                if presented_titles:
                    norm_presented = {_norm_title(t) for t in presented_titles}
                    norm_summary = {_norm_title(t) for t in summary_titles}
                    if norm_presented != norm_summary:
                        only_presented = norm_presented - norm_summary
                        only_summary = norm_summary - norm_presented
                        detail = []
                        if only_presented:
                            detail.append("παρουσιάστηκαν αλλά λείπουν από τη λίστα: " + ", ".join(sorted(only_presented)))
                        if only_summary:
                            detail.append("υπάρχουν στη λίστα αλλά δεν παρουσιάστηκαν: " + ", ".join(sorted(only_summary)))
                        technical.append(
                            "Η συνοπτική λίστα τίτλων δεν ταιριάζει ακριβώς με τους τίτλους που παρουσιάστηκαν -- "
                            + "· ".join(detail) + "."
                        )
            duplicate_talents = _duplicate_talent_titles(text)
            if duplicate_talents:
                technical.append(
                    "Δύο ή περισσότερα ταλέντα φαίνονται ουσιαστικά ίδια στη συνοπτική λίστα: "
                    + ", ".join(f"«{d}»" for d in duplicate_talents) + "."
                )
            # Fix (deep review κριτική #4, σοβαρό, 2ος γύρος): ο έλεγχος
            # έψαχνε στο ΟΛΟΚΛΗΡΟ κείμενο, οπότε μια αναφορά στην ελεύθερη
            # βούληση οπουδήποτε αλλού (π.χ. στο Brief Profile) περνούσε τον
            # έλεγχο, ενώ η ίδια η Τελική Σύνθεση -- το σημείο που πραγματικά
            # έχει σημασία -- μπορούσε να μην την αναφέρει καθόλου. Τώρα
            # απομονώνεται πρώτα η ενότητα Τελική Σύνθεση/Final Synthesis
            # (μέχρι το τέλος του εγγράφου) και ο έλεγχος γίνεται ΜΟΝΟ εκεί.
            final_synthesis_block = _between_headings(
                text, r"Τελική\s+Σύνθεση|Final\s+Synthesis", (),
            ) or text
            if not re.search(
                r"(?:τελική\s+επιλογ|τελική\s+απόφασ|final\s+(?:choice|decision))[\s\S]{0,150}"
                r"(?:δική\s+(?:του|της|σου|σας)|remains\s+yours|is\s+(?:always\s+)?yours)"
                r"|ελεύθερ[ηη]\s+βούλησ|free\s+will",
                final_synthesis_block, re.IGNORECASE,
            ):
                technical.append(
                    "Δεν εντοπίστηκε ρητή αναφορά στην ελεύθερη βούληση/τελική προσωπική επιλογή "
                    "(π.χ. «η τελική επιλογή παραμένει πάντα δική του») στο κλείσιμο του κειμένου."
                )
            forbidden_sections = (
                "Τρόπος μάθησης και δημιουργίας",
                "Δυνατά σημεία που χρειάζονται καλλιέργεια",
                "Πιθανά εμπόδια",
                "Συμβολική Κατεύθυνση Εξέλιξης",
                "Κατάλληλο εργασιακό περιβάλλον",
                "Επόμενα βήματα",
                "Ερωτήσεις για συζήτηση",
                "Οδηγίες προς γονείς",
                "Οδηγίες προς γονείς και εκπαιδευτικούς",
                # Fix (English mode, κριτική): αγγλικά ισοδύναμα, ώστε ένα
                # αγγλικό deliverable να μην μπορεί να παρακάμψει σιωπηλά
                # αυτόν τον έλεγχο απλώς γράφοντας τις απαγορευμένες
                # ενότητες στα αγγλικά.
                "Learning and Creation Style",
                "Strengths That Need Cultivating",
                "Possible Obstacles",
                "Symbolic Direction of Development",
                "Suitable Work Environment",
                "Next Steps",
                "Discussion Questions",
                "Guidance for Parents",
                "Guidance for Parents and Educators",
            )
            present = [s for s in forbidden_sections if re.search(re.escape(s), text, re.IGNORECASE)]
            if present:
                technical.append(
                    "Η σύντομη έκδοση περιέχει αναλυτικές ενότητες που πρέπει να παραλείπονται: "
                    + ", ".join(present) + "."
                )
    else:
        _audit = _orientation_audit_errors(chart, text, text)
        technical.extend(_audit)
        breakdown["audit"] += len(_audit)
    if re.search(r"Τι\s+χρειάζεται\s+επιβεβαίωση\s*:\s*Τι\s+χρειάζεται\s+επιβεβαίωση\s*:", text, re.IGNORECASE):
        technical.append("Η ετικέτα «Τι χρειάζεται επιβεβαίωση:» επαναλαμβάνεται δύο φορές στην ίδια πρόταση.")
    if short_simple:
        talent_match = re.search(
            r"(?:Ταλέντα\s+προς\s+διερεύνηση|Talents\s+to\s+Explore)(?P<body>[\s\S]*?)(?:Επαγγελματικ(?:οί|ούς)\s+Τομ(?:είς|έα)|Career\s+Fields)",
            text,
            re.IGNORECASE,
        )
        if talent_match and re.search(
            r"επαγγέλματ|αναλυτής|ερευνητής|μηχανικός|εκπαιδευτικός|δημοσιογράφος|προγραμματιστής|διαμεσολαβητής"
            r"|\bjobs?\b|professions?|careers?|analyst|researcher|engineer|educator|journalist|programmer|mediator",
            talent_match.group("body"),
            re.IGNORECASE,
        ):
            technical.append("Στη σύντομη έκδοση τα επαγγέλματα πρέπει να εμφανίζονται μόνο στους Επαγγελματικούς Τομείς, όχι μέσα στα Ταλέντα.")
    if short_simple and re.search(
        r"Πλαίσιο\s+Εκπαιδευτικ(?:ού|ο)\s+Συστήματος\s*\(Κύπρος\)|κυπριακ(?:ό|ού)\s+εκπαιδευτικ|\bΟΜΠ\b|Παγκύπρι(?:ες|ων)\s+Εξετάσεις|Επιστημονικ(?:ά|ών)\s+Πεδία|Πλαίσι(?:α|ων)\s+Πρόσβασης",
        text,
        re.IGNORECASE,
    ):
        # Το χαρακτηριστικό Κύπρου/ΟΜΠ καταργήθηκε εντελώς -- καμία σύντομη
        # έκδοση δεν πρέπει ποτέ να το περιλαμβάνει.
        technical.append("Η σύντομη έκδοση δεν πρέπει να περιλαμβάνει ενότητα για την Κύπρο, ΟΜΠ ή εκπαιδευτικές διαδρομές -- το χαρακτηριστικό έχει καταργηθεί.")
    if service != "Παιδί/έφηβος" and re.search(r"υποθετικ(?:ό|ο)\s+σενάριο[^\r\n]{0,30}15\s+ετ", text, re.IGNORECASE):
        technical.append("Η ανάλυση ενηλίκου δεν πρέπει να παρουσιάζεται ως υποθετικό σενάριο 15 ετών.")
    name_issues = [name_issue] if name_issue else []
    length_warnings, length_hard_errors = _talent_paragraph_length_issues(text) if short_simple else ([], [])
    technical.extend(length_hard_errors)
    # Ό,τι δεν προήλθε από όψεις/orb, τεχνικό δελτίο ή τομείς/επαγγέλματα
    # (μορφή, συνοπτική λίστα, απαγορευμένες ενότητες, μήκος κ.λπ.).
    breakdown["structure"] = len(technical) - breakdown["aspect"] - breakdown["audit"] - breakdown["career"]
    return OrientationValidationResult(
        not (wrong or unauthorized or missing or technical or name_issues),
        wrong, unauthorized, missing, technical, name_issues, length_warnings,
        technical_breakdown=breakdown,
    )
