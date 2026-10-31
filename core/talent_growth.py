"""
talent_growth.py
================
v20.18 -- «Πώς φαίνεται να αναπτύσσεται» κάθε ταλέντο, στη συνοπτική λίστα.

Δίπλα σε κάθε τίτλο της λίστας «Συνοπτικά, τα ταλέντα προς διερεύνηση είναι:»
μπαίνει, μετά από παύλα, μία σύντομη φράση:

    • Οργάνωση, συνέπεια και επιμονή — έχει εύκολη βάση και δυναμώνει με την εξάσκηση

Η φράση ΥΠΟΛΟΓΙΖΕΤΑΙ ΕΔΩ, σε Python, από τους δείκτες του τεχνικού δελτίου
-- δεν τη γράφει το μοντέλο. Ο κανόνας ακολουθεί τον Κανόνα 7 της δεσμευτικής
εντολής (τρίγωνα: «φυσικά ή εύκολα»· εξάγωνα: «μέσα από ευκαιρίες»· τετράγωνα
και αντιθέσεις: «μέσα από προσπάθεια και εμπειρία»):

  * Μετρούν μόνο οι ΚΥΡΙΟΙ δείκτες όψης: πραγματική βαρύτητα (από τον χάρτη,
    όχι όπως δηλώθηκε) «Στενή/ισχυρή» ή «Κανονική». Οι πλατιές όψεις είναι
    υποστηρικτικές και δεν μετρούν. Οι δείκτες Θέσης δεν έχουν τύπο όψης.
  * Σύνοδος και χιαστί 150° είναι ουδέτερες: δεν αλλάζουν τη φράση.
  * Αρμονικές (τρίγωνο/εξάγωνο) ΚΑΙ δύσκολες (τετράγωνο/αντίθεση) -> «μικτό».
  * Μόνο δύσκολες -> «εξάσκηση».
  * Μόνο αρμονικές: με τουλάχιστον ένα εξάγωνο -> «ευκαιρία»· μόνο τρίγωνα -> «αβίαστο».
  * Καμία κύρια αρμονική/δύσκολη όψη -> «ανοιχτό».

Η φράση μπαίνει στο Word ΜΕΤΑ τον έλεγχο του validator και μόνο σε εγκεκριμένο
κείμενο: ο validator συγκρίνει τους τίτλους της λίστας ακριβώς με τους τίτλους
των ταλέντων, οπότε δεν πρέπει να βλέπει τη φράση. Αν κάτι δεν ταιριάζει (λείπει
το δελτίο, δεν βρεθεί η λίστα), το Word επιστρέφεται ΑΜΕΤΑΒΛΗΤΟ.

Ο Κανόνας 3 απαγορεύει πίνακες στο καθαρό παραδοτέο -- γι' αυτό η φράση μπαίνει
στην ίδια κουκκίδα, όχι σε πίνακα.
"""

from __future__ import annotations

import io
import re
from copy import deepcopy

from docx import Document
from docx.shared import Pt
from docx.text.paragraph import Paragraph

from .validator import (
    _exact_aspect_type,
    _indicator_kind,
    _indicator_lines,
    _norm_title,
    _parse_indicator_fields,
    _real_aspect_weight,
    _talent_blocks,
)

EASY, OPPORTUNITY, PRACTICE, MIXED, OPEN = "easy", "opportunity", "practice", "mixed", "open"

PRIMARY_WEIGHTS = ("Στενή/ισχυρή", "Κανονική")
HARMONIOUS = ("Τρίγωνο", "Εξάγωνο")
TENSE = ("Τετράγωνο", "Αντίθεση")

PHRASES = {
    "el": {
        EASY: "φαίνεται να βγαίνει αβίαστα",
        OPPORTUNITY: "ανθίζει όταν βρει την κατάλληλη ευκαιρία",
        PRACTICE: "χτίζεται με τον χρόνο και την εμπειρία",
        MIXED: "έχει εύκολη βάση και δυναμώνει με την εξάσκηση",
        OPEN: "θα φανεί στην πράξη",
    },
    "en": {
        EASY: "seems to come naturally",
        OPPORTUNITY: "blossoms when it finds the right opportunity",
        PRACTICE: "builds with time and experience",
        MIXED: "has a natural base and grows stronger with practice",
        OPEN: "will show itself in practice",
    },
}

