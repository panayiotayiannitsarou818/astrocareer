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
import re
import os
import time
from datetime import date
from datetime import time as dtime
from zoneinfo import available_timezones

import streamlit as st

from core import eta
from core.case_state import reset_case_state
from core.costs import CostTracker, cost_history_summary, estimate_report_cost, eur_per_usd, record_report_cost
from core.docx_builder import build_orientation_docx
from core.generator import API_KEY_NAMES, DEFAULT_PROVIDER, PROVIDER_LABELS, PROVIDERS, default_model
from core.birth_input import birth_case_key, chart_from_birth
from core.birthtime import to_ut
from core.i18n import TR
from core.places import DROPDOWN_MAX_PLACES, countries, country_label, places_in_country, search_countries, search_places
from core.parser import parse_astrodienst_pdf
from core.pipeline import (
    CLIENT_OUTPUT_NAME, PRESENTATION, SERVICE_TITLE, RunState, Settings, build_auto_prompt, audit_docx_filename, build_context,
    client_docx_filename, language_clause, make_generate_fn, reinforcement_instructions, run_pipeline,
)
from core.prompts import build_orientation_source
from core.reference_loader import (
    docx_text, load_orientation_command, load_unified_short_example, simple_docx_format_issues,
)
from core.validator import validate_orientation

st.set_page_config(page_title="AstroCheck Career", page_icon="✦", layout="wide")
st.markdown("""<style>
.stApp{background:#f6f2fa}.block-container{max-width:1100px;padding-top:4.5rem}.hero{background:#3d2350;color:white;border-radius:22px;padding:30px 34px;margin-bottom:18px}.hero h1{margin:0 0 8px;font-family:Georgia;font-size:42px}.hero p{color:#e6d9f2}.ok{padding:14px 16px;background:#e5f2e7;border-left:5px solid #39704c;border-radius:8px}.warn{padding:14px 16px;background:#fff1dd;border-left:5px solid #b7791f;border-radius:8px}.stay{padding:16px 18px;background:#fde8e8;border:2px solid #b42318;border-radius:10px;font-weight:600;font-size:1.05rem;color:#7a1a12}</style>""", unsafe_allow_html=True)


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
              "MODEL_PRICES", "EUR_PER_USD"):
    _v = _secret(_name)
    if _v:
        os.environ[_name] = str(_v)

_, lang_col = st.columns([6, 1.6])
with lang_col:
    site_language = st.selectbox("Γλώσσα / Language", ["Ελληνικά", "English"], key="site_language")
lang = "el" if site_language == "Ελληνικά" else "en"
t = TR[lang]

st.markdown(f'<div class="hero"><h1>{t["hero_title"]}</h1><p>{t["hero_subtitle"]}</p></div>', unsafe_allow_html=True)

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


def _new_case():
    """«Νέα αναφορά»: καθαρίζει ΤΑ ΠΑΝΤΑ -- αποτέλεσμα, πρόοδο, μετρητή."""
    ss.chart = None
    ss.cases = {}
    ss.current_case = None
    ss.uploader_gen += 1
    # v20.2: καθαρίζονται και τα στοιχεία γέννησης, οι υπολογισμένοι χάρτες και τα
    # παλιά πεδία της φόρμας (b_*), τα αναγνωσμένα PDF και οι εκτιμήσεις κόστους.
    for key in list(ss.keys()):
        if key in ("birth_charts", "parsed_pdfs", "cost_estimates", "auto_result", "manual_chart",
                   "manual_pdf_hash", "manual_birth_key", "manual_input_key", "orientation_validation") \
                or str(key).startswith(("b_", "m_")):
            del ss[key]
    reset_case_state()


# ---------------------------------------------------------------- πλαϊνή στήλη
with st.sidebar:
    st.header(t["sidebar_header"])
    st.caption(t["sidebar_privacy"])
    if st.button(t["sidebar_reset"], use_container_width=True, help=t["sidebar_reset_help"]):
        _new_case()
        st.rerun()
    admin_password = _secret("ADMIN_PASSWORD")
    # ADMIN_OPEN = "1" (Secret): η Διαχείριση ανοίγει ΧΩΡΙΣ κωδικό, για όλους
    # (χρήσιμο όσο τη σελίδα τη χρησιμοποιεί μόνο η ιδιοκτήτρια).
    admin_open = str(_secret("ADMIN_OPEN") or "").strip().lower() in ("1", "true", "yes", "ναι")
    # v20.1 (εξωτερικός έλεγχος): το ADMIN_OPEN ισχύει ΜΟΝΟ τοπικά (localhost). Σε δημόσια
    # εγκατάσταση αγνοείται, ώστε ένα ξεχασμένο Secret να μην ανοίξει τη Διαχείριση σε όλους.
    if admin_open and not _is_local_request():
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
                cfg = Settings.from_env()
                st.caption(t["admin_settings"].format(
                    model=default_model(provider), stall=cfg.stall_rounds, fresh=cfg.fresh_rounds,
                    fails=cfg.max_failed_requests,
                    cap=(f"${cfg.max_cost_usd:.2f}" if cfg.max_cost_usd else "—"),
                    quality=("✓" if cfg.quality_pass else "✗"),
                ))
                case = ss.cases.get(ss.current_case)
                if case:
                    st.metric(t["admin_cost"], f"€{case['cost'].total_eur:.2f}",
                              f"${case['cost'].total_usd:.2f} · {len(case['cost'].calls)} {t['admin_calls']}",
                              delta_color="off")
                    if case["cost"].unknown_price:
                        st.caption(t["admin_unknown_price"])
                    st.caption(t["admin_cost_note"].format(rate=eur_per_usd()))

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


