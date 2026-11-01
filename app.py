"""
AstroCheck Career -- v18: σελίδα πελάτη, πλήρως αυτόματη.

v20: ο πελάτης δίνει ημερομηνία, ώρα, χώρα και τόπο γέννησης· ο χάρτης
υπολογίζεται μέσα στην εφαρμογή (core/ephemeris.py). Το Astrodienst PDF
μένει μόνο για τη Διαχείριση και τη χειροκίνητη διαδικασία.

ΠΕΛΑΤΗΣ: ανεβάζει το Astrodienst PDF, πατά ΕΝΑ κουμπί, βλέπει βήματα 1-4
με εκτίμηση χρόνου, κατεβάζει το εγκεκριμένο έντυπο. Αν η διαδικασία
διακοπεί από προσωρινό σφάλμα, «▶️ Συνέχεια από εκεί που σταμάτησε».
Δεν βλέπει ποτέ πρόχειρα, προβλήματα ελέγχου, τεχνικό δελτίο ή κόστος.

ΔΙΑΧΕΙΡΙΣΤΡΙΑ (κωδικός ADMIN_PASSWORD): επιπλέον λεπτομέρειες προόδου,
μετρητής κόστους σε € και $, τεχνικό δελτίο, προσχέδιο, επιλογή μοντέλου,
χειροκίνητη διαδικασία.

Η πρόοδος και ο μετρητής κρατιούνται ΜΟΝΟ στη συνεδρία (όχι στον
διακομιστή), ανά PDF: ξαναδιάβασμα του ίδιου PDF δεν μηδενίζει τον μετρητή.
Το «Νέα αναφορά» καθαρίζει τα πάντα.
"""
import hashlib
import hmac
import html
import re
import os
from datetime import date
from datetime import time as dtime
from zoneinfo import available_timezones

import streamlit as st

from core.case_state import reset_case_state
from core.costs import CostTracker
from core.generator import API_KEY_NAMES, DEFAULT_PROVIDER, PROVIDER_LABELS, PROVIDERS, default_model
from core.birth_input import birth_case_key, chart_from_birth
from core.birthtime import to_ut
from core.i18n import TR
from core.places import DROPDOWN_MAX_PLACES, countries, country_label, places_in_country, search_countries, search_places
from core.parser import parse_astrodienst_pdf
from core.docx_builder import build_orientation_docx
from core.pipeline import (
    CLIENT_OUTPUT_NAME, PRESENTATION, SERVICE_TITLE, build_context, language_clause, make_generate_fn,
    reinforcement_instructions,
)
from core.prompts import build_orientation_source
from core.teaser import pick_teaser, teaser_instruction
from core.talent_report import build_engine_report
from core.talent_growth import annotate_client_docx
from core.talent_texts import approval_status, fully_approved
from core.reference_loader import (
    docx_text, load_orientation_command, load_unified_short_example, simple_docx_format_issues,
)
from core.validator import validate_orientation

# v22.25: ΔΥΟ σελίδες από τον ίδιο κώδικα. Το client.py τρέχει αυτό το αρχείο με CLIENT_PAGE=True:
# καθαρή σελίδα πελάτη, χωρίς Διαχείριση και χωρίς πλαϊνή στήλη. Το app.py μόνο του = σελίδα Διαχείρισης.
CLIENT_PAGE = bool(globals().get("CLIENT_PAGE", False))

st.set_page_config(page_title="AstroCheck Career", page_icon="✦", layout="wide",
                   initial_sidebar_state="collapsed" if CLIENT_PAGE else "auto")
# v22.25: χωρίς τα κουμπάκια «− +» στα αριθμητικά πεδία (ημέρα, έτος, ώρα, λεπτά) -- ο χρήστης απλώς γράφει.
st.markdown("""<style>[data-testid="stNumberInputStepUp"],[data-testid="stNumberInputStepDown"]{display:none}
.small-note{color:#7a6d86;font-size:.82rem;text-align:center;max-width:760px;margin:0 auto 10px;line-height:1.5}</style>""",
            unsafe_allow_html=True)
if CLIENT_PAGE:   # σελίδα πελάτη: καθόλου πλαϊνή στήλη
    st.markdown("""<style>[data-testid="stSidebar"],[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"]{display:none!important}</style>""", unsafe_allow_html=True)
st.markdown("""<style>
.stApp{background:#f6f2fa}.block-container{max-width:1100px;padding-top:4.5rem}.hero{background:#3d2350;color:white;border-radius:22px;padding:30px 34px;margin-bottom:18px}.hero h1{margin:0 0 8px;font-family:Georgia;font-size:42px}.hero p{color:#e6d9f2}.mission{color:#5b4a6b;font-style:italic;text-align:center;max-width:760px;margin:0 auto 24px;line-height:1.6}.hero .motto{font-family:Georgia;font-style:italic;font-size:1.05rem;color:#f3e9fb;margin:6px 0 0}.ok{padding:14px 16px;background:#e5f2e7;border-left:5px solid #39704c;border-radius:8px}.warn{padding:14px 16px;background:#fff1dd;border-left:5px solid #b7791f;border-radius:8px}.teaser{padding:18px 20px;background:#fff;border:2px solid #b9a3cf;border-radius:14px;margin:14px 0}.teaser-head{color:#3d2350;font-weight:600;margin-bottom:6px}.teaser-title{font-family:Georgia;font-size:1.35rem;color:#3d2350;margin-bottom:8px}.teaser-more{margin-top:12px;color:#5b4a6b;font-style:italic}.stay{padding:16px 18px;background:#fde8e8;border:2px solid #b42318;border-radius:10px;font-weight:600;font-size:1.05rem;color:#7a1a12}</style>""", unsafe_allow_html=True)


