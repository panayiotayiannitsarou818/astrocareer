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
import secrets as _secrets_mod
import time
import hmac
import html
import urllib.parse
import re
import os
from datetime import date, datetime, timezone
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
from core.payments import (PaymentError, case_fingerprint, check_paid, create_checkout, find_paid_sessions,
                           return_token_of, format_price,
                           parse_price)
from core.emailer import EmailError, send_email, send_report, valid_email
from core import referral as REF
from core.return_token import rebuild as _rt_rebuild, seal as _rt_seal, unseal as _rt_unseal
from core.talent_report import build_engine_report, service_title
from core.pdf_builder import build_report_pdf, pdf_filename
from core.talent_growth import annotate_client_docx
from core.talent_texts import approval_status, fully_approved
from core.reference_loader import (
    docx_text, load_orientation_command, load_unified_short_example, simple_docx_format_issues,
)
from core.validator import validate_orientation

# v22.25: ΔΥΟ σελίδες από τον ίδιο κώδικα. Το client.py τρέχει αυτό το αρχείο με CLIENT_PAGE=True:
# καθαρή σελίδα πελάτη, χωρίς Διαχείριση και χωρίς πλαϊνή στήλη. Το app.py μόνο του = σελίδα Διαχείρισης.
CLIENT_PAGE = bool(globals().get("CLIENT_PAGE", False))

_ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "core", "assets")   # v22.64: λογότυπο (σπόρος)
_FAVICON = os.path.join(_ASSETS, "favicon.png")
st.set_page_config(page_title="AstroCheck Career", page_icon=_FAVICON if os.path.exists(_FAVICON) else "✦", layout="wide",
                   initial_sidebar_state="collapsed" if CLIENT_PAGE else "auto")
# v22.25: χωρίς τα κουμπάκια «− +» στα αριθμητικά πεδία (ημέρα, έτος, ώρα, λεπτά) -- ο χρήστης απλώς γράφει.
st.markdown("""<style>[data-testid="stNumberInputStepUp"],[data-testid="stNumberInputStepDown"]{display:none}
.small-note{color:#7a6d86;font-size:.82rem;text-align:center;max-width:760px;margin:0 auto 10px;line-height:1.5}
/* v22.53: τα αόρατα μπλοκ με <style> δεν πιάνουν χώρο (έδιναν ~50px κενό πάνω από τη γλώσσα) */
[data-testid="stElementContainer"]:has(style){display:none}</style>""",
            unsafe_allow_html=True)
# v22.61: SHOW_TOOLBAR = "1" στα Secrets -> φαίνεται η μπάρα του Streamlit (GitHub, ⋮) και στη σελίδα πελάτη
try:
    _show_toolbar = str(st.secrets.get("SHOW_TOOLBAR") or os.environ.get("SHOW_TOOLBAR") or "").strip() in ("1", "true", "yes")
except Exception:  # noqa: BLE001
    _show_toolbar = str(os.environ.get("SHOW_TOOLBAR") or "").strip() in ("1", "true", "yes")
if CLIENT_PAGE:   # σελίδα πελάτη: καθόλου πλαϊνή στήλη
    # v22.33: πιο ψηλά η φόρμα -- χωρίς τη γραμμή εργαλείων του Streamlit (Share, ☆, ✏️), λιγότερο κενό πάνω,
    # μικρότερο μωβ πλαίσιο, η γλώσσα χωρίς τίτλο.
    st.markdown("""<style>[data-testid="stSidebar"],[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"]{display:none!important}
""" + ("" if _show_toolbar else 'header[data-testid="stHeader"]{display:none!important}\n') + """.block-container,[data-testid="stMainBlockContainer"]{padding-top:.6rem!important}
.hero{padding:16px 24px!important;margin-bottom:10px!important}.hero h1{font-size:40px!important;margin:0!important}
.hero p{margin:2px 0!important}</style>""", unsafe_allow_html=True)
st.markdown("""<style>
@import url("https://fonts.googleapis.com/css2?family=Libre+Caslon+Text:ital@0;1&display=swap");
.stApp{background:#f6f2fa}.block-container{max-width:1100px;padding-top:4.5rem}.hero{background:#efe4f8;color:#4a1d4f;border-radius:22px;padding:26px 30px;margin-bottom:18px;text-align:center}.hero h1{margin:0;padding:0!important;font-family:"Libre Caslon Text",Georgia,serif;font-weight:400;font-size:48px;color:#4a1d4f;letter-spacing:-.3px;line-height:1.05}.hero .career{display:flex;align-items:center;justify-content:center;gap:16px;margin:-2px 0 6px}.hero .career span{font-family:"Libre Caslon Text",Georgia,serif;font-style:italic;font-size:26px;color:#4a1d4f}.hero .career i{display:block;width:90px;height:1px;background:#9b7bb8}.hero img.logo{height:74px;display:block;margin:0 auto 6px}.hero p{color:#4a1d4f;margin:2px 0}.hero p.sub{color:#7a6088;font-size:.9rem;margin-top:6px}.mission{color:#5b4a6b;font-style:italic;text-align:center;max-width:760px;margin:0 auto 24px;line-height:1.6}.hero .motto{font-family:Georgia,serif;font-size:1.15rem;color:#4a1d4f;margin:4px 0 0}.ok{padding:14px 16px;background:#e5f2e7;border-left:5px solid #39704c;border-radius:8px}.warn{padding:14px 16px;background:#fff1dd;border-left:5px solid #b7791f;border-radius:8px}.teaser{padding:18px 20px;background:#fff;border:2px solid #b9a3cf;border-radius:14px;margin:14px 0}.teaser-head{color:#3d2350;font-weight:600;margin-bottom:6px}.teaser-title{font-family:Georgia;font-size:1.35rem;color:#3d2350;margin-bottom:8px}.teaser-more{margin-top:12px;color:#5b4a6b;font-style:italic}.paylink{display:block;text-align:center;background:#6b3f8f;color:#fff!important;text-decoration:none!important;padding:10px 14px;border-radius:8px;font-weight:600;margin:4px 0}.paylink:hover{background:#56306f}.pay{padding:14px 16px;background:#fff;border:2px solid #b9a3cf;border-radius:12px;margin:6px 0 10px;color:#3d2350}.stay{padding:16px 18px;background:#fde8e8;border:2px solid #b42318;border-radius:10px;font-weight:600;font-size:1.05rem;color:#7a1a12}</style>""", unsafe_allow_html=True)


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
    site_language = st.selectbox("Γλώσσα / Language", ["Ελληνικά", "English"], key="site_language",
                                 label_visibility="collapsed" if CLIENT_PAGE else "visible")
