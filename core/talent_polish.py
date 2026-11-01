"""
core/talent_polish.py -- AstroCheck Career (v22.4)

Εκδοχή Β («δέσιμο»): ένα φτηνό βήμα AI κάνει την αναφορά πιο προσωπική, ΧΩΡΙΣ να ελέγχει τη δομή της.

v22.4 (μετά από εξωτερικό έλεγχο): το AI ΔΕΝ ξαναγράφει πλέον ολόκληρη την αναφορά. Παίρνει τη λίστα
με τους ΚΩΔΙΚΟΥΣ των ταλέντων και των τομέων που βρήκε η μηχανή (π.χ. 8 ταλέντα, 7 τομείς) και
επιστρέφει JSON με ΑΚΡΙΒΩΣ αυτούς τους κωδικούς -- ούτε περισσότερους ούτε λιγότερους:
    intro                 -> 4-6 προτάσεις «Τι σε χαρακτηρίζει»
    talents[ΚΩΔΙΚΟΣ]      -> 1-2 προτάσεις ΣΥΝΔΕΣΗΣ για κάθε επιλεγμένο ταλέντο (η περιγραφή της
                             βιβλιοθήκης μένει σταθερή -- το AI δεν την ξαναγράφει)
    fields[ΤΟΜΕΑΣ]        -> μία πρόταση: πώς συναντιούνται τα ταλέντα σε κάθε κύριο τομέα
Αρίθμηση, τίτλους, βασικές περιγραφές, προτάσεις καλλιέργειας, λίστες τομέων, επόμενα βήματα και επιφύλαξη τα συνθέτει η ΕΦΑΡΜΟΓΗ
(talent_report.client_markdown) -- το AI δεν μπορεί να τα αλλάξει, να τα παραλείψει ή να προσθέσει.

Κάθε πεδίο ελέγχεται χωριστά (check_segments). Απορρίπτεται αν:
  * λείπει/περισσεύει κωδικός, ή το μήκος είναι εκτός ορίων,
  * αναφέρει ταλέντο που ΔΕΝ επιλέχθηκε (λεξικό χαρακτηριστικών λέξεων ανά ταλέντο -- επιτρέπονται
    μόνο λέξεις που υπάρχουν ήδη στο προσχέδιο),
  * αναφέρει τομέα του καταλόγου που δεν επιλέχθηκε,
  * αναφέρει επάγγελμα υγείας ΧΩΡΙΣ εγκεκριμένο τον ΣΥΓΚΕΚΡΙΜΕΝΟ τομέα υγείας (Κανόνας 15, ανά τομέα),
  * έχει αστρολογικούς όρους, απόλυτους ισχυρισμούς ή υποθέσεις για το παρελθόν.
Ο έλεγχος παραμένει μηχανικός: μειώνει πολύ, αλλά δεν μηδενίζει, τον κίνδυνο μιας προσθήκης με
λέξεις που δεν προβλέπει το λεξικό -- γι' αυτό η Διαχείριση έχει Α και Β για σύγκριση.
Αν αποτύχει δύο φορές (ή αν το AI δεν απαντήσει), μένει η εκδοχή Α.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field

from .talent_map import colour_phrase
from .talent_engine import EngineResult
from .talent_texts import field_text, load_texts, talent_text
from .validator import _absolute_claims, _past_experience_claims, _simple_presentation_technical_terms

MAX_ATTEMPTS = 2
MAX_OUTPUT_TOKENS = 6000
LIMITS = {"intro": (35, 160), "talent": (6, 35), "field": (6, 40)}   # λέξεις ανά πεδίο

# Επαγγέλματα υγείας ΑΝΑ τομέα (Κανόνας 15): η έγκριση ενός τομέα δεν ανοίγει τους άλλους.
HEALTH_STEMS = {
    "Υγεία και θεραπευτικές υπηρεσίες": (
        "γιατρ", "ιατρ", "νοσηλευτ", "φαρμακοποι", "φυσικοθεραπ", "εργοθεραπ", "λογοθεραπ", "οδοντιατρ",
        "κτηνιατρ", "μαια", "μαιευτ", "doctor", "physician", "nurse", "nursing", "pharmacist", "physiotherap",
        "occupational therap", "speech therap", "dentist", "veterinar", "midwi"),
    "Ψυχολογία και κοινωνική φροντίδα": (
        "ψυχολογ", "ψυχιατρ", "ψυχοθεραπ", "κοινωνικ λειτουργ", "συμβουλ ψυχικ", "psycholog", "psychiatr",
        "psychotherap", "social worker", "counsell"),
    "Διατροφή και διαιτολογία": ("διαιτολογ", "διατροφολογ", "dietitian", "dietician", "nutritionist"),
}
_ANY_THERAPIST = ("θεραπευτ", "therapist")   # γενικό «θεραπευτής»: μόνο με τον τομέα Υγείας

# Χαρακτηριστικές λέξεις (ρίζες, χωρίς τόνους) για κάθε ταλέντο. Αν εμφανιστεί λέξη ταλέντου που ΔΕΝ
# επιλέχθηκε -- και η λέξη δεν υπάρχει ήδη στο προσχέδιο -- το πεδίο απορρίπτεται.
THEME_KEYWORDS = {
    "LEAD": ("ηγεσι", "ηγετ", "leadership", "leader"),
    "ORG": ("οργανωτικ", "organisational", "organizational"),
    "ANALYSIS": ("αναλυτικ", "analytical"),
    "COMM": ("ρητορ", "επικοινωνιακ", "eloquen"),
    "TEACH": ("διδασκ", "διδακτ", "teaching", "teacher"),
    "RESEARCH": ("ερευνητ", "researcher"),
    "INNOV": ("καινοτομ", "innovat"),
    "TECH": ("τεχνολογ", "technolog", "υπολογιστ", "computer", "δικτυ", "network", "προγραμματ", "programm"),
    "ART": ("καλλιτεχν", "μουσικ", "ζωγραφ", "artistic", "music", "painting"),
    "DESIGN": ("αισθητικ", "σχεδιαστ", "aesthetic", "designer"),
    "DIPLO": ("διπλωματ", "diplomac", "diplomat"),
    "JUSTICE": ("δικαιοσυν", "αδικ", "justice", "fairness", "injustice"),
    "CARE": ("ενσυναισθ", "empath"),
    "HOSP": ("φιλοξεν", "hospitality"),
    "ACTION": ("αθλητ", "athlet", "sport"),
    "BUILD": ("κατασκευ", "craftsman", "craftsmanship"),
    "ENTRE": ("επιχειρηματ", "entrepreneur"),
    "STRAT": ("στρατηγικ", "strategic", "strategy"),
    "STORY": ("αφηγ", "συγγραφ", "storytell", "novelist"),
    "COMMUNITY": ("κοινοτητ", "community"),
    "SUPPORT": ("ενθαρρυν", "encourag"),
    "PERFORM": ("σκην", "onstage", "performer"),
    "EXPLORE": ("ταξιδ", "εξερευν", "travel", "explor"),
}


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in text if unicodedata.category(c) != "Mn").casefold()


def _has_stem(plain_text: str, stem: str) -> bool:
    return re.search(r"\b" + re.escape(stem), plain_text) is not None


@dataclass
class PolishOutcome:
    text: str                       # το τελικό κείμενο πελάτη (Β, ή Α αν απέτυχε)
    used_ai: bool
    attempts: int = 0
    issues: list[str] = field(default_factory=list)   # του τελευταίου απορριφθέντος κειμένου
    error: str = ""
    segments: dict | None = None    # τα πεδία του AI που χρησιμοποιήθηκαν


_STOP = {"και", "and", "with", "μέσα", "others", "people", "things", "through", "expression", "wider"}


def _title_stems(theme: str, lang: str, exclude: str | None = None) -> set[str]:
    """Ρίζες (6 γράμματα, χωρίς τόνους) των λέξεων του τίτλου ενός ταλέντου· χωρίς όσες υπάρχουν και
    στον τίτλο/την περιγραφή του `exclude` (για να μη θεωρηθεί «άλλο ταλέντο» μια κοινή λέξη)."""
    words = {w[:6] for w in re.findall(r"\w{6,}", _plain(talent_text(theme, lang)["title"])) if w not in _STOP}
    words -= {w[:6] for w in _STOP}
    if exclude:
        own = _plain(" ".join(talent_text(exclude, lang).values()))
        words = {w for w in words if not _has_stem(own, w)}
    return words


def _sentences(text: str) -> int:
    return max(1, len(re.findall(r"[.!;?](?=\s|$)", text.strip())))


def _main_fields(result: EngineResult):
    return [f for f in result.fields if f.decision == "ΕΠΙΛΕΓΕΤΑΙ"]


def build_polish_prompt(engine_text: str, result: EngineResult, lang: str, name: str = "") -> str:
    data = {
        "talents": [{"code": t.theme, "level": t.rank, "title": talent_text(t.theme, lang)["title"],
                     "description": talent_text(t.theme, lang)["text"],
                     "nuance": colour_phrase(t.colour, t.colour_variant, lang)}
                    for t in result.talents],
        "fields": [{"field": f.name, "name": field_text(f.name, lang)["name"],
                    "talents": [talent_text(th, lang)["title"] for th in f.talents],
                    "only_this_talent": len(f.talents) == 1} for f in _main_fields(result)],
    }
    skeleton = {"intro": "...", "talents": {t.theme: "..." for t in result.talents},
                "fields": {f.name: "..." for f in _main_fields(result)}}
    n_t, n_f = len(result.talents), len(_main_fields(result))
    if lang == "el":
        who = f"Ο πελάτης λέγεται {name}. " if name else ""
        return f"""Είσαι συντάκτης αναφορών επαγγελματικού προσανατολισμού. {who}Μια μηχανή κανόνων έχει ήδη επιλέξει
