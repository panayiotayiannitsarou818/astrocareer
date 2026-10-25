"""
core/chiron.py -- AstroCheck

Θέση του Χείρωνα (2060 Chiron) χωρίς εξωτερική εφημερίδα:
αριθμητική ολοκλήρωση της τροχιάς του (πρόβλημα Ν σωμάτων) με αφετηρία τα
επίσημα τροχιακά στοιχεία του JPL Small-Body Database, και διαταραχές από
Ήλιο και πλανήτες (θέσεις από DE421).

Η ολοκλήρωση γίνεται μία φορά (cache) για όλο το διάστημα 1900-2050 και
μετά κάθε θέση βγαίνει με παρεμβολή.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np

# Τροχιακά στοιχεία JPL SBDB, εποχή JD 2461200.5 TDB (8 Ιουνίου 2026),
# ηλιοκεντρικά, εκλειπτική & ισημερία J2000.
EPOCH_JD = 2461200.5
ELEMENTS = dict(
    e=0.37976563,
    a=13.68426761,  # AU
    i=6.93057447,
    node=209.29612586131,
    peri=339.28783265897,
    M=216.71989660181,
)

K2 = 0.00029591220828559115  # GM Ήλιου σε AU^3/day^2
GM_SUN_KM = 132712440040.944
# GM (km^3/s^2) συμβατά με DE421, για τα βαρυκεντρικά συστήματα.
PERTURBERS = {
    "mercury barycenter": 22032.09,
    "venus barycenter": 324858.59,
    "earth barycenter": 403503.236,
    "mars barycenter": 42828.3762,
    "jupiter barycenter": 126712764.8,
    "saturn barycenter": 37940585.2,
    "uranus barycenter": 5794548.6,
    "neptune barycenter": 6836535.0,
    "pluto barycenter": 977.0,
}
EPS_J2000 = math.radians(23.4392911)
C_AU_PER_DAY = 173.1446326846693
JD_START, JD_END = 2414990.5, 2470000.5  # 1/12/1899 .. 2050 (εντός DE421)


def _elements_to_state(mu):
    e, a = ELEMENTS["e"], ELEMENTS["a"]
    i, O, w = (math.radians(ELEMENTS[k]) for k in ("i", "node", "peri"))
    M = math.radians(ELEMENTS["M"])
    E = M
    for _ in range(50):
        E -= (E - e * math.sin(E) - M) / (1 - e * math.cos(E))
    nu = 2 * math.atan2(math.sqrt(1 + e) * math.sin(E / 2), math.sqrt(1 - e) * math.cos(E / 2))
    r = a * (1 - e * math.cos(E))
    p = a * (1 - e * e)
    x_orb = np.array([r * math.cos(nu), r * math.sin(nu), 0.0])
    v_orb = math.sqrt(mu / p) * np.array([-math.sin(nu), e + math.cos(nu), 0.0])
    cO, sO, ci, si, cw, sw = map(lambda f: f, (math.cos(O), math.sin(O), math.cos(i), math.sin(i), math.cos(w), math.sin(w)))
    R = np.array(
        [
            [cO * cw - sO * sw * ci, -cO * sw - sO * cw * ci, sO * si],
            [sO * cw + cO * sw * ci, -sO * sw + cO * cw * ci, -cO * si],
            [sw * si, cw * si, ci],
        ]
    )
    return R @ x_orb, R @ v_orb


def _ecl_to_eq(v):
    c, s = math.cos(EPS_J2000), math.sin(EPS_J2000)
    return np.array([v[0], c * v[1] - s * v[2], s * v[1] + c * v[2]])


@lru_cache(maxsize=1)
def _solution():
    from scipy.integrate import solve_ivp
    from .ephemeris import _sky

    ts, eph = _sky()
    bodies = [(eph["sun"], K2)] + [
        (eph[name], K2 * gm / GM_SUN_KM) for name, gm in PERTURBERS.items()
    ]

    # Πίνακας θέσεων διαταρακτών ανά 2 ημέρες + κυβική παρεμβολή (ταχύτητα).
    from scipy.interpolate import CubicSpline

    grid = np.arange(JD_START - 10, JD_END + 10, 2.0)
    tgrid = ts.tdb_jd(grid)
    splines = []
    for body, mu in bodies:
        pos = body.at(tgrid).position.au  # ICRF, βαρυκεντρικά
        splines.append((CubicSpline(grid, pos, axis=1), mu))

    def acc(jd, y):
        r = y[:3]
        a = np.zeros(3)
        for sp, mu in splines:
            d = sp(jd) - r
            a += mu * d / np.linalg.norm(d) ** 3
        return np.concatenate([y[3:], a])

    # Αρχική κατάσταση: ηλιοκεντρική (εκλειπτική J2000) -> βαρυκεντρική ICRF.
    mu_helio = K2  # μάζα Χείρωνα αμελητέα
    r_h, v_h = _elements_to_state(mu_helio)
    sun = eph["sun"].at(ts.tdb_jd(EPOCH_JD))
    r0 = _ecl_to_eq(r_h) + sun.position.au
    v0 = _ecl_to_eq(v_h) + sun.velocity.au_per_d
    y0 = np.concatenate([r0, v0])
    opts = dict(method="DOP853", rtol=1e-12, atol=1e-14, dense_output=True)
    back = solve_ivp(acc, (EPOCH_JD, JD_START), y0, **opts)
    fwd = solve_ivp(acc, (EPOCH_JD, JD_END), y0, **opts)
    return back.sol, fwd.sol


def _bary(jd_tdb):
    back, fwd = _solution()
    return (back if jd_tdb <= EPOCH_JD else fwd)(jd_tdb)[:3]


def chiron_longitude(t) -> float:
    """Φαινόμενο γεωκεντρικό εκλειπτικό μήκος (ισημερία της ημερομηνίας)."""
    from skyfield.framelib import ecliptic_frame
    from skyfield.positionlib import ICRF
    from .ephemeris import _sky

    ts, eph = _sky()
    if not (JD_START <= t.tdb <= JD_END):
        raise ValueError("Ο Χείρωνας υπολογίζεται για 1900-2050.")
    earth = eph["earth"].at(t)
    e_pos, e_vel = earth.position.au, earth.velocity.au_per_d
    # χρόνος φωτός
    tau = 0.0
    for _ in range(5):
        vec = _bary(t.tdb - tau) - e_pos
        tau = np.linalg.norm(vec) / C_AU_PER_DAY
    # ετήσια εκτροπή φωτός (aberration), πρώτης τάξης
    dist = np.linalg.norm(vec)
    u = vec / dist + e_vel / C_AU_PER_DAY
    vec = u / np.linalg.norm(u) * dist
    pos = ICRF(vec, t=t, center=399)
    lat, lon, _ = pos.frame_latlon(ecliptic_frame)
    return lon.degrees % 360.0
