"""
core/ephemeris.py -- AstroCheck

Εσωτερικός υπολογισμός γενέθλιου χάρτη από ημερομηνία, ώρα και τόπο γέννησης,
χωρίς το PDF του Astrodienst και χωρίς βιβλιοθήκες AGPL.

  - Θέσεις πλανητών: Skyfield (MIT) + εφημερίδα NASA/JPL DE421 (δημόσιο
    αγαθό), από το πακέτο skyfield-data. Κάλυψη: 1900-2050.
  - Φαινόμενο γεωκεντρικό εκλειπτικό μήκος, αληθινή ισημερία & εκλειπτική
    της ημερομηνίας (όπως το Astrodienst).
  - Αληθινός (osculating) Βόρειος Δεσμός από το διάνυσμα θέσης/ταχύτητας
    της Σελήνης.
  - Ωροσκόπος, Μεσουράνημα και ακμές Placidus με κλασικούς τύπους σφαιρικής
    αστρονομίας.
  - Χείρωνας: βλ. core/chiron.py.

Επιστρέφει αντικείμενο Chart ίδιας μορφής με τον parser, ώστε η υπόλοιπη
ροή (δημιουργία αναφοράς, έλεγχος) να μένει αμετάβλητη.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from functools import lru_cache

from .models import Aspect, Chart, Point
from .astrology import (
    SIGNS,
    absolute,
    angle_conjunctions_from_positions,
    angular_distance,
    house_of,
    opposite_node,
    orb_to_text,
    orb_weight,
    south_node_aspects,
)

CALC_SOURCE = "Υπολογισμός θέσεων AstroCheck (κανόνες orbs πίνακα Astrodienst)"
# Όρια (orbs) όπως στον πίνακα όψεων του Astrodienst "Web Style"· επαληθεύτηκαν
# στα 6 παραδείγματα των tests. Ο Βόρειος Δεσμός παίρνει το μισό όριο.
ASPECT_ORBS = [
    ("Σύνοδος", 0, 10.0),
    ("Εξάγωνο", 60, 6.0),
    ("Τετράγωνο", 90, 10.0),
    ("Τρίγωνο", 120, 10.0),
    ("Χιαστί όψη 150°", 150, 3.0),
    ("Αντίθεση", 180, 10.0),
]
NODE_ORB_FACTOR = 0.5
# Σειρά σημείων στον πίνακα όψεων (στήλες/γραμμές του Astrodienst).
GRID_ORDER = ["A", "B", "C", "D", "E", "F", "G", "O", "I", "J", "L", "N", "Q", "T"]

BODIES = [
    ("A", "Ήλιος", "sun"),
    ("B", "Σελήνη", "moon"),
    ("C", "Ερμής", "mercury"),
    ("D", "Αφροδίτη", "venus"),
    ("E", "Άρης", "mars barycenter"),
    ("F", "Δίας", "jupiter barycenter"),
    ("G", "Κρόνος", "saturn barycenter"),
    ("O", "Ουρανός", "uranus barycenter"),
    ("I", "Ποσειδώνας", "neptune barycenter"),
    ("J", "Πλούτωνας", "pluto barycenter"),
]
MIN_YEAR, MAX_YEAR = 1900, 2049  # τοπική ημερομηνία γέννησης (όπως στη φόρμα)
# Όρια σε UT: η τοπική 01/01/1900 00:30 στην Κύπρο είναι ακόμη 31/12/1899 σε UT,
# και η 31/12/2049 στη Χαβάη είναι ήδη 2050 -- γι' αυτό περιθώριο ±1 ημέρας+.
UT_MIN = datetime(1899, 12, 30, tzinfo=timezone.utc)
UT_MAX = datetime(2050, 1, 2, tzinfo=timezone.utc)


@lru_cache(maxsize=1)
def _sky():
    import warnings

    from skyfield.api import Loader

    with warnings.catch_warnings():
        # Το skyfield-data προειδοποιεί για το finals2000A.all, που ΔΕΝ το
        # χρησιμοποιούμε (builtin timescale του Skyfield).
        warnings.simplefilter("ignore")
        from skyfield_data import get_skyfield_data_path

        data_path = get_skyfield_data_path()
    load = Loader(data_path, expire=False)
    ts = load.timescale(builtin=True)
    eph = load("de421.bsp")
    return ts, eph


def _norm(x: float) -> float:
    return x % 360.0


def _split(lon: float):
    lon = _norm(lon)
    total = round(lon * 3600)  # στρογγυλοποίηση στο δευτερόλεπτο τόξου
    total %= 360 * 3600
    sign = SIGNS[total // (30 * 3600)]
    rest = total % (30 * 3600)
    return sign, rest // 3600, (rest % 3600) // 60, rest % 60


def _make_point(code, name, lon, kind="planet", retro=False) -> Point:
    sign, d, m, s = _split(lon)
    return Point(code, name, sign, d, m, s, absolute(sign, d, m, s), None, retro, kind)


def _ecl_lon(earth, body, t):
    from skyfield.framelib import ecliptic_frame

    lat, lon, _ = earth.at(t).observe(body).apparent().frame_latlon(ecliptic_frame)
    return lon.degrees


def _true_node(eph, t) -> float:
    """Αληθινός Δεσμός: τομή του στιγμιαίου (osculating) επιπέδου τροχιάς της
    Σελήνης με την εκλειπτική της ημερομηνίας."""
    from skyfield.framelib import ecliptic_frame

    rel = (eph["moon"] - eph["earth"]).at(t)
    r, v = rel.frame_xyz_and_velocity(ecliptic_frame)
    rx, ry, rz = r.au
    vx, vy, vz = v.au_per_d
    hx = ry * vz - rz * vy
    hy = rz * vx - rx * vz
    return _norm(math.degrees(math.atan2(hx, -hy)))


def _obliquity(t) -> float:
    """Αληθινή λόξωση της εκλειπτικής (μοίρες)."""
    from skyfield.nutationlib import mean_obliquity, iau2000b_radians

    d_psi, d_eps = iau2000b_radians(t)
    return mean_obliquity(t.tdb) / 3600.0 + math.degrees(d_eps)


def _ecl_from_ra(ra: float, eps: float) -> float:
    """Σημείο της εκλειπτικής με δοσμένη ορθή αναφορά."""
    r, e = math.radians(ra), math.radians(eps)
    return _norm(math.degrees(math.atan2(math.sin(r), math.cos(r) * math.cos(e))))


def _ascendant(armc: float, eps: float, lat: float) -> float:
    a, e, f = math.radians(armc), math.radians(eps), math.radians(lat)
    asc = math.degrees(
        math.atan2(math.cos(a), -(math.sin(e) * math.tan(f) + math.cos(e) * math.sin(a)))
    )
    return _norm(asc)


def _placidus_cusp(armc: float, eps: float, lat: float, frac: float, above: bool) -> float:
    """Ακμή Placidus με επαναλήψεις.
    above=True: οίκοι 11/12 (frac = 1/3, 2/3 του ημερήσιου ημιτόξου από το MC).
    above=False: οίκοι 2/3 (frac = 2/3, 1/3 του νυκτερινού ημιτόξου πριν το IC)."""
    e, f = math.radians(eps), math.radians(lat)
    ra = armc + (frac * 90 if above else 180 - frac * 90)
    for _ in range(100):
        lon = _ecl_from_ra(ra, eps)
        dec = math.asin(math.sin(e) * math.sin(math.radians(lon)))
        x = math.tan(dec) * math.tan(f)
        x = max(-1.0, min(1.0, x))
        ad = math.degrees(math.asin(x))  # ascensional difference
        if above:
            new = armc + frac * (90 + ad)
        else:
            new = armc + 180 - frac * (90 - ad)
        if abs(((new - ra + 180) % 360) - 180) < 1e-9:
            ra = new
            break
        ra = new
    return _ecl_from_ra(ra, eps)


def houses_placidus(armc: float, eps: float, lat: float) -> list[float]:
    if abs(lat) >= 90 - eps:
        raise ValueError(
            "Το σύστημα Placidus δεν ορίζεται σε τόσο μεγάλο γεωγραφικό πλάτος (πολικοί κύκλοι)."
        )
    mc = _ecl_from_ra(armc, eps)
    asc = _ascendant(armc, eps, lat)
    c11 = _placidus_cusp(armc, eps, lat, 1 / 3, True)
    c12 = _placidus_cusp(armc, eps, lat, 2 / 3, True)
    c2 = _placidus_cusp(armc, eps, lat, 2 / 3, False)
    c3 = _placidus_cusp(armc, eps, lat, 1 / 3, False)
    first = [asc, c2, c3, _norm(mc + 180), _norm(c11 + 180), _norm(c12 + 180)]
    return first + [_norm(x + 180) for x in first]


def compute_chart(
    ut: datetime,
    lat: float,
    lon: float,
    *,
    name: str = "",
    place: str = "",
    local_time_text: str = "",
    with_chiron: bool = True,
) -> Chart:
    """ut: χρόνος γέννησης σε UT (timezone-aware ή naive = UT).
    lat: βόρειο +, νότιο -.  lon: ανατολικό +, δυτικό -."""
    if ut.tzinfo is None:
        ut = ut.replace(tzinfo=timezone.utc)
    ut = ut.astimezone(timezone.utc)
    if not (UT_MIN <= ut < UT_MAX):
        raise ValueError(f"Υποστηρίζονται γεννήσεις από {MIN_YEAR} έως {MAX_YEAR}.")
    ts, eph = _sky()
    # Η ώρα γέννησης ερμηνεύεται ως UT1 (όπως στο Astrodienst / Swiss
    # Ephemeris). Το from_datetime του Skyfield θα την ερμήνευε ως UTC, που
    # πριν το 1972 διαφέρει έως ~15 s και μετακινεί τις ακμές έως 3′.
    jd_ut = ut.timestamp() / 86400.0 + 2440587.5
    t = ts.ut1_jd(jd_ut)
    t_next = ts.tt_jd(t.tt + 1 / 24)
    earth = eph["earth"]

    points: list[Point] = []
    speeds: dict[str, float] = {}
    raw: dict[str, float] = {}  # πλήρης ακρίβεια, για τα orbs των όψεων
    for code, gr, key in BODIES:
        if key == "sun":
            body = eph["sun"]
        else:
            body = eph[key]
        lon0 = _ecl_lon(earth, body, t)
        lon1 = _ecl_lon(earth, body, t_next)
        speed = ((lon1 - lon0 + 180) % 360) - 180
        speeds[code] = float(speed)
        raw[code] = float(lon0)
        points.append(_make_point(code, gr, lon0, retro=speed < 0 and key not in ("sun", "moon")))

    n0 = _true_node(eph, t)
    n1 = _true_node(eph, t_next)
    speeds["L"] = ((n1 - n0 + 180) % 360) - 180
    raw["L"] = n0
    points.append(_make_point("L", "Βόρειος Δεσμός", n0, kind="node", retro=speeds["L"] < 0))

    if with_chiron:
        from .chiron import chiron_longitude

        c0 = chiron_longitude(t)
        c1 = chiron_longitude(ts.tt_jd(t.tt + 1 / 24))
        speeds["N"] = float(((c1 - c0 + 180) % 360) - 180)
        raw["N"] = float(c0)
        points.append(_make_point("N", "Χείρωνας", c0, retro=speeds["N"] < 0))

    eps = _obliquity(t)
    armc = _norm(t.gast * 15 + lon)
    cusp_lons = houses_placidus(armc, eps, lat)
    cusps = [_make_point(f"H{i}", f"{i}ος Οίκος", c, kind="cusp") for i, c in enumerate(cusp_lons, 1)]

    for p in points:
        p.house = house_of(p.absolute, cusps)

    asc = _make_point("Q", "Ωροσκόπος", cusp_lons[0], kind="angle")
    mc = _make_point("T", "Μεσουράνημα", cusp_lons[9], kind="angle")
    points.extend([asc, mc])

    # ταχύτητα (μοίρες/ώρα) για το «εφαρμοζόμενη/αποχωρούσα»
    speed = dict(speeds)
    raw["Q"], raw["T"] = cusp_lons[0], cusp_lons[9]
    t_m = ts.ut1_jd(jd_ut + 1 / 1440)  # +1 λεπτό: οι γωνίες κινούνται ~15°/ώρα
    cusp_next = houses_placidus(_norm(t_m.gast * 15 + lon), eps, lat)
    speed["Q"] = (((cusp_next[0] - cusp_lons[0] + 180) % 360) - 180) * 60
    speed["T"] = (((cusp_next[9] - cusp_lons[9] + 180) % 360) - 180) * 60
    by_code = {p.code: p for p in points}
    aspects = compute_aspects(by_code, speed, raw)

    node = by_code.get("L")
    if node:
        south = opposite_node(node)
        south.house = house_of(south.absolute, cusps)
        points.append(south)
        aspects.extend(south_node_aspects(aspects))
    aspects.extend(angle_conjunctions_from_positions(points, aspects))

    return Chart(
        name=name,
        date=ut.strftime("%Y-%m-%d"),
        time=local_time_text or ut.strftime("%H:%M UT"),
        place=place,
        house_system="Placidus",
        points=points,
        cusps=cusps,
        aspects=aspects,
    )


def compute_aspects(by_code: dict, speed: dict, raw: dict | None = None) -> list[Aspect]:
    """Όψεις όπως στον πίνακα Astrodienst: ένα κελί ανά ζεύγος, το πολύ μία όψη."""
    result = []
    codes = [c for c in GRID_ORDER if c in by_code]
    for i, a in enumerate(codes):
        for b in codes[i + 1 :]:
            if {a, b} == {"Q", "T"}:
                continue
            pa, pb = by_code[a], by_code[b]
            ra = (raw or {}).get(a, pa.absolute)
            rb = (raw or {}).get(b, pb.absolute)
            dist = angular_distance(ra, rb)
            factor = NODE_ORB_FACTOR if "L" in (a, b) else 1.0
            for name, angle, base in ASPECT_ORBS:
                orb = abs(dist - angle)
                if orb <= base * factor:
                    # εφαρμοζόμενη: το orb μικραίνει (στιγμιαία παράγωγος, βήμα 1 s)
                    h = 1 / 3600
                    la = ra + speed.get(a, 0.0) * h
                    lb = rb + speed.get(b, 0.0) * h
                    orb_next = abs(angular_distance(la, lb) - angle)
                    rounded = round(orb * 60) / 60  # σε λεπτά τόξου, όπως ο πίνακας
                    result.append(
                        Aspect(
                            pa.name,
                            pb.name,
                            name,
                            rounded,
                            orb_to_text(orb),
                            # v20.5: βαρύτητα από το orb ΣΤΡΟΓΓΥΛΕΜΕΝΟ στο λεπτό, όπως το
                            # διαβάζει ο parser από τον πίνακα -- ίδια κατηγορία στα όρια.
                            orb_weight(rounded, name, "L" in (a, b)),
                            CALC_SOURCE,
                            orb_next < orb,
                        )
                    )
                    break
    return result
