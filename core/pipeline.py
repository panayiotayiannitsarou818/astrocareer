"""
pipeline.py
===========
Πλήρως αυτόματη διαδικασία AstroCheck Career (v18).

    Chart -> prompt -> μοντέλο -> καθαρό παραδοτέο + τεχνικό δελτίο
    -> πραγματικά .docx -> ξαναδιάβασμα -> validator
    -> διόρθωση από την ΚΑΛΥΤΕΡΗ ως τότε απόπειρα, μέχρι να εγκριθεί
    -> (προαιρετικά) γύρος ποιότητας ύφους, που κρατιέται μόνο αν
       εξακολουθεί να εγκρίνεται και δεν έχει χάσει περιεχόμενο.

Σταματά νωρίτερα -- κρατώντας ΠΑΝΤΑ την καλύτερη απόπειρα -- όταν:
  * τα σφάλματα δεν μειώνονται για AUTO_STALL_ROUNDS γύρους (αφού
    εξαντληθούν και οι νέες αρχές AUTO_FRESH_ROUNDS),
  * υπάρξει μόνιμο σφάλμα (λάθος κλειδί, ανύπαρκτο μοντέλο, χωρίς υπόλοιπο),
  * αποτύχουν AUTO_MAX_FAILED_REQUESTS αιτήματα στη σειρά,
  * η επόμενη κλήση θα ξεπερνούσε το όριο κόστους AUTO_MAX_COST_USD,
  * (δίχτυ ασφαλείας) φτάσει τις AUTO_MAX_ATTEMPTS κλήσεις.

Η πρόοδος (RunState) ενημερώνεται επί τόπου μετά από κάθε βελτίωση, ώστε
το «▶️ Συνέχεια» να ξεκινά από εκεί που σταμάτησε, χωρίς νέα πληρωμή για
όσα έγιναν. Αν άλλαξαν γλώσσα, όνομα, οδηγίες ή πρότυπο (fingerprint),
ξεκινά από την αρχή.

Ο validator εκτελείται πάνω στο κείμενο όπως ξαναδιαβάζεται από τα .docx
που θα παραδοθούν, μαζί με τον έλεγχο μορφής του Word.
"""
from __future__ import annotations

import hashlib
import inspect
import os
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from .costs import CostTracker, max_cost_usd
from .docx_builder import build_orientation_audit_docx, build_orientation_client_docx
from .generator import (
    GenerationResult, PERMANENT_ERROR_KEYS, count_input_tokens, TRANSIENT_ERROR_KEYS, classify_generation_error, default_model,
    generate, is_api_error,
)
from .prompts import build_orientation_prompt, build_orientation_source, split_orientation_response
from .reference_loader import (
    docx_text, load_orientation_command, load_unified_short_example, simple_docx_format_issues,
)
from .validator import _between_headings, _career_norm, _extract_talent_titles, validate_orientation

SERVICE_TITLE = "Ανάδειξη Ταλέντων και Διερεύνηση Επαγγελματικών Επιλογών"
# v19.10 (εξωτερικός έλεγχος): το αγγλικό Word έπαιρνε ελληνικό τίτλο, που ο έλεγχος γλώσσας
# μετρούσε μετά ως λάθος γλώσσα. Ο τίτλος του παραδοτέου ακολουθεί πλέον τη γλώσσα.
SERVICE_TITLES = {"el": SERVICE_TITLE, "en": "Talent Discovery and Career Exploration"}


def service_title(lang: str) -> str:
    return SERVICE_TITLES.get(lang, SERVICE_TITLE)
CLIENT_OUTPUT_NAME = "AstroCheck_Anadeixi_Talenton.docx"
AUDIT_TITLE = "Εσωτερικό Τεχνικό Δελτίο Ελέγχου"
PRESENTATION = "Απλή και πρακτική"


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.environ.get(name, default)))
    except ValueError:
        return default


