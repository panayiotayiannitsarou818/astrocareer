"""v19 -- Κατάλογος επαγγελματικών τομέων (Κανόνας 12 της δεσμευτικής εντολής).

Μοναδική πηγή: ο πίνακας μέσα στο ίδιο το .docx της δεσμευτικής εντολής, ώστε
ο έλεγχος κάλυψης τομέων (validator) να χρησιμοποιεί ΑΚΡΙΒΩΣ τον κατάλογο που
είδε το μοντέλο. Δεν εισάγει streamlit (ο validator τρέχει και χωρίς αυτό).
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from docx import Document

REPO_ROOT = Path(__file__).resolve().parent.parent
ORIENTATION_FILENAME = "Desmeftiki_Entoli_Epaggelmatikou_Prosanatolismou_Koini_v13.docx"
_CANDIDATES = (REPO_ROOT / "references" / ORIENTATION_FILENAME, REPO_ROOT / ORIENTATION_FILENAME)
HEALTH_MARK = "(*)"


def clean_sector_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.replace(HEALTH_MARK, "")).strip()


@lru_cache(maxsize=4)
def _load(path_str: str) -> tuple[tuple[str, bool], ...]:
    document = Document(path_str)
    for table in document.tables:
        header = [c.text.strip() for c in table.rows[0].cells]
        if header and header[0].startswith("Επαγγελματικός τομέας"):
            rows = []
            for row in table.rows[1:]:
                raw = row.cells[0].text.strip()
                if raw:
                    rows.append((clean_sector_name(raw), HEALTH_MARK in raw))
            return tuple(rows)
    raise ValueError(f"Δεν βρέθηκε ο πίνακας τομέων μέσα στο {Path(path_str).name}.")


def sector_catalogue(path: str | Path | None = None) -> list[str]:
    """Τα ονόματα των τομέων του καταλόγου (χωρίς το σημάδι υγείας «(*)»)."""
    if path is None:
        path = next((p for p in _CANDIDATES if p.exists()), None)
        if path is None:
            raise FileNotFoundError(f"Λείπει η δεσμευτική εντολή: {ORIENTATION_FILENAME}")
    return [name for name, _ in _load(str(path))]