def _secret(name):
    try:
        value = st.secrets.get(name)
    except Exception:  # δεν υπάρχει secrets.toml
        value = None
    return value or os.environ.get(name)


def _is_local_request() -> bool:
    """True μόνο όταν η σελίδα ανοίγει από τον ίδιο υπολογιστή (localhost)."""
    try:
        host = (st.context.headers.get("Host") or "").split(":")[0].strip().lower()
    except Exception:  # noqa: BLE001 -- άγνωστο περιβάλλον: ασφαλής επιλογή
        return False
    return host in ("localhost", "127.0.0.1", "::1", "[::1]")


# Ρυθμίσεις από τα Secrets -> περιβάλλον, ώστε να τις βλέπει το core/.
for _name in ("ANTHROPIC_MODEL", "OPENAI_MODEL", "AUTO_MAX_ATTEMPTS", "AUTO_FRESH_ROUNDS", "AUTO_STALL_ROUNDS",
              "AUTO_MAX_FAILED_REQUESTS", "AUTO_MAX_COST_USD", "AUTO_QUALITY_PASS", "AUTO_ETA_MINUTES",
              "MODEL_PRICES", "EUR_PER_USD", "POLISH_MODEL"):
    _v = _secret(_name)
    if _v:
        os.environ[_name] = str(_v)

_, lang_col = st.columns([6, 1.6])
with lang_col:
    site_language = st.selectbox("Γλώσσα / Language", ["Ελληνικά", "English"], key="site_language")
lang = "el" if site_language == "Ελληνικά" else "en"
t = TR[lang]

st.markdown(f'<div class="hero"><h1>{t["hero_title"]}</h1><p>{t["hero_subtitle"]}</p>'
            f'<p class="motto">{t["hero_motto"]}</p></div>', unsafe_allow_html=True)

ss = st.session_state
ss.setdefault("chart", None)
ss.setdefault("uploader_gen", 0)
ss.setdefault("cases", {})          # sha256(PDF) -> {"chart", "cost", "state", "name"}
ss.setdefault("current_case", None)

