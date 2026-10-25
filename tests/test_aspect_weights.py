"""v20.3 -- αναλογική βαρύτητα ανά τύπο όψης (core/astrology.orb_weight).

Στενή < 20% · Κανονική < 40% · Πλατιά ≤ 70% · Πολύ πλατιά > 70% του μέγιστου
orb του τύπου (σύνοδος/τρίγωνο/τετράγωνο/αντίθεση 10°, εξάγωνο 6°, χιαστί 3°)·
όψεις Δεσμού: το μισό μέγιστο orb.
"""
import pytest

from core.astrology import orb_weight

S, N, W, VW = "Στενή/ισχυρή", "Κανονική", "Πλατιά αλλά έγκυρη", "Πολύ πλατιά/δευτερεύουσα"


@pytest.mark.parametrize("aspect", ["Σύνοδος", "Τρίγωνο", "Τετράγωνο", "Αντίθεση", None])
@pytest.mark.parametrize("orb,expected", [(1.99, S), (2.0, N), (3.99, N), (4.0, W), (7.0, W), (7.01, VW)])
def test_major_aspects_keep_classic_limits(aspect, orb, expected):
    assert orb_weight(orb, aspect) == expected


@pytest.mark.parametrize("orb,expected", [(1.1, S), (1.3, N), (2.5, W), (4.3, VW)])
def test_sextile_scaled_to_6_degrees(orb, expected):
    assert orb_weight(orb, "Εξάγωνο") == expected


@pytest.mark.parametrize("orb,expected", [(0.5, S), (0.9, N), (2.0, W), (2.5, VW)])
def test_quincunx_scaled_to_3_degrees(orb, expected):
    assert orb_weight(orb, "Χιαστί όψη 150°") == expected


def test_quincunx_of_2_degrees_is_no_longer_strong():
    # Αφορμή της αλλαγής: πριν, χιαστί 1°59′ ήταν «Στενή/ισχυρή» και μπορούσε μόνη της
    # να στηρίξει ταλέντο, ενώ βρίσκεται κοντά στο όριο 3° του τύπου της.
    assert orb_weight(1.98, "Χιαστί όψη 150°") == W


@pytest.mark.parametrize("orb,expected", [(0.9, S), (1.5, N), (3.0, W), (4.0, VW)])
def test_node_aspects_use_half_orb(orb, expected):
    assert orb_weight(orb, "Σύνοδος", node=True) == expected


def test_parser_and_calculation_agree_on_weights():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent))
    from test_ephemeris import FIXTURES, _meta
    from core.ephemeris import compute_chart
    from core.parser import parse_astrodienst_pdf
    for f in FIXTURES:
        ref = parse_astrodienst_pdf(f.read_bytes(), f.name)
        mine = compute_chart(*_meta(f))
        key = lambda a: (frozenset((a.first, a.second)), a.aspect)
        assert {key(a): a.weight for a in ref.aspects} == {key(a): a.weight for a in mine.aspects}



# ---- v20.5 (εξωτερικός έλεγχος)

@pytest.mark.parametrize("aspect,orb,expected", [
    ("Εξάγωνο", 4.2, W),            # 6 × 0,7 = 4,1999… στον υπολογιστή
    ("Εξάγωνο", 1.2, N),            # 6 × 0,2
    ("Εξάγωνο", 2.4, W),            # 6 × 0,4
    ("Χιαστί όψη 150°", 2.1, W),    # 3 × 0,7
    ("Χιαστί όψη 150°", 0.6, N),    # 3 × 0,2
])
def test_exact_boundaries_are_not_hit_by_float_error(aspect, orb, expected):
    assert orb_weight(orb, aspect) == expected


def test_south_node_weight_recomputed_for_new_aspect_type():
    from core.astrology import south_node_aspects
    from core.models import Aspect
    # Β. Δεσμός τρίγωνο 1°24′ (όριο Δεσμού 5°): Κανονική.
    # Ν. Δεσμός -> εξάγωνο 1°24′ (όριο Δεσμού 3°): Πλατιά -- όχι αντιγραφή «Κανονική».
    north = Aspect("Βόρειος Δεσμός", "Ήλιος", "Τρίγωνο", 1.4, "1°24′",
                   orb_weight(1.4, "Τρίγωνο", node=True), "x", True)
    assert north.weight == N
    south = south_node_aspects([north])[0]
    assert south.aspect == "Εξάγωνο" and south.weight == W


def test_weight_uses_orb_rounded_to_the_minute():
    # Πίνακας Astrodienst: 1°12′ (= 1,2°). Πραγματικό orb 1°11′40″ -> ίδια κατηγορία
    # με τον parser, γιατί και ο υπολογισμός στρογγυλεύει πρώτα στο λεπτό.
    from core.ephemeris import compute_aspects
    from core.models import Point
    p1 = Point("A", "Ήλιος", "Κριός", 0, 0, 0, 0.0)
    p2 = Point("B", "Σελήνη", "Δίδυμοι", 1, 11, 40, 61 + 11 / 60 + 40 / 3600)
    (asp,) = compute_aspects({"A": p1, "B": p2}, {}, {"A": 0.0, "B": p2.absolute})
    assert asp.aspect == "Εξάγωνο" and asp.orb_text == "1°12′"
    assert asp.weight == orb_weight(1.2, "Εξάγωνο") == N