@dataclass
class Settings:
    stall_rounds: int = 4          # γύροι χωρίς μείωση σφαλμάτων πριν τη νέα αρχή/διακοπή
    fresh_rounds: int = 3          # πόσες φορές ξεκινά εντελώς από την αρχή
    max_failed_requests: int = 5   # αποτυχημένα αιτήματα στη σειρά
    max_attempts: int = 25         # δίχτυ ασφαλείας: συνολικές κλήσεις
    max_cost_usd: Optional[float] = None
    quality_pass: bool = False     # γύρος ποιότητας ύφους μετά την έγκριση

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            stall_rounds=_env_int("AUTO_STALL_ROUNDS", 4, 1),
            fresh_rounds=_env_int("AUTO_FRESH_ROUNDS", 3, 1),
            max_failed_requests=_env_int("AUTO_MAX_FAILED_REQUESTS", 5, 1),
            max_attempts=_env_int("AUTO_MAX_ATTEMPTS", 25, 1),
            max_cost_usd=max_cost_usd(),
            quality_pass=os.environ.get("AUTO_QUALITY_PASS", "").strip().lower() in ("1", "true", "yes", "ναι"),
        )


def max_attempts_from_env() -> int:  # συμβατότητα
    return Settings.from_env().max_attempts


# ---------------------------------------------------------------- prompts

def language_clause(lang: str) -> str:
    # Το καθαρό παραδοτέο γράφεται στη γλώσσα της σελίδας· οι μηχαναγνώσιμες
    # επικεφαλίδες/ετικέτες του τεχνικού δελτίου μένουν ΠΑΝΤΑ ελληνικές --
    # ο validator εξαρτάται από αυτές.
    if lang == "el":
        return ("Γράψε το καθαρό παραδοτέο του πελάτη εξ ολοκλήρου στα Ελληνικά. Το εσωτερικό τεχνικό "
                "δελτίο μπορεί να έχει επεξηγηματικό κείμενο στα Ελληνικά, αλλά πρέπει να διατηρεί "
                "ΑΚΡΙΒΩΣ τις απαιτούμενες ελληνικές μηχαναγνώσιμες επικεφαλίδες/ετικέτες όπως ορίζονται.")
    return ("Write the clean client deliverable entirely in English. The internal technical audit may use "
            "English explanatory text, but it must preserve the required Greek machine-readable headings "
            "and labels exactly as specified.")


def reinforcement_instructions(name: str, lang: str) -> str:
    if not (name or "").strip():
        if lang == "el":
            return ("Δεν δόθηκε όνομα πελάτη. Μη γράψεις κανένα όνομα και μην επινοήσεις όνομα· "
                    "απευθύνσου στον αναγνώστη απευθείας, χωρίς όνομα.")
        return ("No client name was given. Do not write or invent any name; "
                "address the reader directly, without a name.")
    if lang == "el":
        return (f"Όνομα πελάτη: «{name}». Γράψε το ακριβώς όπως δόθηκε από τον χρήστη, διατηρώντας τους ίδιους "
                "χαρακτήρες, τόνους, ορθογραφία και κενά. Μην το μεταγράψεις, μην το μεταφράσεις και μην το "
                "διορθώσεις αυθαίρετα -- ό,τι αλφάβητο κι αν χρησιμοποιεί.")
    # Η δεσμευτική εντολή είναι στα Ελληνικά· για αγγλικό παραδοτέο δίνεται η
    # ακριβής αντιστοίχιση με τις αγγλικές διατυπώσεις που αναγνωρίζει ο validator.
    return f"""Client name: "{name}". Write it exactly as given -- do not alter its spelling, accents, or spacing, and do not transliterate or translate it.

The binding command is written in Greek. Apply all of its rules, but write the clean client deliverable in English, using these exact English equivalents, because the automated check looks for them literally:
- The four section headings (Heading 1), in this order: "Brief Profile", "Talents to Explore", "Career Fields to Explore", "Final Synthesis".
- Right after the last talent, the bold sentence "In summary, the talents to explore are:" followed by a bulleted list of all talent titles, written exactly as in their headings.
- Inside "Career Fields to Explore", each field has only three kinds of lines: the field title (Heading 2); one paragraph starting "Why it may fit:"; and one line starting "Example Careers per Field:" listing all of the field's careers comma-separated, with any explanation in parentheses right after the career name. A career name itself never contains parentheses. No other paragraphs or bullets in that section, except the optional brief-mention line described next.
- Optional, only for fields with the decision ΣΥΝΤΟΜΗ ΑΝΑΦΟΡΑ (Rule 12): after the last main field, ONE paragraph starting exactly with "Other directions you may also explore:" followed only by those field names, comma-separated, with no careers and no explanation.
- Do not write any dense-chart note or any other paragraph before the first talent title (Rule 11: the density check stays only in the technical audit).
- The closing paragraph of "Final Synthesis" starts with the bold words "What to Remember:" (not a separate heading) and states that these directions are not a final decision, that the subjects and activities the person enjoys and their actual performance can confirm or revise them, and above all that the final choice always remains theirs, as an expression of their free will.
- Never claim what the person has lived through or felt (e.g. "what you've been through", "your wound", "you have suffered"): the software knows only the chart. Words like pain, wound or hardship are fine only in general ("the difficulties everyone meets...") or hypothetical ("when you face...") form.
- Never use in the client deliverable: planet or point names, zodiac signs, the words "House" or "ruler", orb values, weight categories, or the words conjunction, trine, sextile, square, opposition, quincunx -- not even in their everyday sense.

The internal technical audit sheet keeps all its Greek machine-readable headings and labels exactly as the binding command specifies (ΤΑΛΕΝΤΟ:, Δείκτης 1/2, Μοναδικός ισχυρός δείκτης, ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ, ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ, ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ ΤΟΜΕΑ ΥΓΕΙΑΣ, Παράρτημα Επιβεβαιωμένων Όψεων, Παράρτημα Κάλυψης Θέσεων, Παράρτημα Κάλυψης Τομέων, Τελικός έλεγχος) and its Greek line labels and decision words (Σημείο:, Ζώδιο:, Οίκος:, Συγκέντρωση:, Σημεία:, Κοινό σημείο:, Όψεις:, Τομέας:, Απόφαση:, ΧΡΗΣΙΜΟΠΟΙΕΙΤΑΙ, ΕΞΑΙΡΕΙΤΑΙ, ΕΠΙΛΕΓΕΤΑΙ ως, ΣΥΝΤΟΜΗ ΑΝΑΦΟΡΑ ως, ΑΠΟΡΡΙΠΤΕΤΑΙ, εγγύηση). In the Παράρτημα Κάλυψης Τομέων, the catalogue field names stay in Greek exactly as in the catalogue, while the «» names after ΕΠΙΛΕΓΕΤΑΙ ως / ΣΥΝΤΟΜΗ ΑΝΑΦΟΡΑ ως and the talent names are the English names. The talent titles in its ΤΑΛΕΝΤΟ: lines, and the field and career names in its approved lists, must be the English names exactly as they appear in the client deliverable."""