ΑΚΡΙΒΩΣ {n_t} ταλέντα και {n_f} κύριους τομείς (ΔΕΔΟΜΕΝΑ). Γράψε ΜΟΝΟ τα παρακάτω πεδία, ώστε η αναφορά να
διαβάζεται πιο προσωπικά:

- "intro": 4-6 προτάσεις που δείχνουν πώς συνδέονται τα ταλέντα μεταξύ τους (κυρίως τα κυρίαρχα).
- "talents": για ΚΑΘΕ έναν από τους {n_t} κωδικούς, ΜΙΑ μόνο πρόταση (έως 30 λέξεις) που ΣΥΝΔΕΕΙ αυτό το
  ταλέντο με ένα ή δύο από τα άλλα επιλεγμένα ταλέντα. Η πρόταση μπαίνει στο τέλος της παραγράφου του ταλέντου,
  μετά την περιγραφή (description): να συνεχίζει φυσικά τη ροή, χωρίς να επαναλαμβάνει λέξεις ή ιδέες της.
  Κάθε πρόταση να ξεκινά διαφορετικά (όχι συνέχεια «Μαζί με…», «Ίσως…», «Μπορεί να…»). Η βασική περιγραφή (description) μένει όπως είναι και μπαίνει πριν από τις προτάσεις σου·
  μην την επαναλάβεις. Μη γράψεις τίτλο, αρίθμηση ή τρόπους καλλιέργειας -- τα βάζει η εφαρμογή. Το "nuance"
  εμφανίζεται δίπλα στον τίτλο ως δεύτερος τίτλος· μπορείς να το αξιοποιήσεις, αλλά μην το επαναλάβεις αυτούσιο.
