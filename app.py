import re
import openai
import streamlit as st
from core.reference_loader import (
    docx_text, load_orientation_command, load_unified_short_example,
    simple_docx_format_issues,
)
from core.prompts import (
    CAREER_CONSISTENCY_RULE_EL, CAREER_CONSISTENCY_RULE_EN,
    build_orientation_source, build_orientation_prompt, split_orientation_response,
)
from core.docx_builder import build_orientation_docx, build_orientation_client_docx, build_orientation_audit_docx
from core.generator import generate_analysis, classify_generation_error
from core.validator import validate_orientation
from core.case_state import reset_case_state, handle_pdf_upload
from core.i18n import TR

# UI text in both languages now lives in core/i18n.py (κριτική #12 -- testable
# without running the Streamlit app). Internal identifiers used by
# core/validator.py and core/prompts.py (presentation, "Ναι"/"Όχι", the
# "Όνομα" key) stay as the original Greek literals no matter which UI
# language is shown -- only what the person reads/labels-for changes.

st.set_page_config(page_title="AstroCheck Career", page_icon="✦", layout="wide")
st.markdown("""<style>
.stApp{background:#f6f2fa}.block-container{max-width:1100px;padding-top:2rem}.hero{background:#3d2350;color:white;border-radius:22px;padding:30px 34px;margin-bottom:18px}.hero h1{margin:0 0 8px;font-family:Georgia;font-size:42px}.hero p{color:#e6d9f2}.ok{padding:14px 16px;background:#e5f2e7;border-left:5px solid #39704c;border-radius:8px}.warn{padding:14px 16px;background:#fff1dd;border-left:5px solid #b7791f;border-radius:8px}</style>""",unsafe_allow_html=True)

_, lang_col = st.columns([6, 1.6])
with lang_col:
    site_language = st.selectbox("Γλώσσα / Language", ["Ελληνικά", "English"], key="site_language")
lang = "el" if site_language == "Ελληνικά" else "en"
t = TR[lang]

st.markdown(f'<div class="hero"><h1>{t["hero_title"]}</h1><p>{t["hero_subtitle"]}</p></div>', unsafe_allow_html=True)

if 'chart' not in st.session_state: st.session_state.chart = None
if 'uploader_gen' not in st.session_state: st.session_state.uploader_gen = 0

with st.sidebar:
    st.header(t["sidebar_header"])
    st.caption(t["sidebar_privacy"])
    if st.button(t["sidebar_reset"], use_container_width=True, help=t["sidebar_reset_help"]):
        st.session_state.chart = None
        st.session_state.uploader_gen += 1
        reset_case_state()
        st.rerun()

chart = st.session_state.chart

if not chart:
    st.subheader(t["step1_title"])
    pdf = st.file_uploader(t["pdf_uploader"], type=['pdf'], key=f"pdf_{st.session_state.uploader_gen}")
    if pdf and st.button(t["read_pdf"], type="primary", use_container_width=True):
        with st.spinner(t["reading_spinner"]):
            ok, new_chart, err = handle_pdf_upload(pdf.getvalue(), pdf.name)
            if ok:
                st.rerun()
            else:
                st.error(t["pdf_error"])
                with st.expander(t["technical_detail"]): st.code(str(err))
    st.stop()

st.success(t["chart_loaded"].format(name=chart.name))

st.subheader(t["step2_title"])
name_override = st.text_input(t["name_label"], value=chart.name, key='name_override')

SERVICE_TITLE = "Ανάδειξη Ταλέντων και Διερεύνηση Επαγγελματικών Επιλογών"
OUTPUT_NAME = "AstroCheck_Anadeixi_Talenton.docx"


