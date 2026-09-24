from .astrology import movement_text

def fmt(p):
    rx = " ανάδρομος" if p.retrograde else ""
    return f"{p.sign} {p.degree}°{p.minute:02d}′{p.second:02d}″{rx}"


ORIENTATION_RESPONSE_DELIMITER = "===TECHNICAL_AUDIT==="
ORIENTATION_CLIENT_MARKER = "===CLIENT_DELIVERABLE==="


def build_orientation_prompt(context, command_text, orientation_source,
                              style_example_text="", language_clause="",
                              need_audit=False, extra_instructions=""):
    """Καθαρό text prompt για απευθείας κλήση στο μοντέλο (χωρίς να χρειάζεται
    το ενδιάμεσο βήμα «κατέβασε Word -> επικόλλησε σε ChatGPT/Claude -> ανέβασε
    το αποτέλεσμα»). Χρησιμοποιεί ακριβώς τα ίδια υλικά με το
    docx_builder.build_orientation_docx (δεσμευτική εντολή, δηλωμένο πλαίσιο,
    ελεγμένα δεδομένα, ανώνυμο πρότυπο ύφους) -- μόνο η μορφή αλλάζει, από
    .docx σε ένα ενιαίο string κατάλληλο για το generator.generate_analysis.
    """
    context_lines = "\n".join(f"- {k}: {v}" for k, v in context.items() if str(v).strip())
    parts = [
        "ΔΕΣΜΕΥΤΙΚΗ ΑΡΧΗ\nΠρόκειται για χωριστή προαιρετική υπηρεσία. Χρησιμοποίησε αποκλειστικά την παρακάτω δεσμευτική εντολή, το δηλωμένο πλαίσιο και την ήδη ελεγμένη τεχνική ανάλυση του ίδιου ατόμου. Μην χρησιμοποιήσεις μνήμη ή προηγούμενες συνομιλίες και μην επινοήσεις προσωπικά δεδομένα.",
        f"ΔΗΛΩΜΕΝΟ ΠΛΑΙΣΙΟ ΥΠΗΡΕΣΙΑΣ\n{context_lines}",
        # Ο κανόνας συνέπειας και ο φραγμός υγείας ζουν πλέον μέσα στη
        # δεσμευτική εντολή (v12, Κανόνες 14-15) -- δεν ξαναστέλνονται εδώ.
        f"ΔΕΣΜΕΥΤΙΚΗ ΕΝΤΟΛΗ ΕΠΑΓΓΕΛΜΑΤΙΚΟΥ ΠΡΟΣΑΝΑΤΟΛΙΣΜΟΥ\n{command_text}",
    ]
    if style_example_text.strip():
        parts.append(
            "ΑΝΩΝΥΜΟ ΠΡΟΤΥΠΟ ΣΥΝΤΟΜΗΣ ΕΚΔΟΣΗΣ — ΜΟΝΟ ΓΙΑ ΔΟΜΗ ΚΑΙ ΥΦΟΣ\n"
            "Χρησιμοποίησε το ακόλουθο υλικό μόνο ως πρότυπο μήκους, διάταξης και "
            "απλής γλώσσας. Απαγορεύεται να αντιγράψεις από αυτό ταλέντα, "
            "επαγγελματικούς τομείς, επαγγέλματα ή συμπεράσματα. Το περιεχόμενο "
            "για το νέο πρόσωπο πρέπει να προκύπτει αποκλειστικά από τα ελεγμένα "
            "δεδομένα που ακολουθούν.\n" + style_example_text
        )
    parts.append(f"ΕΛΕΓΜΕΝΗ ΤΕΧΝΙΚΗ ΑΝΑΛΥΣΗ — ΜΟΝΑΔΙΚΗ ΑΣΤΡΟΛΟΓΙΚΗ ΠΗΓΗ\n{orientation_source}")
    if language_clause.strip():
        parts.append(language_clause)
    if extra_instructions.strip():
        parts.append(extra_instructions)
    if need_audit:
        parts.append(
            "ΜΟΡΦΗ ΑΠΑΝΤΗΣΗΣ (ΥΠΟΧΡΕΩΤΙΚΗ)\n"
            "Επίστρεψε ΑΚΡΙΒΩΣ δύο ενότητες, με αυτή τη σειρά, καθεμία σε δική "
            "της γραμμή με τον ακριβή τίτλο:\n"
            f"{ORIENTATION_CLIENT_MARKER}\n"
            "(εδώ το καθαρό παραδοτέο του πελάτη, σύμφωνα με τους παραπάνω κανόνες)\n"
            f"{ORIENTATION_RESPONSE_DELIMITER}\n"
            "(εδώ το πλήρες εσωτερικό τεχνικό δελτίο ελέγχου, με όλη την τεκμηρίωση "
            "που απαιτεί η δεσμευτική εντολή)\n"
            "Μην προσθέσεις κανένα άλλο κείμενο πριν από τον πρώτο τίτλο ή μετά "
            "το τέλος του τεχνικού δελτίου."
        )
    return "\n\n".join(parts)