- "fields": για ΚΑΘΕ έναν από τους {n_f} τομείς, ΜΙΑ πρόταση: πώς συναντιούνται εκεί τα ταλέντα του. Όταν ο
  τομέας έχει "only_this_talent": true, μίλα ΜΟΝΟ για εκείνο το ένα ταλέντο -- μην αναφέρεις κανένα άλλο.

ΑΠΑΓΟΡΕΥΕΤΑΙ: να αναφέρεις ταλέντο, ικανότητα ή τομέα που ΔΕΝ υπάρχει στα ΔΕΔΟΜΕΝΑ (π.χ. «και μουσική
ικανότητα»)· επαγγέλματα υγείας (γιατρός, ψυχολόγος, διαιτολόγος κ.λπ.)· αστρολογικοί όροι (πλανήτες, ζώδια,
Οίκοι, όψεις, χάρτης ως απόδειξη)· βεβαιότητες («θα πετύχεις», «γεννήθηκες για», «πρέπει να γίνεις»)·
υποθέσεις για το παρελθόν του πελάτη· το «είσαι» -- γράφε «μπορεί να», «συχνά», «ίσως».
Απόφυγε μεταφορές όπως «το ταξίδι σου» ή «η σκηνή της ζωής». Γλώσσα: ελληνικά, απλά, ζεστά, β΄ ενικό, χωρίς markdown.

