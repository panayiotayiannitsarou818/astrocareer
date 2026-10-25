"""v19 -- τόπος γέννησης, τοπική ώρα -> UT, χάρτης από στοιχεία γέννησης."""
from datetime import date, time

import pytest

from core.birth_input import birth_case_key, chart_from_birth
from core.birthtime import to_ut
from core.places import normalize, search_places


@pytest.mark.parametrize(
    "query,expected_cc,expected_tz",
    [
        ("Πάφος", "CY", "Asia/Nicosia"),
        ("παφος", "CY", "Asia/Nicosia"),
        ("Paphos", "CY", "Asia/Nicosia"),
        ("Δάλι", "CY", "Asia/Nicosia"),
        ("Λεμεσός", "CY", "Asia/Nicosia"),
        ("Θεσσαλονίκη", "GR", "Europe/Athens"),
        ("Λονδίνο", "GB", "Europe/London"),
        ("Bulawayo", "ZW", "Africa/Harare"),
    ],
)
def test_place_search(query, expected_cc, expected_tz):
    found = search_places(query, 5)
    assert found, query
    assert found[0].country_code == expected_cc
    assert found[0].timezone == expected_tz


def test_normalize_greek():
    assert normalize("Λεμεσός") == normalize("ΛΕΜΕΣΟΣ") == "λεμεσοσ"


@pytest.mark.parametrize(
    "d,t,tz,ut",
    [
        (date(1983, 1, 27), time(5, 0), "Asia/Nicosia", "1983-01-27 03:00"),
        (date(1982, 2, 11), time(1, 45), "Asia/Nicosia", "1982-02-10 23:45"),
        (date(1978, 7, 31), time(1, 0), "Asia/Nicosia", "1978-07-30 22:00"),  # θερινή
        (date(1965, 7, 30), time(19, 0), "Africa/Harare", "1965-07-30 17:00"),
        (date(1947, 2, 23), time(18, 0), "Asia/Nicosia", "1947-02-23 16:00"),
        (date(1985, 6, 27), time(4, 0), "Asia/Nicosia", "1985-06-27 01:00"),  # θερινή
    ],
)
def test_local_to_ut_matches_astrodienst(d, t, tz, ut):
    assert to_ut(d, t, tz).ut.strftime("%Y-%m-%d %H:%M") == ut


def test_nonexistent_local_time_warns():
    m = to_ut(date(1985, 3, 31), time(0, 30), "Asia/Nicosia")
    assert any("δεν υπήρξε" in w for w in m.warnings)
    assert m.nonexistent
    assert not to_ut(date(1985, 3, 31), time(2, 30), "Asia/Nicosia").nonexistent


def test_manual_offset():
    m = to_ut(date(1990, 5, 1), time(12, 0), "Asia/Nicosia", manual_offset_hours=2)
    assert m.ut.strftime("%H:%M") == "10:00"


def test_chart_from_birth_end_to_end():
    place = search_places("Λεμεσός", 1)[0]
    chart, moment = chart_from_birth("Δοκιμή", date(1985, 6, 27), time(4, 0), place.lat, place.lon, place.timezone, "Λεμεσός")
    assert chart.name == "Δοκιμή"
    assert len(chart.cusps) == 12
    names = {p.name for p in chart.points}
    for n in ("Ήλιος", "Σελήνη", "Χείρωνας", "Βόρειος Δεσμός", "Νότιος Δεσμός", "Ωροσκόπος", "Μεσουράνημα"):
        assert n in names
    assert any(a.aspect == "Τετράγωνο" for a in chart.aspects)
    # ίδια στοιχεία -> ίδιο κλειδί υπόθεσης (ο μετρητής κόστους δεν μηδενίζεται)
    k1 = birth_case_key("Δοκιμή", date(1985, 6, 27), time(4, 0), place.lat, place.lon, moment.offset_hours)
    k2 = birth_case_key(" Δοκιμή ", date(1985, 6, 27), time(4, 0), place.lat, place.lon, moment.offset_hours)
    assert k1 == k2


