"""
core/talent_texts.py -- AstroCheck Career (v22)

Έτοιμα κείμενα για τη μηχανή ταλέντων (core/data/talent_texts.json): περιγραφή και
τρόπος καλλιέργειας για κάθε ταλέντο, σύντομη εξήγηση με παραδείγματα για κάθε τομέα.
Χωρίς κλήση AI. Οι τομείς υγείας εμφανίζονται μόνο όταν περάσει ο φραγμός του Κανόνα 15.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

TEXTS = os.path.join(os.path.dirname(__file__), "data", "talent_texts.json")


@lru_cache(maxsize=1)
def load_texts() -> dict:
    with open(TEXTS, encoding="utf-8") as f:
        return json.load(f)


def talent_text(theme: str, lang: str = "el") -> dict:
    """{'title', 'text', 'develop'} στη γλώσσα του πελάτη (ελληνικά αν λείπει)."""
    entry = load_texts()["talents"][theme]
    return entry.get(lang) or entry["el"]


def field_text(name: str, lang: str = "el") -> dict:
    """{'name', 'desc'}· `name` = το ελληνικό όνομα του τομέα από τον κατάλογο v13."""
    entry = load_texts()["fields"][name]
    return entry.get(lang) or entry["el"]


def approval_status() -> dict[str, int]:
    """Πόσα στοιχεία είναι ακόμη πρόχειρα: {'tables': 0/1, 'talents': n, 'fields': n, 'teasers': n}."""
    from .talent_map import TABLES_STATUS
    from .teaser import teaser_drafts
    d = load_texts()
    return {"tables": int(TABLES_STATUS != "approved"), "teasers": teaser_drafts(),
            "talents": sum(e["status"] != "approved" for e in d["talents"].values()),
            "fields": sum(e["status"] != "approved" for e in d["fields"].values())}


def fully_approved() -> bool:
    """Η ΠΛΗΡΗΣ αναφορά: πίνακες + κείμενα ταλέντων/τομέων (το δωρεάν ταλέντο ελέγχεται χωριστά)."""
    st = approval_status()
    return not (st["tables"] or st["talents"] or st["fields"])
