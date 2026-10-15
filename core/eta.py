"""
eta.py -- εκτίμηση χρόνου αναμονής (v18).

Ξεκινά από το εύρος AUTO_ETA_MINUTES (π.χ. "10-25") και, μόλις υπάρξουν
τουλάχιστον 3 πραγματικές ολοκληρωμένες εκτελέσεις, «μαθαίνει» από αυτές
(25ο-75ο εκατοστημόριο). Οι διάρκειες κρατιούνται σε ένα μικρό αρχείο στον
προσωρινό φάκελο του διακομιστή (μόνο αριθμοί λεπτών -- κανένα προσωπικό
στοιχείο). Στο Streamlit Cloud το αρχείο σβήνεται σε επανεκκίνηση· τότε η
εκτίμηση ξαναρχίζει από το AUTO_ETA_MINUTES.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

DEFAULT_RANGE = (5.0, 10.0)  # πρώτη πραγματική αναφορά: 7–8 λεπτά
_FILE = Path(tempfile.gettempdir()) / "astrocheck_career_durations.json"
_KEEP = 30


def _configured_range() -> tuple[float, float]:
    raw = os.environ.get("AUTO_ETA_MINUTES", "")
    try:
        lo, hi = (float(x) for x in raw.replace("–", "-").split("-"))
        return (min(lo, hi), max(lo, hi))
    except ValueError:
        return DEFAULT_RANGE


def _load(path: Path = _FILE) -> list[float]:
    try:
        return [float(x) for x in json.loads(path.read_text())][-_KEEP:]
    except (OSError, ValueError, TypeError):
        return []


def record_duration(minutes: float, path: Path = _FILE) -> None:
    data = (_load(path) + [round(minutes, 1)])[-_KEEP:]
    try:
        path.write_text(json.dumps(data))
    except OSError:
        pass


def typical_range(path: Path = _FILE) -> tuple[int, int]:
    data = sorted(_load(path))
    if len(data) < 3:
        lo, hi = _configured_range()
    else:
        lo = data[int(0.25 * (len(data) - 1))]
        hi = data[int(round(0.75 * (len(data) - 1)))]
    lo_i = max(1, int(lo))
    return lo_i, max(lo_i + 1, int(hi + 0.999))


def remaining_minutes(elapsed_min: float, path: Path = _FILE) -> tuple[int, int]:
    lo, hi = typical_range(path)
    return max(0, int(lo - elapsed_min)), max(1, int(hi - elapsed_min + 0.999))