Απάντησε ΜΟΝΟ με έγκυρο JSON, ακριβώς με αυτά τα κλειδιά (ούτε λιγότερα ούτε περισσότερα):
{json.dumps(skeleton, ensure_ascii=False)}

ΔΕΔΟΜΕΝΑ
{json.dumps(data, ensure_ascii=False, indent=1)}
"""
    who = f"The client's name is {name}. " if name else ""
    return f"""You write career guidance reports. {who}A rules engine has already chosen EXACTLY {n_t} talents and
{n_f} main fields (DATA). Write ONLY the fields below, so the report reads more personally:

- "intro": 4-6 sentences showing how the talents connect with each other (mainly the leading ones).
- "talents": for EACH of the {n_t} codes, ONE sentence only (max 30 words) that LINKS this talent with one or two of
  the other chosen talents. It goes at the end of the talent's paragraph, after its description: it should continue
  the flow naturally, without repeating words or ideas from it. Start each sentence differently (not repeatedly
  "Together with…", "Perhaps…", "You may…"). The
  basic description stays as it is and comes before your sentences; do not repeat it. Do not write a title,
  numbering or ways to develop it -- the app adds those. The "nuance" is shown next to the title as a subtitle;
  you may build on it, but do not repeat it word for word.
- "fields": for EACH of the {n_f} fields, ONE sentence: how its talents meet there. When a field has
  "only_this_talent": true, speak ONLY about that one talent -- do not mention any other.

FORBIDDEN: mentioning any talent, ability or field NOT in the DATA (e.g. "and a musical gift"); health professions
(doctor, psychologist, dietitian etc.); astrological terms (planets, signs, houses, aspects, the chart as proof);
certainty ("you will succeed", "born to", "must become"); assumptions about the client's past; "you are" -- write
"you may", "often", "perhaps". Avoid metaphors such as "your journey" or "the stage of life". Language: English, plain and warm, second person, no markdown.

Reply ONLY with valid JSON, with exactly these keys (no fewer, no more):
{json.dumps(skeleton, ensure_ascii=False)}

