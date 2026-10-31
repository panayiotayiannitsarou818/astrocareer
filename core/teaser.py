"""
core/teaser.py -- AstroCheck Career (v21)

«Δωρεάν ταλέντο»: ένα έτοιμο κείμενο από βιβλιοθήκη (core/data/teaser_library.json),
χωρίς κλήση AI -- άρα χωρίς κόστος ανά επισκέπτη.

Κανόνας επιλογής:
  1. Τρίγωνα του χάρτη με ΤΟΥΛΑΧΙΣΤΟΝ ένα προσωπικό σημείο (Ήλιος, Σελήνη, Ερμής,
     Αφροδίτη, Άρης, Ωροσκόπος, Μεσουράνημα). Τα τρίγωνα μόνο ανάμεσα σε αργούς
     πλανήτες είναι κοινά σε μια ολόκληρη γενιά και εξαιρούνται (όπως και στον
     Κανόνα 5 της δεσμευτικής εντολής). Οι Δεσμοί εξαιρούνται.
  2. Το ΣΤΕΝΟΤΕΡΟ (μικρότερο orb) κερδίζει.
  3. Αν δεν υπάρχει (≈0,3% των χαρτών): το στενότερο εξάγωνο με την ίδια συνθήκη.
  4. Αν δεν υπάρχει ούτε αυτό (≈1 στους 1.500): κανένα δωρεάν ταλέντο.
Το ίδιο ταλέντο δίνεται στο AI με οδηγία να συμπεριληφθεί στην πλήρη αναφορά,
εφόσον τεκμηριώνεται κατά τους κανόνες (teaser_instruction).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache

LIBRARY = os.path.join(os.path.dirname(__file__), "data", "teaser_library.json")
PERSONAL_POINTS = ("Ήλιος", "Σελήνη", "Ερμής", "Αφροδίτη", "Άρης", "Ωροσκόπος", "Μεσουράνημα")
NODE_POINTS = ("Βόρειος Δεσμός", "Νότιος Δεσμός")
ASPECT_PRIORITY = ("Τρίγωνο", "Εξάγωνο")


@dataclass(frozen=True)
class Teaser:
    pair: tuple[str, str]
    aspect: str  # «Τρίγωνο» ή «Εξάγωνο»
    orb_text: str
    weight: str
    title: str
    text: str
    status: str  # «draft» / «approved»

    @property
    def natural(self) -> bool:
        """Τρίγωνο = ταλέντο που βγαίνει φυσικά· εξάγωνο = με ευκαιρίες και εξάσκηση."""
        return self.aspect == "Τρίγωνο"


@lru_cache(maxsize=1)
def load_library() -> dict[frozenset, dict]:
    with open(LIBRARY, encoding="utf-8") as f:
        data = json.load(f)
    return {frozenset(e["pair"]): e for e in data["entries"]}


def pick_teaser(chart, lang: str = "el", approved_only: bool = False) -> Teaser | None:
    """v22: διαλέγει ΜΟΝΟ ανάμεσα σε όψεις που η μηχανή ταλέντων χρησιμοποιεί ως δείκτη
    εγκεκριμένου ταλέντου -- ώστε το δωρεάν ταλέντο να υπάρχει ΠΑΝΤΑ και στην πλήρη
    αναφορά. Αν δεν υπάρχει τέτοια όψη, πέφτει στον αρχικό κανόνα (v21).
    approved_only (v22.4): μόνο κείμενα με status «approved» -- για τους πελάτες όσο ισχύει η έγκριση."""
    library = load_library()
    if approved_only:
        library = {k: v for k, v in library.items() if v.get("status") == "approved"}
    try:
        from .talent_engine import run_engine
        approved = {frozenset(i.points) for t in run_engine(chart).talents for i in t.indicators if i.kind == "Όψη"}
    except Exception:  # noqa: BLE001 -- η μηχανή δεν πρέπει ποτέ να «ρίξει» το δωρεάν ταλέντο
        approved = set()
    for restrict in ((True, False) if approved else (False,)):
        found = _pick(chart, lang, library, approved if restrict else None)
        if found:
            return found
    return None


def _pick(chart, lang, library, approved) -> Teaser | None:
    for aspect_type in ASPECT_PRIORITY:
        candidates = [
            a for a in chart.aspects
            if a.aspect == aspect_type
            and (a.first in PERSONAL_POINTS or a.second in PERSONAL_POINTS)
            and a.first not in NODE_POINTS and a.second not in NODE_POINTS
            and frozenset((a.first, a.second)) in library
            and (approved is None or frozenset((a.first, a.second)) in approved)
        ]
        if candidates:
            best = min(candidates, key=lambda a: (a.orb, a.first, a.second))
            entry = library[frozenset((best.first, best.second))]
            texts = entry.get(lang) or entry["el"]
            return Teaser((best.first, best.second), best.aspect, best.orb_text, best.weight,
                          texts["title"], texts["text"], entry.get("status", "draft"))
    return None


def teaser_instruction(chart, lang: str) -> str:
    """Οδηγία για το AI: το δωρεάν ταλέντο να εμφανίζεται και στην πλήρη αναφορά
    (ο πελάτης το έχει ήδη δει), ΜΟΝΟ εφόσον τεκμηριώνεται κατά τους κανόνες."""
    teaser = pick_teaser(chart, lang)
    if teaser is None:
        return ""
    a, b = teaser.pair
    if lang == "el":
        return (f"Δωρεάν δείγμα που έχει ήδη δει ο πελάτης: το ταλέντο «{teaser.title}», από την όψη "
                f"{a}–{b} ({teaser.aspect}, orb {teaser.orb_text}). Συμπερίλαβε στην αναφορά ταλέντο με το "
                f"ίδιο νόημα και, κατά προτίμηση, τον ίδιο ή παρόμοιο τίτλο, ΜΟΝΟ εφόσον τεκμηριώνεται πλήρως "
                f"κατά τους κανόνες της εντολής (η όψη αυτή είναι ένας από τους δείκτες του). Αν δεν "
                f"τεκμηριώνεται, μην το προσθέσεις -- οι κανόνες τεκμηρίωσης έχουν πάντα προτεραιότητα.")
    return (f"Free sample the client has already seen: the talent \"{teaser.title}\", from the aspect "
            f"{a}–{b} ({teaser.aspect}, orb {teaser.orb_text}). Include in the report a talent with the same "
            f"meaning and, preferably, the same or a similar title, ONLY if it is fully documented under the "
            f"command's rules (this aspect is one of its indicators). If it is not documented, do not add it -- "
            f"the documentation rules always take priority.")


def teaser_drafts() -> int:
    """Πόσα κείμενα της βιβλιοθήκης δωρεάν ταλέντου δεν έχουν ακόμη εγκριθεί."""
    return sum(e.get("status") != "approved" for e in load_library().values())
