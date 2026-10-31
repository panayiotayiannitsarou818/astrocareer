"""
core/talent_engine.py -- AstroCheck Career (v22, ΠΡΟΧΕΙΡΟ -- υβριδική μέθοδος)

ΜΗΧΑΝΗ ΤΑΛΕΝΤΩΝ: από τον χάρτη στη ΠΛΗΡΗ λίστα ταλέντων και επαγγελματικών τομέων,
με τους κανόνες της δεσμευτικής εντολής v13 -- χωρίς AI. Ο ίδιος χάρτης δίνει
πάντα το ίδιο αποτέλεσμα, και κανένας δείκτης δεν «ξεχνιέται».

Ροή:
  1. Δείκτες Θέσης  (Κανόνες 4–6): πλανήτης σε ζώδιο/βασικό Οίκο που ταιριάζει με
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
    ANGLES, HEALTH_RULES, HOUSE_THEMES, NODES, PAIR_THEME, PERSONAL, PLANET_THEMES, SIGN_THEMES, SLOW, THEME_FIELDS, THEMES,
)

STRONG, NORMAL, WIDE, VERY_WIDE = "Στενή/ισχυρή", "Κανονική", "Πλατιά αλλά έγκυρη", "Πολύ πλατιά/δευτερεύουσα"
ASPECT_SCORE = {STRONG: 3.0, NORMAL: 2.0, WIDE: 1.0, VERY_WIDE: 0.5}
POSITION_SCORE = 1.5
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
    health_basis: list[str] = field(default_factory=list)  # Κανόνας 15: «Δείκτης 1:», «Δείκτης 2:»


@dataclass
class EngineResult:
    talents: list[Talent]
    fields: list[FieldChoice]
    candidates_rejected: dict[str, str]  # θέμα -> λόγος


def _position_indicators(chart) -> dict[str, list[Indicator]]:
    by_theme: dict[str, list[Indicator]] = {}
    in_concentration: dict[tuple[str, str], str] = {}  # (πλανήτης, θέμα) -> ετικέτα
    for label, names in planet_concentrations(chart.points):
        kind, value = label.split(" ", 1)
        if kind == "Ζώδιο":
            theme = SIGN_THEMES[value][0]
        else:
            themes = HOUSE_THEMES.get(int(value))
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
        themes |= {t for (n, t) in in_concentration if n == p.name}
        for t in themes:
            conc = (p.name, t) in in_concentration
            by_theme.setdefault(t, []).append(Indicator(
                "Θέση", f"pos:{p.name}", (p.name,),
                f"{p.name} σε {p.sign}, Οίκος {p.house}" + (f" ({in_concentration[(p.name, t)]})" if conc else ""),
                concentration=conc))
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
    aspects = [i for i in indicators if i.kind == "Όψη"]
    in_aspects = {p for i in aspects if i.weight != VERY_WIDE for p in i.points}
    counted, supporting = [], []
    for i in indicators:
        if i.weight == VERY_WIDE:
            supporting.append(i)                       # μόνο απόχρωση
        elif i.kind == "Θέση" and i.points[0] in in_aspects:
            supporting.append(i)                       # ήδη μετρημένος μέσω όψης του
        else:
            counted.append(i)
    primary = [i for i in counted if i.kind == "Θέση" or i.weight in (STRONG, NORMAL)]
    wide = [i for i in counted if i.weight == WIDE]
    strong_single = [i for i in counted if i.weight == STRONG and set(i.points) & set(PERSONAL_OR_ANGLE)]
    if len(counted) >= 2 and primary:
        return counted, supporting, "δύο δείκτες"
    if strong_single:
        return counted, supporting, "μοναδικός ισχυρός δείκτης"
    for x in wide:
        for y in wide:
            if x is not y and set(x.points) & set(y.points) & set(PERSONAL_OR_ANGLE):
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


def run_engine(chart) -> EngineResult:
    positions, aspects = _position_indicators(chart), _aspect_indicators(chart)
    talents, rejected = [], {}
    for theme in THEMES:
        indicators = aspects.get(theme, []) + positions.get(theme, [])
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
            else:
                fields.append(FieldChoice(best, [t.theme], "ΕΠΙΛΕΓΕΤΑΙ", guarantee=True,
                                          score=round(support[best][t.theme], 2)))
            main_names.add(best)
    brief: dict[str, list[str]] = {}
    for t in talents:  # άλλες κατευθύνσεις: οι καλύτεροι τομείς κάθε ταλέντου, εκτός κύριων
        ranked = sorted(THEME_FIELDS.get(t.theme, ()), key=lambda f: -support[f][t.theme])
        for f in [f for f in ranked if f not in main_names][:FIELDS_PER_THEME]:
            brief.setdefault(f, []).append(t.theme)
    for f, ts in brief.items():
        fields.append(FieldChoice(f, ts, "ΣΥΝΤΟΜΗ ΑΝΑΦΟΡΑ", score=round(sum(support[f][th] for th in ts), 2)))
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