def correction_note(previous_raw: str, issues: list[str], lang: str) -> str:
    issues_list = "\n".join(f"- {line}" for line in issues)
    if lang == "el":
        return (f"\n\nΗ ΠΡΟΗΓΟΥΜΕΝΗ ΣΟΥ ΑΠΑΝΤΗΣΗ (προς διόρθωση):\n{previous_raw}\n\n"
                f"Ο ΠΡΑΓΜΑΤΙΚΟΣ ΜΗΧΑΝΙΚΟΣ ΕΛΕΓΧΟΣ ΒΡΗΚΕ ΤΑ ΕΞΗΣ ΠΡΟΒΛΗΜΑΤΑ:\n{issues_list}\n\n"
                "Ξαναγράψε ολόκληρη την απάντηση (με την ίδια ακριβώς μορφή/δείκτες όπως πριν), "
                "διορθώνοντας ΜΟΝΟ αυτά τα συγκεκριμένα προβλήματα. Μην αλλάξεις τίποτα άλλο που "
                "ήδη ήταν σωστό.")
    return (f"\n\nYOUR PREVIOUS ANSWER (to be corrected):\n{previous_raw}\n\n"
            f"THE REAL ENGINEERING CHECK FOUND THESE ISSUES:\n{issues_list}\n\n"
            "Rewrite the entire answer (using the exact same format/markers as before), "
            "fixing ONLY these specific issues. Do not change anything else that was already correct.")


def build_context(name: str, lang: str) -> dict:
    from .i18n import TR
    t = TR[lang]
    return {t["ctx_name"]: name, t["ctx_presentation"]: t["presentation_simple"]}


def build_auto_prompt(chart, name: str, lang: str) -> str:
    return build_orientation_prompt(
        build_context(name, lang), load_orientation_command(), build_orientation_source(chart),
        load_unified_short_example(), language_clause=language_clause(lang), need_audit=True,
        extra_instructions=reinforcement_instructions(name, lang),
    )