def split_orientation_response(raw_text):
    """Σπάει την απάντηση του μοντέλου σε (καθαρό_κείμενο_πελάτη, τεχνικό_δελτίο).

    Το δεύτερο στοιχείο είναι None όταν δεν ζητήθηκε τεχνικό δελτίο (αναλυτική
    παρουσίαση) ή όταν το μοντέλο δεν ακολούθησε τη ζητούμενη μορφή -- σε αυτή
    την περίπτωση επιστρέφεται όλο το κείμενο ως παραδοτέο πελάτη, ώστε ο
    validator να αποφασίσει (και πιθανόν να απορρίψει) αντί να χαθεί σιωπηλά
    περιεχόμενο.
    """
    text = raw_text.strip()
    if ORIENTATION_RESPONSE_DELIMITER in text:
        client_part, _, audit_part = text.partition(ORIENTATION_RESPONSE_DELIMITER)
        client_part = client_part.replace(ORIENTATION_CLIENT_MARKER, "").strip()
        return client_part, audit_part.strip()
    return text.replace(ORIENTATION_CLIENT_MARKER, "").strip(), None



def build_orientation_source(chart):
    """Καθαρή τεχνική πηγή για την προαιρετική υπηρεσία προσανατολισμού.

    Δεν περνά την αφηγηματική ανάλυση των 12 Οίκων, η οποία μπορεί να
    περιέχει προσωπικό πλαίσιο. Έτσι το μοντέλο βλέπει μόνο τα ελεγμένα
    αστρολογικά δεδομένα που χρειάζεται η ξεχωριστή υπηρεσία.
    """
    points = "\n".join(
        f"- {p.name}: {fmt(p)} | Οίκος {p.house or '—'} | {movement_text(p)}"
        for p in chart.points
    )
    cusps = "\n".join(
        f"- {number}ος Οίκος: {fmt(c)}"
        for number, c in enumerate(chart.cusps, start=1)
    )
    aspects = "\n".join(
        f"- {a.first}–{a.second} | {a.aspect} | orb {a.orb_text} | {a.weight} | πηγή: {a.source}"
        for a in chart.aspects
    ) or "- Δεν αναγνωρίστηκαν όψεις. Σταμάτησε και ζήτησε τεχνικό έλεγχο."
    return f"""ΕΛΕΓΜΕΝΑ ΑΣΤΡΟΛΟΓΙΚΑ ΔΕΔΟΜΕΝΑ

ΠΛΑΝΗΤΕΣ ΚΑΙ ΣΗΜΕΙΑ
{points}

ΑΚΜΕΣ ΟΙΚΩΝ
{cusps}

ΠΑΡΑΡΤΗΜΑ ΕΠΙΒΕΒΑΙΩΜΕΝΩΝ ΟΨΕΩΝ — ΜΟΝΑΔΙΚΗ ΠΗΓΗ ORB ΚΑΙ ΒΑΡΥΤΗΤΑΣ
{aspects}
"""
