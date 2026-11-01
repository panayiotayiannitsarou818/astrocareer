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
        assert len([f for f in main if not f.coverage]) <= MAX_MAIN_FIELDS
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
        orig_rul = te._ruler_indicators
        te._ruler_indicators = lambda chart: {}
        te._position_indicators = lambda chart: {"LEAD": [ind], "STRAT": [ind]}
        te._aspect_indicators = lambda chart: {}
        te._qualify = lambda inds: (inds, [], "δύο δείκτες")
        r = te.run_engine(_pafos())
    finally:
        te.MAX_MAIN_FIELDS = orig_main
        te._qualify, te._position_indicators, te._aspect_indicators = orig_qualify, orig_pos, orig_asp
        te._ruler_indicators = orig_rul
    names = [f.name for f in r.fields]
    assert len(names) == len(set(names))
    biz = next(f for f in r.fields if f.name == "Επιχειρήσεις και επιχειρηματικότητα")
    assert set(biz.talents) == {"LEAD", "STRAT"} and not biz.guarantee and biz.decision == "ΕΠΙΛΕΓΕΤΑΙ"


def test_fields_are_unique_on_random_charts():
    for c in _charts(150, 16):
        names = [f.name for f in run_engine(c).fields]
        assert len(names) == len(set(names))


def test_rule10_position_plus_aspect_and_wide_pair_v22_9():
    """Κανόνας 10: «μία θέση πλανήτη και μία όψη του ίδιου πλανήτη προς διαφορετικό πλανήτη (δύο)»·
    δύο Πλατιές με ΚΟΙΝΟ σημείο (οποιοδήποτε) αρκούν. Στο 11/02/1982: Ήλιος–Άρης τρίγωνο + Άρης στον
    Οίκο 10 -> Ηγεσία· Ήλιος–Πλούτωνας + Ερμής–Πλούτωνας (κοινό: Πλούτωνας) -> Έρευνα σε βάθος."""
    r = run_engine(_pafos())
    by = {t.theme: t for t in r.talents}
    assert by["LEAD"].basis == "δύο δείκτες"
    assert by["RESEARCH"].basis == "δύο πλατιές με κοινό σημείο"



def test_rule6_house_rulers_v22_10():
    """Κανόνας 6: ο Ερμής κυβερνά το Μεσουράνημα (Παρθένος) -> μαζί με το Ερμής–Ωροσκόπος (Κανονική)
    εγκρίνεται η «Επικοινωνία». Ο κυβερνήτης ΔΕΝ αρκεί ως κύριος δείκτης: με μία μόνο Πλατιά όψη
    (Ερμής–Δίας) και τον Δία κυβερνήτη του Ωροσκόπου, η «Διδασκαλία» δεν εγκρίνεται."""
    from core import talent_engine as te
    rul = te._ruler_indicators(_pafos())
    assert any("Μεσουρανήματος" in i.label for i in rul["COMM"])
    r = run_engine(_pafos())
    assert "COMM" in {t.theme for t in r.talents}
    assert "TEACH" in r.candidates_rejected


def test_generational_sign_concentration_needs_personal_link_v22_11():
    """Κανόνας 5: Κρόνος + Πλούτωνας σε Ζυγό (1981-83) είναι «γενιά». Μετρούν σε συγκέντρωση ζωδίου
    μόνο αν συνδέονται με προσωπικό πλανήτη/γωνία, και η συγκέντρωση θέλει προσωπικό πλανήτη.
    11/02/1982: Άρης σε Ζυγό + Κρόνος σύνοδος Άρη + Πλούτωνας τετράγωνο Αφροδίτης -> μένει."""
    r = run_engine(_pafos())
    assert "JUSTICE" in {t.theme for t in r.talents}
    random.seed(21)
    hits = n = 0
    for _ in range(80):
        ut = datetime(1981, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=random.randint(0, 3 * 365 * 24 * 60))
        n += 1
        hits += "JUSTICE" in {t.theme for t in run_engine(compute_chart(ut, 35.0, 33.0)).talents}
    assert hits / n < 0.6          # πριν τη διόρθωση: ~89% της γενιάς