configured = {p: _secret(API_KEY_NAMES[p]) for p in PROVIDERS}
preferred = (_secret("AI_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
available = [p for p in PROVIDERS if configured[p]]
provider = preferred if preferred in available else (available[0] if available else DEFAULT_PROVIDER)
api_key = configured.get(provider)

# v22: REPORT_MODE (Secret):
#   "engine" (προεπιλογή) = εκδοχή Α: μηχανή ταλέντων + έτοιμα κείμενα, χωρίς AI, κόστος 0
#   "hybrid"              = εκδοχή Β: η Α «δεμένη» σε προσωπικό κείμενο από φτηνό AI· αν το AI
#                           αποτύχει ή δεν περάσει τον έλεγχο, ο πελάτης παίρνει αυτόματα την Α
#   ("ai" -- η παλιά αναφορά μόνο με AI -- αφαιρέθηκε στο v22.17· αντιμετωπίζεται ως "hybrid")
# Το μοντέλο της Β: POLISH_MODEL (Secret)· αλλιώς Claude Sonnet / το προεπιλεγμένο OpenAI.
REPORT_MODE = str(_secret("REPORT_MODE") or "engine").strip().lower()
if REPORT_MODE not in ("engine", "hybrid"):
    REPORT_MODE = "hybrid" if REPORT_MODE == "ai" else "engine"
# v22.2: REQUIRE_APPROVAL (Secret, προεπιλογή "1"): όσο οι πίνακες/τα κείμενα της μηχανής είναι
# πρόχειρα, ο ΠΕΛΑΤΗΣ δεν παίρνει πλήρη αναφορά (μόνο η Διαχείριση). "0" = επιτρέπεται (π.χ. δοκιμές).
REQUIRE_APPROVAL = str(_secret("REQUIRE_APPROVAL") or "1").strip() != "0"
POLISH_MODEL = (os.environ.get("POLISH_MODEL") or
                ("claude-sonnet-5-5" if provider == "anthropic" else default_model(provider)))


def _new_case():
    """«Νέα αναφορά»: καθαρίζει ΤΑ ΠΑΝΤΑ -- αποτέλεσμα, πρόοδο, μετρητή."""
    ss.chart = None
    ss.cases = {}
    ss.current_case = None
    ss.uploader_gen += 1
    # v20.2: καθαρίζονται και τα στοιχεία γέννησης, οι υπολογισμένοι χάρτες και τα
    # παλιά πεδία της φόρμας (b_*), τα αναγνωσμένα PDF και οι εκτιμήσεις κόστους.
    for key in list(ss.keys()):
        if key in ("birth_charts", "parsed_pdfs", "cost_estimates", "auto_result", "engine_result", "manual_chart",
                   "manual_pdf_hash", "manual_birth_key", "manual_input_key", "orientation_validation") \
                or str(key).startswith(("b_", "m_")):
            del ss[key]
    reset_case_state()


# ---------------------------------------------------------------- πλαϊνή στήλη
with st.sidebar:
    st.header(t["sidebar_header"])
    st.caption(t.get(f"sidebar_privacy_{REPORT_MODE}", t["sidebar_privacy"]))
    if st.button(t["sidebar_reset"], use_container_width=True, help=t["sidebar_reset_help"]):
        _new_case()
        st.rerun()
    admin_password = None if CLIENT_PAGE else _secret("ADMIN_PASSWORD")   # v22.25: ποτέ Διαχείριση στον πελάτη
    # ADMIN_OPEN = "1" (Secret): η Διαχείριση ανοίγει ΧΩΡΙΣ κωδικό, για όλους
    # (χρήσιμο όσο τη σελίδα τη χρησιμοποιεί μόνο η ιδιοκτήτρια).
    admin_open = str(_secret("ADMIN_OPEN") or "").strip().lower() in ("1", "true", "yes", "ναι")
    # v20.1 (εξωτερικός έλεγχος): το ADMIN_OPEN ισχύει ΜΟΝΟ τοπικά (localhost). Σε δημόσια
    # εγκατάσταση αγνοείται, ώστε ένα ξεχασμένο Secret να μην ανοίξει τη Διαχείριση σε όλους.
    if admin_open and (CLIENT_PAGE or not _is_local_request()):
        admin_open = False
    is_admin = admin_open
    if admin_password or admin_open:
        st.write("")
        with st.expander(t["admin_expander"], expanded=admin_open):
            if not admin_open:
                typed = st.text_input(t["admin_password"], type="password", key="admin_pw")
                # v20.4: σύγκριση σε bytes UTF-8 -- με str, το compare_digest σκάει σε μη-ASCII
                # χαρακτήρες (π.χ. αν κάποιος πληκτρολογήσει ελληνικά).
                is_admin = bool(typed) and hmac.compare_digest(
                    str(typed).encode("utf-8"), str(admin_password).encode("utf-8"))
                if typed and not is_admin:
                    st.caption(t["admin_wrong"])
            if is_admin:
                st.caption(t["admin_on"])
                if not admin_open:
                    # v22.24: έξοδος με ένα κλικ -- σβήνει τον κωδικό, η σελίδα γίνεται αμέσως «σελίδα πελάτη».
                    st.button(t["admin_logout"], use_container_width=True, key="admin_logout",
                              on_click=lambda: ss.update(admin_pw=""))
                provider = st.selectbox(
                    t["provider_label"], list(PROVIDERS), index=list(PROVIDERS).index(provider),
                    format_func=lambda p: PROVIDER_LABELS[p], key="provider",
                )
                if configured[provider]:
                    st.caption(t["key_from_secrets"])
                    api_key = configured[provider]
                else:
                    api_key = st.text_input(t["api_key_label"].format(provider=PROVIDER_LABELS[provider]),
                                            type="password", key=f"api_key_{provider}")
                    st.caption(t["key_hint"].format(secret=API_KEY_NAMES[provider]))
                st.caption(t["admin_polish_model"].format(model=POLISH_MODEL, mode=REPORT_MODE))

def _parse_cached(uploaded):
    """Διαβάζει το PDF ΜΙΑ φορά ανά αρχείο (κλειδί: αποτύπωμα περιεχομένου)."""
    data = uploaded.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    cache = ss.setdefault("parsed_pdfs", {})
    if digest not in cache:
        try:
            cache[digest] = (parse_astrodienst_pdf(data, uploaded.name), None)
        except Exception as err:  # noqa: BLE001
            cache[digest] = (None, err)
    return (digest,) + cache[digest]


def _birth_form(prefix: str = "b"):
    """v20: στοιχεία γέννησης -> υπολογισμός χάρτη μέσα στην εφαρμογή.
    Επιστρέφει (case_key, chart, error). Χώρες/τόποι στη γλώσσα του πελάτη.
    Η γραμμή «Υπολογισμός για…», οι προειδοποιήσεις ώρας και η διόρθωση της
    διαφοράς από UT εμφανίζονται ΜΟΝΟ στη Διαχείριση."""
    g = ss.uploader_gen
    name = st.text_input(t["birth_name"], key=f"{prefix}_name_{g}", max_chars=60)
    # v20.6: ημερομηνία ΓΡΑΦΕΤΑΙ (ημέρα · μήνας · έτος, όπως στο astro.com) -- χωρίς
    # ημερολόγιο. Γεννήσεις των τελευταίων 100 ετών, έως σήμερα.
    today = date.today()
    min_year = today.year - 100
    # v20.16: πιο εύχρηστη φόρμα -- αριθμημένα βήματα· ημερομηνία ΚΑΙ ώρα γράφονται
    # σε απλά πεδία στην ίδια γραμμή (χωρίς «HH:mm» που ήθελε Enter)· χώρα προσυμπληρωμένη
    # «Κύπρος»· το «Δεν βρίσκω τον τόπο μου» κάτω από τον τόπο.
    st.markdown(f"**{t['step_when']}**")
    d1, d2, d3, d4, d5 = st.columns([1, 1.7, 1.2, 1, 1])
    day = d1.number_input(t["birth_day"], min_value=1, max_value=31, value=None, step=1,
                          placeholder=t["birth_day_ph"], key=f"{prefix}_day_{g}")
    month = d2.selectbox(t["birth_month"], list(range(1, 13)), index=None, key=f"{prefix}_month_{g}",
                         placeholder=t["birth_month_ph"], format_func=lambda m: t["months"].split(",")[m - 1])
    year = d3.number_input(t["birth_year"], min_value=1, max_value=9999, value=None, step=1,
                           placeholder=t["birth_year_ph"], key=f"{prefix}_year_{g}",
                           help=t["birth_years"].format(min_year=min_year))
    hour = d4.number_input(t["birth_hour"], min_value=0, max_value=23, value=None, step=1,
                           placeholder=t["birth_hour_ph"], key=f"{prefix}_hour_{g}", help=t["birth_time_help"])
    minute = d5.number_input(t["birth_minute"], min_value=0, max_value=59, value=None, step=1,
                             placeholder=t["birth_minute_ph"], key=f"{prefix}_minute_{g}")
    bdate = None
    if year and not (min_year <= int(year) <= today.year):
        st.caption("⚠️ " + t["birth_years"].format(min_year=min_year))
    elif day and month and year:
        try:
            bdate = date(int(year), int(month), int(day))
        except ValueError:
            st.caption("⚠️ " + t["birth_date_invalid"])
        else:
            if bdate > today:
                st.caption("⚠️ " + t["birth_date_future"])
                bdate = None
    btime = dtime(int(hour), int(minute)) if hour is not None and minute is not None else None

    st.markdown(f"**{t['step_where']}**")
    lat = lon = tz = None
    label = ""
    # v20.7: η χώρα ΓΡΑΦΕΤΑΙ και αναζητείται χωρίς τόνους/κεφαλαία, ελληνικά ή αγγλικά.
    # v20.11: η χώρα είναι ΥΠΟΧΡΕΩΤΙΚΗ -- ο τόπος εμφανίζεται μόνο αφού επιλεγεί χώρα.
    # v20.17: ΜΙΑ γραμμή για τη χώρα και ΜΙΑ για τον τόπο -- βέλος για λίστα Ή
    # πληκτρολόγηση. Το φίλτρο της λίστας του Streamlit θέλει ακριβή τόνο, οπότε ό,τι
    # γραφτεί και δεν βρεθεί (π.χ. «κυπρος», «παφος») γίνεται δεκτό με Enter
    # (accept_new_options) και αναζητείται από εμάς χωρίς τόνους/κεφαλαία.
    cc = ""
    all_c = countries(lang)
    c_codes = [c for c, _ in all_c]
    c_names = dict(all_c)
    c_pick = st.selectbox(
        t["birth_country"], c_codes, index=c_codes.index("CY") if "CY" in c_codes else None,
        key=f"{prefix}_cc_{g}_{lang}", accept_new_options=True, placeholder=t["birth_country_ph"],
        format_func=lambda c: country_label(c, c_names[c], lang) if c in c_names else c)
    if c_pick in c_names:
        cc = c_pick
    elif c_pick:
        cfound = search_countries(c_pick, lang)
        if len(cfound) == 1:
            cc = cfound[0][0]
            st.caption("✓ " + country_label(cc, cfound[0][1], lang))
        elif cfound:
            cc = st.selectbox(t["birth_country_pick"], cfound, key=f"{prefix}_cc2_{g}_{lang}",
                              format_func=lambda o: country_label(o[0], o[1], lang))[0]
        else:
            st.caption(t["birth_country_none"])

    place = None
    if not cc:
        st.caption(t["birth_country_first"])
    else:
        in_country = places_in_country(cc, lang)
        small = len(in_country) <= DROPDOWN_MAX_PLACES
        options, by_label = [], {}
        if small:
            for p_ in in_country:
                lbl = p_.name_only(lang)
                n = 2
                while lbl in by_label:  # ίδιο όνομα δύο φορές -> διάκριση
                    lbl = f"{p_.name_only(lang)} ({n})"; n += 1
                by_label[lbl] = p_
                options.append(lbl)
        p_pick = st.selectbox(
            t["birth_place"] if not small else t["birth_place_list"].format(n=len(in_country)),
            options, index=None, key=f"{prefix}_place_{g}_{cc}_{lang}", accept_new_options=True,
            placeholder=t["birth_place_ph"] if small else t["birth_place_type_ph"])
        if p_pick in by_label:
            place = by_label[p_pick]
        elif p_pick:
            found = search_places(p_pick, 30, (cc,))
            if len(found) == 1:
                place = found[0]
                st.caption("✓ " + place.name_only(lang))
            elif found:
                place = st.selectbox(t["birth_place_pick"], found, index=None,
                                     format_func=lambda p: p.name_only(lang),
                                     key=f"{prefix}_pick_{g}_{cc}_{lang}", placeholder=t["birth_place_pick_ph"])
            else:
                st.caption(t["birth_place_none"])
    if place is not None:
        lat, lon, tz = place.lat, place.lon, place.timezone
        label = place.short(lang)

    if st.checkbox(t["birth_place_manual"], key=f"{prefix}_manual_{g}"):
        st.caption(t["birth_coords_help"])
        c1, c2, c3 = st.columns(3)
        lat = c1.number_input(t["birth_lat"], min_value=-66.0, max_value=66.0, value=34.7768,
                              step=0.01, format="%.4f", key=f"{prefix}_lat_{g}")
        lon = c2.number_input(t["birth_lon"], min_value=-180.0, max_value=180.0, value=32.4245,
                              step=0.01, format="%.4f", key=f"{prefix}_lon_{g}")
        zones = sorted(available_timezones())
        tz = c3.selectbox(t["birth_tz"], zones, index=zones.index("Asia/Nicosia"), key=f"{prefix}_tz_{g}")
        label = f"{lat:.4f}, {lon:.4f}"
    if not CLIENT_PAGE:   # v22.25: στη σελίδα πελάτη η πηγή των δεδομένων μπαίνει στο τέλος της σελίδας
        st.caption(t["places_credit"])

    # v20.1/v20.8: αγοραστής πάντα 18+· αν η αναφορά αφορά ανήλικο, δηλώνει γονική ευθύνη.
    # v22.23: εμφανίζεται αμέσως, μαζί με την υπόλοιπη φόρμα (πριν: μόνο αφού συμπληρωθούν όλα
    # και υπολογιστεί ο χάρτης -- έβγαινε με καθυστέρηση).
    st.markdown(f"**{t['step_who']}**")
    who = st.radio(t["birth_who"], ["adult", "minor"], index=None, label_visibility="collapsed", key=f"{prefix}_who_{g}",
                   format_func=lambda w: t["birth_who_adult" if w == "adult" else "birth_who_minor"])

    # v22.25: τι λείπει ακόμα (το δείχνει η σελίδα κάτω από το κουμπί, αντί για ένα απλώς ανενεργό κουμπί)
    ss["form_missing"] = [t[k] for k, miss in (("missing_date", bdate is None), ("missing_time", btime is None),
                                                ("missing_place", lat is None), ("missing_who", who is None)) if miss]
    if bdate is None or btime is None or lat is None:
        return None, None, None

    manual_offset = None
    if is_admin and st.checkbox(t["birth_offset_override"], key=f"{prefix}_ovr_{g}"):
        manual_offset = st.number_input(t["birth_offset_value"], min_value=-14.0, max_value=14.0, value=2.0,
                                        step=0.5, key=f"{prefix}_off_{g}")

    # v20.2: έλεγχος της τοπικής ώρας ΠΡΙΝ τον χάρτη.
    #  - ώρα που δεν υπήρξε (μπροστά τα ρολόγια): μπλοκάρει μέχρι να διορθωθεί
    #  - ώρα που υπήρξε δύο φορές (πίσω τα ρολόγια): ο πελάτης διαλέγει ποια από τις δύο
    fold = None
    if manual_offset is None:
        probe = to_ut(bdate, btime, tz)
        if probe.nonexistent:
            st.error(t["birth_time_nonexistent"])
            return None, None, None
        if probe.ambiguous:
            first, second = to_ut(bdate, btime, tz, fold=0), to_ut(bdate, btime, tz, fold=1)
            choice = st.radio(
                t["birth_time_ambiguous"],
                [0, 1], index=None, key=f"{prefix}_fold_{g}",
                format_func=lambda f: t["birth_fold_first" if f == 0 else "birth_fold_second"].format(
                    offset=(first if f == 0 else second).offset_text),
            )
            if choice is None:
                return None, None, None
            fold = choice

    cache = ss.setdefault("birth_charts", {})
    raw_key = (name.strip(), bdate, btime, lat, lon, tz, manual_offset, label, fold)
    if raw_key not in cache:
        try:
            chart, moment = chart_from_birth(name, bdate, btime, lat, lon, tz, label, manual_offset, fold)
            key = birth_case_key(name, bdate, btime, lat, lon, moment.offset_hours)
            cache[raw_key] = (key, chart, moment, None)
        except Exception as err:  # noqa: BLE001
            cache[raw_key] = (None, None, None, err)
    key, chart, moment, err = cache[raw_key]
    if err is not None:
        st.error(t["birth_error"])
        if isinstance(err, ValueError) and not is_admin:
            msg = str(err)
            if "Placidus" in msg:
                st.caption(t["birth_polar"])
            elif "1900" in msg:
                st.caption(t["birth_years"].format(min_year=date.today().year - 100))
        if is_admin:
            with st.expander(t["technical_detail"]): st.code(str(err))
        return None, None, err
    # v20.1: αγοραστής πάντα 18+· αν η αναφορά αφορά ανήλικο, δηλώνει γονική ευθύνη
    # (όπως το Astrodienst με τις αναφορές για παιδιά/νέους). Χωρίς τη δήλωση το
    # κουμπί δεν ενεργοποιείται.
    # v20.8: δύο επιλογές (διαλέγεται μία): «18+, για μένα» ή «ανήλικος, έχω γονική ευθύνη».
    # Αν η ημερομηνία γέννησης δίνει ηλικία < 18, η πρώτη επιλογή δεν γίνεται δεκτή.
    # v22.23: η ερώτηση ③ εμφανίζεται ΑΜΕΣΩΣ με τη φόρμα (πιο πάνω), όχι μετά τον υπολογισμό του χάρτη.
    age = (date.today().year - bdate.year) - ((date.today().month, date.today().day) < (bdate.month, bdate.day))
    consent = who is not None
    if who is None:
        st.caption(t["birth_adult_needed"])
    elif who == "adult" and age < 18:
        st.warning(t["birth_who_age_mismatch"])
        consent = False
    if is_admin:
        st.info(t["birth_summary"].format(
            date=bdate.strftime("%d/%m/%Y"), time=btime.strftime("%H:%M"), place=label,
            ut=moment.ut.strftime("%d/%m/%Y %H:%M"), offset=moment.offset_text))
        for w in moment.warnings:
            st.caption("⚠️ " + w)
    if not consent:
        return None, chart, None
    return key, chart, None


def _chart_input():
    """v20.14: ΚΟΙΝΑ στοιχεία γέννησης (ή PDF για τη Διαχείριση) για αυτόματη ΚΑΙ
    χειροκίνητη δημιουργία -- ο πελάτης τα γράφει μία φορά και μετά διαλέγει τρόπο.
    Επιστρέφει (input_key, chart, error)."""
    if not CLIENT_PAGE:   # v22.26: στη σελίδα πελάτη η επισήμανση μένει μόνο στο τέλος της σελίδας
        st.caption(t["service_note"])
    use_pdf = False
    if is_admin:
        use_pdf = st.radio(t["input_mode"], [t["input_mode_birth"], t["input_mode_pdf"]], horizontal=True,
                           key="input_mode") == t["input_mode_pdf"]
    if use_pdf:
        st.subheader(t["step1_title"])
        pdf = st.file_uploader(t["pdf_uploader"], type=['pdf'], key=f"pdf_{ss.uploader_gen}")
        if pdf is None:
            return None, None, None
        key, chart, err = _parse_cached(pdf)
        if err is not None:
            st.error(t["pdf_error"])
            with st.expander(t["technical_detail"]): st.code(str(err))
            return None, None, err
        return key, chart, None
    st.subheader(t["birth_step1_title"])
    with st.container(border=True):   # v22.25: η φόρμα σε πλαίσιο, για να φαίνεται καθαρά τι συμπληρώνεται
        return _birth_form()


def _engine_report(preview, input_key, with_ai):
    gen, cost = None, None
    if with_ai and api_key:
        gen, cost = make_generate_fn(provider, api_key, POLISH_MODEL), CostTracker()
    if gen:
        with st.spinner(t["polish_wait"]):
            report = build_engine_report(preview, preview.name, lang, generate_fn=gen, cost=cost,
                                         model_name=POLISH_MODEL)
    else:
        report = build_engine_report(preview, preview.name, lang)
    p = report.polish
    return {"case_key": input_key, "lang": lang, "client_docx": report.client_docx,
            "engine_docx": report.engine_docx, "audit_docx": report.audit_docx,
            "client_name": report.client_name, "audit_name": report.audit_name,
            "client_text": report.client_text, "engine_text": report.engine_text,
            "n_talents": len(report.result.talents), "n_fields": len(report.result.fields),
            "tried_ai": p is not None, "used_ai": bool(p and p.used_ai),
            "ai_issues": list(p.issues) if p else [], "ai_error": p.error if p else "",
            "cost": cost.format() if cost else ""}


def _engine_section(input_key, preview):
    """v22 -- Υβριδική μέθοδος: ταλέντα και τομείς από κανόνες, κείμενα από έτοιμη βιβλιοθήκη,
    και (REPORT_MODE="hybrid") προαιρετικό «δέσιμο» από φτηνό AI με αυτόματη επιστροφή στην Α."""
    if not fully_approved():
        if is_admin:
            st.warning(t["draft_admin"].format(**approval_status()) +
                       (" " + t["draft_admin_blocked"] if REQUIRE_APPROVAL else ""))
        elif REQUIRE_APPROVAL:
            has_teaser = preview is not None and pick_teaser(preview, lang, approved_only=True) is not None
            st.info(t["draft_client"] if has_teaser else t["draft_client_no_teaser"])
            return
    ready = preview is not None and input_key is not None
    clicked = st.button(t["run_button"], type="primary", use_container_width=True, disabled=not ready,
                        key="engine_run")
    if not ready and ss.get("form_missing"):
        st.caption(t["missing_hint"].format(items=", ".join(ss["form_missing"])))
    if clicked:
        ss.engine_result = _engine_report(preview, input_key, with_ai=REPORT_MODE == "hybrid")
    res = ss.get("engine_result")
    if res and (res["case_key"] != input_key or res["lang"] != lang):
        ss.pop("engine_result", None)  # νέα στοιχεία ή άλλη γλώσσα: όχι παλιό αποτέλεσμα
        res = None
    if not res:
        return
    st.markdown(f'<div class="ok">{t["customer_ready"]}</div>', unsafe_allow_html=True)
    st.write("")
    st.download_button(t["download_final"], res["client_docx"], file_name=res["client_name"],
                       type="primary", use_container_width=True, key="engine_dl")
    if not is_admin:
        return
    version = "B" if res["used_ai"] else "A"
    st.caption(t["engine_admin_done"].format(talents=res["n_talents"], fields=res["n_fields"]) + " " +
               t["engine_version"].format(v=version) + (f" · {res['cost']}" if res["cost"] else ""))
    if res["tried_ai"] and not res["used_ai"]:
        st.warning(t["polish_fallback"])
        for line in res["ai_issues"]:
            st.write("•", line)
        if res["ai_error"]:
            st.code(res["ai_error"])
    st.download_button(t["download_audit_docx"], res["audit_docx"], file_name=res["audit_name"],
                       use_container_width=True, key="engine_audit_dl")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(t["download_version_a"], res["engine_docx"], file_name="A_" + res["client_name"],
                           use_container_width=True, key="engine_a_dl")
    with c2:
        if res["used_ai"]:
            st.download_button(t["download_version_b"], res["client_docx"], file_name="B_" + res["client_name"],
                               use_container_width=True, key="engine_b_dl")
        elif api_key and st.button(t["try_version_b"], use_container_width=True, key="engine_try_b"):
            ss.engine_result = _engine_report(preview, input_key, with_ai=True)
            st.rerun()
    with st.expander(t["engine_preview"]):
        st.markdown(res["client_text"])


def _auto_tab(input_key, preview, preview_err):
    """v22.17: μόνο η υβριδική μέθοδος (μηχανή + προαιρετικό φτηνό «δέσιμο»). Η παλιά πλήρης αναφορά με AI
    και η χειροκίνητη διαδικασία (ChatGPT/Claude) αφαιρέθηκαν από τη σελίδα -- κόστιζαν πολύ."""
    _engine_section(input_key, preview)


def _manual_tab(input_key, chart):
    """✍️ Χειροκίνητη: εντολή για ChatGPT/Claude -> ανέβασμα των δύο Word ->
    ίδιος μηχανικός έλεγχος. Δουλεύει ΚΑΙ χωρίς κλειδί API (δεν καλεί μοντέλο).
    v20.14: χρησιμοποιεί τα ΚΟΙΝΑ στοιχεία γέννησης της σελίδας."""
    st.caption(t["manual_intro"])
    if ss.get("manual_input_key") != input_key:
        ss.manual_input_key = input_key
        ss.pop("orientation_validation", None)
    if not chart or not input_key:
        st.info(t["manual_need_pdf"])
        return
    # v20.17: δείχνει ΠΟΙΟΣ χάρτης φορτώθηκε (ημερομηνία · ώρα · τόπος), όχι μόνο το όνομα
    # -- χωρίς όνομα έβγαινε «✓ Χάρτης: —» και φαινόταν σαν να λείπει ο χάρτης.
    st.success(t["manual_chart_loaded"].format(name=_chart_summary(chart)))
    display_name = chart.name  # μόνο από το PDF· κενό = αναφορά χωρίς όνομα

    st.markdown(t["manual_step1"])
    context = build_context(display_name, lang)
    orientation_doc = build_orientation_docx(
        display_name, SERVICE_TITLE, context, load_orientation_command(),
        build_orientation_source(chart), style_example_text=load_unified_short_example(),
    )
    st.download_button(t["download_command"], orientation_doc, file_name=CLIENT_OUTPUT_NAME,
                       type="primary", use_container_width=True)

    st.markdown(t["manual_step2"])
    st.caption(t["upload_hint_simple"])
    if lang == "el":
        paste_message = ("Ακολούθησε πιστά τη δεσμευτική εντολή που περιλαμβάνεται στο έγγραφο και χρησιμοποίησε "
                         "αποκλειστικά τα ελεγμένα τεχνικά δεδομένα που περιέχει. Μην επινοήσεις προσωπικά, "
                         "επαγγελματικά ή ψυχολογικά στοιχεία.\n\nΠαράδωσε δύο χωριστά, ολοκληρωμένα αρχεία Word:\n"
                         "1. Το καθαρό παραδοτέο του πελάτη.\n2. Το εσωτερικό τεχνικό δελτίο ελέγχου, που δεν "
                         "παραδίδεται στον πελάτη.\n\nΤο ανώνυμο πρότυπο σύντομης έκδοσης που περιλαμβάνεται στο "
                         "έγγραφο χρησιμοποιείται αποκλειστικά για τη δομή, το μήκος και την απλή γλώσσα· μην "
                         "αντιγράψεις από αυτό περιεχόμενο ή συμπεράσματα.\n\n" + language_clause(lang) +
                         "\n\nΚάνε προσεκτικό αυτοέλεγχο πριν από την παράδοση. Ο validator του AstroCheck Career "
                         "θα εκτελεστεί στη συνέχεια.")
    else:
        paste_message = ("Follow the binding command included in the document precisely, and use only the checked "
                         "technical data it contains. Do not invent personal, professional, or psychological details."
                         "\n\nDeliver two separate, complete Word files:\n1. The clean client deliverable.\n2. The "
                         "internal technical audit sheet, which is not delivered to the client.\n\nThe anonymous "
                         "short-version template included in the document is to be used only for structure, length, "
                         "and plain language; do not copy content or conclusions from it.\n\n" + language_clause(lang) +
                         "\n\nDo a careful self-check before delivering. The AstroCheck Career validator will run afterwards.")
    paste_message += "\n\n" + reinforcement_instructions(display_name, lang)
    _teaser_note = teaser_instruction(chart, lang)  # v21: το δωρεάν ταλέντο και στη χειροκίνητη
    if _teaser_note:
        paste_message += "\n\n" + _teaser_note
    st.code(paste_message, language=None)

    st.markdown(t["manual_step3"])
    orientation_result = st.file_uploader(t["result_uploader"], type=['docx'], key=f"orientation_result_{ss.uploader_gen}")
    orientation_audit = st.file_uploader(t["audit_uploader"], type=['docx'], key=f"orientation_audit_{ss.uploader_gen}")
    # v19.9 (εξωτερικός έλεγχος): η έγκριση ανήκει σε συγκεκριμένα αρχεία. Αν αλλάξει το PDF,
    # οποιοδήποτε από τα δύο Word ή η γλώσσα, το παλιό αποτέλεσμα ελέγχου δεν εμφανίζεται.
    def _manual_fingerprint():
        if not (orientation_result and orientation_audit):
            return None
        h = hashlib.sha256()
        for part in (orientation_result.getvalue(), orientation_audit.getvalue(),
                     repr(chart.to_dict()).encode("utf-8"), lang.encode("utf-8")):
            h.update(hashlib.sha256(part).digest())
        return h.hexdigest()

    if st.button(t["check_button"], disabled=not (orientation_result and orientation_audit), use_container_width=True):
        result_bytes = orientation_result.getvalue()
        manual_audit_text = docx_text(orientation_audit.getvalue())
        ss.orientation_validation = validate_orientation(
            chart, docx_text(result_bytes), {"Όνομα": display_name},
            presentation_mode=PRESENTATION, audit_text=manual_audit_text,
            format_issues=simple_docx_format_issues(result_bytes), expected_lang=lang,
        )
        # v20.18: η φράση «πώς φαίνεται να αναπτύσσεται» μπαίνει ΜΕΤΑ τον έλεγχο,
        # μόνο σε εγκεκριμένο αρχείο (όπως και στην αυτόματη ροή).
        if ss.orientation_validation.ok:
            result_bytes = annotate_client_docx(result_bytes, manual_audit_text, chart, lang)
        ss.orientation_docx_bytes = result_bytes
        ss.orientation_docx_name = orientation_result.name
        ss.orientation_fingerprint = _manual_fingerprint()
    if ss.get("orientation_validation") is not None and ss.get("orientation_fingerprint") != _manual_fingerprint():
        for key in ("orientation_validation", "orientation_docx_bytes", "orientation_docx_name", "orientation_fingerprint"):
            ss.pop(key, None)
    check = ss.get('orientation_validation')
    if check:
        if check.ok:
            st.markdown(f'<div class="ok">{check.summary(lang)}</div>', unsafe_allow_html=True)
            if check.warnings and lang == "en": st.caption(t["details_in_greek"])
            for line in check.warnings: st.write("•", line)
            st.download_button(t["download_checked"], ss.orientation_docx_bytes,
                               file_name=ss.orientation_docx_name, type="primary", use_container_width=True)
        else:
            st.markdown(f'<div class="warn">⚠ {check.summary(lang)}</div>', unsafe_allow_html=True)
            if lang == "en": st.caption(t["details_in_greek"])
            for line in check.details_lines(): st.write("•", line)


def _chart_summary(chart) -> str:
    """Σύντομη ταυτότητα χάρτη: «Μαρία · 11/02/1982 · 01:45 · Πάφος, Κύπρος»."""
    time_txt = (chart.time or "").split(" (")[0]
    parts = [chart.name, chart.date, time_txt, chart.place]
    return " · ".join(x for x in parts if x) or "—"


def _chart_data_text(chart) -> str:
    """v20.15: τα υπολογισμένα δεδομένα του χάρτη σε αναγνώσιμο κείμενο (αυτά ακριβώς
    παίρνει το AI), χωρίς τις τεχνικές σημειώσεις «πηγή:»."""
    head = " · ".join(x for x in (chart.name, chart.date, chart.time, chart.place, chart.house_system) if x)
    body = build_orientation_source(chart)
    body = re.sub(r" \| πηγή: [^\n]*", "", body)
    return (head + "\n\n" if head else "") + body


def _show_chart_data(chart):
    """v20.15 (μόνο Διαχείριση): «📊 Δεδομένα χάρτη» + λήψη σε αρχείο."""
    if not (is_admin and chart):
        return
    text = _chart_data_text(chart)
    with st.expander(t["chart_data_title"]):
        st.code(text, language=None, wrap_lines=True)
        st.download_button(t["chart_data_download"], text.encode("utf-8"),
                           file_name=f"Xartis_{(chart.name or 'AstroCheck').replace(' ', '_')}.txt",
                           mime="text/plain", key="chart_data_dl")


def _show_teaser(chart):
    """v21: «Δωρεάν ταλέντο» από έτοιμη βιβλιοθήκη -- χωρίς AI, χωρίς κόστος."""
    # v22.4: όσο ισχύει η έγκριση (REQUIRE_APPROVAL), ο πελάτης βλέπει ΜΟΝΟ εγκεκριμένα κείμενα·
    # η Διαχείριση βλέπει και τα πρόχειρα.
    approved_only = REQUIRE_APPROVAL and not is_admin
    teaser = pick_teaser(chart, lang, approved_only=approved_only) if chart else None
    if teaser is None:
        return
    head = t["teaser_head_natural"] if teaser.natural else t["teaser_head_practice"]
    st.markdown(
        f'<div class="teaser"><div class="teaser-head">🎁 {head}</div>'
        f'<div class="teaser-title">{html.escape(teaser.title)}</div>'
        f'<div>{html.escape(teaser.text)}</div>'
        f'<div class="teaser-more">{t["teaser_more"]}</div></div>',
        unsafe_allow_html=True)
    if is_admin:
        st.caption(t["teaser_admin"].format(a=teaser.pair[0], b=teaser.pair[1], aspect=teaser.aspect,
                                            orb=teaser.orb_text, status=teaser.status))


# v20.14: πρώτα τα κοινά στοιχεία, μετά ο τρόπος δημιουργίας.
if is_admin:   # v22.24: να φαίνεται καθαρά ότι ΔΕΝ είναι η σελίδα του πελάτη
    st.warning(t["admin_banner"])
_input_key, _chart, _chart_err = _chart_input()
_show_teaser(_chart if _input_key else None)
_show_chart_data(_chart if _input_key else None)
if is_admin:
    # v22.17: η χειροκίνητη διαδικασία (ChatGPT/Claude, χωρίς κόστος API) μόνο για τη Διαχείριση.
    st.markdown(f"#### {t['choose_mode']}")
    tab_auto, tab_manual = st.tabs([t["tab_auto"], t["tab_manual"]])
    with tab_auto:
        _auto_tab(_input_key, _chart, _chart_err)
    with tab_manual:
        _manual_tab(_input_key, _chart)
else:
    _auto_tab(_input_key, _chart, _chart_err)

# v22.6: η φιλοσοφία «Δύνασαι» -- μία παράγραφος στο κάτω μέρος της σελίδας, χωρίς τίτλο.
st.divider()
st.markdown(f'<div class="mission">{html.escape(t["about_mission"])}</div>', unsafe_allow_html=True)
if CLIENT_PAGE:   # v22.25: ό,τι ήταν στην πλαϊνή στήλη / στη φόρμα, εδώ με μικρά γράμματα
    for _note in (t["service_note"], t.get(f"sidebar_privacy_{REPORT_MODE}", t["sidebar_privacy"]), t["places_credit"]):
        st.markdown(f'<div class="small-note">{html.escape(_note)}</div>', unsafe_allow_html=True)
    _c = st.columns([1.2, 2, 1.2])[1]
    if _c.button(t["sidebar_reset"], use_container_width=True, key="client_reset"):
        _new_case()
        st.rerun()
