import io
import re
from pathlib import Path

import streamlit as st
from docx import Document
from docx.oxml.ns import qn


# Το core/ είναι πλέον υποφάκελος του repo (χρησιμοποιείται και από τα τρία
# entry-point scripts: Home.py, AstroCheck_Analysis.py, AstroCheck_Career.py),
# οπότε η ρίζα του repo είναι ένα επίπεδο πάνω από αυτό το αρχείο, όχι το ίδιο
# επίπεδο όπως παλιά που το reference_loader.py ζούσε δίπλα στο app.py.
REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = REPO_ROOT / "references"
DEFAULT_INSTRUCTIONS = REFERENCE_DIR / "Odigies_v5.docx"
DEFAULT_STYLE = REFERENCE_DIR / "Elena_style_guide_v2.docx"
ROOT_INSTRUCTIONS = REPO_ROOT / "Odigies_v5.docx"
ROOT_STYLE = REPO_ROOT / "Elena_style_guide_v2.docx"
COMMON_ORIENTATION = REFERENCE_DIR / "Desmeftiki_Entoli_Epaggelmatikou_Prosanatolismou_Koini_v11_UNIFIED.docx"
UNIFIED_SHORT_EXAMPLE = REFERENCE_DIR / "Protypo_Syntomis_Ekdosis_ENOPOIIMENO.docx"
_ROOT_COMMON_ORIENTATION = REPO_ROOT / "Desmeftiki_Entoli_Epaggelmatikou_Prosanatolismou_Koini_v11_UNIFIED.docx"
_ROOT_UNIFIED_SHORT_EXAMPLE = REPO_ROOT / "Protypo_Syntomis_Ekdosis_ENOPOIIMENO.docx"


def docx_text(source) -> str:
    """Extract paragraphs and tables from a DOCX path or uploaded bytes."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    document = Document(source)
    blocks = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            line = " | ".join(cell.text.strip() for cell in row.cells)
            if line.strip(" |"):
                blocks.append(line)
    return "\n".join(blocks)


def simple_docx_format_issues(source) -> list[str]:
    """Εντοπίζει χρωματικές επισημάνσεις που απαγορεύονται στο καθαρό Word."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    document = Document(source)
    found = set()
    for paragraph in document.paragraphs:
        ppr = paragraph._p.pPr
        if ppr is not None:
            shd = ppr.find(qn("w:shd"))
            if shd is not None and shd.get(qn("w:fill"), "auto").lower() not in ("auto", "ffffff", "clear", "nil"):
                found.add("σκίαση παραγράφου")
        for run in paragraph.runs:
            if run.font.highlight_color is not None:
                found.add("highlight")
            rpr = run._r.rPr
            if rpr is not None:
                shd = rpr.find(qn("w:shd"))
                if shd is not None and shd.get(qn("w:fill"), "auto").lower() not in ("auto", "ffffff", "clear", "nil"):
                    found.add("χρωματιστό φόντο κειμένου")
            if run.font.color.rgb is not None and str(run.font.color.rgb).upper() not in ("000000", "FFFFFF"):
                found.add("έγχρωμο κείμενο")
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                tcpr = cell._tc.tcPr
                shd = tcpr.find(qn("w:shd")) if tcpr is not None else None
                if shd is not None and shd.get(qn("w:fill"), "auto").lower() not in ("auto", "ffffff", "clear", "nil"):
                    found.add("σκίαση πίνακα")
    return sorted(found)


@st.cache_data(show_spinner=False)
def load_default_references() -> tuple[str, str]:
    # @st.cache_data: το Streamlit ξανατρέχει ολόκληρο το script σε κάθε
    # interaction, οπότε χωρίς caching αυτά τα (συχνά εκτενή) .docx
    # ξαναδιαβάζονταν και ξαναπαρσάρονταν από τον δίσκο σε κάθε κλικ.
    #
    # Accept both repository layouts: a dedicated references/ folder or the
    # two DOCX files beside app.py.  This makes GitHub web uploads simpler.
    instructions = DEFAULT_INSTRUCTIONS if DEFAULT_INSTRUCTIONS.exists() else ROOT_INSTRUCTIONS
    style = DEFAULT_STYLE if DEFAULT_STYLE.exists() else ROOT_STYLE
    if not instructions.exists() or not style.exists():
        # Πριν έγραφε "...v4...", ενώ το πραγματικό αρχείο είναι Odigies_v5.docx
        # (και το app.py το παρουσιάζει ως "Ενσωματωμένες οδηγίες v5.3") --
        # ένα μήνυμα σφάλματος έπρεπε τουλάχιστον να συμφωνεί με το filename.
        raise FileNotFoundError("Λείπουν οι ενσωματωμένες οδηγίες v5 ή το πρότυπο ύφους.")
    return docx_text(instructions), docx_text(style)