def _audit_docx_filename(display_name: str) -> str:
    """π.χ. «Γαβριέλα Δοε» -> «Γαβριέλα_Δοε_Εσωτερικό_Τεχνικό_Δελτίο.docx»
    (κριτική #3, αρχικά· διορθώθηκε ξανά μετά από chat κριτική #7: η παλιά
    εκδοχή έκανε ASCII-only μεταγραφή, που δεν μετέγραφε πραγματικά τα
    ελληνικά -- τα αφαιρούσε, οπότε τα περισσότερα ελληνικά ονόματα
    κατέληγαν όλα στο ίδιο, απρόσωπο "AstroCheck_Esoteriko_Technico_Deltio.docx".
    Τα ονόματα αρχείων .docx δέχονται Unicode κανονικά -- δεν χρειάζεται
    μεταγραφή, μόνο αφαίρεση χαρακτήρων μη έγκυρων σε filename."""
    name = (display_name or "").strip()
    # Χαρακτήρες που απαγορεύονται σε ονόματα αρχείων στα κύρια λειτουργικά
    # συστήματα (Windows είναι το πιο αυστηρό): \ / : * ? " < > | και κενά.
    safe = re.sub(r'[\\/:*?"<>|]+', "", name)
    safe = re.sub(r"\s+", "_", safe).strip("_") or "AstroCheck"
    return f"{safe}_Εσωτερικό_Τεχνικό_Δελτίο.docx"


# Η "Αναλυτική με αστρολογική τεκμηρίωση" παρουσίαση αφαιρέθηκε -- στην πράξη
# χρησιμοποιείται πάντα η "Απλή και πρακτική", οπότε κλειδώνεται σταθερά εδώ.
presentation_label = t["presentation_simple"]
presentation = "Απλή και πρακτική"

st.success(t["success_simple"])
st.caption(t["no_extra_data"])

st.subheader(t["step3_title"])
context = {
    t["ctx_name"]: name_override or chart.name,
    t["ctx_presentation"]: presentation_label,
}

command_text = load_orientation_command()
orientation_source = build_orientation_source(chart)
style_example_text = load_unified_short_example()
orientation_doc = build_orientation_docx(
    name_override or chart.name, SERVICE_TITLE, context, command_text,
    orientation_source, style_example_text=style_example_text,
)
st.download_button(t["download_command"], orientation_doc, file_name=OUTPUT_NAME, type="primary", use_container_width=True)

# The single top language toggle now decides the deliverable's language too
# (instead of asking again in a separate control) — this was the strongest
# idea worth adopting from the reviewed prototype.
language_clause = (
    # Fix (deep review κριτική #7, σοβαρό): η προηγούμενη διατύπωση έλεγε
    # "και, αν ζητηθεί, το εσωτερικό τεχνικό δελτίο... εξ ολοκλήρου στα
    # Ελληνικά/Αγγλικά" -- αντέφασκε με τις reinforcement_instructions
    # παρακάτω, που λένε ρητά ότι οι ΕΠΙΚΕΦΑΛΙΔΕΣ/ετικέτες του τεχνικού
    # δελτίου (ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ, ΤΑΛΕΝΤΟ:, Δείκτης 1/2
    # κ.λπ.) παραμένουν ΠΑΝΤΑ ελληνικές -- ο validator εξαρτάται από αυτές.
    # Τώρα και οι δύο οδηγίες λένε το ίδιο πράγμα.
    "Γράψε το καθαρό παραδοτέο του πελάτη εξ ολοκλήρου στα Ελληνικά. Το εσωτερικό τεχνικό δελτίο μπορεί να έχει επεξηγηματικό κείμενο στα Ελληνικά, αλλά πρέπει να διατηρεί ΑΚΡΙΒΩΣ τις απαιτούμενες ελληνικές μηχαναγνώσιμες επικεφαλίδες/ετικέτες όπως ορίζονται."
    if lang == "el" else
    "Write the clean client deliverable entirely in English. The internal technical audit may use English explanatory text, but it must preserve the required Greek machine-readable headings and labels exactly as specified."
)