def _show_cost_estimate(chart, display_name):
    """Διαχείριση: εκτίμηση κόστους ΠΡΙΝ πατηθεί το κουμπί. Υπολογίζεται μία
    φορά ανά χάρτη/όνομα/γλώσσα/μοντέλο (η καταμέτρηση tokens είναι αίτημα
    στην Anthropic -- δεν επαναλαμβάνεται σε κάθε ανανέωση της σελίδας)."""
    model = default_model(provider)
    prompt = build_auto_prompt(chart, display_name, lang)
    key = (hashlib.sha256(prompt.encode("utf-8")).hexdigest(), model)
    cache = ss.setdefault("cost_estimates", {})
    if key not in cache:
        counter = getattr(make_generate_fn(provider, api_key), "count_tokens", None)
        try:
            counted = counter(prompt) if counter else None
        except Exception:  # noqa: BLE001
            counted = None
        hist = cost_history_summary()
        cache[key] = (estimate_report_cost(model, prompt, counted, hist["avg_out"] if hist else None), hist)
    est, hist = cache[key]
    rate = eur_per_usd()
    lines = [t["estimate_line"].format(
        lo_eur=est["low_usd"] * rate, hi_eur=est["high_usd"] * rate,
        lo_usd=est["low_usd"], hi_usd=est["high_usd"], model=model)]
    lines.append(t["estimate_basis"].format(
        tin=est["input_tokens"], how=t["estimate_counted"] if est["counted"] else t["estimate_approx"],
        tout=est["output_tokens"]))
    if hist:
        lines.append(t["estimate_history"].format(
            avg_eur=hist["avg_usd"] * rate, min_eur=hist["min_usd"] * rate, max_eur=hist["max_usd"] * rate,
            n=hist["n"], calls=hist["avg_calls"]))
    if not est["known_price"]:
        lines.append(t["admin_unknown_price"])
    st.info("\n\n".join(lines))


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
    st.caption(t["places_credit"])

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
    st.markdown(f"**{t['step_who']}**")
    who = st.radio(t["birth_who"], ["adult", "minor"], index=None, label_visibility="collapsed", key=f"{prefix}_who_{g}",
                   format_func=lambda w: t["birth_who_adult" if w == "adult" else "birth_who_minor"])
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
    return _birth_form()