def docx_text_in_order(source) -> str:
    """Όπως η docx_text, αλλά διαβάζει παραγράφους ΚΑΙ πίνακες με τη σειρά
    που εμφανίζονται στο έγγραφο. Η docx_text βάζει όλους τους πίνακες στο
    τέλος -- για τη δεσμευτική εντολή αυτό απομάκρυνε τον κατάλογο
    επαγγελματικών τομέων από τον κανόνα στον οποίο ανήκει."""
    if isinstance(source, (bytes, bytearray)):
        source = io.BytesIO(source)
    document = Document(source)
    blocks = []
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            text = "".join(t.text or "" for t in child.iter(qn("w:t"))).strip()
            if text:
                blocks.append(text)
        elif child.tag == qn("w:tbl"):
            for row in child.iter(qn("w:tr")):
                cells = []
                for cell in row.iter(qn("w:tc")):
                    cells.append("".join(t.text or "" for t in cell.iter(qn("w:t"))).strip())
                line = " | ".join(cells)
                if line.strip(" |"):
                    blocks.append(line)
    return "\n".join(blocks)


def load_orientation_command() -> str:
    """Επιστρέφει ΟΛΟΚΛΗΡΗ τη δεσμευτική εντολή (v12 και μετά).

    Η v12 περιέχει αποκλειστικά την «Απλή και πρακτική» έκδοση, οπότε δεν
    υπάρχει πια τίποτα να αφαιρεθεί. Ο παλιός μηχανισμός αποκοπής
    (_filter_orientation_sections / _ANALYTICAL_ONLY_HEADINGS) γράφτηκε για
    την αρίθμηση της v11 και, με τη νέα αρίθμηση της v12, έκοβε λανθασμένα
    τη μορφή των δεικτών, το Παράρτημα κάλυψης, τον Κανόνα 17 και ολόκληρο
    τον κατάλογο τομέων -- αφαιρέθηκε εντελώς."""
    path = COMMON_ORIENTATION if COMMON_ORIENTATION.exists() else _ROOT_COMMON_ORIENTATION
    if not path.exists():
        raise FileNotFoundError(f"Λείπει η κοινή εντολή προσανατολισμού: {COMMON_ORIENTATION.name}")
    return docx_text_in_order(path)


def _load_unified_reference_example() -> str:
    """Εσωτερικό βοηθητικό: διαβάζει το ενιαίο ανώνυμο πρότυπο (βλ.
    load_unified_short_example παρακάτω, που είναι το δημόσιο API)."""
    path = UNIFIED_SHORT_EXAMPLE if UNIFIED_SHORT_EXAMPLE.exists() else _ROOT_UNIFIED_SHORT_EXAMPLE
    if not path.exists():
        raise FileNotFoundError(f"Λείπει το ενοποιημένο πρότυπο σύντομης έκδοσης: {UNIFIED_SHORT_EXAMPLE.name}")
    return docx_text(path)


def load_unified_short_example() -> str:
    """Η υπηρεσία ενοποιήθηκε σε ένα μόνο mode, για κάθε άτομο -- όχι
    ξεχωριστά «παιδί/έφηβος» vs «ενήλικας» -- οπότε χρειαζόταν ΕΝΑ ανώνυμο
    πρότυπο μορφής, όχι δύο. Βάση είναι το Protypo_Syntomis_Ekdosis_ENOPOIIMENO.docx,
    από το οποίο αφαιρέθηκε η ενότητα Κύπρου/ΟΜΠ και η απαγορευμένη
    επικεφαλίδα «Τι χρειάζεται να θυμάσαι» (η υπενθύμιση μεταφέρθηκε στο
    κλείσιμο της Τελικής Σύνθεσης), ώστε να συμφωνεί πλήρως με τον
    Κανόνα 3 της δεσμευτικής εντολής v12."""
    return _load_unified_reference_example()