st.caption(t["upload_hint_simple"])
if lang == "el":
    paste_message = """Ακολούθησε πιστά τη δεσμευτική εντολή που περιλαμβάνεται στο έγγραφο και χρησιμοποίησε αποκλειστικά τα ελεγμένα τεχνικά δεδομένα που περιέχει. Μην επινοήσεις προσωπικά, επαγγελματικά ή ψυχολογικά στοιχεία.

Η επιλεγμένη παρουσίαση είναι «Απλή και πρακτική». Παράδωσε δύο χωριστά, ολοκληρωμένα αρχεία Word:
1. Το καθαρό παραδοτέο του πελάτη, χωρίς πλανήτες, Οίκους, όψεις, orb ή κατηγορίες βαρύτητας.
2. Το εσωτερικό τεχνικό δελτίο ελέγχου, με την πλήρη τεκμηρίωση που απαιτεί η δεσμευτική εντολή. Το δεύτερο αρχείο δεν παραδίδεται στον πελάτη.

Εφάρμοσε υποχρεωτικά τον Κανόνα 0Γ («Ενοποιημένος κανόνας σύντομης και απλής έκδοσης»): το καθαρό παραδοτέο σε καθημερινή γλώσσα, χωρίς σταθερό αριθμό σελίδων -- η έκταση προσαρμόζεται στον αριθμό των τεκμηριωμένων ταλέντων και επαγγελματικών τομέων -- και χωρίς τους αναλυτικούς πίνακες, το εργασιακό περιβάλλον, τα επόμενα βήματα, το σχέδιο 8–12 εβδομάδων ή τις επαναλαμβανόμενες ενότητες της πλήρους έκδοσης. Το εσωτερικό τεχνικό δελτίο παραμένει αναλυτικό.

Το ανώνυμο πρότυπο σύντομης έκδοσης περιλαμβάνεται ήδη μέσα στο έγγραφο. Χρησιμοποίησέ το αποκλειστικά για τη δομή, το μήκος και την απλή γλώσσα· μην αντιγράψεις από αυτό περιεχόμενο ή συμπεράσματα.

Το καθαρό Word πρέπει να έχει λευκό φόντο και μαύρο κείμενο, όπως το πρότυπο. Μην χρησιμοποιήσεις highlight, χρωματιστό φόντο, σκιάσεις, έγχρωμα πλαίσια ή χρωματιστές λωρίδες. Η έμφαση να γίνεται μόνο με τίτλους, κουκκίδες και περιορισμένη έντονη γραφή.

""" + language_clause + """

Κάνε προσεκτικό αυτοέλεγχο πριν από την παράδοση. Ο πραγματικός validator θα εκτελεστεί στη συνέχεια μέσα στο AstroCheck Career."""
else:
    paste_message = """Follow the binding command included in the document precisely, and use only the checked technical data it contains. Do not invent personal, professional, or psychological details.

The chosen presentation is "Simple & practical". Deliver two separate, complete Word files:
1. The clean client deliverable, without planets, Houses, aspects, orb, or weight categories.
2. The internal technical audit sheet, with the full documentation the binding command requires. This second file is not delivered to the client.

Apply Rule 0Γ ("Unified simple-version rule") mandatorily: the clean deliverable in everyday language, with no fixed page count -- length adapts to the number of well-documented talents and career fields -- and must NOT include the detailed tables, work environment, next steps, the 8–12 week plan, or the repeated sections of the full version. The internal technical sheet stays detailed.

The short-version anonymous template is already included inside the document. Use it only for structure, length, and plain language — do not copy content or conclusions from it.

The clean Word file must have a white background and black text, like the template. Do not use highlighting, colored backgrounds, shading, colored boxes, or colored bars. Emphasis should only come from headings, bullet points, and limited bold text.

""" + language_clause + """

Do a careful self-check before delivering. The real validator will run afterwards inside AstroCheck Career."""

