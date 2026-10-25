"""
core/birthtime.py -- AstroCheck

Τοπική ώρα γέννησης -> UT, με την ιστορική βάση ζωνών ώρας IANA (tzdata):
χειμερινή/θερινή ώρα της χρονιάς, αλλαγές ζώνης, τοπική ώρα (LMT) πριν την
υιοθέτηση ζώνης.

Προσοχή (από την ίδια την τεκμηρίωση της IANA): πριν το 1970 αρκετές
καταχωρήσεις είναι αβέβαιες. Γι' αυτό η διαφορά από UT ΕΜΦΑΝΙΖΕΤΑΙ στον
χρήστη για επιβεβαίωση και μπορεί να διορθωθεί χειροκίνητα.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


@dataclass
class BirthMoment:
    local: datetime  # naive, τοπική ώρα όπως τη δήλωσε ο χρήστης
    ut: datetime  # timezone-aware UTC
    offset_hours: float  # τοπική - UT
    zone_name: str
    is_dst: bool
    warnings: list[str] = field(default_factory=list)
    nonexistent: bool = False  # η τοπική ώρα δεν υπήρξε (τα ρολόγια πήγαν μπροστά)
    ambiguous: bool = False  # η τοπική ώρα υπήρξε δύο φορές (τα ρολόγια γύρισαν πίσω)

    @property
    def offset_text(self) -> str:
        sign = "+" if self.offset_hours >= 0 else "−"
        total = round(abs(self.offset_hours) * 60)
        h, m = divmod(total, 60)
        base = f"UT{sign}{h}" + (f":{m:02d}" if m else "")
        return base + (" (θερινή ώρα)" if self.is_dst else "")


def to_ut(
    birth_date: date,
    birth_time: time,
    tz_name: str,
    *,
    manual_offset_hours: float | None = None,
    fold: int | None = None,
) -> BirthMoment:
    """fold: για διπλή ώρα (επιστροφή ρολογιών) 0 = η πρώτη φορά (πριν γυρίσουν
    τα ρολόγια), 1 = η δεύτερη. Αν δεν δοθεί, χρησιμοποιείται η πρώτη και το
    BirthMoment.ambiguous = True ώστε η σελίδα να ζητήσει επιλογή."""
    local = datetime.combine(birth_date, birth_time)
    warnings: list[str] = []
    nonexistent = False
    ambiguous = False

    if manual_offset_hours is not None:
        ut = (local - timedelta(hours=manual_offset_hours)).replace(tzinfo=timezone.utc)
        return BirthMoment(local, ut, manual_offset_hours, "χειροκίνητα", False, [])

    zone = ZoneInfo(tz_name)
    a = local.replace(tzinfo=zone, fold=0)
    b = local.replace(tzinfo=zone, fold=1)
    off_a, off_b = a.utcoffset(), b.utcoffset()

    if off_a != off_b:
        # Είτε διπλή ώρα (επιστροφή ρολογιών) είτε ανύπαρκτη (μπροστά τα ρολόγια).
        back_a = a.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None)
        if back_a != local:
            nonexistent = True
            warnings.append(
                "Αυτή η ώρα δεν υπήρξε στον τόπο γέννησης (τα ρολόγια πήγαν μπροστά εκείνη "
                "τη νύχτα). Ελέγξτε την ώρα γέννησης."
            )
        else:
            ambiguous = True
            warnings.append(
                "Αυτή η ώρα υπήρξε δύο φορές (τα ρολόγια γύρισαν πίσω εκείνη τη νύχτα). "
                + ("Επιλέχθηκε η δεύτερη φορά." if fold == 1 else "Επιλέχθηκε η πρώτη φορά.")
            )
    chosen = b if (ambiguous and fold == 1) else a
    off = chosen.utcoffset()
    dst = bool(chosen.dst())
    if local.year < 1970:
        warnings.append(
            "Για γεννήσεις πριν το 1970 τα ιστορικά στοιχεία θερινής ώρας είναι μερικές φορές "
            "αβέβαια· επιβεβαιώστε τη διαφορά από UT."
        )
    tzname = chosen.tzname() or ""
    if tzname == "LMT":
        warnings.append("Χρησιμοποιήθηκε τοπικός μέσος χρόνος (LMT) του τόπου, πριν την υιοθέτηση ζώνης ώρας.")
    ut = chosen.astimezone(timezone.utc)
    return BirthMoment(local, ut, off.total_seconds() / 3600, tz_name, dst, warnings, nonexistent, ambiguous)
