"""v22.4 -- Εκδοχή Β: το AI γράφει ΜΟΝΟ πεδία ανά κωδικό· η εφαρμογή συνθέτει (core/talent_polish.py)."""
import json
from datetime import datetime, timezone

from core.costs import CostTracker
from core.ephemeris import compute_chart
from core.generator import GenerationResult
from core.talent_engine import run_engine
from core.talent_polish import MAX_ATTEMPTS, build_polish_prompt, check_segments, polish_report
from core.talent_report import build_engine_report, client_markdown
from core.talent_texts import talent_text


def _setup(lang="el"):
    chart = compute_chart(datetime(1982, 2, 10, 23, 45, tzinfo=timezone.utc), 34.7754, 32.4218)
    result = run_engine(chart)
    return chart, result, client_markdown(result, lang)


def _good(result, lang="el"):
    if lang == "el":
        intro = ("Μπορεί να συνδυάζεις τη διάθεση να στηρίζεις τους άλλους με μια έντονη αίσθηση του δικαίου "
                 "και μια ματιά που ψάχνει νέους τρόπους. Συχνά αυτά τα στοιχεία δουλεύουν μαζί, ώστε να "
                 "βοηθάς τους ανθρώπους γύρω σου και ταυτόχρονα να βελτιώνεις τον τρόπο που γίνονται τα πράγματα.")
        link = "Αυτό μπορεί να δένει όμορφα με τα υπόλοιπα ταλέντα σου όταν δουλεύεις με άλλους."
        flink = "Εδώ μπορούν να συναντηθούν τα ταλέντα σου σε κάτι χρήσιμο για άλλους."
    else:
        intro = ("You may combine a wish to support others with a strong sense of fairness and an eye for new "
                 "ways of doing things. These qualities often work together, so that you help the people around "
                 "you while improving the way things are done.")
        link = "This may link well with your other talents when you work with others."
        flink = "Here your talents may meet in something useful to others."
    if lang == "el":
        openers = ["Αυτό", "Εδώ", "Συχνά", "Παράλληλα", "Έτσι", "Επιπλέον", "Ακόμη", "Επίσης", "Τότε",
                   "Συνδυαστικά", "Με αυτόν τον τρόπο", "Στην πράξη", "Μέσα σε ομάδα"]
    else:
        openers = ["This", "Here", "Often", "At the same time", "In this way", "Also", "Then", "Besides",
                   "In practice", "Combined", "Likewise", "In a team", "Over time"]
    talents = {t.theme: f"{openers[i % len(openers)]} {link[0].lower()}{link[1:]}"
               for i, t in enumerate(result.talents)}
    return {"intro": intro, "talents": talents,
            "fields": {f.name: flink for f in result.fields if f.decision == "ΕΠΙΛΕΓΕΤΑΙ"}}


def test_prompt_gives_exact_codes_and_count():
    _, result, text = _setup()
    prompt = build_polish_prompt(text, result, "el", "Μαρία")
    assert "Μαρία" in prompt and "ΑΠΑΓΟΡΕΥΕΤΑΙ" in prompt and f"ΑΚΡΙΒΩΣ {len(result.talents)} ταλέντα" in prompt
    for t in result.talents:
        assert f'"{t.theme}"' in prompt


def test_good_segments_are_composed_by_the_app():
    _, result, text = _setup()
    seg = _good(result)

    def gen(prompt, max_output_tokens=None):
        return GenerationResult("```json\n" + json.dumps(seg, ensure_ascii=False) + "\n```",
                                "claude-sonnet-5-5", 4000, 1500)
    cost = CostTracker()
    out = polish_report(text, result, "el", gen, cost=cost)
    assert out.used_ai and out.attempts == 1 and cost.total_usd > 0
    assert "## Τι σε χαρακτηρίζει" in out.text
    for i, t in enumerate(result.talents, 1):                 # αρίθμηση + σταθερή περιγραφή βιβλιοθήκης
        lib = talent_text(t.theme, "el")
        develop = lib["develop"] if result.minor else lib["develop_adult"]   # v22.48: ενήλικας -> develop_adult
        assert f"**{i}. {lib['title']}**" in out.text and lib["text"] in out.text and develop in out.text
    assert out.text.strip().endswith("*") and all(v in out.text for v in seg["talents"].values())


def _reject(seg, result, text, lang="el"):
    out = polish_report(text, result, lang, lambda p, max_output_tokens=None: json.dumps(seg, ensure_ascii=False))
    assert not out.used_ai and out.text == text and out.attempts == MAX_ATTEMPTS and out.issues
    return out.issues


def test_missing_extra_or_replaced_talent_codes_are_rejected():
    _, result, text = _setup()
    first = result.talents[0].theme
    seg = _good(result); del seg["talents"][first]
    assert any("ταλέντα" in x for x in _reject(seg, result, text))
    from core.talent_map import THEMES
    other = next(k for k in THEMES if k not in {t.theme for t in result.talents})   # ταλέντο που ΔΕΝ επιλέχθηκε
    seg = _good(result); seg["talents"][other] = "Μπορεί να έχεις και καλλιτεχνική φλέβα."
    assert any("ταλέντα" in x for x in _reject(seg, result, text))
    seg = _good(result); seg["talents"][other] = seg["talents"].pop(first)          # αντικατάσταση
    assert any("ταλέντα" in x for x in _reject(seg, result, text))