# Ενισχυτικές οδηγίες (ισχύουν πάντα) -- προστέθηκαν μετά από πραγματικά
# περιστατικά όπου το μοντέλο έγραφε το όνομα με λατινικούς χαρακτήρες ή τον
# τίτλο ολόκληρο σε κεφαλαία. Χτίζονται σε ΞΕΧΩΡΙΣΤΗ μεταβλητή (όχι απευθείας
# μέσα στο paste_message) ώστε να περνούν ΚΑΙ στο κουμπί αυτόματης δημιουργίας
# (μέσω build_orientation_prompt), όχι μόνο στο κείμενο αντιγραφής για
# ChatGPT/Claude -- αλλιώς τα δύο μονοπάτια θα έδιναν διαφορετικό αποτέλεσμα.
reinforcement_instructions = (
    # Fix (chat κριτική #3): η παλιά διατύπωση απαιτούσε "ελληνικούς
    # χαρακτήρες" ακόμη και στην ελληνική λειτουργία -- αντίθετο με την
    # απόφαση "ο πελάτης γράφει το όνομά του όπως θέλει" (π.χ. πελάτης που
    # δίνει "Klia" δεν έπρεπε ποτέ να μετατραπεί σε "Κλία"). Η οδηγία τώρα
    # απλώς διατηρεί ό,τι δόθηκε, χωρίς να επιβάλλει αλφάβητο.
    f"""Γράψε το όνομα «{name_override or chart.name}» ακριβώς όπως δόθηκε από τον χρήστη, διατηρώντας τους ίδιους χαρακτήρες, τόνους, ορθογραφία και κενά. Μην το μεταγράψεις, μην το μεταφράσεις και μην το διορθώσεις αυθαίρετα -- ό,τι αλφάβητο κι αν χρησιμοποιεί το όνομα όπως δόθηκε. Ο κύριος τίτλος του εγγράφου να είναι σε κανονική μορφή πεζών/κεφαλαίων (π.χ. «Ανάδειξη Ταλέντων και Διερεύνηση Επαγγελματικών Επιλογών»), όχι ολόκληρος σε κεφαλαία."""
    if lang == "el" else
    # Fix: η παλιά αγγλική εκδοχή έλεγε επίσης "in Greek characters" -- λάθος
    # αντίγραφο του ελληνικού κλάδου, άσχετο και παραπλανητικό για πελάτη
    # που έδωσε το όνομά του στα αγγλικά/λατινικά. Η οδηγία περί
    # μεταγραφής έχει νόημα μόνο όταν το όνομα είναι ήδη ελληνικό.
    #
    # Fix (English mode): προστέθηκαν οι ακριβείς αγγλικές επικεφαλίδες που
    # πλέον αναγνωρίζει ο validator (core/validator.py, common_topics EN
    # patterns) -- χωρίς αυτή τη ρητή λίστα το μοντέλο θα επέλεγε δικές του
    # διατυπώσεις, που ο μηχανικός έλεγχος δεν θα αναγνώριζε ποτέ αξιόπιστα.
    # Το εσωτερικό τεχνικό δελτίο ΠΑΡΑΜΕΝΕΙ ελληνικό ακόμη και εδώ, ακριβώς
    # όπως ήδη επιβάλλει το CAREER_CONSISTENCY_RULE_EN.
    f"""Write the name "{name_override or chart.name}" exactly as given -- do not alter its spelling or spacing. The document's main title should use normal sentence/title case, not ALL CAPS.

The clean client deliverable must use exactly these section headings, in this order, since the automated check looks for them literally: "Brief Profile", "Talents to Explore", "Career Fields to Explore", "Example Careers per Field", "Final Synthesis". Close the Final Synthesis with a short reminder under the heading "What to Remember". Immediately after the last talent card, before the Career Fields section, add a short bold introductory sentence, in English, using exactly this wording: "In summary, the talents to explore are:" followed by a bulleted list of all the talent titles just presented, with no ranking or omission -- the automated check also looks for this exact sentence to verify there are no duplicate talents. The internal technical audit sheet keeps its Greek section headings (ΕΓΚΕΚΡΙΜΕΝΟΙ ΕΠΑΓΓΕΛΜΑΤΙΚΟΙ ΤΟΜΕΙΣ, ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ, ΡΗΤΗ ΤΕΚΜΗΡΙΩΣΗ ΤΟΜΕΑ ΥΓΕΙΑΣ, Παράρτημα, ΤΑΛΕΝΤΟ:, Δείκτης 1/2, Μοναδικός ισχυρός δείκτης) even though the client deliverable is in English -- it is never shown to the client, and the talent titles inside its ΤΑΛΕΝΤΟ: blocks must match the English titles used in the client deliverable exactly, so the automated cross-check can match them."""
)

paste_message += "\n\n" + reinforcement_instructions
paste_message += "\n\n" + (CAREER_CONSISTENCY_RULE_EL if lang == "el" else CAREER_CONSISTENCY_RULE_EN)

with st.expander(t["paste_expander"], expanded=True):
    st.code(paste_message, language=None)

