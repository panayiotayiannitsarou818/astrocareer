"""v22 -- Μηχανή ταλέντων (core/talent_engine.py, core/talent_map.py)."""
import random
from datetime import datetime, timedelta, timezone

from core.ephemeris import compute_chart
from core.talent_engine import FIELDS_PER_THEME, MAX_MAIN_FIELDS, run_engine
from core.talent_map import HEALTH_FIELDS, PAIR_THEME, THEME_FIELDS, THEMES
from core.teaser import pick_teaser

_PAIR = {frozenset(k): v for k, v in PAIR_THEME.items()}


def _charts(n, seed):
    random.seed(seed)
    for _ in range(n):
        ut = datetime(1930, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=random.randint(0, 95 * 365 * 24 * 60))
        yield compute_chart(ut, random.uniform(-45, 60), random.uniform(-120, 150))


def _pafos():
    # 11/02/1982 01:45 Πάφος (EET, UTC+2)
    return compute_chart(datetime(1982, 2, 10, 23, 45, tzinfo=timezone.utc), 34.7754, 32.4218)


def test_tables_are_consistent():
    assert set(THEME_FIELDS) == set(THEMES)
    assert set(_PAIR.values()) <= set(THEMES)
    for fields in THEME_FIELDS.values():
        assert not set(fields) & set(HEALTH_FIELDS)        # Κανόνας 15


def test_deterministic():
    a, b = run_engine(_pafos()), run_engine(_pafos())
    assert [(t.theme, t.score) for t in a.talents] == [(t.theme, t.score) for t in b.talents]


def test_pafos_finds_the_justice_talent_the_ai_missed():
    themes = {t.theme for t in run_engine(_pafos()).talents}
    assert "JUSTICE" in themes


def test_every_talent_is_documented_and_has_a_main_field():
    for c in _charts(60, 11):
        r = run_engine(c)
        for t in r.talents:
            assert t.basis and t.rank in ("κυρίαρχο", "βασικό", "αναδυόμενο")
            assert any(f.decision == "ΕΠΙΛΕΓΕΤΑΙ" and t.theme in f.talents for f in r.fields)
            for i in t.indicators:                         # Δεσμοί ποτέ ως δείκτης ταλέντου
                assert not {"Βόρειος Δεσμός", "Νότιος Δεσμός"} & set(i.points)


def test_field_rules_v22_2():
    """Κύριος = συνάντηση 2+ ταλέντων (έως MAX_MAIN_FIELDS) ή ρητά σημειωμένη εγγύηση με 1 ταλέντο·
    άλλες κατευθύνσεις: έως FIELDS_PER_THEME ανά ταλέντο."""
    for c in _charts(60, 15):
        r = run_engine(c)
        main = [f for f in r.fields if f.decision == "ΕΠΙΛΕΓΕΤΑΙ" and f.name not in HEALTH_FIELDS]
        assert len([f for f in main if not f.guarantee]) <= MAX_MAIN_FIELDS
        for f in main:
            assert (len(f.talents) >= 2) != f.guarantee
        for t in r.talents:
            brief = [f for f in r.fields if f.decision != "ΕΠΙΛΕΓΕΤΑΙ" and f.name not in HEALTH_FIELDS
                     and t.theme in f.talents]
            assert len(brief) <= FIELDS_PER_THEME


def test_field_count_stays_readable():
    totals = sorted(len(run_engine(c).fields) for c in _charts(60, 12))
    assert totals[len(totals) // 2] <= 16


def test_teaser_is_almost_always_in_the_full_report():
    ok = got = 0
    for c in _charts(80, 13):
        t = pick_teaser(c)
        if t:
            got += 1
            ok += _PAIR[frozenset(t.pair)] in {x.theme for x in run_engine(c).talents}
    assert ok >= got * 0.95


# ---- Κανόνας 15: φραγμός υγείας
from core.talent_map import HEALTH_RULES  # noqa: E402


def test_health_fields_need_two_specific_indicators_and_a_related_talent():
    seen = 0
    for c in _charts(80, 14):
        r = run_engine(c)
        approved = {t.theme for t in r.talents}
        for f in r.fields:
            if f.name in HEALTH_FIELDS:
                seen += 1
                assert len(f.health_basis) == 2 and f.health_basis[0].startswith("Δείκτης 1:")
                assert set(f.talents) <= approved & set(HEALTH_RULES[f.name]["related"]) and f.talents
            else:
                assert not f.health_basis
    assert 0 < seen < 80 * 3 * 0.5          # υπάρχουν, αλλά δεν βγαίνουν στους μισούς χάρτες


def test_pafos_health_barrier():
    r = run_engine(_pafos())
    health = {f.name: f.health_basis for f in r.fields if f.name in HEALTH_FIELDS}
    assert health == {"Υγεία και θεραπευτικές υπηρεσίες":
                      ["Δείκτης 1: Χείρωνας στον Οίκο 6", "Δείκτης 2: Μεσουράνημα σε Παρθένος"]}
    assert "Ψυχολογία και κοινωνική φροντίδα" in r.candidates_rejected


def test_no_duplicate_fields_even_when_two_uncovered_talents_share_a_best_field():
    """v22.3 (εξωτερικός έλεγχος): Ηγεσία + Στρατηγική σκέψη χωρίς κοινό αρχικό τομέα -> ο τομέας
    «Επιχειρήσεις και επιχειρηματικότητα» πρέπει να εμφανίζεται ΜΙΑ φορά, με τα δύο ταλέντα."""
    from core import talent_engine as te
    from core.talent_engine import Indicator
    orig_main = te.MAX_MAIN_FIELDS
    try:
        te.MAX_MAIN_FIELDS = 0     # αναγκάζει τη διαδρομή «εγγύησης» για όλα τα ταλέντα
        ind = Indicator("Θέση", "pos:x", ("Ήλιος",), "x")
        orig_qualify, orig_pos, orig_asp = te._qualify, te._position_indicators, te._aspect_indicators
        te._position_indicators = lambda chart: {"LEAD": [ind], "STRAT": [ind]}
        te._aspect_indicators = lambda chart: {}
        te._qualify = lambda inds: (inds, [], "δύο δείκτες")
        r = te.run_engine(_pafos())
    finally:
        te.MAX_MAIN_FIELDS = orig_main
        te._qualify, te._position_indicators, te._aspect_indicators = orig_qualify, orig_pos, orig_asp
    names = [f.name for f in r.fields]
    assert len(names) == len(set(names))
    biz = next(f for f in r.fields if f.name == "Επιχειρήσεις και επιχειρηματικότητα")
    assert set(biz.talents) == {"LEAD", "STRAT"} and not biz.guarantee and biz.decision == "ΕΠΙΛΕΓΕΤΑΙ"


def test_fields_are_unique_on_random_charts():
    for c in _charts(150, 16):
        names = [f.name for f in run_engine(c).fields]
        assert len(names) == len(set(names))
