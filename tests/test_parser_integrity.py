"""
tests/test_parser_integrity.py
===============================
Ο parser του AstroCheck Career είναι συγχρονισμένος με του AstroCheck Pro.
Αυτά τα tests αποδεικνύουν ότι οι έλεγχοι ακεραιότητας του PDF λειτουργούν:
κάθε όψη επιβεβαιώνεται μαθηματικά, ο πίνακας διαβάζεται πλήρως, κανένα κελί
δύο φορές, και ότι ο έλεγχος λογικότητας του Career παραμένει ενεργός.
"""

from __future__ import annotations
from dataclasses import replace
from pathlib import Path

import pytest

from core.astrology import POSITION_DERIVED_SOURCE, angle_conjunctions_from_positions
from core.models import Point
from core.parser import _validate_chart_sanity, integrity_problems, parse_astrodienst_pdf

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("*.pdf"))


def _grid(chart):
    return [a for a in chart.aspects if a.source == "Πίνακας Astrodienst"]


def _printed(chart):
    return {p.name: p.house for p in chart.points}


def test_six_fixtures_present():
    assert len(FIXTURES) == 6


@pytest.mark.parametrize("pdf", FIXTURES, ids=lambda p: p.name)
def test_all_fixtures_pass_both_checks(pdf):
    chart = parse_astrodienst_pdf(pdf.read_bytes(), pdf.name)
    assert integrity_problems(
        chart.points, chart.cusps, chart.aspects, _printed(chart), grid_glyphs=len(_grid(chart))
    ) == []
    assert _validate_chart_sanity(chart) == []


@pytest.fixture(scope="module")
def chart():
    pdf = FIXTURES[1]
    return parse_astrodienst_pdf(pdf.read_bytes(), pdf.name)


def _problems(chart, aspects):
    grid = _grid(chart)
    return integrity_problems(chart.points, chart.cusps, aspects, _printed(chart), grid_glyphs=len(grid))


def test_dropped_aspect_is_detected(chart):
    grid = _grid(chart)
    one_less = [a for a in chart.aspects if a is not grid[0]]
    assert any("δεν διαβάστηκε πλήρως" in p for p in _problems(chart, one_less))


def test_same_cell_read_twice_is_detected(chart):
    grid = _grid(chart)
    swapped = [a for a in chart.aspects if a is not grid[1]] + [grid[0]]
    assert any("πιθανή λάθος αντιστοίχιση" in p for p in _problems(chart, swapped))


def test_wrong_orb_is_detected_mathematically(chart):
    grid = _grid(chart)
    bad = replace(grid[0], orb=grid[0].orb + 2, orb_text="9°59′")
    assert _problems(chart, [bad if a is grid[0] else a for a in chart.aspects])


def test_wrong_aspect_type_is_detected_mathematically(chart):
    target = next(a for a in _grid(chart) if a.aspect != "Αντίθεση")
    bad = replace(target, aspect="Αντίθεση")
    assert _problems(chart, [bad if a is target else a for a in chart.aspects])


def test_correct_chart_has_no_problems(chart):
    assert _problems(chart, chart.aspects) == []


def test_missing_angle_conjunction_is_computed():
    pts = [
        Point("Q", "Ωροσκόπος", "Καρκίνος", 10, 0, 0, 100.0, kind="angle"),
        Point("T", "Μεσουράνημα", "Κριός", 10, 0, 0, 10.0, kind="angle"),
        Point("C", "Ερμής", "Καρκίνος", 19, 0, 0, 109.0),
    ]
    added = angle_conjunctions_from_positions(pts, [])
    assert [(a.first, a.second, a.orb_text, a.source) for a in added] == [
        ("Ερμής", "Ωροσκόπος", "9°00′", POSITION_DERIVED_SOURCE)
    ]
    # πάντα «Πολύ πλατιά/δευτερεύουσα»: δεν δημιουργεί υποχρέωση κάλυψης
    assert added[0].weight == "Πολύ πλατιά/δευτερεύουσα"
