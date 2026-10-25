"""
core/birth_input.py -- AstroCheck

Από τα στοιχεία που δίνει ο χρήστης (όνομα, ημερομηνία, ώρα, τόπος) στο
αντικείμενο Chart που χρησιμοποιεί η υπόλοιπη εφαρμογή -- χωρίς PDF.
"""
from __future__ import annotations

import hashlib
from datetime import date, time

from .birthtime import BirthMoment, to_ut
from .ephemeris import compute_chart
from .models import Chart
from .parser import _validate_chart_sanity


class NonexistentTimeError(ValueError):
    """Η ώρα δεν υπήρξε στον τόπο (τα ρολόγια πήγαν μπροστά): ζητείται διόρθωση."""


def chart_from_birth(
    name: str,
    birth_date: date,
    birth_time: time,
    lat: float,
    lon: float,
    tz_name: str,
    place_label: str = "",
    manual_offset_hours: float | None = None,
    fold: int | None = None,
) -> tuple[Chart, BirthMoment]:
    moment = to_ut(birth_date, birth_time, tz_name, manual_offset_hours=manual_offset_hours, fold=fold)
    if moment.nonexistent:
        raise NonexistentTimeError("Η τοπική ώρα γέννησης δεν υπήρξε (αλλαγή ρολογιών).")
    chart = compute_chart(
        moment.ut,
        lat,
        lon,
        name=(name or "").strip(),
        place=place_label,
        local_time_text=f"{birth_time.strftime('%H:%M')} ({moment.offset_text})",
    )
    chart.date = birth_date.strftime("%d/%m/%Y")
    chart.warnings.extend(moment.warnings)
    errors = _validate_chart_sanity(chart)
    if errors:
        raise ValueError("Ο υπολογισμός του χάρτη απέτυχε στους ελέγχους λογικότητας: " + " · ".join(errors))
    return chart, moment


def birth_case_key(name, birth_date, birth_time, lat, lon, offset_hours) -> str:
    raw = f"{(name or '').strip()}|{birth_date.isoformat()}|{birth_time.strftime('%H:%M')}|{lat:.5f}|{lon:.5f}|{offset_hours:.4f}"
    return "birth:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