def test_country_filter():
    from core.places import countries, country_label
    codes = [c for c, _ in countries("el")]
    assert [c for c, _ in countries("en")][:2] == ["CY", "GR"]
    assert codes[:2] == ["CY", "GR"]
    assert len(codes) > 200
    india = search_places("Dhali", 5, ("IN",))
    assert india and all(p.country_code == "IN" for p in india)
    cyprus = search_places("Dhali", 5, ("CY",))
    assert cyprus and cyprus[0].country_code == "CY"



def test_labels_follow_customer_language():
    from core.places import country_label
    p = search_places("Limassol", 1)[0]
    assert p.short("el") == "Λεμεσός, Κύπρος"
    assert p.short("en") == "Limassol, Cyprus"
    assert "34°41′Β" in p.label("el") and "34°41′N" in p.label("en")
    assert country_label("NO", "Norway", "el") == "Νορβηγία"
    assert country_label("NO", "Norway", "en") == "Norway"


# ---- v20.2 (εξωτερικός έλεγχος): διπλή/ανύπαρκτη ώρα, αγγλικά χωρίς όνομα

def test_ambiguous_time_needs_choice_and_fold_changes_ut():
    first = to_ut(date(1985, 9, 28), time(23, 30), "Asia/Nicosia", fold=0)
    second = to_ut(date(1985, 9, 28), time(23, 30), "Asia/Nicosia", fold=1)
    assert first.ambiguous and second.ambiguous
    assert first.offset_hours == 3 and second.offset_hours == 2
    assert (second.ut - first.ut).total_seconds() == 3600


def test_nonexistent_time_is_blocked():
    from core.birth_input import NonexistentTimeError
    place = search_places("Λεμεσός", 1)[0]
    with pytest.raises(NonexistentTimeError):
        chart_from_birth("", date(1985, 3, 31), time(0, 30), place.lat, place.lon, place.timezone)


def test_english_instructions_kept_without_name():
    from core.pipeline import reinforcement_instructions
    no_name = reinforcement_instructions("", "en")
    with_name = reinforcement_instructions("Maria", "en")
    assert "No client name was given" in no_name
    for marker in ("Brief Profile", "Talents to Explore", "Career Fields to Explore", "What to Remember:"):
        assert marker in no_name and marker in with_name
    assert with_name.split("\n", 1)[1] == no_name.split("\n", 1)[1]



@pytest.mark.parametrize("query,lang,code", [
    ("Κύπρος", "el", "CY"), ("κυπρος", "el", "CY"), ("ΚΥΠΡΟΣ", "el", "CY"), ("Cyprus", "el", "CY"),
    ("κυπ", "el", "CY"), ("ελλαδα", "el", "GR"), ("ΕΛΛΑΔΑ", "en", "GR"), ("Greece", "en", "GR"),
    ("ηπα", "el", "US"), ("USA", "en", "US"), ("αγγλια", "el", "GB"), ("νορβηγια", "el", "NO"),
])
def test_country_search_ignores_accents_case_and_language(query, lang, code):
    # v20.7: η λίστα του Streamlit έβρισκε την Κύπρο μόνο με ακριβή τόνο «Κύπρος».
    from core.places import search_countries
    found = search_countries(query, lang)
    assert found and found[0][0] == code, (query, found[:3])



def test_places_in_country_for_dropdown():
    from core.places import DROPDOWN_MAX_PLACES, normalize, places_in_country
    cy = places_in_country("CY", "el")
    assert 50 < len(cy) <= DROPDOWN_MAX_PLACES
    assert all(p.country_code == "CY" for p in cy)
    names = [normalize(p.name_el or p.name) for p in cy]
    assert names == sorted(names)
    assert any(p.name == "Paphos" for p in cy) and any(p.name == "Limassol" for p in cy)
    assert len(places_in_country("GR", "el")) > DROPDOWN_MAX_PLACES  # Ελλάδα: αναζήτηση, όχι λίστα