def test_ruler_placement_only_supports_v22_12():
    """Κανόνας 6, «πού βρίσκεται ο κυβερνήτης»: ο Ερμής (κυβερνήτης Μεσουρανήματος) στον Οίκο 2 σε Υδροχόο
    ενισχύει την «Πρωτοτυπία», αλλά δεν δημιουργεί νέο ταλέντο (π.χ. Επιχειρηματικότητα)."""
    r = run_engine(_pafos())
    innov = next(t for t in r.talents if t.theme == "INNOV")
    assert any("βρίσκεται στον Οίκο 2" in i.label for i in innov.supporting)
    assert "ENTRE" in r.candidates_rejected


def test_talent_colours_v22_21():
    """Αποχρώσεις («πώς φαίνεται σε σένα»): από το «άλλο» σημείο ενός δείκτη, ποτέ από την ίδια την πηγή·
    έως 4 ανά ταλέντο από διαφορετικά σημεία· καμία φράση δύο φορές στην αναφορά."""
    from core.talent_map import COLOUR_SPECIFIC, COLOURS, PLANET_THEMES, SIGN_THEMES, colour_phrases
    from core.talent_engine import MAX_COLOURS
    assert set(PLANET_THEMES) | set(SIGN_THEMES) <= set(COLOURS)
    assert all(len(v) == 3 for v in COLOURS.values())
    texts = [v[0] for v in COLOUR_SPECIFIC.values()]
    assert len(texts) == len(set(texts)) >= 80
    by = {t.theme: t for t in run_engine(_pafos()).talents}
    assert colour_phrases(by["LEAD"])[0] == "με συνεργατικό πνεύμα"
    assert colour_phrases(by["DESIGN"])[0] == "με βάθος, πέρα από την επιφάνεια"
    assert set(colour_phrases(by["CARE"])) == {"με πρακτική βοήθεια και προσοχή στη λεπτομέρεια",
                                                "με φαντασία για το τι χρειάζεται ο άλλος"}
    assert all(t.colours for t in by.values())
    got = n = 0
    for c in _charts(150, 17):
        talents = run_engine(c).talents
        for lang in ("el", "en"):
            shown = [p for t in talents for p in colour_phrases(t, lang)]
            assert len(shown) == len(set(shown))
        for t in talents:
            n += 1
            got += bool(t.colours)
            assert len(t.colours) <= MAX_COLOURS and len({k for k, _, _ in t.colours}) == len(t.colours)
            for key, _, src in t.colours:
                own = PLANET_THEMES.get(key) or SIGN_THEMES[key]
                assert own[0] != t.theme and src
    assert got / n > 0.75


def test_sun_supports_its_house_theme_v22_20():
    """Ο Ήλιος «λάμπει» στον Οίκο του: στηρίζει το κύριο θέμα του βασικού Οίκου όπου βρίσκεται.
    11/02/1982: Ήλιος στον Οίκο 3 -> η «Επικοινωνία» από αναδυόμενο γίνεται βασικό."""
    comm = next(t for t in run_engine(_pafos()).talents if t.theme == "COMM")
    assert comm.rank == "βασικό"
    assert any(i.kind == "Θέση" and i.points == ("Ήλιος",) for i in comm.indicators)


def test_colours_do_not_repeat_words_v22_22():
    """Αναφορά Α (11/02/1982): «…που δίνει κουράγιο» πάνω από «…μπορεί να δίνει κουράγιο», «με υπομονή» πάνω από
    «Η υπομονή…». Η απόχρωση δεν επαναλαμβάνει λέξη του τίτλου/της περιγραφής, ούτε λέξη άλλης απόχρωσης."""
    from core.talent_engine import _library_stems, _stems
    from core.talent_map import colour_phrases
    for c in list(_charts(80, 19)) + [_pafos()]:
        seen: set[str] = set()
        for t in run_engine(c).talents:
            for el, en in zip(colour_phrases(t, "el"), colour_phrases(t, "en")):
                stems = _stems(el) | _stems(en)
                assert not stems & _library_stems(t.theme), (t.theme, el)
                assert not stems & seen, el
                seen |= stems
