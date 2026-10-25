"""
tools/build_places.py -- δημιουργεί το core/data/places.tsv.gz

Πηγή: πακέτο geonamescache (MIT) με δεδομένα GeoNames (CC-BY 4.0 --
απαιτείται αναφορά «GeoNames» στο site).
  - Κύπρος και Ελλάδα: όλοι οι οικισμοί με πληθυσμό >= 500 (και τα χωριά)
  - Υπόλοιπος κόσμος: πόλεις >= 5000 κατοίκων
Κρατάμε μόνο ονόματα με λατινικούς ή ελληνικούς χαρακτήρες.

Εκτέλεση (μία φορά, όταν θέλουμε ενημέρωση):
    pip install geonamescache babel
    python tools/build_places.py
"""
import gzip
import os
import re
import sys

import geonamescache

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core.places import normalize  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "core", "data", "places.tsv.gz")
FULL_COUNTRIES = {"CY", "GR"}
OK_CHARS = re.compile(r"^[A-Za-zÀ-ɏͰ-Ͽἀ-῿ .'’()\-]+$")


def main():
    small = geonamescache.GeonamesCache(min_city_population=500).get_cities()
    big_ids = set(geonamescache.GeonamesCache(min_city_population=5000).get_cities())
    countries = {c["iso"]: c["name"] for c in geonamescache.GeonamesCache().get_countries().values()}
    rows = 0
    with gzip.open(OUT, "wt", encoding="utf-8") as out:
        for gid, c in small.items():
            if c["countrycode"] not in FULL_COUNTRIES and gid not in big_ids:
                continue
            names = [c["name"]] + [a for a in c.get("alternatenames", []) if OK_CHARS.match(a)]
            greek = next((a for a in c.get("alternatenames", []) if re.search(r"[Ͱ-Ͽ]", a)), "")
            keys = sorted({normalize(n) for n in names if n.strip()})
            out.write(
                "\t".join(
                    [
                        c["name"],
                        greek,
                        c["countrycode"],
                        countries.get(c["countrycode"], c["countrycode"]),
                        f"{c['latitude']:.5f}",
                        f"{c['longitude']:.5f}",
                        c["timezone"],
                        str(c["population"]),
                        "|".join(keys),
                    ]
                )
                + "\n"
            )
            rows += 1
    print(rows, "τόποι ->", OUT, os.path.getsize(OUT) // 1024, "KB")

    # Ελληνικά ονόματα χωρών (CLDR). Χρειάζεται: pip install babel
    import json

    from babel import Locale

    el = Locale("el").territories
    names = {cc: el[cc] for cc in sorted(countries) if cc in el}
    path = os.path.join(os.path.dirname(OUT), "countries_el.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(names, f, ensure_ascii=False, indent=0, sort_keys=True)


if __name__ == "__main__":
    main()
