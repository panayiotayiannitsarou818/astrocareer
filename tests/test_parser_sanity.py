"""
Νέα tests, ύστερα από την κριτική #8: ο PDF parser βασίζεται αποκλειστικά σε
hardcoded pixel x0-εύρη, και μια μικρή αλλαγή διάταξης Astrodienst θα
μπορούσε να δέσει σιωπηλά λάθος στήλη με λάθος πλανήτη, χωρίς exception.

Αυτά τα tests δεν χρειάζονται δεύτερο πραγματικό Astrodienst PDF -- ελέγχουν
απευθείας το core/parser.py::_validate_chart_sanity() πάνω σε τεχνητά
"χαλασμένα" Chart αντικείμενα, όπως θα προέκυπταν από μια λάθος στήλη.
"""
from core.models import Aspect, Chart, Point
from core.parser import _validate_chart_sanity


def _cusp(number, absolute):
    sign_index = int(absolute // 30)
    degree = absolute - sign_index * 30
    from core.astrology import SIGNS
    return Point(f"H{number}", f"{number}ος Οίκος", SIGNS[sign_index], int(degree), 0, 0, absolute, kind="cusp")


def _valid_cusps():
    """12 ακμές ίσα κατανεμημένες κάθε 30° -- έγκυρος, καθαρός κύκλος 360°."""
    return [_cusp(i + 1, i * 30) for i in range(12)]


def _valid_point(code="A", name="Ήλιος", degree=15, minute=30, second=0, house=1):
    return Point(code, name, "Κριός", degree, minute, second, degree + minute / 60, house=house)


def test_valid_chart_passes_with_no_errors():
    chart = Chart(points=[_valid_point()], cusps=_valid_cusps(), aspects=[])
    assert _validate_chart_sanity(chart) == []


def test_invalid_degree_out_of_range_is_caught():
    chart = Chart(points=[_valid_point(degree=35)], cusps=_valid_cusps(), aspects=[])
    errors = _validate_chart_sanity(chart)
    assert any("μη έγκυρη μοίρα" in e for e in errors)


def test_invalid_minute_out_of_range_is_caught():
    chart = Chart(points=[_valid_point(minute=75)], cusps=_valid_cusps(), aspects=[])
    errors = _validate_chart_sanity(chart)
    assert any("μη έγκυρο λεπτό" in e for e in errors)


def test_duplicate_point_code_is_caught():
    """Δύο πλανήτες με τον ίδιο κωδικό -- σαφές σημάδι λάθος αντιστοίχισης στήλης."""
    chart = Chart(
        points=[_valid_point(code="A", name="Ήλιος"), _valid_point(code="A", name="Σελήνη")],
        cusps=_valid_cusps(), aspects=[],
    )
    errors = _validate_chart_sanity(chart)
    assert any("Διπλότυπος κωδικός" in e for e in errors)


def test_non_monotonic_cusps_are_caught():
    """Ακμές που δεν σχηματίζουν αύξουσα διαδοχή γύρω από τον κύκλο --
    ακριβώς αυτό που θα παρήγαγε μια λάθος δεμένη στήλη ζωδίου/μοίρας."""
    cusps = _valid_cusps()
    # Σπάει τη σειρά: η 3η ακμή μπαίνει πριν την 2η.
    cusps[1], cusps[2] = cusps[2], cusps[1]
    chart = Chart(points=[_valid_point()], cusps=cusps, aspects=[])
    errors = _validate_chart_sanity(chart)
    assert any("αύξουσα διαδοχή" in e for e in errors)


def test_absurd_orb_is_caught():
    aspect = Aspect("Ήλιος", "Σελήνη", "Τρίγωνο", 40.0, "40°00′", "Πολύ πλατιά/δευτερεύουσα", "test")
    chart = Chart(points=[_valid_point()], cusps=_valid_cusps(), aspects=[aspect])
    errors = _validate_chart_sanity(chart)
    assert any("μη έγκυρο orb" in e for e in errors)


def test_real_fixture_chart_passes_sanity_check():
    """Το πραγματικό δημόσιο fixture (astro_paradeigma.pdf) δεν πρέπει ποτέ
    να απορρίπτεται από τον νέο έλεγχο -- διαφορετικά είναι πολύ αυστηρός."""
    from pathlib import Path
    from core.parser import parse_astrodienst_pdf

    fixture = Path(__file__).parent / "fixtures" / "astro_paradeigma.pdf"
    chart = parse_astrodienst_pdf(fixture.read_bytes(), "astro_paradeigma.pdf")
    assert _validate_chart_sanity(chart) == []
