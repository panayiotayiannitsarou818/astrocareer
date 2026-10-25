"""
v19 -- εσωτερικός υπολογισμός χάρτη (core/ephemeris.py, core/chiron.py).

Ο υπολογισμός πρέπει να δίνει ΤΑ ΙΔΙΑ δεδομένα με το Astrodienst για τα 6
πραγματικά PDF των fixtures: θέσεις (±2″), ακμές Placidus, οίκους, ανάδρομη
κίνηση και τον πλήρη πίνακα όψεων (τύπος, orb σε λεπτά, εφαρμοζόμενη).
"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pdfplumber
import pytest

from core.ephemeris import compute_chart
from core.parser import parse_astrodienst_pdf

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("astro_paradeigma*.pdf"))


def _meta(path):
    text = pdfplumber.open(path).pages[0].extract_text()
    born = re.search(r"born on \w+\., (\d+ \w+ \d{4}) Univ\.Time (\d+):(\d+)( \(\d+ \w+\.?\))?", text)
    d = datetime.strptime(born.group(1), "%d %B %Y")
    if born.group(4):  # η UT πέφτει την προηγούμενη ημέρα
        d -= timedelta(days=1)
    ut = d.replace(hour=int(born.group(2)), minute=int(born.group(3)), tzinfo=timezone.utc)
    m = re.search(r"(\d+)([ew])(\d+), (\d+)([ns])(\d+)", text)
    lon = (int(m.group(1)) + int(m.group(3)) / 60) * (1 if m.group(2) == "e" else -1)
    lat = (int(m.group(4)) + int(m.group(6)) / 60) * (1 if m.group(5) == "n" else -1)
    return ut, lat, lon


def _diff_arcsec(a, b):
    return abs(((a - b + 180) % 360) - 180) * 3600


@pytest.fixture(scope="module", params=FIXTURES, ids=lambda p: p.name)
def pair(request):
    ref = parse_astrodienst_pdf(request.param.read_bytes(), request.param.name)
    mine = compute_chart(*_meta(request.param))
    return ref, mine


def test_six_fixtures_present():
    assert len(FIXTURES) == 6


def test_points_match_astrodienst(pair):
    ref, mine = pair
    by_code = {p.code: p for p in mine.points}
    assert {p.code for p in ref.points} == set(by_code)
    for p in ref.points:
        m = by_code[p.code]
        assert _diff_arcsec(m.absolute, p.absolute) <= 2, (p.name, m.absolute, p.absolute)
        assert m.sign == p.sign, p.name
        assert m.house == p.house, p.name
        assert m.retrograde == p.retrograde, p.name
        assert m.kind == p.kind, p.name


def test_cusps_match_astrodienst(pair):
    ref, mine = pair
    assert len(mine.cusps) == 12
    for r, m in zip(ref.cusps, mine.cusps):
        assert _diff_arcsec(m.absolute, r.absolute) <= 2, r.name


def test_aspect_table_matches_astrodienst(pair):
    ref, mine = pair

    def table(chart):
        return {
            (frozenset((a.first, a.second)), a.aspect): (a.orb_text, a.applying, a.weight)
            for a in chart.aspects
        }

    assert table(mine) == table(ref)


def test_years_out_of_range_are_rejected():
    with pytest.raises(ValueError):
        compute_chart(datetime(1899, 12, 1, 12, tzinfo=timezone.utc), 35.0, 33.0)
    with pytest.raises(ValueError):
        compute_chart(datetime(2050, 2, 1, 12, tzinfo=timezone.utc), 35.0, 33.0)


def test_polar_latitude_is_rejected():
    with pytest.raises(ValueError):
        compute_chart(datetime(1990, 6, 1, 12, tzinfo=timezone.utc), 70.0, 25.0)



def test_form_date_limits_work_in_every_time_zone():
    # v20.4: τοπική 01/01/1900 00:30 στην Κύπρο = 31/12/1899 σε UT· 31/12/2049 στη Χαβάη = 2050 σε UT.
    from datetime import date, time
    from core.birth_input import chart_from_birth
    chart_from_birth("", date(1900, 1, 1), time(0, 30), 34.68, 33.04, "Asia/Nicosia")
    chart_from_birth("", date(2049, 12, 31), time(23, 30), 21.31, -157.86, "Pacific/Honolulu")