st.divider()
with st.container(border=True):
    st.markdown(t["auto_title"])
    st.caption(t["auto_caption"])
    career_api_key = st.text_input("OpenAI API key", type="password", key="career_api_key", placeholder="sk-...", label_visibility="collapsed")
    if st.button(t["auto_button"], type="primary", disabled=not career_api_key, use_container_width=True):
        with st.spinner(t["auto_spinner"]):
            try:
                auto_prompt = build_orientation_prompt(
                    context, command_text, orientation_source, style_example_text,
                    language_clause=language_clause, need_audit=True,
                    extra_instructions=reinforcement_instructions,
                )
                MAX_AUTO_ATTEMPTS = 3
                current_prompt = auto_prompt
                previous_raw = None
                check = None
                client_text = audit_text = None
                for attempt in range(1, MAX_AUTO_ATTEMPTS + 1):
                    if attempt == 1:
                        spinner_msg = t["auto_attempt_spinner"].format(n=attempt, max=MAX_AUTO_ATTEMPTS)
                    else:
                        spinner_msg = t["auto_correcting_spinner"].format(
                            n=attempt, max=MAX_AUTO_ATTEMPTS, count=len(check.details_lines())
                        )
                    with st.spinner(spinner_msg):
                        raw = generate_analysis(career_api_key, current_prompt)
                    client_text, audit_text = split_orientation_response(raw)
                    orientation_personal = {"Όνομα": name_override or chart.name}
                    check = validate_orientation(
                        chart, client_text, orientation_personal,
                        presentation_mode=presentation, audit_text=audit_text,
                        format_issues=[],
                    )
                    if check.ok or attempt == MAX_AUTO_ATTEMPTS:
                        break
                    # Ο επόμενος γύρος δεν ξαναγράφει τα πάντα από την αρχή --
                    # στέλνει πίσω στο μοντέλο ό,τι μόλις έγραψε, μαζί με τη
                    # συγκεκριμένη λίστα προβλημάτων που εντόπισε ο πραγματικός
                    # validator, και του ζητά να διορθώσει ΜΟΝΟ αυτά. Αυτό είναι
                    # που πλησιάζει τον στόχο "χωρίς ανθρώπινη παρέμβαση".
                    issues_list = "\n".join(f"- {line}" for line in check.details_lines())
                    correction_note = (
                        f"\n\nΗ ΠΡΟΗΓΟΥΜΕΝΗ ΣΟΥ ΑΠΑΝΤΗΣΗ (προς διόρθωση):\n{raw}\n\n"
                        f"Ο ΠΡΑΓΜΑΤΙΚΟΣ ΜΗΧΑΝΙΚΟΣ ΕΛΕΓΧΟΣ ΒΡΗΚΕ ΤΑ ΕΞΗΣ ΠΡΟΒΛΗΜΑΤΑ:\n{issues_list}\n\n"
                        "Ξαναγράψε ολόκληρη την απάντηση (με την ίδια ακριβώς μορφή/δείκτες όπως πριν), "
                        "διορθώνοντας ΜΟΝΟ αυτά τα συγκεκριμένα προβλήματα. Μην αλλάξεις τίποτα άλλο που "
                        "ήδη ήταν σωστό."
                        if lang == "el" else
                        f"\n\nYOUR PREVIOUS ANSWER (to be corrected):\n{raw}\n\n"
                        f"THE REAL ENGINEERING CHECK FOUND THESE ISSUES:\n{issues_list}\n\n"
                        "Rewrite the entire answer (using the exact same format/markers as before), "
                        "fixing ONLY these specific issues. Do not change anything else that was already correct."
                    )
                    current_prompt = auto_prompt + correction_note

                st.session_state.orientation_validation = check
                st.session_state.orientation_docx_bytes = build_orientation_client_docx(SERVICE_TITLE, name_override or chart.name, client_text)
                st.session_state.orientation_docx_name = OUTPUT_NAME
                # Fix (κριτική #3): πριν ήταν audit_text.encode("utf-8") -- ωμό
                # κείμενο σε .docx επέκταση, όχι πραγματικό Word, και χωρίς
                # κουμπί λήψης πουθενά. Τώρα φτιάχνεται πραγματικό .docx με
                # προσωποποιημένο όνομα αρχείου.
                st.session_state.orientation_audit_docx_bytes = (
                    build_orientation_audit_docx(
                        "Εσωτερικό Τεχνικό Δελτίο Ελέγχου", name_override or chart.name, audit_text,
                    ) if audit_text else None
                )
                st.session_state.orientation_audit_docx_name = _audit_docx_filename(name_override or chart.name)
                if check.ok:
                    if attempt == 1:
                        st.success(t["auto_ok"])
                    else:
                        st.success(t["auto_ok_after_retries"].format(n=attempt))
                    if check.warnings:
                        with st.expander(t["details_expander"]):
                            for line in check.warnings: st.write("•", line)
                else:
                    st.error(t["auto_exhausted"].format(max=MAX_AUTO_ATTEMPTS))
                # Fix (κριτική #3): πριν δεν υπήρχε ΚΑΘΟΛΟΥ κουμπί λήψης για
                # το εσωτερικό τεχνικό δελτίο στο μονοπάτι αυτόματης
                # δημιουργίας -- το περιεχόμενο χανόταν σιωπηλά.
                if st.session_state.orientation_audit_docx_bytes:
                    st.download_button(
                        t["download_audit_docx"],
                        st.session_state.orientation_audit_docx_bytes,
                        file_name=st.session_state.orientation_audit_docx_name,
                        use_container_width=True,
                    )
            except openai.APIError as e:
                # Fix (πρόβλημα #11 από τη σταθερή λίστα ελέγχου): πριν όλα τα
                # σφάλματα API/δικτύου έδειχναν το ΙΔΙΟ γενικό μήνυμα
                # "Η αυτόματη δημιουργία απέτυχε" -- αδιακρίτως από αποτυχία
                # validation (που ήδη είχε το δικό της, σαφές auto_exhausted
                # μήνυμα). Η ταξινόμηση γίνεται στο core/generator.py
                # (classify_generation_error), ώστε να ελέγχεται με tests.
                key = classify_generation_error(e)
                st.error(t.get(f"auto_error_{key}", t["auto_error"]))
                if key == "other":
                    with st.expander(t["technical_detail"]): st.code(str(e))
            except Exception as e:
                st.error(t["auto_error"])
                with st.expander(t["technical_detail"]): st.code(str(e))
    st.caption(t["auto_need_audit_caption"])