lang = "el" if site_language == "Ελληνικά" else "en"
t = TR[lang]

# v22.63: λογότυπο-κείμενο όπως το λογότυπο της ιδιοκτήτριας (AstroCheck / — Career — / σύνθημα)
def _logo_tag():
    try:
        import base64 as _b64
        with open(os.path.join(_ASSETS, "logo_symbol.png"), "rb") as fh:
            return f'<img class="logo" alt="" src="data:image/png;base64,{_b64.b64encode(fh.read()).decode()}">'
    except OSError:
        return ""


st.markdown(f'<div class="hero">{_logo_tag()}<h1>AstroCheck</h1><div class="career"><i></i><span>Career</span><i></i></div>'
            f'<p class="motto">{t["hero_subtitle"]}</p></div>',   # v22.64: μία γραμμή κάτω από το Career
            unsafe_allow_html=True)

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
# v22.39: Πληρωμή (Stripe). Χωρίς STRIPE_SECRET_KEY η σελίδα δουλεύει όπως πριν (χωρίς πληρωμή).
STRIPE_KEY = str(_secret("STRIPE_SECRET_KEY") or "").strip()
PAYMENTS_ON = STRIPE_KEY.startswith(("sk_test_", "sk_live_", "rk_test_", "rk_live_"))
REPORT_PRICE_CENTS = parse_price(_secret("REPORT_PRICE") or "20")
# v22.43: αποστολή της αναφοράς με email (Resend). Χωρίς κλειδί: δεν στέλνεται email.
RESEND_KEY = str(_secret("RESEND_API_KEY") or "").strip()
EMAIL_FROM = str(_secret("EMAIL_FROM") or "AstroCheck Career <onboarding@resend.dev>").strip()
EMAIL_ON = RESEND_KEY.startswith("re_")
# v22.62: χωρίς δικό σου domain (αποστολέας onboarding@resend.dev) το Resend στέλνει ΜΟΝΟ στο email του λογαριασμού.
# Τότε η σελίδα ΔΕΝ υπόσχεται email στους πελάτες και δεν δείχνει «Δεν μπορέσαμε…»· η αποστολή γίνεται σιωπηλά
# (για τη δοκιμή της ιδιοκτήτριας). Με EMAIL_FROM από δικό σου domain -> όλα κανονικά.
EMAIL_TEST = EMAIL_ON and "resend.dev" in EMAIL_FROM.lower()
EMAIL_LIVE = EMAIL_ON and not EMAIL_TEST
# v22.49: πρόγραμμα παραπομπών (ενεργό μαζί με τις πληρωμές). Ρυθμίσεις στα Secrets (προαιρετικές).
# v22.65: το «Φέρε έναν φίλο» είναι ΠΑΓΩΜΕΝΟ εκτός αν REFERRAL_ON = "1" στα Secrets (απόφαση ιδιοκτήτριας:
# πρώτες πωλήσεις με την απλή διαδρομή). Οι πιστώσεις που έχουν ήδη δοθεί μένουν στο Stripe -- δεν σβήνεται τίποτα.
FREE_REPORTS = str(_secret("FREE_REPORTS") or "0").strip().lower() in ("1", "true", "yes", "on")
REF_ON = PAYMENTS_ON and str(_secret("REFERRAL_ON") or "0").strip().lower() in ("1", "true", "yes", "on")
REF_SECRET = str(_secret("REFERRAL_SECRET") or STRIPE_KEY)
RETURN_SECRET = str(_secret("RETURN_SECRET") or STRIPE_KEY)   # v22.56: κλειδί του εισιτηρίου επιστροφής
# v22.57: προεπιλογή ΧΩΡΙΣ έκπτωση για τον φίλο (απόφαση ιδιοκτήτριας: «η τιμή μένει σταθερά 20 € για όλους»)·
# με REFERRAL_DISCOUNT = "2" (κ.λπ.) στα Secrets ξαναμπαίνει.
_ref_disc_raw = str(_secret("REFERRAL_DISCOUNT") or "0").strip()
REF_SET = REF.Settings(discount=0 if _ref_disc_raw in ("0", "0.0", "0,0", "") else parse_price(_ref_disc_raw, 2.0),
                       reward=parse_price(_secret("REFERRAL_REWARD") or "2", 2.0),
                       days=max(0, int(str(_secret("REFERRAL_DAYS") or "1").strip() or 1)),
                       payout_min=parse_price(_secret("REFERRAL_PAYOUT_MIN") or "20", 20.0),
                       months=max(1, int(str(_secret("REFERRAL_MONTHS") or "12").strip() or 12)),
                       # v22.59: ανώτατο φίλων που ανταμείβονται ανά έτος (REFERRAL_MAX_PER_YEAR, 0 = χωρίς όριο)
                       max_per_year=max(0, int(str(_secret("REFERRAL_MAX_PER_YEAR") or "50").strip() or 50)))
POLISH_MODEL = (os.environ.get("POLISH_MODEL") or
                ("claude-sonnet-5-5" if provider == "anthropic" else default_model(provider)))