NOTE = {
    "el": "Όλα αυτά είναι δυνατότητες. Το πόσο θα αναπτυχθεί το καθένα εξαρτάται από τις επιλογές σου.",
    "en": "All of these are possibilities. How far each one develops depends on your choices.",
}

SEPARATOR = " — "

_SUMMARY_RE = re.compile(
    r"^\s*(?:Συνοπτικά,\s*τα\s+ταλέντα\s+προς\s+διερεύνηση\s+είναι|"
    r"In\s+summary,\s*the\s+talents\s+to\s+explore\s+are)\s*:?\s*$",
    re.IGNORECASE,
)
_BULLET_PREFIX_RE = re.compile(r"^[\s•\-–*·]+")


def classify_block(block: str, chart) -> str:
    """Η κατηγορία ενός μπλοκ «ΤΑΛΕΝΤΟ:» του δελτίου (βλ. κανόνα στην κορυφή)."""
    types = set()
    for indicator in _indicator_lines(block):
        if _indicator_kind(indicator) != "οψη":
            continue
        if _real_aspect_weight(indicator, chart) not in PRIMARY_WEIGHTS:
            continue
        aspect = _exact_aspect_type(_parse_indicator_fields(indicator).get("οψη", ""))
        if aspect:
            types.add(aspect)
    harmonious = types & set(HARMONIOUS)
    tense = types & set(TENSE)
    if harmonious and tense:
        return MIXED
    if tense:
        return PRACTICE
    if harmonious:
        return OPPORTUNITY if "Εξάγωνο" in harmonious else EASY
    return OPEN


def talent_growth(audit_text: str | None, chart) -> dict[str, str]:
    """{κανονικοποιημένος τίτλος ταλέντου: κατηγορία} από το τεχνικό δελτίο."""
    if not audit_text or chart is None:
        return {}
    return {title: classify_block(block, chart) for title, block in _talent_blocks(audit_text).items()}


def _plain(text: str) -> str:
    return _BULLET_PREFIX_RE.sub("", text.replace("**", "")).strip()


def annotate_client_docx(docx_bytes: bytes, audit_text: str | None, chart, lang: str = "el") -> bytes:
    """Προσθέτει τη φράση δίπλα σε κάθε τίτλο της συνοπτικής λίστας ταλέντων και
    μία πρόταση για τις επιλογές από κάτω. Επιστρέφει το Word αμετάβλητο αν δεν
    βρεθούν δελτίο, λίστα ή αντιστοιχίες."""
    growth = talent_growth(audit_text, chart)
    if not growth or not docx_bytes:
        return docx_bytes
    phrases = PHRASES.get(lang, PHRASES["el"])
    document = Document(io.BytesIO(docx_bytes))
    paragraphs = document.paragraphs
    start = next((i for i, p in enumerate(paragraphs) if _SUMMARY_RE.match(_plain(p.text))), None)
    if start is None:
        return docx_bytes

    annotated = []
    for paragraph in paragraphs[start + 1:]:
        text = _plain(paragraph.text)
        if not text:
            if annotated:
                break
            continue
        key = growth.get(_norm_title(text))
        if key is None:
            break  # τέλος της λίστας (επόμενη επικεφαλίδα ή παράγραφος)
        run = paragraph.add_run(SEPARATOR + phrases[key])
        run.italic = True
        annotated.append(paragraph)
    if not annotated:
        return docx_bytes

    # Η πρόταση για τις επιλογές, αμέσως μετά την τελευταία κουκκίδα, ως απλή
    # παράγραφος (ίδιο στυλ με το σώμα του κειμένου, χωρίς κουκκίδα).
    last = annotated[-1]
    note = deepcopy(last._p)
    for child in list(note):
        note.remove(child)
    last._p.addnext(note)
    note_paragraph = Paragraph(note, last._parent)
    note_paragraph.style = document.styles["Normal"]
    note_paragraph.paragraph_format.space_before = Pt(4)
    note_run = note_paragraph.add_run(NOTE.get(lang, NOTE["el"]))
    note_run.italic = True

    out = io.BytesIO()
    document.save(out)
    return out.getvalue()
