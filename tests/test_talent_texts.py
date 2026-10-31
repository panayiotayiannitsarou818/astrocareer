"""v22 -- Κείμενα ταλέντων και τομέων (core/talent_texts.py)."""
from core.catalogue import sector_catalogue
from core.talent_map import HEALTH_FIELDS, THEME_FIELDS, THEMES
from core.talent_texts import field_text, load_texts, talent_text
from core.validator import _absolute_claims, _past_experience_claims, _simple_presentation_technical_terms


def test_every_theme_and_non_health_field_has_text():
    d = load_texts()
    assert set(d["talents"]) == set(THEMES)
    assert set(d["fields"]) == set(sector_catalogue())   # και οι 3 τομείς υγείας (Κανόνας 15)
    assert set(HEALTH_FIELDS) <= set(d["fields"])
    assert {f for fs in THEME_FIELDS.values() for f in fs} <= set(d["fields"])


def test_titles_match_engine_and_both_languages_exist():
    for k, (el, en) in THEMES.items():
        assert talent_text(k, "el")["title"] == el and talent_text(k, "en")["title"] == en
        for lang in ("el", "en"):
            t = talent_text(k, lang)
            assert len(t["text"].split()) >= 20 and len(t["develop"].split()) >= 12
    assert field_text("Νομική και δικαιοσύνη", "en")["name"] == "Law and justice"


def test_texts_obey_the_report_wording_rules():
    d = load_texts()
    for section in ("talents", "fields"):
        for key, e in d[section].items():
            assert e["status"] in ("draft", "approved")
            for lang in ("el", "en"):
                text = " ".join(e[lang].values())
                assert not _simple_presentation_technical_terms(text), (key, lang)
                assert not _absolute_claims(text), (key, lang)
                assert not _past_experience_claims(text), (key, lang)


def test_approval_status_counts_drafts():
    from core.talent_texts import approval_status, fully_approved
    st = approval_status()
    assert set(st) == {"tables", "talents", "fields", "teasers"}
    assert fully_approved() == (not (st["tables"] or st["talents"] or st["fields"]))