def _new_case():
    """«Νέα αναφορά»: καθαρίζει ΤΑ ΠΑΝΤΑ -- αποτέλεσμα, πρόοδο, μετρητή."""
    ss.chart = None
    ss.cases = {}
    ss.current_case = None
    ss.uploader_gen += 1
    try:   # v22.54: η επιστροφή από το Stripe (?paid=…&r=…) δεν ξαναφορτώνει την παλιά αναφορά
        for _k in ("paid", "r", "pay"):
            st.query_params.pop(_k, None)
    except Exception:  # noqa: BLE001
        pass
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
    # v22.40: ΟΛΑ με βελάκι (λίστα), όπως ο μήνας -- και πληκτρολόγηση για γρήγορη εύρεση.
    day = d1.selectbox(t["birth_day"], list(range(1, 32)), index=None, key=f"{prefix}_day_{g}",
                       placeholder=t["birth_day_ph"])
    month = d2.selectbox(t["birth_month"], list(range(1, 13)), index=None, key=f"{prefix}_month_{g}",
                         placeholder=t["birth_month_ph"], format_func=lambda m: t["months"].split(",")[m - 1])
    year = d3.selectbox(t["birth_year"], list(range(today.year, min_year - 1, -1)), index=None,
                        placeholder=t["birth_year_ph"], key=f"{prefix}_year_{g}",
                        help=t["birth_years"].format(min_year=min_year))
    hour = d4.selectbox(t["birth_hour"], list(range(24)), index=None, format_func=lambda h: f"{h:02d}",
                        placeholder=t["birth_hour_ph"], key=f"{prefix}_hour_{g}", help=t["birth_time_help"])
    minute = d5.selectbox(t["birth_minute"], list(range(60)), index=None, format_func=lambda m: f"{m:02d}",
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
    p_pick = None
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
    # v22.41: ό,τι λείπει ή είναι λάθος -> κόκκινο περίγραμμα (μόνο αφού ο πελάτης αρχίσει να συμπληρώνει)
    started = any(v not in (None, "") for v in (name.strip(), day, month, year, hour, minute, p_pick, who))
    red = []
    if bdate is None:
        empty = [k for k, v in (("day", day), ("month", month), ("year", year)) if v is None]
        red += empty or ["day", "month"]          # όλα γραμμένα αλλά άκυρη ημερομηνία (π.χ. 31 Φεβρουαρίου)
    red += [k for k, v in (("hour", hour), ("minute", minute)) if v is None]
    red_keys = [f"{prefix}_{k}_{g}" for k in red]
    if lat is None:
        if not cc:
            red_keys.append(f"{prefix}_cc_{g}_{lang}")
        elif p_pick and p_pick not in by_label and ss.get(f"{prefix}_pick_{g}_{cc}_{lang}", "") is None:
            red_keys.append(f"{prefix}_pick_{g}_{cc}_{lang}")
        else:
            red_keys.append(f"{prefix}_place_{g}_{cc}_{lang}")
    if who is None:
        red_keys.append(f"{prefix}_who_{g}")
    if started and red_keys:
        css = "".join(
            f".st-key-{k} [data-baseweb='select']>div,.st-key-{k} .react-aria-ComboBox [role='group']"
            f"{{border:2px solid #d92d20 !important;border-radius:8px}}"
            f".st-key-{k} [role='radiogroup']{{outline:2px solid #d92d20;border-radius:8px;padding:6px 10px}}"
            for k in red_keys)
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
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
            ss.setdefault("raw_by_key", {})[key] = raw_key   # v22.56: για το κρυπτογραφημένο εισιτήριο επιστροφής
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
    try:   # v22.52: και PDF
        client_pdf = build_report_pdf(service_title(lang), preview.name, report.client_text)
    except Exception:  # noqa: BLE001 -- χωρίς PDF, μένει το Word
        client_pdf = None
    return {"case_key": input_key, "lang": lang, "client_docx": report.client_docx,
            "client_pdf": client_pdf, "client_pdf_name": pdf_filename(report.client_name),
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
    if CLIENT_PAGE and not PAYMENTS_ON and not is_admin and not FREE_REPORTS:
        # v22.65: σελίδα πελάτη χωρίς (σωστό) κλειδί Stripe -> ΟΧΙ δωρεάν αναφορά· μόνο με FREE_REPORTS = "1"
        st.warning(t["pay_offline"])
        return
    if PAYMENTS_ON and not is_admin and not _paid(input_key):
        _pay_box(input_key, ready, preview)
        return
    # v22.69: μετά την πληρωμή η αναφορά φτιάχνεται ΜΟΝΗ της -- χωρίς το κουμπί «Δημιουργία», που μπέρδευε·
    # και όταν η αναφορά για αυτά τα στοιχεία είναι ήδη έτοιμη, ο πελάτης δεν βλέπει ξανά το κουμπί.
    _auto = ready and ss.pop("auto_run", False)
    _have = (ss.get("engine_result") or {}).get("case_key") == input_key and (ss.get("engine_result") or {}).get("lang") == lang
    if _auto:
        clicked = True
    elif _have and not is_admin and PAYMENTS_ON:
        clicked = False
    else:
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
    if res.get("client_pdf") and not is_admin:
        # v22.68: ο πελάτης παίρνει ΜΟΝΟ PDF (απόφαση ιδιοκτήτριας)· η Διαχείριση βλέπει και το Word
        st.download_button(t["download_pdf"], res["client_pdf"], file_name=res["client_pdf_name"],
                           mime="application/pdf", type="primary", use_container_width=True, on_click="ignore",
                           key="engine_pdf_dl")
    elif res.get("client_pdf"):
        d1, d2 = st.columns(2)
        d1.download_button(t["download_pdf"], res["client_pdf"], file_name=res["client_pdf_name"],
                           mime="application/pdf", type="primary", use_container_width=True, on_click="ignore", key="engine_pdf_dl")
        d2.download_button(t["download_final"], res["client_docx"], file_name=res["client_name"],
                           use_container_width=True, on_click="ignore", key="engine_dl")
    else:
        st.download_button(t["download_final"], res["client_docx"], file_name=res["client_name"],
                           type="primary", use_container_width=True, on_click="ignore", key="engine_dl")
    _email_report(input_key, res)
    if REF_ON and not is_admin and ss.get("my_code"):
        _share_box(ss["my_code"])
    elif not is_admin and PAYMENTS_ON:
        _recommend_box()   # v22.66: χωρίς πρόγραμμα πιστώσεων -- απλή σύσταση σε φίλο, χωρίς ανταμοιβή
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


def _email_report(input_key, res):
    """v22.43: στέλνει ΜΙΑ φορά την αναφορά στο email που δόθηκε στο Stripe."""
    if not (EMAIL_ON and PAYMENTS_ON) or is_admin or input_key is None:
        return
    fp = case_fingerprint(input_key)
    to = ss.get("pay_email", {}).get(fp, "")
    if not valid_email(to):
        return
    sent = ss.setdefault("emailed", {})
    tag = (fp, res["lang"])
    if tag not in sent:
        try:
            body = t["email_body"]
            if ss.get("waiver_ts", {}).get(fp):
                body += t["email_waiver"].format(ts=ss["waiver_ts"][fp])
            if REF_ON and ss.get("my_code"):
                body += t["ref_mail_share" if REF_SET.discount > 0 else "ref_mail_share_nodisc"].format(off=format_price(REF_SET.discount),
                                                   reward=format_price(REF_SET.reward),
                                                   share=html.escape(_share_link(ss["my_code"])),
                                                   me=html.escape(_me_link(ss["my_code"])))
                body += _ref_mail_extra(ss["my_code"], t)
            send_report(RESEND_KEY, sender=EMAIL_FROM, to=to, subject=t["email_subject"],
                        html=body,   # v22.68: μόνο PDF (Word μόνο αν για κάποιο λόγο δεν φτιάχτηκε PDF)
                        filename=res["client_pdf_name"] if res.get("client_pdf") else res["client_name"],
                        content=res["client_pdf"] if res.get("client_pdf") else res["client_docx"])
            sent[tag] = True
        except EmailError:
            sent[tag] = False
    if EMAIL_TEST and not sent[tag]:
        st.caption(t["email_test_hint"])   # δοκιμαστική λειτουργία: χωρίς «Δεν μπορέσαμε…» στον πελάτη
        return
    st.caption((t["email_sent"] if sent[tag] else t["email_failed"]).format(email=html.escape(to)))
    if not sent[tag] and st.button(t["email_retry"], key="email_retry"):   # v22.56: επανάληψη αποστολής
        sent.pop(tag, None)
        st.rerun()


def _app_url():
    url = str(_secret("APP_URL") or "").strip()
    if not url:
        try:
            url = str(st.context.url or "")
        except Exception:  # noqa: BLE001
            url = ""
    url = url.split("?")[0].rstrip("/")
    return url or "https://astrocheck-career.streamlit.app"


def _paid(input_key):
    """v22.39: έχει πληρωθεί η αναφορά ΓΙ' ΑΥΤΑ τα στοιχεία; (έλεγχος στο Stripe, με μνήμη)"""
    if input_key is None:
        return False
    fp = case_fingerprint(input_key)
    if fp in ss.setdefault("paid_fps", set()):
        return True
    checked = ss.setdefault("pay_checked", set())
    for sid in list(ss.setdefault("pay_sessions", [])):
        if (sid, fp) in checked and not ss.get("pay_recheck"):
            continue
        checked.add((sid, fp))
        try:
            ok, email = check_paid(STRIPE_KEY, sid, fp)
        except PaymentError as exc:
            ss["pay_error"] = str(exc)
            continue
        if ok:
            ss.paid_fps.add(fp)
            if email:
                ss.setdefault("pay_email", {})[fp] = email
            _after_purchase(sid)
            ss["auto_run"] = True      # v22.42: η αναφορά φτιάχνεται ΑΜΕΣΩΣ, χωρίς κουμπί
            ss.pop("pay_recheck", None)
            return True
    ss.pop("pay_recheck", None)
    return False


def _ref_balance(code, fresh=False):
    """Υπόλοιπο κωδικού παραπομπής (από το Stripe· μνήμη 60″)."""
    cache = ss.setdefault("ref_bal", {})
    hit = cache.get(code)
    if hit and not fresh and time.time() - hit[0] < 60:
        return hit[1]
    b = REF.balance(STRIPE_KEY, code, REF_SET)
    cache[code] = (time.time(), b)
    return b


def _discount():
    """(είδος, λεπτά, κουπόνι-ή-None, metadata) -- πίστωση του ίδιου ή έκπτωση από σύνδεσμο φίλου."""
    if not REF_ON:
        return None
    code = ss.get("credit_code")
    if code:
        try:
            b = _ref_balance(code)
        except PaymentError:
            b = None
        if b and b.available > 0:
            cents = min(b.available, REPORT_PRICE_CENTS)
            return ("credit", cents, b, {"credit_used_by": code, "credit_used": cents})
    ref = ss.get("ref_code")
    if ref and REF_SET.discount <= 0:
        return ("friend", 0, None, {"ref": ref})   # χωρίς έκπτωση: μόνο καταγραφή, για την πίστωση του φίλου
    if ref and ss.get("ref_deadline") and datetime.now(timezone.utc) <= ss["ref_deadline"]:
        return ("friend", min(REF_SET.discount, REPORT_PRICE_CENTS - 50), None, {"ref": ref})
    return None


def _pay_box(input_key, ready, preview=None):
    disc = _discount()
    cents = REPORT_PRICE_CENTS - (disc[1] if disc else 0)
    price = format_price(REPORT_PRICE_CENTS)
    if disc and disc[0] == "friend" and disc[1] <= 0:
        st.info(t["ref_friend_banner_nodisc"])
    elif disc and disc[0] == "friend":
        st.success(t["ref_friend_banner"].format(off=format_price(disc[1]),
                                                 until=REF.format_deadline(ss["ref_deadline"], lang)))
    elif disc and disc[0] == "credit":
        st.success(t["ref_credit_banner"].format(off=format_price(disc[1])))
    st.markdown(f'<div class="pay">{t["pay_intro"].format(price=price if not disc else format_price(cents))}</div>',
                unsafe_allow_html=True)
    label = t["pay_button"].format(price=format_price(cents) if disc else price)
    if not ready:
        st.button(label, type="primary", use_container_width=True, disabled=True, key="pay_disabled")
        if ss.get("form_missing"):
            st.caption(t["missing_hint"].format(items=", ".join(ss["form_missing"])))
        return
    fp = case_fingerprint(input_key)
    _c = globals().get("_chart")
    if _c is not None:   # v22.60: έλεγχος στοιχείων πριν από την πληρωμή (λάθος ώρα/τόπος = άλλη αναφορά)
        st.info(t["pay_check_data"].format(who=html.escape(_chart_summary(_c))))
    if disc and disc[0] == "credit" and cents <= 0:
        # Η πίστωση καλύπτει όλη την τιμή: δωρεάν αναφορά, χωρίς Stripe Checkout.
        if st.button(t["ref_free_button"], type="primary", use_container_width=True, key="ref_free"):
            try:   # v22.65: κλείδωμα + φρέσκο υπόλοιπο -> η ίδια πίστωση δεν περνά από δύο καρτέλες
                _nonce = REF.acquire_lock(STRIPE_KEY, disc[2])
                try:
                    _fresh = REF.balance(STRIPE_KEY, ss.get("credit_code", ""), REF_SET)
                    if _fresh.available < REPORT_PRICE_CENTS:
                        ss.setdefault("ref_bal", {}).pop(ss.get("credit_code"), None)
                        st.warning(t["ref_credit_changed"])
                        return
                    REF.spend(STRIPE_KEY, _fresh, REPORT_PRICE_CENTS)
                finally:
                    REF.release_lock(STRIPE_KEY, disc[2], _nonce)
            except REF.CreditBusy:
                st.warning(t["ref_credit_busy"])
                return
            except PaymentError as exc:
                st.error(t["pay_unavailable"])
                if is_admin:
                    st.code(str(exc))
                return
            ss.setdefault("ref_bal", {}).pop(ss.get("credit_code"), None)
            ss.pop("credit_code", None)
            ss.setdefault("paid_fps", set()).add(fp)
            ss["auto_run"] = True
            st.rerun()
        return
    # v22.51: ρητή συγκατάθεση για άμεση παράδοση και απώλεια του δικαιώματος υπαναχώρησης (Οδηγία 2011/83/ΕΕ,
    # άρθρο 16(μ)) -- ΠΡΙΝ από την πληρωμή· καταγράφεται με ημερομηνία/ώρα στην πληρωμή του Stripe και στο email.
    waived = st.checkbox(t["pay_waiver"], key=f"waiver_{fp}")
    if not waived:
        st.button(label, type="primary", use_container_width=True, disabled=True, key="pay_need_waiver")
        st.caption(t["pay_waiver_needed"])
        return
    ts = ss.setdefault("waiver_ts", {}).setdefault(fp, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
    links = ss.setdefault("pay_links", {})
    lkey = (fp, disc[0] if disc else "", disc[1] if disc else 0)
    if lkey not in links:
        base = _app_url()
        try:
            coupon = ""
            if disc and disc[0] == "friend" and disc[1] > 0:
                coupon = REF.ensure_coupon(STRIPE_KEY, disc[1], coupon_id="ASTRO_FRIEND", name=t["ref_coupon_friend"])
            elif disc and disc[0] == "credit":
                # v22.65: κλείδωμα + φρέσκο υπόλοιπο πριν από τη δέσμευση της πίστωσης (ανοιχτή συνεδρία Stripe)
                _nonce = REF.acquire_lock(STRIPE_KEY, disc[2])
                ss["_credit_lock"] = (disc[2], _nonce)
                _fresh = REF.balance(STRIPE_KEY, ss.get("credit_code", ""), REF_SET)
                if _fresh.available < disc[1]:
                    raise REF.CreditBusy("άλλαξε το υπόλοιπο")
                coupon = REF.ensure_coupon(STRIPE_KEY, disc[1], name=t["ref_coupon_credit"])
            # v22.56: στην επιστροφή από το Stripe τα στοιχεία ξαναβρίσκονται από το «εισιτήριο» r=…: τα στοιχεία
            # γέννησης ΚΡΥΠΤΟΓΡΑΦΗΜΕΝΑ μέσα στο URL (όχι σε μνήμη/αρχείο) -- αντέχει επανεκκίνηση και καθυστέρηση.
            raw = ss.get("raw_by_key", {}).get(input_key)
            tok = _rt_seal(raw, RETURN_SECRET, {"w": ts, "lg": lang}) if raw else _secrets_mod.token_urlsafe(12)
            co = create_checkout(STRIPE_KEY, amount_cents=REPORT_PRICE_CENTS, product_name=t["pay_product"],
                                 fingerprint=fp, success_url=base + "/?paid={CHECKOUT_SESSION_ID}&r=" + tok,
                                 cancel_url=base + "/?pay=cancel&r=" + tok, locale=lang,
                                 submit_message=t["pay_stripe_note"] if EMAIL_LIVE else "",
                                 coupon=coupon, metadata={**(disc[3] if disc else {}), "withdrawal_waiver": ts},
                                 expires_in=1800 if disc and disc[0] == "credit" else 0)
        except REF.CreditBusy:
            ss.setdefault("ref_bal", {}).pop(ss.get("credit_code"), None)
            st.warning(t["ref_credit_busy"])
            return
        except PaymentError as exc:
            st.error(t["pay_unavailable"])
            if is_admin:
                st.code(str(exc))
            return
        finally:
            _lk = ss.pop("_credit_lock", None)
            if _lk:
                REF.release_lock(STRIPE_KEY, _lk[0], _lk[1])
        links[lkey] = co.url
        ss.setdefault("pay_sessions", []).append(co.id)
    # v22.55: ΝΕΑ καρτέλα -- το Streamlit Cloud δεν επιτρέπει αλλαγή της ίδιας καρτέλας (δοκιμή ιδιοκτήτριας).
    # Στη νέα καρτέλα, μετά την πληρωμή, η αναφορά εμφανίζεται αμέσως (?paid=…&r=…).
    st.markdown(f'<a class="paylink" href="{html.escape(links[lkey])}" target="_blank">{html.escape(label)}</a>',
                unsafe_allow_html=True)
    st.caption(t["pay_note"] + (t["pay_note_email"] if EMAIL_LIVE else ""))
    # v22.55: χωρίς έλεγχο κάθε 3″ (καθυστερούσε τη σελίδα) -- με την πληρωμή στην ίδια καρτέλα, η επιστροφή
    # από το Stripe φέρνει μόνη της την αναφορά (?paid=…&r=…).


def _after_purchase(session_id):
    """v22.49: ο αγοραστής παίρνει προσωπικό σύνδεσμο· αν ήρθε από φίλο, ο φίλος παίρνει email «Κέρδισες…»."""
    if not REF_ON or session_id in ss.setdefault("ref_done", set()):
        return
    ss.ref_done.add(session_id)
    try:
        info = REF.after_purchase(STRIPE_KEY, session_id, REF_SECRET, REF_SET)
    except PaymentError as exc:
        ss["ref_error"] = str(exc)
        return
    if info.code:
        ss["my_code"] = info.code
    if ss.get("credit_code"):
        ss.setdefault("ref_bal", {}).pop(ss["credit_code"], None)
        ss.pop("credit_code", None)
    if info.referrer_rewarded and EMAIL_ON and valid_email(info.referrer_email):
        try:
            send_email(RESEND_KEY, sender=EMAIL_FROM, to=info.referrer_email, subject=t["ref_mail_subject"].format(reward=format_price(REF_SET.reward)),
                       html=t["ref_mail_body"].format(reward=format_price(REF_SET.reward),
                                                      total=format_price(info.referrer_balance),
                                                      me=html.escape(_me_link(info.referrer_code)),
                                                      share=html.escape(_share_link(info.referrer_code)))
                            + _ref_mail_extra(info.referrer_code, t))
        except EmailError:
            pass


def _share_link(code):
    return f"{_app_url()}/?ref={code}"


def _me_link(code):
    return f"{_app_url()}/?me={code}&k={REF.me_signature(code, REF_SECRET)}"


def _qr_png(url):
    try:
        import io
        import qrcode
        img = qrcode.make(url, box_size=6, border=2)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:  # noqa: BLE001 -- χωρίς QR αν λείπει η βιβλιοθήκη
        return None


def _ref_disclosure(code):
    """v22.58: ο σύνδεσμος + υπενθύμιση ότι ο πελάτης λέει στους φίλους του πως κερδίζει (διαφάνεια σύστασης
    με αμοιβή) + έτοιμο μήνυμα για αντιγραφή."""
    st.code(_share_link(code), language=None)
    st.caption(t["ref_disclose"])
    msg = t["ref_ready_msg"].format(reward=format_price(REF_SET.reward), link=_share_link(code))
    st.code(msg, language=None, wrap_lines=True)
    # v22.59: κουμπιά μοιράσματος -- ανοίγουν την εφαρμογή με το μήνυμα ήδη γραμμένο
    q = urllib.parse.quote(msg)
    c1, c2 = st.columns(2)
    c1.link_button(t["ref_send_whatsapp"], f"https://wa.me/?text={q}", use_container_width=True)
    c2.link_button(t["ref_send_viber"], f"viber://forward?text={q}", use_container_width=True)


def _ref_mail_extra(code, tx):
    return tx["ref_mail_disclose"].format(msg=html.escape(tx["ref_ready_msg"].format(
        reward=format_price(REF_SET.reward), link=_share_link(code))))


def _recommend_box():
    """v22.66: «Σε βοήθησε; Σύστησέ μας σε έναν φίλο» -- ο σύνδεσμος της σελίδας, WhatsApp/Viber, QR. Χωρίς πιστώσεις."""
    import urllib.parse as _up
    link = _app_url()
    msg = t["rec_msg"].format(link=link)
    with st.container(border=True):
        st.markdown(f"**{t['rec_title']}**")
        st.code(msg, language=None, wrap_lines=True)
        q = _up.quote(msg)
        c1, c2 = st.columns(2)
        c1.link_button(t["ref_send_whatsapp"], f"https://wa.me/?text={q}", use_container_width=True)
        c2.link_button(t["ref_send_viber"], f"viber://forward?text={q}", use_container_width=True)
        png = _qr_png(link)
        if png:
            st.image(png, width=140)


def _share_box(code):
    """Μετά την αγορά: ο προσωπικός σύνδεσμος για φίλους (και QR)."""
    with st.container(border=True):
        st.markdown(f"**{t['ref_share_title']}**")
        st.write(t["ref_share_text" if REF_SET.discount > 0 else "ref_share_text_nodisc"].format(off=format_price(REF_SET.discount), reward=format_price(REF_SET.reward)))
        _ref_disclosure(code)
        png = _qr_png(_share_link(code))
        if png:
            st.image(png, width=160)
        st.markdown(f"[{t['ref_my_balance']}]({_me_link(code)})")


def _referrer_panel(code):
    """?me=ΚΩΔΙΚΟΣ&k=ΥΠΟΓΡΑΦΗ -- το υπόλοιπο του αρχικού πελάτη, χρήση ή αίτημα Revolut."""
    with st.container(border=True):
        st.markdown(f"### {t['ref_panel_title']}")
        try:
            b = _ref_balance(code, fresh=ss.pop("ref_refresh", False))
        except PaymentError as exc:
            st.error(t["pay_unavailable"])
            if is_admin:
                st.code(str(exc))
            return
        st.metric(t["ref_panel_available"], format_price(b.available))
        st.caption(t["ref_panel_friends"].format(n=b.friends) +
                   (" " + t["ref_panel_expires"].format(date=REF.format_date(b.expires, lang)) if b.expires and b.available else "") +
                   (" " + t["ref_panel_expired"] if b.expired else ""))
        st.write(t["ref_share_text" if REF_SET.discount > 0 else "ref_share_text_nodisc"].format(off=format_price(REF_SET.discount), reward=format_price(REF_SET.reward)))
        _ref_disclosure(code)
        png = _qr_png(_share_link(code))
        if png:
            st.image(png, width=160)
        if b.available > 0 and not b.payout_pending:
            if ss.get("credit_code") == code:
                st.info(t["ref_panel_using"])
            elif st.button(t["ref_panel_use"].format(amount=format_price(min(b.available, REPORT_PRICE_CENTS))),
                           type="primary", use_container_width=True, key="ref_use"):
                ss["credit_code"] = code
                st.rerun()
        if b.payout_pending:
            st.info(t["ref_panel_pending"].format(amount=format_price(b.payout_cents), revtag=b.payout_revtag))
        elif b.available >= REF_SET.payout_min:
            st.markdown(t["ref_panel_payout_intro"].format(min=format_price(REF_SET.payout_min)))
            revtag = st.text_input(t["ref_panel_revtag"], key="ref_revtag", placeholder="@maria123")
            if st.button(t["ref_panel_payout"].format(amount=format_price(b.available)), key="ref_payout"):
                try:   # v22.65: κλείδωμα + φρέσκο υπόλοιπο
                    _nonce = REF.acquire_lock(STRIPE_KEY, b)
                    try:
                        _fresh = REF.balance(STRIPE_KEY, code, REF_SET)
                        if _fresh.available < REF_SET.payout_min or _fresh.payout_pending:
                            raise REF.CreditBusy("άλλαξε το υπόλοιπο")
                        REF.request_payout(STRIPE_KEY, _fresh, revtag)
                    finally:
                        REF.release_lock(STRIPE_KEY, b, _nonce)
                    ss["ref_refresh"] = True
                    st.rerun()
                except REF.CreditBusy:
                    ss["ref_refresh"] = True
                    st.warning(t["ref_credit_busy"])
                except PaymentError:
                    st.warning(t["ref_panel_revtag_bad"])
        else:
            st.caption(t["ref_panel_payout_later"].format(min=format_price(REF_SET.payout_min)))


def _admin_payouts():
    """Διαχείριση: αιτήματα πληρωμής στο Revolut -- «Πληρώθηκε» μετά τη μεταφορά."""
    with st.expander(t["ref_admin_title"]):
        try:
            rows = REF.pending_payouts(STRIPE_KEY)
        except PaymentError as exc:
            st.code(str(exc))
            return
        if not rows:
            st.caption(t["ref_admin_none"])
        for i, r in enumerate(rows):
            c1, c2 = st.columns([3, 1])
            c1.write(f"**{format_price(r['cents'])}** → Revolut **{r['revtag']}** · {r['email']} · {r['code']}")
            if c2.button(t["ref_admin_paid"], key=f"ref_paid_{i}"):
                REF.mark_paid(STRIPE_KEY, r)
                st.rerun()


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


@st.cache_data(show_spinner=False)
def _sample_pdf(lang_code):
    """v22.52: δείγμα πλήρους αναφοράς για ΦΑΝΤΑΣΤΙΚΟ πρόσωπο -- να δει ο πελάτης τι αγοράζει."""
    from core.birth_input import chart_from_birth as _cfb
    tx = TR[lang_code]
    chart, _ = _cfb(tx["sample_name"], date(1995, 5, 15), dtime(10, 30), 35.1856, 33.3823, "Asia/Nicosia")
    rep = build_engine_report(chart, chart.name, lang_code)
    # v22.60: χωρίς την ένδειξη «ΔΕΙΓΜΑ» και τη σημείωση μέσα στο PDF (απόφαση ιδιοκτήτριας)·
    # το κουμπί και το όνομα αρχείου λένε ήδη ότι είναι δείγμα.
    return build_report_pdf(service_title(lang_code), tx["sample_name"], rep.client_text)


def _sample_button():
    if REQUIRE_APPROVAL and not fully_approved() and not is_admin:
        return   # όσο τα κείμενα είναι πρόχειρα, όχι δείγμα στους πελάτες
    try:
        pdf = _sample_pdf(lang)
    except Exception:  # noqa: BLE001
        return
    st.download_button(t["sample_button"], pdf, file_name=t["sample_file"], mime="application/pdf",
                       use_container_width=True, on_click="ignore", key="sample_dl")


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
# v22.39: επιστροφή από τη σελίδα πληρωμής του Stripe
_qp_paid = str(st.query_params.get("paid", "") or "")
_restored = None
if PAYMENTS_ON and st.query_params.get("r"):   # v22.56: επιστροφή από το Stripe με κρυπτογραφημένο εισιτήριο
    _rt = _rt_unseal(st.query_params.get("r"), RETURN_SECRET)
    if _rt:
        try:
            _rk, _rc = _rt_rebuild(_rt[0])
            _restored = {"key": _rk, "chart": _rc, "waiver": _rt[1].get("w", "")}
            ss.setdefault("raw_by_key", {})[_rk] = _rt[0]
        except Exception:  # noqa: BLE001
            _restored = None
if PAYMENTS_ON and _qp_paid.startswith("cs_"):
    if _qp_paid not in ss.setdefault("pay_sessions", []):
        ss.pay_sessions.append(_qp_paid)
    if _restored:
        ss.setdefault("waiver_ts", {})[case_fingerprint(_restored["key"])] = _restored["waiver"]
        # v22.56: «ολοκληρώθηκε» ΜΟΝΟ αφού το επιβεβαιώσει το Stripe
        if _paid(_restored["key"]):
            st.success(t["pay_returned_here"])
        else:
            st.warning(t["pay_not_confirmed"])
            if st.button(t["pay_check_again"], key="pay_check_again"):
                ss["pay_recheck"] = True
                st.rerun()
    elif not ss.get("paid_fps"):
        st.info(t["pay_returned_unknown"])
elif PAYMENTS_ON and st.query_params.get("pay") == "cancel" and not ss.get("paid_fps"):
    st.info(t["pay_cancelled"])
# v22.49: σύνδεσμος φίλου (?ref=) και σελίδα υπολοίπου (?me=…&k=…)
_qp_ref = str(st.query_params.get("ref", "") or "").strip().upper()
if REF_ON and REF.valid_code(_qp_ref) and ss.get("ref_code") != _qp_ref:
    ss["ref_code"] = _qp_ref   # η προθεσμία μετρά από το (πρώτο, σε αυτή την καρτέλα) άνοιγμα του συνδέσμου
    ss["ref_deadline"] = REF.deadline(datetime.now(timezone.utc), REF_SET.days)
_qp_me = str(st.query_params.get("me", "") or "").strip().upper()
if REF_ON and REF.valid_me(_qp_me, st.query_params.get("k", ""), REF_SECRET):
    _referrer_panel(_qp_me)
if REF_ON and is_admin:
    _admin_payouts()
if _restored and (_qp_paid.startswith("cs_") or st.query_params.get("pay") == "cancel"):
    # Μετά την πληρωμή: η αναφορά για τα ίδια στοιχεία, χωρίς ξανά τη φόρμα.
    _input_key, _chart, _chart_err = _restored["key"], _restored["chart"], None
    st.caption(t["pay_for"].format(who=html.escape(_chart_summary(_chart))))
else:
    _input_key, _chart, _chart_err = _chart_input()
_show_teaser(_chart if _input_key else None)
if CLIENT_PAGE and not _input_key:   # v22.53: να ξέρει ο πελάτης ότι υπάρχει δωρεάν ταλέντο
    st.info(t["teaser_hint"])
_show_chart_data(_chart if _input_key else None)
if PAYMENTS_ON or is_admin:
    _sample_button()
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
# v22.52: συχνές ερωτήσεις, στοιχεία πωλητή και επικοινωνία (Secrets: SELLER_INFO, CONTACT_EMAIL)
SELLER_INFO = str(_secret("SELLER_INFO") or "").strip()
CONTACT_EMAIL = str(_secret("CONTACT_EMAIL") or "").strip()
if CLIENT_PAGE:
    with st.expander(t["faq_title"]):
        for _q, _a in t["faq"]:
            if not PAYMENTS_ON and ("Stripe" in _a or "Revolut" in _a or "υπαναχώρησης" in _a or "withdrawal" in _a
                                    or "email" in _a.lower()):
                continue   # χωρίς πληρωμές: μόνο οι γενικές ερωτήσεις
            if REF_SET.discount <= 0 and "{off}" in _a:   # v22.57: χωρίς έκπτωση φίλου -> χωρίς εκείνη τη γραμμή
                _a = "\n".join(x for x in _a.split("\n") if "{off}" not in x)
            _a = _a.replace("{off}", format_price(REF_SET.discount)).replace("{reward}", format_price(REF_SET.reward)) \
                   .replace("{min}", format_price(REF_SET.payout_min))
            if not EMAIL_LIVE:   # v22.62: χωρίς δικό σου domain -> χωρίς υποσχέσεις για email στις ερωτήσεις
                if "Έχασα" in _q or "lost my" in _q.lower():
                    continue
                for _old, _new in ((", στη σελίδα και στο email σου", ", στη σελίδα"),
                                   (", on the page and in your email", ", on the page"),
                                   (" Αν δεν τη βρίσκεις, δοκίμασε πρώτα το «Έχασες την αναφορά σου;» πιο κάτω στη σελίδα.", ""),
                                   (" If you cannot find it, first try \u201cLost your report?\u201d further down the page.", ""),
                                   (", και σου έρχεται email κάθε φορά", ""), (", and you get an email each time", "")):
                    _a = _a.replace(_old, _new)
            if not REF_SET.max_per_year:
                _a = "\n".join(x for x in _a.split("\n") if "{cap}" not in x)
            _a = _a.replace("{cap}", str(REF_SET.max_per_year))
            st.markdown(f"**{_q}**  \n{_a}")
def _recover_reports(email):
    """v22.56: «Έχασες την αναφορά σου;» -- ξαναφτιάχνει τις πληρωμένες αναφορές ενός email από τα κρυπτογραφημένα
    εισιτήρια του Stripe και τις στέλνει ΜΟΝΟ σε αυτό το email (μαζί με τον σύνδεσμο για φίλους). Τίποτα δεν
    εμφανίζεται στη σελίδα, ώστε κανείς να μη βλέπει στοιχεία άλλου."""
    sent = 0
    for cs in find_paid_sessions(STRIPE_KEY, email)[:3]:
        tok = _rt_unseal(return_token_of(cs), RETURN_SECRET)
        if not tok:
            continue
        key, chart = _rt_rebuild(tok[0])
        lg = tok[1].get("lg", lang) if tok[1].get("lg") in ("el", "en") else lang
        rep = build_engine_report(chart, chart.name, lg)
        pdf = build_report_pdf(service_title(lg), chart.name, rep.client_text)
        body = TR[lg]["recover_body"]
        if REF_ON:
            code = REF.ref_code(email, REF_SECRET)
            body += TR[lg]["ref_mail_share" if REF_SET.discount > 0 else "ref_mail_share_nodisc"].format(off=format_price(REF_SET.discount), reward=format_price(REF_SET.reward),
                                                    share=html.escape(_share_link(code)), me=html.escape(_me_link(code)))
            body += _ref_mail_extra(code, TR[lg])
        send_report(RESEND_KEY, sender=EMAIL_FROM, to=email, subject=TR[lg]["email_subject"], html=body,
                    filename=pdf_filename(rep.client_name), content=pdf)   # v22.68: μόνο PDF
        sent += 1
    return sent


if CLIENT_PAGE and PAYMENTS_ON and EMAIL_LIVE:
    with st.expander(t["recover_title"]):
        st.caption(t["recover_intro"])
        _rec_email = st.text_input(t["recover_email"], key="recover_email", placeholder="name@example.com")
        if st.button(t["recover_button"], key="recover_go"):
            ss["recover_n"] = ss.get("recover_n", 0) + 1
            if ss["recover_n"] > 3:
                st.warning(t["recover_limit"])
            elif not valid_email(_rec_email):
                st.warning(t["recover_bad"])
            else:
                try:
                    with st.spinner(t["recover_wait"]):
                        _recover_reports(_rec_email.strip())
                except Exception:  # noqa: BLE001 -- ίδιο μήνυμα, για να μη φαίνεται αν υπάρχει αγορά
                    pass
                st.success(t["recover_done"])
if CLIENT_PAGE:   # v22.25: ό,τι ήταν στην πλαϊνή στήλη / στη φόρμα, εδώ με μικρά γράμματα
    for _note in (t["service_note"], t.get(f"sidebar_privacy_{REPORT_MODE}", t["sidebar_privacy"]),
                  *((t["privacy_payments"],) if PAYMENTS_ON else ()),
                  *((t["seller_line"].format(seller=SELLER_INFO),) if SELLER_INFO else ()),
                  *((t["contact_line"].format(email=CONTACT_EMAIL),) if CONTACT_EMAIL else ()), t["places_credit"]):
        st.markdown(f'<div class="small-note">{html.escape(_note)}</div>', unsafe_allow_html=True)
    _c = st.columns([1.2, 2, 1.2])[1]
    if _c.button(t["sidebar_reset"], use_container_width=True, key="client_reset"):
        _new_case()
        st.rerun()