def audit_docx_filename(display_name: str) -> str:
    """π.χ. «Γαβριέλα Δοε» -> «Γαβριέλα_Δοε_Εσωτερικό_Τεχνικό_Δελτίο.docx».
    Unicode επιτρέπεται· αφαιρούνται μόνο χαρακτήρες μη έγκυροι σε filename."""
    safe = re.sub(r'[\\/:*?"<>|]+', "", (display_name or "").strip())
    safe = re.sub(r"\s+", "_", safe).strip("_") or "AstroCheck"
    return f"{safe}_Εσωτερικό_Τεχνικό_Δελτίο.docx"


def client_docx_filename(display_name: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|]+', "", (display_name or "").strip())
    safe = re.sub(r"\s+", "_", safe).strip("_")
    return f"{safe}_{CLIENT_OUTPUT_NAME}" if safe else CLIENT_OUTPUT_NAME



def truncation_note(lang: str) -> str:
    if lang == "el":
        return ("\n\nΣΗΜΑΝΤΙΚΟ: Η προηγούμενη απάντησή σου κόπηκε επειδή ξεπέρασε το μέγιστο μήκος. "
                "Γράψε ολόκληρη την απάντηση ΠΙΟ ΣΥΝΤΟΜΑ (ιδίως το τεχνικό δελτίο: χωρίς επαναλήψεις), "
                "ώστε να ολοκληρωθεί μέχρι το τέλος.")
    return ("\n\nIMPORTANT: Your previous answer was cut off because it exceeded the maximum length. "
            "Write the whole answer MORE CONCISELY (especially the technical audit: no repetition), "
            "so that it is complete to the end.")


def quality_note(approved_raw: str, lang: str) -> str:
    if lang == "el":
        return (f"\n\nΑΚΟΛΟΥΘΕΙ ΜΙΑ ΗΔΗ ΕΓΚΕΚΡΙΜΕΝΗ ΑΠΑΝΤΗΣΗ:\n{approved_raw}\n\n"
                "ΓΥΡΟΣ ΠΟΙΟΤΗΤΑΣ: Βελτίωσε ΜΟΝΟ το ύφος του καθαρού παραδοτέου -- ροή, φυσικότητα, ζεστασιά, "
                "σαφήνεια, ποικιλία στις διατυπώσεις, ελληνική ορθογραφία και στίξη. ΜΗΝ αλλάξεις: τους τίτλους "
                "των ταλέντων, τους τίτλους των επαγγελματικών τομέων, τα επαγγέλματα, τη δομή, τις επικεφαλίδες, "
                "τη σειρά. Μην προσθέσεις και μην αφαιρέσεις περιεχόμενο, και μη συντομεύσεις. Το τεχνικό δελτίο "
                "επίστρεψέ το ΑΜΕΤΑΒΛΗΤΟ. Επίστρεψε ολόκληρη την απάντηση με την ίδια ακριβώς μορφή/δείκτες.")
    return (f"\n\nHERE IS AN ALREADY APPROVED ANSWER:\n{approved_raw}\n\n"
            "QUALITY ROUND: Improve ONLY the style of the clean client deliverable -- flow, naturalness, warmth, "
            "clarity, varied phrasing, spelling and punctuation. Do NOT change: talent titles, career field titles, "
            "careers, structure, headings, order. Do not add or remove content and do not shorten. Return the "
            "technical audit UNCHANGED. Return the whole answer in exactly the same format/markers.")


# ---------------------------------------------------------------- αποτύπωμα / κατάσταση

def fingerprint(chart, name: str, lang: str) -> str:
    """Αλλάζει αν αλλάξει οτιδήποτε που επηρεάζει το περιεχόμενο: γλώσσα,
    όνομα, δεσμευτική εντολή, πρότυπο, δεδομένα χάρτη."""
    h = hashlib.sha256()
    for part in (lang, name, load_orientation_command(), load_unified_short_example(), build_orientation_source(chart)):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


@dataclass
class AttemptRecord:
    attempt: int
    kind: str          # write | correct | fresh | quality
    ok: bool
    issues: list[str]
    truncated: bool = False


@dataclass
class RunState:
    """Πρόοδος μιας εκτέλεσης -- φυλάσσεται στη συνεδρία, ενημερώνεται επί τόπου."""
    fingerprint: str
    best_raw: Optional[str] = None
    best_issues: Optional[list] = None      # None = δεν υπάρχει ακόμη απόπειρα
    approved: bool = False
    quality_done: bool = False
    fresh_rounds_used: int = 1
    rounds_without_improvement: int = 0
    attempts: int = 0
    history: list = field(default_factory=list)
    finished: bool = False

    @property
    def best_count(self) -> Optional[int]:
        return None if self.best_issues is None else len(self.best_issues)


