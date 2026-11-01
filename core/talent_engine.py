"""
core/talent_engine.py -- AstroCheck Career (v22, ΠΡΟΧΕΙΡΟ -- υβριδική μέθοδος)

ΜΗΧΑΝΗ ΤΑΛΕΝΤΩΝ: από τον χάρτη στη ΠΛΗΡΗ λίστα ταλέντων και επαγγελματικών τομέων,
με τους κανόνες της δεσμευτικής εντολής v13 -- χωρίς AI. Ο ίδιος χάρτης δίνει
πάντα το ίδιο αποτέλεσμα, και κανένας δείκτης δεν «ξεχνιέται».

Ροή:
  1. Δείκτες Θέσης  (Κανόνες 4–6) + Κυβερνήτες βασικών Οίκων (Κανόνας 6, v22.10): πλανήτης σε ζώδιο/βασικό Οίκο που ταιριάζει με
     λειτουργία του πλανήτη· συγκεντρώσεις (3+ πλανήτες) -> κύριο θέμα ζωδίου/Οίκου.
  2. Δείκτες Όψης   (Κανόνας 7): κάθε όψη με προσωπικό σημείο -> θέμα του ζεύγους.
  3. Τεκμηρίωση     (Κανόνας 10): δύο διακριτοί δείκτες (ο ένας Θέση ή Στενή/Κανονική
     όψη) ή μία Στενή/ισχυρή όψη με προσωπικό σημείο ή δύο Πλατιές με κοινό σημείο.
  4. Ιεράρχηση      (Κανόνας 10): κυρίαρχο / βασικό / αναδυόμενο.
  5. Τομείς         (Κανόνας 12): κύριος με 2+ ταλέντα, σύντομη αναφορά με 1, εγγύηση.
  6. Τομείς υγείας  (Κανόνας 15): μόνο με δύο ειδικούς δείκτες υγείας (HEALTH_RULES)
     και τουλάχιστον ένα σχετικό εγκεκριμένο ταλέντο· η τεκμηρίωση κρατιέται στο health_basis.
Οι πίνακες αντιστοίχισης βρίσκονται στο core/talent_map.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .astrology import planet_concentrations
from .talent_map import (
    ANGLES, COLOURS, CONCENTRATION_ONLY_HOUSES, colour_options, colour_phrase, HEALTH_RULES, HOUSE_THEMES, NODES, PAIR_THEME, PERSONAL, PLANET_THEMES, SIGN_THEMES, SLOW, THEME_FIELDS, THEMES,
)

STRONG, NORMAL, WIDE, VERY_WIDE = "Στενή/ισχυρή", "Κανονική", "Πλατιά αλλά έγκυρη", "Πολύ πλατιά/δευτερεύουσα"
ASPECT_SCORE = {STRONG: 3.0, NORMAL: 2.0, WIDE: 1.0, VERY_WIDE: 0.5}
POSITION_SCORE = 1.5
RULER_SCORE = 1.0
# Θέση κυβερνήτη (v22.12): ΜΟΝΟ υποστηρικτική -- ενισχύει/κατατάσσει ταλέντα που ήδη τεκμηριώνονται,
# δεν δημιουργεί νέο ταλέντο. Μετρά 1/4 όπως κάθε υποστηρικτικός δείκτης: 0,25 x 2,0 = 0,5 ο καθένας.
RULER_PLACEMENT_SCORE = 2.0
# Κανόνας 6 (v22.10): Οίκοι όπου ο κυβερνήτης φέρνει την ΚΥΡΙΑ λειτουργία του πλανήτη του (π.χ. ο
# κυβερνήτης του Μεσουρανήματος δείχνει τον «τρόπο προσφοράς» στη δουλειά), όχι μόνο τα θέματα του Οίκου.
RULER_PRIMARY_HOUSES = (1, 10)
RULER_PLACEMENT_HOUSES = (1, 2, 6, 10)   # Οίκοι σταδιοδρομίας: μετρά και πού βρίσκεται ο κυβερνήτης τους
CONCENTRATION_BONUS = 0.5
DOMINANT_MIN, BASIC_MIN = 6.0, 3.5
VERY_TIGHT_ORB, VERY_TIGHT_BONUS = 1.0, 1.5
# Τομείς (Κανόνας 12), v22.2: εξετάζονται ΟΛΟΙ οι τομείς κάθε ταλέντου, με βάρος ανάλογα με τη
# θέση τους στη λίστα (ο πρώτος είναι ο πιο χαρακτηριστικός). Βαθμός τομέα = Σ(βαθμός ταλέντου × βάρος).
#  * Κύριος τομέας: εκεί όπου συναντιούνται 2+ ταλέντα -- έως MAX_MAIN_FIELDS ΑΡΧΙΚΟΙ τομείς με τον
#    υψηλότερο βαθμό, ΣΥΝ πρόσθετοι όπου χρειάζεται (εγγύηση κάλυψης ταλέντων, τομείς υγείας). Άρα το
#    6 ΔΕΝ είναι συνολικό όριο κύριων τομέων.
#  * Εγγύηση: ταλέντο χωρίς κύριο τομέα -> ο τομέας του με τον υψηλότερο βαθμό, σημειωμένος ως
#    «ο πιο ταιριαστός τομέας για ένα ταλέντο» (όχι ως συνάντηση ταλέντων).
#  * Άλλες κατευθύνσεις: οι FIELDS_PER_THEME καλύτεροι τομείς κάθε ταλέντου που δεν είναι ήδη κύριοι.
FIELD_POSITION_WEIGHTS = (1.0, 0.8, 0.6, 0.4)
MAX_MAIN_FIELDS = 6
MAX_BRIEF_FIELDS = 6   # v22.14: «Άλλες κατευθύνσεις» -- οι 6 με τον υψηλότερο βαθμό
FIELDS_PER_THEME = 1
PERSONAL_OR_ANGLE = PERSONAL + ANGLES
_PAIR = {frozenset(k): v for k, v in PAIR_THEME.items()}


@dataclass(frozen=True)
class Indicator:
    kind: str                 # «Θέση» ή «Όψη»
    key: str                  # μοναδικό κλειδί (για τον κανόνα «ίδιος δείκτης μετρά μία φορά»)
    points: tuple[str, ...]
    label: str                # π.χ. «Κρόνος σε Ζυγό, Οίκος 11» ή «Ήλιος–Κρόνος | Τρίγωνο | orb 0°14′»
    weight: str = ""          # μόνο για όψεις
    aspect: str = ""
    orb: float = 0.0
    concentration: bool = False

    @property
    def score(self) -> float:
        if self.kind == "Κυβερνήτης":
            return RULER_PLACEMENT_SCORE if self.key.startswith("rulpos:") else RULER_SCORE
        if self.kind == "Θέση":
            return POSITION_SCORE + (CONCENTRATION_BONUS if self.concentration else 0.0)
        base = ASPECT_SCORE.get(self.weight, 0.0)
        if self.weight == STRONG and self.orb < VERY_TIGHT_ORB:
            # Πολύ στενή όψη (κάτω από 1°): η πιο αξιόπιστη ένδειξη (Κανόνας 7) -- έως +1,5.
            base += VERY_TIGHT_BONUS * (1 - self.orb / VERY_TIGHT_ORB)
        return base


@dataclass
class Talent:
    theme: str
    title_el: str
    title_en: str
    indicators: list[Indicator]
    supporting: list[Indicator]          # μετρήθηκαν ήδη μέσω όψης ή είναι «Πολύ πλατιές» (απόχρωση)
    basis: str                           # «δύο δείκτες» / «μοναδικός ισχυρός δείκτης» / «δύο πλατιές με κοινό σημείο»
    rank: str = ""                       # κυρίαρχο / βασικό / αναδυόμενο
    score: float = 0.0
    fields: list[str] = field(default_factory=list)
    # v22.15-21: αποχρώσεις («πώς φαίνεται σε σένα»): [(κλειδί COLOURS, διατύπωση 0-2, δείκτης)], έως 4
    colours: list = field(default_factory=list)

    @property
    def colour(self) -> str:
        return self.colours[0][0] if self.colours else ""

    @property
    def colour_variant(self) -> int:
        return self.colours[0][1] if self.colours else 0

    @property
    def colour_from(self) -> str:
        return self.colours[0][2] if self.colours else ""

    @property
    def natural(self) -> bool:
        return any(i.aspect == "Τρίγωνο" for i in self.indicators)

    @property
    def growth(self) -> str:
        """v22.5 -- πώς αναπτύσσεται το ταλέντο. ΙΔΙΟΣ κανόνας με το core/talent_growth.py (v20.18,
        λειτουργία "ai"/χειροκίνητη), κατά τον Κανόνα 7 της εντολής: μετρούν μόνο οι Στενές/Κανονικές
        όψεις· σύνοδος και χιαστί 150° ουδέτερες.
          mixed       -> αρμονικές (τρίγωνο/εξάγωνο) ΚΑΙ δύσκολες (τετράγωνο/αντίθεση)
          practice    -> μόνο δύσκολες
          opportunity -> μόνο αρμονικές, με τουλάχιστον ένα εξάγωνο
          easy        -> μόνο τρίγωνα
          open        -> καμία κύρια αρμονική/δύσκολη όψη (μόνο θέσεις, σύνοδοι, χιαστί)"""
        from .talent_growth import EASY, HARMONIOUS, MIXED, OPEN, OPPORTUNITY, PRACTICE, PRIMARY_WEIGHTS, TENSE
        kinds = {i.aspect for i in self.indicators if i.kind == "Όψη" and i.weight in PRIMARY_WEIGHTS}
        harmonious, tense = kinds & set(HARMONIOUS), kinds & set(TENSE)
        if harmonious and tense:
            return MIXED
        if tense:
            return PRACTICE
        if harmonious:
            return OPPORTUNITY if "Εξάγωνο" in harmonious else EASY
        return OPEN


@dataclass
class FieldChoice:
    name: str
    talents: list[str]                   # θέματα
    decision: str                        # «ΕΠΙΛΕΓΕΤΑΙ» / «ΣΥΝΤΟΜΗ ΑΝΑΦΟΡΑ»
    guarantee: bool = False
    score: float = 0.0
    coverage: bool = False   # προστέθηκε για κάλυψη ταλέντου (εκτός του ορίου MAX_MAIN_FIELDS)
    health_basis: list[str] = field(default_factory=list)  # Κανόνας 15: «Δείκτης 1:», «Δείκτης 2:»


@dataclass
class EngineResult:
    talents: list[Talent]
    fields: list[FieldChoice]
    candidates_rejected: dict[str, str]  # θέμα -> λόγος


def _position_indicators(chart) -> dict[str, list[Indicator]]:
    by_theme: dict[str, list[Indicator]] = {}
    in_concentration: dict[tuple[str, str], str] = {}  # (πλανήτης, θέμα) -> ετικέτα
    # v22.11 -- Κανόνας 5: σε συγκέντρωση σε ΖΩΔΙΟ, ένας αργός πλανήτης μετρά μόνο αν συνδέεται με
    # προσωπικό πλανήτη ή γωνία (Στενή/Κανονική όψη)· και η συγκέντρωση χρειάζεται τουλάχιστον έναν
    # προσωπικό πλανήτη. Αλλιώς είναι «γενιά» (π.χ. Κρόνος + Πλούτωνας σε Ζυγό, 1981-83), όχι προσωπικό ταλέντο.
    # Οι συγκεντρώσεις σε ΟΙΚΟ μένουν ως έχουν: οι Οίκοι εξαρτώνται από την ώρα γέννησης.
    linked = {p for a in chart.aspects if a.weight in (STRONG, NORMAL)
              and not ({a.first, a.second} & set(NODES))
              for p, q in ((a.first, a.second), (a.second, a.first)) if q in PERSONAL_OR_ANGLE}
    for label, names in planet_concentrations(chart.points):
        kind, value = label.split(" ", 1)
        if kind == "Ζώδιο":
            names = [n for n in names if n not in SLOW or n in linked]
            if len(names) < 3 or not set(names) & set(PERSONAL):
                continue
            theme = SIGN_THEMES[value][0]
        else:
            # v22.32: οι Οίκοι 4, 8, 12 μετρούν ΜΟΝΟ σε συγκέντρωση 3+ πλανητών (όχι για μεμονωμένο πλανήτη ή κυβερνήτη).
            #          Εκεί η συγκέντρωση χρειάζεται και τουλάχιστον έναν προσωπικό πλανήτη (όχι μόνο αργούς).
            themes = HOUSE_THEMES.get(int(value))
            if not themes and int(value) in CONCENTRATION_ONLY_HOUSES and set(names) & set(PERSONAL):
                themes = CONCENTRATION_ONLY_HOUSES[int(value)]
            if not themes:
                continue
            theme = themes[0]
        for n in names:
            in_concentration[(n, theme)] = label
    for p in chart.points:
        if p.name not in PLANET_THEMES or p.name == "Χείρωνας":
            continue  # Χείρωνας: μόνο μέσω όψεων (Κανόνας 10)
        sign_themes = () if p.name in SLOW else SIGN_THEMES.get(p.sign, ())   # αργοί: το ζώδιο είναι γενεακό
        house_themes = HOUSE_THEMES.get(p.house, ())
        themes = {t for t in PLANET_THEMES[p.name] if t in sign_themes or t in house_themes}
        if p.name == "Ήλιος":
            # Ο Ήλιος = δημιουργική ταυτότητα (Κανόνας 4): στηρίζει πάντα το κύριο θέμα του ζωδίου του.
            themes.add(SIGN_THEMES[p.sign][0])
            # v22.20: ...και το κύριο θέμα του βασικού Οίκου όπου βρίσκεται («πού λάμπει»).
            if house_themes:
                themes.add(house_themes[0])
        themes |= {t for (n, t) in in_concentration if n == p.name}
        for t in themes:
            conc = (p.name, t) in in_concentration
            by_theme.setdefault(t, []).append(Indicator(
                "Θέση", f"pos:{p.name}", (p.name,),
                f"{p.name} σε {p.sign}, Οίκος {p.house}" + (f" ({in_concentration[(p.name, t)]})" if conc else ""),
                concentration=conc))
    return by_theme


def _ruler_indicators(chart) -> dict[str, list[Indicator]]:
    """Κανόνας 6: ο κυβερνήτης κάθε βασικού Οίκου (ζώδιο της ακμής· κύριος και, όπου υπάρχει,
    παραδοσιακός συγκυβερνήτης). Δίνει δείκτη για τα θέματα του πλανήτη που ταιριάζουν με τον Οίκο,
    και για τους Οίκους 1 και 10 και για την κύρια λειτουργία του πλανήτη. Δείκτης ΥΠΟΣΤΗΡΙΚΤΙΚΟΥ
    τύπου: μετρά ως διακριτός, αλλά δεν αρκεί χωρίς έναν κύριο δείκτη (θέση ή Στενή/Κανονική όψη)."""
    from .astrology import RULERS
    cusp_sign = {}
    for c in getattr(chart, "cusps", []) or []:
        try:
            cusp_sign[int(c.name.split("ο")[0])] = c.sign
        except ValueError:
            continue
    present = {p.name for p in chart.points}
    by_theme: dict[str, list[Indicator]] = {}
    seen = set()
    for house, house_themes in HOUSE_THEMES.items():
        sign = cusp_sign.get(house)
        if not sign:
            continue
        for ruler in (r for r in RULERS.get(sign, ()) if r):
            if ruler not in PLANET_THEMES or ruler not in present:
                continue
            themes = {t for t in PLANET_THEMES[ruler] if t in house_themes}
            if house in RULER_PRIMARY_HOUSES:
                themes.add(PLANET_THEMES[ruler][0])
            for t in themes:
                if (ruler, t) in seen:
                    continue  # ο ίδιος κυβερνήτης για το ίδιο θέμα μετρά μία φορά
                seen.add((ruler, t))
                label = (f"{ruler}, κυβερνήτης του Οίκου {house} ({sign})" if house != 10
                         else f"{ruler}, κυβερνήτης του Μεσουρανήματος / Οίκου 10 ({sign})")
                by_theme.setdefault(t, []).append(Indicator("Κυβερνήτης", f"rul:{ruler}", (ruler,), label))
    # v22.12 -- Κανόνας 6: «πού βρίσκεται» ο κυβερνήτης. Ο κυβερνήτης ενός Οίκου ΣΤΑΔΙΟΔΡΟΜΙΑΣ (1, 2, 6, 10)
    # «μεταφέρει» το θέμα του εκεί όπου βρίσκεται: στα θέματα του Οίκου του (αν είναι βασικός) και στο κύριο
    # θέμα του ζωδίου του. Για αργό κυβερνήτη μετρά μόνο ο Οίκος (το ζώδιο του είναι κοινό σε μια γενιά).
    pts = {p.name: p for p in chart.points}
    for house in RULER_PLACEMENT_HOUSES:
        sign = cusp_sign.get(house)
        if not sign:
            continue
        for ruler in (r for r in RULERS.get(sign, ()) if r):
            p = pts.get(ruler)
            if p is None or ruler not in PLANET_THEMES:
                continue
            themes = set(HOUSE_THEMES.get(p.house, ()))
            if ruler not in SLOW and p.sign in SIGN_THEMES:
                themes.add(SIGN_THEMES[p.sign][0])
            where = "Μεσουρανήματος / Οίκου 10" if house == 10 else f"Οίκου {house}"
            for t in themes:
                if (ruler, t) in seen:
                    continue
                seen.add((ruler, t))
                label = f"{ruler}, κυβερνήτης του {where} ({sign}), βρίσκεται στον Οίκο {p.house} σε {p.sign}"
                by_theme.setdefault(t, []).append(Indicator("Κυβερνήτης", f"rulpos:{ruler}", (ruler,), label))
    return by_theme


def _aspect_indicators(chart) -> dict[str, list[Indicator]]:
    by_theme: dict[str, list[Indicator]] = {}
    seen = set()
    for a in chart.aspects:
        if a.first in NODES or a.second in NODES:
            continue  # Δεσμοί: συμβολική κατεύθυνση, όχι ταλέντο (Κανόνας 10)
        key = frozenset((a.first, a.second))
        theme = _PAIR.get(key)
        if theme is None or key in seen:
            continue
        seen.add(key)
        by_theme.setdefault(theme, []).append(Indicator(
            "Όψη", f"asp:{a.first}|{a.second}", (a.first, a.second),
            f"{a.first}–{a.second} | {a.aspect} | orb {a.orb_text}", a.weight, a.aspect, a.orb))
    return by_theme


def _qualify(indicators: list[Indicator]) -> tuple[list[Indicator], list[Indicator], str | None]:
    """Κανόνας 10 της εντολής v13 (v22.9: ακριβής εφαρμογή, μετά από σύγκριση με αναφορά AI).
    Διακριτοί δείκτες: «μία θέση πλανήτη και μία όψη του ίδιου πλανήτη προς διαφορετικό πλανήτη
    (δύο)». ΔΕΝ μετρούν ως νέοι: «δύο πλανήτες που έχουν ήδη μετρηθεί μέσω της μεταξύ τους όψης,
    αν παρουσιαστούν ξανά ως ξεχωριστές θέσεις» -- δηλαδή όταν υπάρχουν οι θέσεις ΚΑΙ των δύο.
    Εξαίρεση πλατιών: δύο «Πλατιά αλλά έγκυρη» με ΚΟΙΝΟ σημείο (οποιοδήποτε), η καθεμία με
    προσωπικό πλανήτη ή γωνία (όπως το astrology.wide_aspect_clusters)."""
    aspects = [i for i in indicators if i.kind == "Όψη" and i.weight != VERY_WIDE]
    positions = {i.points[0] for i in indicators if i.kind == "Θέση"}
    repeated = {p for a in aspects if set(a.points) <= positions for p in a.points}
    counted, supporting = [], []
    for i in indicators:
        if i.weight == VERY_WIDE:
            supporting.append(i)                       # μόνο απόχρωση
        elif i.kind == "Θέση" and i.points[0] in repeated:
            supporting.append(i)                       # και οι δύο πλανήτες ήδη μετρημένοι μέσω της όψης τους
        elif i.kind == "Κυβερνήτης" and i.key.startswith("rulpos:"):
            supporting.append(i)                       # πού βρίσκεται ο κυβερνήτης: μόνο ενίσχυση (v22.12)
        elif i.kind == "Κυβερνήτης" and i.points[0] in positions:
            supporting.append(i)                       # ο ίδιος πλανήτης μετρά ήδη μέσω της θέσης του
        else:
            counted.append(i)
    primary = [i for i in counted if i.kind == "Θέση" or i.weight in (STRONG, NORMAL)]   # ΟΧΙ ο κυβερνήτης
    wide = [i for i in counted if i.weight == WIDE and set(i.points) & set(PERSONAL_OR_ANGLE)]
    strong_single = [i for i in counted if i.weight == STRONG and set(i.points) & set(PERSONAL_OR_ANGLE)]
    if len(counted) >= 2 and primary:
        return counted, supporting, "δύο δείκτες"
    if strong_single:
        return counted, supporting, "μοναδικός ισχυρός δείκτης"
    for x in wide:
        for y in wide:
            if x is not y and set(x.points) & set(y.points):
                return counted, supporting, "δύο πλατιές με κοινό σημείο"
    return counted, supporting, None


def _health_indicators(chart, rules) -> list[tuple[str, frozenset, str]]:
    """Όλοι οι δείκτες υγείας του χάρτη για έναν τομέα: (περιγραφή, σημεία)."""
    pts = {p.name: p for p in chart.points}
    found = []
    for kind, a, b in rules:
        if kind in ("house", "sign"):
            for name in a:
                p = pts.get(name)
                if p is None:
                    continue
                if kind == "house" and p.house in b:
                    found.append((f"{name} στον Οίκο {p.house}", frozenset((name,)), kind))
                elif kind == "sign" and p.sign in b:
                    found.append((f"{name} σε {p.sign}", frozenset((name,)), kind))
        else:
            for x in chart.aspects:
                if {x.first, x.second} & {a} and ({x.first, x.second} - {a}) & set(b) and x.weight == STRONG:
                    found.append((f"{x.first}–{x.second} | {x.aspect} | orb {x.orb_text} | {x.weight}",
                                  frozenset((x.first, x.second)), kind))
    return found  # σειρά: όπως ο πίνακας HEALTH_RULES (ο αστρολόγος ορίζει την προτεραιότητα)


def _health_pair(found) -> list[str] | None:
    """Δύο δείκτες με διαφορετικά σημεία (π.χ. «Ήλιος στον 6ο» + «Ήλιος σε Παρθένο» = ένας
    πλανήτης, δεν αρκεί)."""
    for i, (la, pa, ka) in enumerate(found):
        for lb, pb, kb in found[i + 1:]:
            if pa != pb and len(pa | pb) >= 2 and "sign" in (ka, kb) and ka == kb == "sign":
                continue  # δύο ζώδια μόνο: πολύ γενικό
            if pa != pb and len(pa | pb) >= 2:
                return [f"Δείκτης 1: {la}", f"Δείκτης 2: {lb}"]
    return None


def _rank(score: float) -> str:
    return "κυρίαρχο" if score >= DOMINANT_MIN else "βασικό" if score >= BASIC_MIN else "αναδυόμενο"


def _colour_candidates(chart, t: Talent):
    """v22.15 -- υποψήφιες αποχρώσεις ενός ταλέντου: (προτεραιότητα, βαθμός δείκτη, κλειδί, δείκτης).
    Μετρούν μόνο οι δείκτες που στηρίζουν το ταλέντο (θέσεις και όψεις, όχι κυβερνήτες). Ένα σημείο
    «χρωματίζει» το ταλέντο όταν ΔΕΝ είναι η πηγή του: προτεραιότητα 2 αν δεν έχει καθόλου το θέμα,
    1 αν το έχει αλλά όχι ως κύρια λειτουργία. Γωνίες και Δεσμοί δεν δίνουν απόχρωση· το ζώδιο αργού
    πλανήτη επίσης όχι (είναι κοινό σε μια γενιά)."""
    signs = {p.name: p.sign for p in chart.points}
    out = []
    for i in t.indicators:
        keys = []
        if i.kind == "Όψη":
            keys = [(p, PLANET_THEMES.get(p)) for p in i.points if p in PLANET_THEMES]
            # v22.21: και το ΖΩΔΙΟ ενός προσωπικού πλανήτη της όψης (π.χ. Σελήνη σε Παρθένο στη Σελήνη–
            # Ποσειδώνας) -- με μισό βάρος, ώστε να προηγούνται οι πλανήτες της όψης.
            for p in i.points:   # μόνο ο πλανήτης-ΠΗΓΗ (έχει το θέμα): το ζώδιό του δείχνει «πώς»
                if p in PERSONAL and t.theme in PLANET_THEMES.get(p, ()) and signs.get(p) in SIGN_THEMES:
                    themes = SIGN_THEMES[signs[p]]
                    prio = 2 if t.theme not in themes else (1 if themes[0] != t.theme else 0)
                    if prio and signs[p] in COLOURS:
                        out.append((prio, i.score * 0.5, signs[p], f"{p} σε {signs[p]} ({i.label})"))
        elif i.kind == "Θέση":
            p = i.points[0]
            keys = [(p, PLANET_THEMES.get(p))]
            if p not in SLOW and signs.get(p) in SIGN_THEMES:
                keys.append((signs[p], SIGN_THEMES[signs[p]]))
        for key, themes in keys:
            if key not in COLOURS or not themes:
                continue
            prio = 2 if t.theme not in themes else (1 if themes[0] != t.theme else 0)
            if prio:
                out.append((prio, i.score, key, i.label))
    out.sort(key=lambda c: (-c[0], -c[1]))
    return out


MAX_COLOURS = 4


_COLOUR_STOP = {"αλλους", "αλλου", "αλλον", "αλλοι", "αλλων", "ειναι", "δινει", "πραγματα", "πραγματων", "εαυτου", "others", "other",
                "things", "which", "where", "yourself"}


def _stems(text: str) -> set[str]:
    import re
    import unicodedata
    plain = "".join(c for c in unicodedata.normalize("NFD", text or "") if unicodedata.category(c) != "Mn").casefold()
    return {w[:5] for w in re.findall(r"\w{5,}", plain) if w not in _COLOUR_STOP}


def _library_stems(theme: str) -> set[str]:
    """Ρίζες λέξεων του τίτλου και της περιγραφής (el + en) του ταλέντου."""
    from .talent_texts import talent_text
    out: set[str] = set()
    for lang in ("el", "en"):
        tx = talent_text(theme, lang)
        out |= _stems(" ".join((tx.get("title", ""), tx.get("text", ""))))
    return out


def _assign_colours(chart, talents: list[Talent]) -> None:
    """Αποχρώσεις («πώς φαίνεται σε σένα»).
      * Κάθε σημείο έχει διατυπώσεις: πρώτα η ειδική του συνδυασμού (αν υπάρχει), μετά 3 γενικές. Παίρνεται
        η πρώτη που (α) δεν έχει ήδη μπει στην αναφορά και (β) v22.22: ΔΕΝ επαναλαμβάνει λέξη από τον τίτλο ή
        την περιγραφή του ίδιου ταλέντου. Αν δεν υπάρχει τέτοια, το σημείο
        παραλείπεται.
      1. Πρώτη απόχρωση για ΚΑΘΕ ταλέντο: πρώτα οι πιο καθαρές (σημείο χωρίς το θέμα, από ισχυρότερο δείκτη)·
         κάθε σημείο σε ένα ταλέντο· όσα μείνουν χωρίς παίρνουν σημείο ήδη χρησιμοποιημένο.
      2. v22.21: οι υπόλοιπες αληθινές αποχρώσεις κάθε ταλέντου, από άλλα σημεία, έως MAX_COLOURS."""
    cands = {t.theme: _colour_candidates(chart, t) for t in talents}
    lib = {t.theme: _library_stems(t.theme) for t in talents}
    pairs = sorted(((-prio, -score, n, key, label, t)
                    for n, t in enumerate(talents) for prio, score, key, label in cands[t.theme]),
                   key=lambda x: x[:3])
    used_phrases: set[str] = set()
    used_keys: set[str] = set()

    used_stems: set[str] = set()      # v22.22: ούτε η ίδια λέξη-κλειδί δύο φορές στην αναφορά (π.χ. «θάρρος»)

    def pick(t, key):
        for v in colour_options(key, t.theme):
            el, en = colour_phrase(key, v, "el", t.theme), colour_phrase(key, v, "en", t.theme)
            stems = _stems(el) | _stems(en)
            if el and el not in used_phrases and not stems & (lib[t.theme] | used_stems):
                return v, el, stems
        return None

    def add(t, key, label):
        got = pick(t, key)
        if got is None:
            return False
        t.colours.append((key, got[0], label))
        used_phrases.add(got[1])
        used_stems.update(got[2])
        used_keys.add(key)
        return True

    for t in talents:
        t.colours = []
    for allow_reuse in (False, True):
        for _, _, _, key, label, t in pairs:
            if t.colours or (key in used_keys and not allow_reuse):
                continue
            add(t, key, label)
    for t in talents:
        for _, _, key, label in cands[t.theme]:
            if len(t.colours) >= MAX_COLOURS or key in {c[0] for c in t.colours}:
                continue
            add(t, key, label)
    for t in talents:   # σειρά εμφάνισης: πρώτα η πιο καθαρή/ισχυρή απόχρωση
        order: dict[str, int] = {}
        for i, (_, _, key, _) in enumerate(cands[t.theme]):
            order.setdefault(key, i)
        t.colours.sort(key=lambda c: order.get(c[0], 99))


def run_engine(chart) -> EngineResult:
    positions, aspects = _position_indicators(chart), _aspect_indicators(chart)
    rulers = _ruler_indicators(chart)
    talents, rejected = [], {}
    for theme in THEMES:
        indicators = aspects.get(theme, []) + positions.get(theme, []) + rulers.get(theme, [])
        if not indicators:
            continue
        counted, supporting, basis = _qualify(indicators)
        if basis is None:
            rejected[theme] = "ανεπαρκής τεκμηρίωση (Κανόνας 10)"
            continue
        score = sum(i.score for i in counted) + 0.25 * sum(i.score for i in supporting)
        talents.append(Talent(theme, THEMES[theme][0], THEMES[theme][1], counted, supporting, basis,
                              _rank(score), round(score, 2)))
    order = {"κυρίαρχο": 0, "βασικό": 1, "αναδυόμενο": 2}
    talents.sort(key=lambda t: (order[t.rank], -t.score, min((i.orb for i in t.indicators if i.kind == "Όψη"),
                                                                   default=99)))
    _assign_colours(chart, talents)
    # ---- τομείς (Κανόνας 12)
    support: dict[str, dict[str, float]] = {}            # τομέας -> {ταλέντο: συνεισφορά}
    for t in talents:
        for pos, f in enumerate(THEME_FIELDS.get(t.theme, ())):
            support.setdefault(f, {})[t.theme] = t.score * FIELD_POSITION_WEIGHTS[min(pos, 3)]
    meeting = sorted((f for f, c in support.items() if len(c) >= 2),
                     key=lambda f: (-sum(support[f].values()), f))[:MAX_MAIN_FIELDS]
    fields: list[FieldChoice] = [
        FieldChoice(f, sorted(support[f], key=lambda th: -support[f][th]), "ΕΠΙΛΕΓΕΤΑΙ",
                    score=round(sum(support[f].values()), 2)) for f in meeting]
    main_names = {fc.name for fc in fields}
    for t in talents:  # εγγύηση: κάθε ταλέντο σε τουλάχιστον έναν κύριο τομέα
        if not any(t.theme in fc.talents for fc in fields):
            best = max(THEME_FIELDS[t.theme], key=lambda f: (support[f][t.theme], f))
            existing = next((fc for fc in fields if fc.name == best), None)
            if existing:  # v22.3: ίδιος τομέας για δύο ταλέντα -> ΜΙΑ εγγραφή (όχι διπλή)
                existing.talents.append(t.theme)
                existing.score = round(existing.score + support[best][t.theme], 2)
                existing.guarantee = len(existing.talents) < 2
                existing.coverage = True
            else:
                fields.append(FieldChoice(best, [t.theme], "ΕΠΙΛΕΓΕΤΑΙ", guarantee=True, coverage=True,
                                          score=round(support[best][t.theme], 2)))
            main_names.add(best)
    brief: dict[str, list[str]] = {}
    for t in talents:  # άλλες κατευθύνσεις: οι καλύτεροι τομείς κάθε ταλέντου, εκτός κύριων
        ranked = sorted(THEME_FIELDS.get(t.theme, ()), key=lambda f: -support[f][t.theme])
        for f in [f for f in ranked if f not in main_names][:FIELDS_PER_THEME]:
            brief.setdefault(f, []).append(t.theme)
    brief_choices = [FieldChoice(f, ts, "ΣΥΝΤΟΜΗ ΑΝΑΦΟΡΑ", score=round(sum(support[f][th] for th in ts), 2))
                     for f, ts in brief.items()]
    brief_choices.sort(key=lambda fc: (-fc.score, fc.name))
    fields += brief_choices[:MAX_BRIEF_FIELDS]
    # ---- τομείς υγείας (Κανόνας 15): μόνο με δύο ειδικούς δείκτες + σχετικό εγκεκριμένο ταλέντο
    approved = [t.theme for t in talents]
    for name, rule in HEALTH_RULES.items():
        basis = _health_pair(_health_indicators(chart, rule["indicators"]))
        related = [th for th in approved if th in rule["related"]]
        if basis and related:
            sc = round(sum(t.score for t in talents if t.theme in related), 2)
            fields.append(FieldChoice(name, related, "ΕΠΙΛΕΓΕΤΑΙ" if len(related) >= 2 else "ΣΥΝΤΟΜΗ ΑΝΑΦΟΡΑ",
                                      score=sc, health_basis=basis))
        elif basis or related:
            rejected[name] = ("φραγμός υγείας: δεν υπάρχουν δύο ειδικοί δείκτες (Κανόνας 15)" if not basis
                              else "φραγμός υγείας: λείπει σχετικό εγκεκριμένο ταλέντο")
    fields.sort(key=lambda fc: (fc.decision != "ΕΠΙΛΕΓΕΤΑΙ", fc.guarantee, -len(fc.talents), -fc.score))
    for t in talents:
        t.fields = [fc.name for fc in fields if t.theme in fc.talents]  # περιλαμβάνει τομείς υγείας
    return EngineResult(talents, fields, rejected)