st.divider()
st.subheader(t["step4_title"])
orientation_result = st.file_uploader(t["result_uploader"], type=['docx'], key=f"orientation_result_{st.session_state.uploader_gen}")
orientation_audit = st.file_uploader(t["audit_uploader"], type=['docx'], key=f"orientation_audit_{st.session_state.uploader_gen}")
ready_to_check = bool(orientation_result) and bool(orientation_audit)
if st.button(t["check_button"], disabled=not ready_to_check, use_container_width=True):
    result_bytes = orientation_result.getvalue()
    result_text = docx_text(result_bytes)
    result_format_issues = simple_docx_format_issues(result_bytes)
    audit_bytes = orientation_audit.getvalue() if orientation_audit else None
    audit_text = docx_text(audit_bytes) if audit_bytes else None
    orientation_personal = {"Όνομα": name_override or chart.name}
    check = validate_orientation(
        chart, result_text, orientation_personal,
        presentation_mode=presentation, audit_text=audit_text,
        format_issues=result_format_issues,
    )
    st.session_state.orientation_validation = check
    st.session_state.orientation_docx_bytes = result_bytes
    st.session_state.orientation_docx_name = orientation_result.name
    st.session_state.orientation_audit_docx_bytes = audit_bytes
check = st.session_state.get('orientation_validation')
if check:
    if check.ok:
        st.markdown(f'<div class="ok">{check.summary()}</div>', unsafe_allow_html=True)
        # Fix (chat κριτική #4): πριν οι λεπτομέρειες (άρα και τα μη
        # δεσμευτικά warnings, π.χ. έκταση παραγράφου ταλέντου) φαίνονταν
        # ΜΟΝΟ σε περίπτωση απόρριψης -- ένα εγκεκριμένο παραδοτέο με
        # warnings τα έκρυβε εντελώς.
        if check.warnings:
            with st.expander(t["details_expander"]):
                for line in check.warnings: st.write("•", line)
        st.download_button(t["download_checked"], st.session_state.orientation_docx_bytes, file_name=st.session_state.orientation_docx_name, use_container_width=True)
    else:
        st.markdown(f'<div class="warn">⚠ {check.summary()}</div>', unsafe_allow_html=True)
        with st.expander(t["details_expander"], expanded=True):
            for line in check.details_lines(): st.write("•", line)
