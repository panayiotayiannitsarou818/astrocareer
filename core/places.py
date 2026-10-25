"""
core/places.py -- AstroCheck

Αναζήτηση τόπου γέννησης (ελληνικά ή λατινικά) χωρίς εξωτερική υπηρεσία.
Δεδομένα: GeoNames (CC-BY 4.0), βλ. tools/build_places.py.
Κάθε αποτέλεσμα δίνει γεωγραφικό πλάτος/μήκος και ζώνη ώρας IANA.
"""
from __future__ import annotations

import gzip
import os
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

DATA = os.path.join(os.path.dirname(__file__), "data", "places.tsv.gz")
ATTRIBUTION = "Δεδομένα τόπων: GeoNames (geonames.org), CC-BY 4.0"


def normalize(text: str) -> str:
    """Πεζά, χωρίς τόνους/διαλυτικά, τελικό σίγμα -> σ."""
    t = unicodedata.normalize("NFD", text.strip().lower())
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    return t.replace("ς", "σ").replace("’", "'")


@dataclass(frozen=True)
class Place:
    name: str
    name_el: str
    country_code: str
    country: str
    lat: float
    lon: float
    timezone: str
    population: int

    def label(self, lang: str = "el") -> str:
        """Ετικέτα στη γλώσσα του πελάτη (ελληνικά ή αγγλικά)."""
        if lang == "el":
            main = self.name_el or self.name
            extra = f" ({self.name})" if self.name_el and self.name_el != self.name else ""
            country = COUNTRY_EL.get(self.country_code, self.country)
            coords = f"{_fmt_coord(self.lat, 'Β', 'Ν')} {_fmt_coord(self.lon, 'Α', 'Δ')}"
        else:
            main, extra, country = self.name, "", self.country
            coords = f"{_fmt_coord(self.lat, 'N', 'S')} {_fmt_coord(self.lon, 'E', 'W')}"
        return f"{main}{extra}, {country} — {coords}"

    def short(self, lang: str = "el") -> str:
        if lang == "el":
            return f"{self.name_el or self.name}, {COUNTRY_EL.get(self.country_code, self.country)}"
        return f"{self.name}, {self.country}"


def _fmt_coord(v: float, pos: str, neg: str) -> str:
    d = abs(v)
    deg = int(d)
    minutes = round((d - deg) * 60)
    if minutes == 60:
        deg, minutes = deg + 1, 0
    return f"{deg}°{minutes:02d}′{pos if v >= 0 else neg}"


@lru_cache(maxsize=1)
def _index():
    rows = []
    with gzip.open(DATA, "rt", encoding="utf-8") as f:
        for line in f:
            name, el, cc, country, lat, lon, tz, pop, keys = line.rstrip("\n").split("\t")
            rows.append(
                (Place(name, el, cc, country, float(lat), float(lon), tz, int(pop)), keys.split("|"))
            )
    return rows


def search_places(query: str, limit: int = 10, country_codes: tuple[str, ...] = ()) -> list[Place]:
    """Ακριβής αντιστοίχιση πρώτα, μετά «αρχίζει με». Ταξινόμηση: Κύπρος,
    Ελλάδα, μετά κατά πληθυσμό."""
    q = normalize(query)
    if len(q) < 2:
        return []
    exact, prefix = [], []
    for place, keys in _index():
        if country_codes and place.country_code not in country_codes:
            continue
        if q in keys:
            exact.append(place)
        elif any(k.startswith(q) for k in keys):
            prefix.append(place)

    def rank(p: Place):
        return (0 if p.country_code == "CY" else 1 if p.country_code == "GR" else 2, -p.population)

    return (sorted(exact, key=rank) + sorted(prefix, key=rank))[:limit]


# Ελληνικά ονόματα χωρών (CLDR μέσω Babel, BSD) -- βλ. tools/build_places.py
import json as _json

with open(os.path.join(os.path.dirname(__file__), "data", "countries_el.json"), encoding="utf-8") as _f:
    COUNTRY_EL = _json.load(_f)


@lru_cache(maxsize=2)
def countries(lang: str = "el") -> list[tuple[str, str]]:
    """[(κωδικός, αγγλικό όνομα)] -- Κύπρος, Ελλάδα πρώτα, μετά αλφαβητικά
    στη γλώσσα του πελάτη."""
    seen = {}
    for place, _ in _index():
        seen.setdefault(place.country_code, place.country)
    first = [(c, seen[c]) for c in ("CY", "GR") if c in seen]
    rest = [(c, n) for c, n in seen.items() if c not in ("CY", "GR")]
    rest.sort(key=lambda x: normalize(country_label(x[0], x[1], lang)))
    return first + rest


def country_label(code: str, name: str, lang: str = "el") -> str:
    if lang == "el":
        return COUNTRY_EL.get(code, name)
    return name