def test_unselected_talent_inside_a_sentence_is_rejected():
    """Εξωτερικός έλεγχος #1: «Μπορεί να έχεις επίσης εξαιρετική μουσική ικανότητα.» περνούσε."""
    _, result, text = _setup()
    seg = _good(result)
    # v22.46: στον χάρτη αυτόν η «Φαντασία και καλλιτεχνική έκφραση» εγκρίνεται πλέον (Ποσειδώνας στον 1ο, βιβλίο)·
    # το παράδειγμα γίνεται με ταλέντο που ΔΕΝ επιλέχθηκε.
    assert "HOSP" not in {t.theme for t in result.talents}
    seg["talents"][result.talents[0].theme] += " Μπορεί να έχεις επίσης εξαιρετική ικανότητα στη φιλοξενία."
    assert any("δεν επιλέχθηκε" in x and "HOSP" in x for x in _reject(seg, result, text))


def test_health_profession_needs_its_own_approved_field():
    """Εξωτερικός έλεγχος #2: με εγκεκριμένο μόνο τον τομέα «Υγεία…», «ψυχολόγος ή διαιτολόγος» περνούσε."""
    _, result, text = _setup()
    assert any(f.name == "Υγεία και θεραπευτικές υπηρεσίες" for f in result.fields)
    seg = _good(result)
    seg["intro"] += " Μπορεί να σε ενδιαφέρει να γίνεις ψυχολόγος ή διαιτολόγος."
    issues = check_segments(seg, text, result, "el")
    assert any("υγείας" in x for x in issues)
    seg = _good(result)
    seg["intro"] += " Ίσως σε ενδιαφέρει και η νοσηλευτική."       # εγκεκριμένος τομέας: επιτρέπεται
    assert not any("υγείας" in x for x in check_segments(seg, text, result, "el"))


def test_other_bad_segments():
    _, result, text = _setup()
    first = result.talents[0].theme
    cases = {
        "astro term": ("intro", "Ο Ήλιος σου δείχνει ότι μπορεί να στηρίζεις τους άλλους. " * 5),
        "certainty": ("intro", _good(result)["intro"] + " Θα πετύχεις σίγουρα."),
        "unselected field": ("intro", _good(result)["intro"] + " Ίσως και στην αεροπορία και διάστημα."),
        "markdown": ("talent", "**Νέο ταλέντο** που μπορεί να σε βοηθήσει πολύ στη δουλειά."),
        "too long": ("talent", "Μπορεί να βοηθάς. " * 40),
    }
    for label, (where, value) in cases.items():
        seg = _good(result)
        if where == "intro":
            seg["intro"] = value
        else:
            seg["talents"][first] = value
        _reject(seg, result, text)
    out = polish_report(text, result, "el", lambda p, max_output_tokens=None: "όχι JSON")
    assert not out.used_ai and "JSON" in out.issues[0]


def test_ai_error_gives_version_a_and_report_says_so():
    chart, _, _ = _setup()

    def boom(prompt, max_output_tokens=None):
        raise RuntimeError("no credit")
    r = build_engine_report(chart, "Μαρία", "el", generate_fn=boom)
    assert r.polish is not None and not r.polish.used_ai and r.client_text == r.engine_text
    assert "Δόθηκε η εκδοχή Α" in r.audit_text and "no credit" in r.audit_text


def test_english_version_b():
    chart, result, _ = _setup("en")
    seg = _good(result, "en")
    r = build_engine_report(chart, "", "en", generate_fn=lambda p, max_output_tokens=None: json.dumps(seg))
    assert r.polish.used_ai and "## What characterises you" in r.client_text and r.engine_text != r.client_text


def test_one_sentence_per_talent_v22_13():
    _, result, text = _setup()
    seg = _good(result)
    seg["talents"][result.talents[0].theme] = ("Αυτό μπορεί να δένει με την ομαδικότητα σου. "
                                               "Μαζί με την οργάνωση ίσως γίνεται ακόμη πιο χρήσιμο.")
    assert any("πάνω από μία πρόταση" in x for x in check_segments(seg, text, result, "el"))


def test_single_talent_field_mentions_only_its_talent_v22_13():
    """Αναφορά Β (11/02/1982): «Εικαστικές τέχνες» είναι τομέας ΜΟΝΟ για την «Αισθητική», αλλά το AI
    έγραψε «…συνδυάζεται εδώ με την πρωτοτυπία και την πρακτική δημιουργία…»."""
    _, result, text = _setup()
    single = [f for f in result.fields if f.decision == "ΕΠΙΛΕΓΕΤΑΙ" and len(f.talents) == 1]
    assert single
    f = next((x for x in single if x.talents[0] == "DESIGN"), single[0])
    seg = _good(result)
    seg["fields"][f.name] = ("Η αισθητική μπορεί να συνδυάζεται εδώ με την πρωτοτυπία και την πρακτική "
                             "δημιουργία, ώστε ό,τι φτιάχνεις να είναι όμορφο και λειτουργικό.")
    issues = check_segments(seg, text, result, "el")
    assert any("τομέας ενός ταλέντου" in x for x in issues)
    from core.talent_map import THEMES
    seg["fields"][f.name] = f"Εδώ το ταλέντο «{THEMES[f.talents[0]][0]}» μπορεί να βρει χώρο."
    assert not any("τομέας ενός ταλέντου" in x for x in check_segments(seg, text, result, "el"))
    assert '"only_this_talent": true' in build_polish_prompt(text, result, "el")
