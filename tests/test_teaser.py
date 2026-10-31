"""v21 -- «Δωρεάν ταλέντο» από έτοιμη βιβλιοθήκη (core/teaser.py, core/data/teaser_library.json)."""
import itertools
import json
import random
from datetime import datetime, timedelta, timezone

import pytest

from core.ephemeris import compute_chart
from core.models import Aspect, Chart
from core.teaser import LIBRARY, PERSONAL_POINTS, load_library, pick_teaser, teaser_instruction
from core.validator import _absolute_claims, _past_experience_claims, _simple_presentation_technical_terms

SLOW = ("Δίας", "Κρόνος", "Ουρανός", "Ποσειδώνας", "Πλούτωνας", "Χείρωνας")
IMPOSSIBLE_TRINES = [{"Ήλιος", "Ερμής"}, {"Ήλιος", "Αφροδίτη"}, {"Ερμής", "Αφροδίτη"}, {"Ωροσκόπος", "Μεσουράνημα"}]


def test_library_covers_exactly_the_59_pairs():
    expected = {frozenset(p) for p in itertools.combinations(PERSONAL_POINTS, 2) if set(p) not in IMPOSSIBLE_TRINES}
    expected |= {frozenset((a, b)) for a in PERSONAL_POINTS for b in SLOW}
    assert set(load_library()) == expected and len(expected) == 59


def test_every_entry_has_both_languages_and_status():
    data = json.load(open(LIBRARY, encoding="utf-8"))
    for e in data["entries"]:
        assert e["status"] in ("draft", "approved")
        for lang in ("el", "en"):
            assert e[lang]["title"].strip() and len(e[lang]["text"].split()) >= 30


def test_library_obeys_the_report_wording_rules():
    """Ίδιοι κανόνες με το καθαρό παραδοτέο: χωρίς αστρολογικούς όρους, απόλυτους
    ισχυρισμούς ή ισχυρισμούς για όσα έχει ζήσει ο πελάτης."""
    for pair, e in load_library().items():
        for lang in ("el", "en"):
            text = e[lang]["title"] + ". " + e[lang]["text"]
            assert not _simple_presentation_technical_terms(text), (sorted(pair), lang)
            assert not _absolute_claims(text), (sorted(pair), lang)
            assert not _past_experience_claims(text), (sorted(pair), lang)


def test_titles_are_unique():
    for lang in ("el", "en"):
        titles = [e[lang]["title"] for e in load_library().values()]
        assert len(titles) == len(set(titles))


def _aspect(a, b, kind, orb):
    return Aspect(a, b, kind, orb, f"{int(orb)}°{round(orb % 1 * 60):02d}′", "x", "test", True)


def test_tightest_personal_trine_wins_and_slow_only_trines_are_ignored():
    chart = Chart(aspects=[
        _aspect("Ουρανός", "Ποσειδώνας", "Τρίγωνο", 0.05),   # γενεακό: αγνοείται
        _aspect("Σελήνη", "Δίας", "Τρίγωνο", 2.0),
        _aspect("Ήλιος", "Κρόνος", "Τρίγωνο", 0.5),
        _aspect("Ερμής", "Άρης", "Εξάγωνο", 0.1),            # εξάγωνο: μόνο αν λείπει τρίγωνο
        _aspect("Βόρειος Δεσμός", "Ήλιος", "Τρίγωνο", 0.0),  # Δεσμός: αγνοείται
    ])
    t = pick_teaser(chart, "el")
    assert t.pair == ("Ήλιος", "Κρόνος") and t.natural and t.title == "Οργάνωση και συνέπεια"
    assert pick_teaser(chart, "en").title == "Organisation and consistency"


def test_sextile_fallback_and_none():
    chart = Chart(aspects=[_aspect("Ερμής", "Άρης", "Εξάγωνο", 1.0), _aspect("Ήλιος", "Σελήνη", "Τετράγωνο", 0.1)])
    t = pick_teaser(chart)
    assert t.pair == ("Ερμής", "Άρης") and not t.natural
    assert pick_teaser(Chart(aspects=[_aspect("Ήλιος", "Σελήνη", "Τετράγωνο", 0.1)])) is None
    assert teaser_instruction(Chart(), "el") == ""


def test_instruction_tells_ai_rules_come_first():
    chart = Chart(aspects=[_aspect("Ήλιος", "Κρόνος", "Τρίγωνο", 0.5)])
    el, en = teaser_instruction(chart, "el"), teaser_instruction(chart, "en")
    assert "Οργάνωση και συνέπεια" in el and "ΜΟΝΟ εφόσον τεκμηριώνεται" in el
    assert "Organisation and consistency" in en and "ONLY if it is fully documented" in en


def test_almost_every_real_chart_gets_a_teaser():
    random.seed(7)
    got = 0
    for _ in range(150):
        ut = datetime(1930, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=random.randint(0, 95 * 365 * 24 * 60))
        got += pick_teaser(compute_chart(ut, random.uniform(-45, 60), random.uniform(-120, 150))) is not None
    assert got >= 147


def test_clients_only_see_approved_teasers():
    """v22.4 (εξωτερικός έλεγχος #3): με approved_only, πρόχειρα κείμενα δεν δίνονται."""
    import core.teaser as tz
    chart = Chart(aspects=[_aspect("Ήλιος", "Κρόνος", "Τρίγωνο", 0.5), _aspect("Σελήνη", "Δίας", "Τρίγωνο", 2.0)])
    lib = load_library()
    assert pick_teaser(chart, approved_only=True) is None or pick_teaser(chart, approved_only=True).status == "approved"
    key = frozenset(("Σελήνη", "Δίας"))
    original = dict(lib[key])
    try:
        lib[key]["status"] = "approved"
        t = pick_teaser(chart, approved_only=True)
        assert t.pair == ("Σελήνη", "Δίας") and t.status == "approved"   # το εγκεκριμένο, όχι το στενότερο πρόχειρο
        assert pick_teaser(chart).pair == ("Ήλιος", "Κρόνος")
    finally:
        lib[key].clear(); lib[key].update(original)
    assert tz.teaser_drafts() == sum(e["status"] != "approved" for e in lib.values())