def _auto_tab(input_key, preview, preview_err):
    """🤖 Αυτόματη: κοινά στοιχεία -> ένα κουμπί -> εγκεκριμένο έντυπο."""
    # ---------------------------------------------------------------- σελίδα πελάτη
    if not api_key:
        st.info(t["service_unavailable_auto"] if manual_visible else t["service_unavailable"])
        if not is_admin:
            return

    lo, hi = eta.typical_range()
    # Όνομα: από τη φόρμα (ή το PDF). Κενό -> αναφορά χωρίς όνομα.
    if is_admin and preview is not None and api_key:
        _show_cost_estimate(preview, preview.name)

    STEPS = {1: "step_read", 2: "step_write", 3: "step_check", 4: "step_final"}


    def _run(case_key, case, display_name, resume=False):
        """Εκτελεί/συνεχίζει τη διαδικασία με βήματα 1-4, εκτίμηση χρόνου και
        εμφανή προειδοποίηση. Η πρόοδος γράφεται επί τόπου στο case['state']."""
        stay = st.empty()
        stay.markdown(f'<div class="stay">⚠️ {t["stay_on_page"]}</div>', unsafe_allow_html=True)
        bar = st.progress(0.0)
        log = st.status(t["run_status"], expanded=True) if is_admin else None
        started = time.time()

        def show(step, extra_fraction=0.0):
            elapsed = (time.time() - started) / 60
            r_lo, r_hi = eta.remaining_minutes(elapsed)
            frac = min(0.97, (step - 1 + min(extra_fraction, 0.95)) / 4)
            bar.progress(frac, text=t["progress_line"].format(
                step=step, label=t[STEPS[step]], lo=r_lo, hi=r_hi, tlo=lo, thi=hi))

        def note(msg):
            if log:
                log.write(msg)

        calls = {"n": 0}

        def on_progress(event, **info):
            if event == "call":
                calls["n"] += 1
                kind = info["kind"]
                if kind in ("write", "fresh") and info.get("best_count") is None:
                    show(2)
                else:
                    # Κάθε διόρθωση προχωρά λίγο τη μπάρα μέσα στο βήμα 3 (χωρίς να φτάνει στο τέλος).
                    show(3 if kind != "quality" else 4, 1 - 0.7 ** calls["n"])
                note(t["log_call"].format(n=info["attempt"], kind=t.get(f"kind_{kind}", kind),
                                          cost=case["cost"].format()))
            elif event == "checked":
                show(3, 1 - 0.7 ** calls["n"])
                note(t["checked_ok"] if info["count"] == 0 else t["checked_issues"].format(count=info["count"]))
            elif event == "improved" and info["count"]:
                note(t["log_improved"].format(count=info["count"]))
            elif event == "api_retry":
                note(t["api_retry"].format(n=info["n"]))
            elif event == "new_round":
                note(t["new_round"].format(n=info["n"]))
            elif event == "truncated":
                note(t["log_truncated"])
            elif event == "quality":
                show(4)
                note(t["log_quality"])

        # Το αντικείμενο προόδου υπάρχει στη συνεδρία ΠΡΙΝ την πρώτη κλήση, ώστε
        # κάθε βελτίωση να σώζεται αμέσως -- ακόμη κι αν η εκτέλεση κοπεί απότομα.
        calls_before = len(case["cost"].calls)
        if case.get("state") is None:
            case["state"] = RunState(fingerprint="")
        case["name"] = display_name
        show(2 if not resume else 3)
        try:
            result = run_pipeline(
                case["chart"], display_name, lang,
                generate_fn=make_generate_fn(provider, api_key), model_name=default_model(provider),
                state=case.get("state"), cost=case["cost"], on_progress=on_progress,
            )
        finally:
            stay.empty()
            bar.empty()
        case["state"] = result.state
        case["name"] = display_name
        show_minutes = (time.time() - started) / 60
        if result.ok and not resume:
            eta.record_duration(show_minutes)
        run_calls = case["cost"].calls[calls_before:]
        if result.ok and run_calls:
            # Πραγματικό κόστος αυτής της αναφοράς -> μέσος όρος για τις επόμενες εκτιμήσεις.
            record_report_cost(sum(c["cost_usd"] for c in run_calls), len(run_calls),
                               sum(c["output_tokens"] for c in run_calls) / len(run_calls))
        ss.auto_result = {
            # v19.5: το αποτέλεσμα ανήκει σε συγκεκριμένο PDF + γλώσσα.
            "case_key": case_key, "lang": lang,
            "ok": result.ok, "reason": result.stopped_reason, "attempts": result.attempts,
            "resumable": result.resumable, "error_key": result.error_key, "error_detail": result.error_detail,
            "client_docx": result.client_docx, "audit_docx": result.audit_docx,
            "client_name": client_docx_filename(display_name), "audit_name": audit_docx_filename(display_name),
            "check": result.check, "quality": result.quality_applied, "minutes": show_minutes,
        }
        if log:
            log.update(state="complete", expanded=False)


    ready = preview is not None and input_key is not None
    run_clicked = st.button(t["run_button"], type="primary", use_container_width=True, disabled=not ready or not api_key)

    if run_clicked:
        ss.pop("auto_result", None)
        case_key = input_key
        case = ss.cases.get(case_key)
        step1 = st.progress(0.0, text=t["progress_line"].format(step=1, label=t["step_read"], lo=lo, hi=hi, tlo=lo, thi=hi))
        if case is None:
            # Ίδια στοιχεία/PDF ξανά -> ίδιο case: ο μετρητής και η πρόοδος ΔΕΝ μηδενίζονται.
            case = {"chart": preview, "cost": CostTracker(), "state": None, "name": None}
            ss.cases[case_key] = case
        step1.empty()
        ss.current_case = case_key
        ss.chart = case["chart"]
        _run(case_key, case, case["chart"].name)
        st.rerun()

    # ---------------------------------------------------------------- αποτέλεσμα
    res = ss.get("auto_result")
    if res and input_key is not None:
        # v19.5 (εξωτερικός έλεγχος): με νέα στοιχεία/PDF ή άλλη γλώσσα, το παλιό αποτέλεσμα δεν
        # εμφανίζεται -- αλλιώς φαινόταν «νέα στοιχεία + κουμπί λήψης της προηγούμενης αναφοράς».
        if res.get("case_key") != input_key or res.get("lang") != lang:
            ss.pop("auto_result", None)
            res = None
    elif res and input_key is None:
        ss.pop("auto_result", None)
        res = None
    case = ss.cases.get(ss.current_case)
    if res:
        if res["ok"]:
            st.markdown(f'<div class="ok">{t["customer_ready"]}</div>', unsafe_allow_html=True)
            st.write("")
            st.download_button(t["download_final"], res["client_docx"], file_name=res["client_name"],
                               type="primary", use_container_width=True)
            if is_admin:
                st.caption(t["admin_done"].format(n=res["attempts"], m=res["minutes"],
                                                  q=t["admin_quality_yes"] if res["quality"] else t["admin_quality_no"]))
                if res["audit_docx"]:
                    st.download_button(t["download_audit_docx"], res["audit_docx"], file_name=res["audit_name"],
                                       use_container_width=True)
                if res["check"].warnings:
                    with st.expander(t["details_expander"]):
                        for line in res["check"].warnings: st.write("•", line)
        else:
            # Ο πελάτης ΔΕΝ παίρνει ποτέ μη εγκεκριμένο έντυπο.
            customer_can_resume = res["resumable"] and res["reason"] == "api_failures"
            st.markdown(f'<div class="warn">{t["customer_interrupted"] if customer_can_resume else t["customer_failed"]}</div>',
                        unsafe_allow_html=True)
            if case and (customer_can_resume or (is_admin and res["resumable"])):
                st.write("")
                if st.button(t["resume_button"], type="primary", use_container_width=True):
                    ss.pop("auto_result", None)
                    display_name = case["chart"].name
                    _run(ss.current_case, case, display_name, resume=True)
                    st.rerun()
            if is_admin:
                reason_text = t.get(f"reason_{res['reason']}", res["reason"])
                st.caption(t["admin_stopped"].format(n=res["attempts"], reason=reason_text))
                if res["error_key"]:
                    st.error(t.get(f"auto_error_{res['error_key']}", t["auto_error"]))
                    with st.expander(t["technical_detail"]): st.code(res["error_detail"] or "")
                if res["check"] is not None:
                    with st.expander(t["details_expander"], expanded=True):
                        for line in res["check"].details_lines(): st.write("•", line)
                if res["client_docx"]:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.download_button(t["download_draft"], res["client_docx"],
                                           file_name="ΠΡΟΣΧΕΔΙΟ_" + res["client_name"], use_container_width=True)
                    with c2:
                        if res["audit_docx"]:
                            st.download_button(t["download_audit_docx"], res["audit_docx"],
                                               file_name=res["audit_name"], use_container_width=True)

    elif case and case.get("state") is not None and not case["state"].finished and case["state"].attempts > 0:
        # Η προηγούμενη εκτέλεση κόπηκε απότομα (χωρίς αποτέλεσμα) -- η πρόοδος
        # έχει σωθεί στη συνεδρία, οπότε προσφέρεται συνέχεια.
        st.markdown(f'<div class="warn">{t["customer_interrupted"]}</div>', unsafe_allow_html=True)
        st.write("")
        if st.button(t["resume_button"], type="primary", use_container_width=True, key="resume_after_cut"):
            _run(ss.current_case, case, case["chart"].name, resume=True)
            st.rerun()



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
        ss.orientation_validation = validate_orientation(
            chart, docx_text(result_bytes), {"Όνομα": display_name},
            presentation_mode=PRESENTATION, audit_text=docx_text(orientation_audit.getvalue()),
            format_issues=simple_docx_format_issues(result_bytes), expected_lang=lang,
        )
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


# ---------------------------------------------------------------- δύο τρόποι: καρτέλες
# MANUAL_MODE (Secret): "all" (προεπιλογή) = χειροκίνητη καρτέλα για όλους ·
# "admin" = μόνο μετά τον κωδικό διαχείρισης · "off" = καθόλου.
_manual_mode = str(_secret("MANUAL_MODE") or "all").strip().lower()
manual_visible = _manual_mode == "all" or (_manual_mode == "admin" and is_admin)

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


# v20.14: πρώτα τα κοινά στοιχεία, μετά ο τρόπος δημιουργίας.
_input_key, _chart, _chart_err = _chart_input()
_show_chart_data(_chart if _input_key else None)
if manual_visible:
    st.markdown(f"#### {t['choose_mode']}")
    tab_auto, tab_manual = st.tabs([t["tab_auto"], t["tab_manual"]])
    with tab_auto:
        _auto_tab(_input_key, _chart, _chart_err)
    with tab_manual:
        _manual_tab(_input_key, _chart)
else:
    _auto_tab(_input_key, _chart, _chart_err)