@dataclass
class PipelineResult:
    ok: bool
    attempts: int
    check: object
    raw: Optional[str]
    client_text: Optional[str]
    audit_text: Optional[str]
    client_docx: Optional[bytes]
    audit_docx: Optional[bytes]
    # approved | stalled | permanent_error | api_failures | cost_limit | max_attempts
    stopped_reason: str
    state: RunState
    cost: CostTracker
    error_key: Optional[str] = None
    error_detail: Optional[str] = None
    quality_applied: bool = False

    @property
    def history(self):
        return self.state.history

    @property
    def resumable(self) -> bool:
        """Αξίζει «▶️ Συνέχεια»: δεν εγκρίθηκε λόγω σφάλματος/ορίου, όχι λόγω λάθους κλειδιού."""
        # Fix (v18.1, κριτική #3): το "max_attempts" ήταν «συνεχίσιμο», αλλά ο
        # μετρητής κλήσεων ήταν ΣΥΝΟΛΙΚΟΣ, οπότε η Συνέχεια έκανε 0 νέες κλήσεις.
        # Τώρα το όριο κλήσεων ισχύει ανά εκτέλεση (βλ. run_calls). Το
        # "cost_limit" ΔΕΝ είναι συνεχίσιμο: το όριο είναι ανά χάρτη, άρα μια
        # Συνέχεια θα σταματούσε αμέσως -- χρειάζεται πρώτα μεγαλύτερο όριο.
        return not self.ok and self.stopped_reason in ("api_failures", "permanent_error", "max_attempts")


# ---------------------------------------------------------------- έλεγχοι

def evaluate_response(chart, name: str, raw: str, lang: str = "el"):
    """Πλήρης έλεγχος μιας απάντησης όπως θα τη δει ο πελάτης:
    .docx -> ξαναδιάβασμα -> validator (+ μορφή Word)."""
    client_text, audit_text = split_orientation_response(raw)
    client_docx = build_orientation_client_docx(service_title(lang), name, client_text)
    audit_docx = build_orientation_audit_docx(AUDIT_TITLE, name, audit_text) if audit_text else None
    check = validate_orientation(
        chart, docx_text(client_docx), {"Όνομα": name},
        presentation_mode=PRESENTATION,
        audit_text=docx_text(audit_docx) if audit_docx else None,
        format_issues=simple_docx_format_issues(client_docx),
        expected_lang=lang,
    )
    return check, client_text, audit_text, client_docx, audit_docx


_WHY_RE = re.compile(r"^\s*(Γιατί\s+μπορεί\s+να\s+ταιριάζει|Why\s+it\s+may\s+fit)", re.IGNORECASE)


def content_signature(client_text: str) -> tuple:
    """Τι ΔΕΝ επιτρέπεται να αλλάξει στον γύρο ποιότητας: τίτλοι ταλέντων,
    τίτλοι τομέων, επαγγέλματα. (Οι επεξηγηματικές παράγραφοι «Γιατί μπορεί
    να ταιριάζει» μπορούν να ξαναδιατυπωθούν.)"""
    talents = frozenset(_career_norm(t) for t in _extract_talent_titles(client_text))
    fields_block = _between_headings(
        client_text,
        r"Επαγγελματικ(?:οί|ούς)\s+Τομ(?:είς|έα)(?:\s+προς\s+Διερεύνηση)?|Career\s+Fields(?:\s+to\s+Explore)?",
        (r"Τελική\s+Σύνθεση", r"Final\s+Synthesis"),
    )
    lines = frozenset(
        _career_norm(re.sub(r"^[\s#*•\-]*(?:\d+[.)])?\s*", "", ln))
        for ln in fields_block.splitlines() if ln.strip() and not _WHY_RE.match(ln)
    )
    return talents, lines


def _word_count(text: str) -> int:
    return len(re.findall(r"\w+", text or ""))


_SECTION_RE = re.compile(
    r"^\W*(Σύντομο\s+προφίλ|Brief\s+Profile|Ταλέντα\s+προς\s+διερεύνηση|Talents\s+to\s+Explore|"
    r"Επαγγελματικ(?:οί|ούς)\s+Τομ(?:είς|έα)|Career\s+Fields|Τελική\s+σύνθεση|Final\s+Synthesis)",
    re.IGNORECASE,
)