DATA
{json.dumps(data, ensure_ascii=False, indent=1)}
"""


def parse_segments(raw: str) -> dict | None:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip()).strip()
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        return None
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def check_segments(seg: dict, engine_text: str, result: EngineResult, lang: str) -> list[str]:
    issues = []
    want_t = [t.theme for t in result.talents]
    want_f = [f.name for f in _main_fields(result)]
    if set(seg) != {"intro", "talents", "fields"} or not isinstance(seg.get("intro"), str) \
            or not isinstance(seg.get("talents"), dict) or not isinstance(seg.get("fields"), dict):
        return ["λάθος μορφή JSON (κλειδιά intro / talents / fields)"]
    if set(seg["talents"]) != set(want_t):
        issues.append(f"ταλέντα: το AI έδωσε {len(seg['talents'])}, η μηχανή βρήκε {len(want_t)} -- "
                      "πρέπει να είναι ακριβώς τα ίδια")
    if set(seg["fields"]) != set(want_f):
        issues.append(f"τομείς: το AI έδωσε {len(seg['fields'])}, η μηχανή βρήκε {len(want_f)} -- "
                      "πρέπει να είναι ακριβώς οι ίδιοι")
    pieces = [("intro", "εισαγωγή", seg["intro"])]
    pieces += [("talent", f"ταλέντο {k}", v) for k, v in seg["talents"].items()]
    pieces += [("field", f"τομέας «{k}»", v) for k, v in seg["fields"].items()]
    single = {f.name: f.talents[0] for f in _main_fields(result) if len(f.talents) == 1}
    openings = [" ".join(_plain(v).split()[:2]) for v in seg["talents"].values() if isinstance(v, str)]
    worst = max((openings.count(o) for o in set(openings)), default=0)
    if worst > max(2, len(openings) // 3):
        issues.append(f"οι προτάσεις σύνδεσης ξεκινούν {worst} φορές με τον ίδιο τρόπο (επανάληψη)")

    draft = _plain(engine_text)
    chosen_t = set(want_t)
    chosen_f = {f.name for f in result.fields}
    other_fields = [(n, _plain((e.get(lang) or e["el"])["name"])) for n, e in load_texts()["fields"].items()
                    if n not in chosen_f]
    allowed_health = {s for f, stems in HEALTH_STEMS.items() if f in chosen_f for s in stems}
    if "Υγεία και θεραπευτικές υπηρεσίες" in chosen_f:
        allowed_health |= set(_ANY_THERAPIST)
    forbidden_health = {s for stems in HEALTH_STEMS.values() for s in stems} | set(_ANY_THERAPIST)
    forbidden_health -= allowed_health

    for kind, label, value in pieces:
        if not isinstance(value, str) or not value.strip():
            issues.append(f"{label}: κενό")
            continue
        p = _plain(value)
        lo, hi = LIMITS[kind]
        n = len(value.split())
        if not lo <= n <= hi:
            issues.append(f"{label}: μήκος {n} λέξεις (όριο {lo}-{hi})")
        if "*" in value or "#" in value:
            issues.append(f"{label}: περιέχει μορφοποίηση markdown")
        if kind in ("talent", "field") and _sentences(value) > 1:
            issues.append(f"{label}: πάνω από μία πρόταση")
        if kind == "field":
            name = label[len("τομέας «"):-1]
            if name in single:
                others = [th for th in want_t if th != single[name]
                          and any(_has_stem(p, st) for st in _title_stems(th, lang, exclude=single[name]))]
                if others:
                    issues.append(f"{label}: τομέας ενός ταλέντου, αλλά αναφέρει και άλλο ταλέντο ({', '.join(others)})")
        for theme, stems in THEME_KEYWORDS.items():
            if theme in chosen_t:
                continue
            hit = next((s for s in stems if _has_stem(p, s) and not _has_stem(draft, s)), None)
            if hit:
                issues.append(f"{label}: αναφέρει ταλέντο που δεν επιλέχθηκε ({theme}: «{hit}…»)")
        for name, shown in other_fields:
            if shown in p:
                issues.append(f"{label}: αναφέρει τομέα που δεν επιλέχθηκε («{name}»)")
        hit = next((s for s in forbidden_health if _has_stem(p, s)), None)
        if hit:
            issues.append(f"{label}: επάγγελμα υγείας χωρίς εγκεκριμένο τον αντίστοιχο τομέα («{hit}…», Κανόνας 15)")
        issues += [f"{label}: τεχνικός όρος: {x}" for x in _simple_presentation_technical_terms(value)]
        issues += [f"{label}: απόλυτη διατύπωση: {x}" for x in _absolute_claims(value)]
        issues += [f"{label}: υπόθεση για το παρελθόν: {x}" for x in _past_experience_claims(value)]
    return issues


def polish_report(engine_text: str, result: EngineResult, lang: str, generate_fn, *, name: str = "",
                  cost=None, model_name: str = "") -> PolishOutcome:
    """Δοκιμάζει έως MAX_ATTEMPTS φορές· αλλιώς επιστρέφει την εκδοχή Α."""
    from .talent_report import client_markdown   # αποφυγή κυκλικής εισαγωγής
    prompt = build_polish_prompt(engine_text, result, lang, name)
    outcome = PolishOutcome(engine_text, False)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        outcome.attempts = attempt
        try:
            raw = generate_fn(prompt, max_output_tokens=MAX_OUTPUT_TOKENS)
        except Exception as exc:  # noqa: BLE001 -- οποιοδήποτε σφάλμα AI -> εκδοχή Α
            outcome.error = f"{type(exc).__name__}: {exc}"[:300]
            break
        if cost is not None and hasattr(raw, "input_tokens"):
            cost.add(raw.model or model_name, raw.input_tokens, raw.output_tokens, kind="polish",
                     truncated=getattr(raw, "truncated", False))
        seg = parse_segments(getattr(raw, "text", raw))
        if seg is None:
            outcome.issues = ["η απάντηση δεν είναι έγκυρο JSON"]
            continue
        issues = check_segments(seg, engine_text, result, lang)
        if getattr(raw, "truncated", False):
            issues.append("η απάντηση κόπηκε (όριο μήκους)")
        if not issues:
            text = client_markdown(result, lang, ai=seg)
            final = (_simple_presentation_technical_terms(text) + _absolute_claims(text)
                     + _past_experience_claims(text))
            if not final:
                return PolishOutcome(text, True, attempt, segments=seg)
            issues = [f"τελικό κείμενο: {x}" for x in final]
        outcome.issues = issues
    return outcome