def section_shape(client_text: str) -> list[tuple[str, int, int]]:
    """[(ενότητα, παράγραφοι, λέξεις)] για τις 4 ενότητες του παραδοτέου."""
    shape, current, paras, words = [], None, 0, 0
    for line in (client_text or "").splitlines():
        if not line.strip():
            continue
        m = _SECTION_RE.match(line.strip())
        if m:
            if current is not None:
                shape.append((current, paras, words))
            current, paras, words = _career_norm(m.group(1)), 0, 0
            continue
        if current is not None:
            paras += 1
            words += _word_count(line)
    if current is not None:
        shape.append((current, paras, words))
    return shape


# Ο γύρος ποιότητας αλλάζει ΜΟΝΟ ύφος: κάθε ενότητα κρατά τον ίδιο αριθμό
# παραγράφων και περίπου το ίδιο μήκος. Ένα μεγάλο άλμα μήκους σε μία
# ενότητα σημαίνει προσθήκη/αφαίρεση περιεχομένου, όχι ύφος.
QUALITY_SECTION_MIN_RATIO = 0.85
QUALITY_SECTION_MAX_RATIO = 1.20


def quality_is_acceptable(old_client: str, new_client: str, new_check) -> bool:
    """Κρατά τη «βελτίωση» ύφους ΜΟΝΟ αν:
      1. εξακολουθεί να περνά ΟΛΟ τον έλεγχο -- άρα και τον έλεγχο απόλυτων
         διατυπώσεων (v18.2.1): «Είσαι γεννημένος για…» απορρίπτεται·
      2. ίδιοι τίτλοι ταλέντων, τομείς, επαγγέλματα·
      3. συνολικά ≥ 90% των λέξεων·
      4. (v18.2.1, εξωτερική κριτική) σε ΚΑΘΕ ενότητα: ίδιος αριθμός
         παραγράφων και μήκος 85%–120% του αρχικού -- ώστε να μη χωρά νέο
         περιεχόμενο που αλλάζει το νόημα.
    Σημείωση: το νόημα μιας πρότασης δεν ελέγχεται πλήρως μηχανικά· γι' αυτό
    ο γύρος ποιότητας είναι κλειστός εξ ορισμού (AUTO_QUALITY_PASS)."""
    if not (new_check.ok
            and content_signature(new_client) == content_signature(old_client)
            and _word_count(new_client) >= 0.9 * _word_count(old_client)):
        return False
    old_shape, new_shape = section_shape(old_client), section_shape(new_client)
    if [(n, p) for n, p, _ in old_shape] != [(n, p) for n, p, _ in new_shape]:
        return False
    for (_, _, w_old), (_, _, w_new) in zip(old_shape, new_shape):
        if w_old and not (QUALITY_SECTION_MIN_RATIO * w_old <= w_new <= QUALITY_SECTION_MAX_RATIO * w_old):
            return False
    return True


# ---------------------------------------------------------------- εκτέλεση

class _Stop(Exception):
    def __init__(self, reason, key=None, detail=None):
        super().__init__(reason)
        self.reason, self.key, self.detail = reason, key, detail


def _accepts_output_limit(fn) -> bool:
    try:
        params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(p.name == "max_output_tokens" or p.kind is p.VAR_KEYWORD for p in params)


def _normalize(result, model_name) -> GenerationResult:
    if isinstance(result, GenerationResult):
        return result
    return GenerationResult(text=str(result), model=model_name)  # ψεύτικο generate_fn στα tests


def run_pipeline(chart, name: str, lang: str = "el", *,
                 generate_fn: Callable[[str], object],
                 model_name: str = "",
                 settings: Optional[Settings] = None,
                 state: Optional[RunState] = None,
                 cost: Optional[CostTracker] = None,
                 on_progress: Optional[Callable] = None,
                 sleep_fn: Callable[[float], None] = time.sleep) -> PipelineResult:
    """Εκτελεί (ή ΣΥΝΕΧΙΖΕΙ, αν δοθεί state με ίδιο fingerprint) τη διαδικασία.

    generate_fn(prompt) -> GenerationResult (ή str στα tests).
    on_progress(event, **info): events = call, checked, api_retry, new_round,
    truncated, improved, quality.
    `state` και `cost` είναι μεταβλητά αντικείμενα: ο καλών τα κρατά (π.χ. στη
    συνεδρία) και βλέπει την πρόοδο ακόμη κι αν η εκτέλεση διακοπεί.
    """
    settings = settings or Settings.from_env()
    cost = cost if cost is not None else CostTracker()
    fp = fingerprint(chart, name, lang)
    if state is None or state.fingerprint != fp:
        new = RunState(fingerprint=fp)
        if state is not None:  # αλλαγή γλώσσας/οδηγιών: καθαρή αρχή, ίδιο αντικείμενο
            state.__dict__.update(new.__dict__)
        else:
            state = new
    state.finished = False
    notify = on_progress or (lambda event, **info: None)
    base_prompt = build_auto_prompt(chart, name, lang)
    failed_in_row = 0
    run_calls = 0  # όριο ασφαλείας ΑΝΑ ΕΚΤΕΛΕΣΗ (η Συνέχεια ξεκινά με νέο)
    stop: Optional[_Stop] = None
    quality_applied = False
    limit_output = _accepts_output_limit(generate_fn)
    # Προαιρετική ακριβής καταμέτρηση εισόδου (π.χ. Anthropic count_tokens).
    token_counter = getattr(generate_fn, "count_tokens", None)

    def call(prompt: str, kind: str) -> GenerationResult:
        nonlocal failed_in_row, run_calls
        while True:
            if run_calls >= settings.max_attempts:
                raise _Stop("max_attempts")
            counted = None
            if settings.max_cost_usd and token_counter is not None:
                try:
                    counted = token_counter(prompt)
                except Exception:  # noqa: BLE001
                    counted = None
            if cost.would_exceed(model_name, prompt, settings.max_cost_usd, counted):
                raise _Stop("cost_limit")
            budget = cost.output_budget(model_name, prompt, settings.max_cost_usd, counted)
            notify("call", kind=kind, attempt=state.attempts + 1, best_count=state.best_count)
            try:
                raw_result = (generate_fn(prompt, max_output_tokens=budget) if limit_output and budget is not None
                              else generate_fn(prompt))
                res = _normalize(raw_result, model_name)
            except Exception as exc:  # noqa: BLE001
                key = classify_generation_error(exc) if is_api_error(exc) else "other"
                if key in PERMANENT_ERROR_KEYS or key == "other":
                    raise _Stop("permanent_error", key, str(exc))
                failed_in_row += 1
                if failed_in_row >= settings.max_failed_requests:
                    raise _Stop("api_failures", key, str(exc))
                notify("api_retry", n=failed_in_row, key=key)
                sleep_fn(min(60, 5 * 2 ** (failed_in_row - 1)))
                continue
            failed_in_row = 0
            run_calls += 1
            state.attempts += 1
            cost.add(res.model or model_name, res.input_tokens, res.output_tokens, kind=kind, truncated=res.truncated)
            return res

    def next_prompt():
        if state.best_raw is None:
            return base_prompt, "write" if state.attempts == 0 else "fresh"
        return base_prompt + correction_note(state.best_raw, state.best_issues, lang), "correct"

    try:
        # --- κύκλος διόρθωσης μέχρι την έγκριση
        prompt_extra = ""
        while not state.approved:
            prompt, kind = next_prompt()
            res = call(prompt + prompt_extra, kind)
            prompt_extra = ""
            if res.truncated:
                state.history.append(AttemptRecord(state.attempts, kind, False, ["κομμένη απάντηση"], True))
                notify("truncated", attempt=state.attempts)
                prompt_extra = truncation_note(lang)
                state.rounds_without_improvement += 1
            else:
                check = evaluate_response(chart, name, res.text, lang)[0]
                issues = [] if check.ok else list(check.details_lines())
                state.history.append(AttemptRecord(state.attempts, kind, check.ok, issues))
                notify("checked", attempt=state.attempts, count=len(issues))
                if check.ok:
                    state.best_raw, state.best_issues, state.approved = res.text, [], True
                    notify("improved", count=0)
                    break
                if state.best_issues is None or len(issues) < len(state.best_issues):
                    state.best_raw, state.best_issues = res.text, issues
                    state.rounds_without_improvement = 0
                    notify("improved", count=len(issues))
                else:
                    state.rounds_without_improvement += 1
            if state.rounds_without_improvement >= settings.stall_rounds:
                if state.fresh_rounds_used >= settings.fresh_rounds:
                    raise _Stop("stalled")
                # Νέα αρχή: καθαρή γραφή. Η καλύτερη απόπειρα ΚΡΑΤΙΕΤΑΙ ως
                # αποτέλεσμα ασφαλείας -- αν η νέα γραφή βγει καλύτερη, την αντικαθιστά.
                state.fresh_rounds_used += 1
                state.rounds_without_improvement = 0
                notify("new_round", n=state.fresh_rounds_used)
                fresh = call(base_prompt, "fresh")
                if fresh.truncated:
                    state.history.append(AttemptRecord(state.attempts, "fresh", False, ["κομμένη απάντηση"], True))
                    prompt_extra = truncation_note(lang)
                    continue
                check = evaluate_response(chart, name, fresh.text, lang)[0]
                issues = [] if check.ok else list(check.details_lines())
                state.history.append(AttemptRecord(state.attempts, "fresh", check.ok, issues))
                notify("checked", attempt=state.attempts, count=len(issues))
                if check.ok:
                    state.best_raw, state.best_issues, state.approved = fresh.text, [], True
                    break
                # Fix (v18.1, κριτική #4): αν ΟΛΕΣ οι προηγούμενες απαντήσεις
                # ήταν κομμένες, δεν υπάρχει ακόμη «καλύτερη» (best_issues=None)
                # -- πριν εδώ γινόταν len(None) και η εκτέλεση κατέρρεε.
                if state.best_issues is None or len(issues) <= len(state.best_issues):
                    state.best_raw, state.best_issues = fresh.text, issues
                    notify("improved", count=len(issues))

        # --- γύρος ποιότητας (προαιρετικός, μία φορά)
        if state.approved and settings.quality_pass and not state.quality_done:
            notify("quality")
            try:
                res = call(base_prompt + quality_note(state.best_raw, lang), "quality")
                if not res.truncated:
                    old_client = split_orientation_response(state.best_raw)[0]
                    new_check, new_client, *_ = evaluate_response(chart, name, res.text, lang)
                    if quality_is_acceptable(old_client, new_client, new_check):
                        state.best_raw = res.text
                        quality_applied = True
                state.history.append(AttemptRecord(state.attempts, "quality", quality_applied, []))
            except _Stop:
                pass  # το εγκεκριμένο κείμενο μένει ως έχει
            state.quality_done = True
    except _Stop as s:
        stop = s

    state.finished = True
    reason = "approved" if state.approved else (stop.reason if stop else "max_attempts")
    if state.best_raw is None:
        return PipelineResult(False, state.attempts, None, None, None, None, None, None, reason, state, cost,
                              stop.key if stop else None, stop.detail if stop else None)
    check, client_text, audit_text, client_docx, audit_docx = evaluate_response(chart, name, state.best_raw, lang)
    return PipelineResult(
        ok=check.ok, attempts=state.attempts, check=check, raw=state.best_raw,
        client_text=client_text, audit_text=audit_text, client_docx=client_docx, audit_docx=audit_docx,
        stopped_reason="approved" if check.ok else reason, state=state, cost=cost,
        error_key=stop.key if stop else None, error_detail=stop.detail if stop else None,
        quality_applied=quality_applied,
    )


# Συμβατότητα με v17 ονόματα
def run_until_approved(chart, name, lang="el", *, generate_fn, rounds=None, max_attempts=None,
                       stall_limit=None, on_progress=None, sleep_fn=time.sleep):
    s = Settings.from_env()
    if rounds: s.fresh_rounds = rounds
    if max_attempts: s.max_attempts = max_attempts
    if stall_limit: s.stall_rounds = stall_limit
    return run_pipeline(chart, name, lang, generate_fn=generate_fn, settings=s,
                        on_progress=on_progress, sleep_fn=sleep_fn)


def make_generate_fn(provider: str, api_key: str, model: Optional[str] = None) -> Callable[..., GenerationResult]:
    model = model or default_model(provider)

    def _fn(prompt, max_output_tokens=None):
        return generate(api_key, prompt, model=model, provider=provider, max_output_tokens=max_output_tokens)
    _fn.count_tokens = lambda prompt: count_input_tokens(api_key, prompt, model=model, provider=provider)
    return _fn
