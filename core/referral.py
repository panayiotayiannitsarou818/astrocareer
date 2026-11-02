"""
referral.py
===========
v22.49 -- Πρόγραμμα παραπομπών («φέρε έναν φίλο»), ΧΩΡΙΣ δική μας βάση δεδομένων: όλα στο Stripe.

Λογική (αποφάσεις ιδιοκτήτριας, 2/11/2026):
* Κάθε αγοραστής παίρνει προσωπικό σύνδεσμο (`?ref=ΚΩΔΙΚΟΣ`).
* Ο φίλος που ανοίγει τον σύνδεσμο έχει έκπτωση (REFERRAL_DISCOUNT, 2 €) μέχρι τα μεσάνυχτα (ώρα Κύπρου)
  της ΕΠΟΜΕΝΗΣ μέρας από τη στιγμή που τον άνοιξε (REFERRAL_DAYS = 1).
* Ο αρχικός πελάτης κερδίζει REFERRAL_REWARD (2 €) για κάθε φίλο που αγοράζει. Τα ποσά αθροίζονται και
  χρησιμοποιούνται ως έκπτωση σε ΚΑΘΕ αναφορά· από REFERRAL_PAYOUT_MIN (20 €) και πάνω μπορεί να ζητήσει
  να του σταλούν στο Revolut (η ιδιοκτήτρια τα στέλνει στο τέλος του μήνα και τα σημειώνει «Πληρώθηκε»).
* Το υπόλοιπο λήγει REFERRAL_MONTHS (12) μήνες μετά την ΤΕΛΕΥΤΑΙΑ φορά που κέρδισε.
* Δεν κερδίζει αν ο «φίλος» είναι ο ίδιος (ίδιο email ή ίδια κάρτα -- «αποτύπωμα» κάρτας του Stripe).

Πού κρατιούνται (μεταδεδομένα στις πληρωμές του Stripe -- κανένα στοιχείο γέννησης):
* `ref_owner=ΚΩΔΙΚΟΣ`  στην πληρωμή του αρχικού πελάτη (από εκεί: email και κάρτα του).
* `ref=ΚΩΔΙΚΟΣ`        στην πληρωμή του φίλου (έσοδο πίστωσης)· `ref_notified=1` όταν σταλεί το email.
* `credit_used_by=ΚΩΔΙΚΟΣ`, `credit_used=λεπτά` στην πληρωμή όπου χρησιμοποιήθηκε πίστωση.
* Στην ΠΡΩΤΗ πληρωμή του αρχικού πελάτη («άγκυρα»): `spent=λεπτά` (δωρεάν αναφορές + πληρωμές Revolut),
  `payout_pending=1`, `payout_revtag`, `payout_cents` (αίτημα πληρωμής).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .payments import API, PaymentError, _default_http

CYPRUS = ZoneInfo("Asia/Nicosia")
CODE_RE = re.compile(r"^[A-Z2-7]{8}$")
REVTAG_RE = re.compile(r"^@?[A-Za-z0-9_.]{3,32}$|^\+?[0-9 ]{8,16}$")


@dataclass
class Settings:
    discount: int = 200        # λεπτά -- έκπτωση του φίλου
    reward: int = 200          # λεπτά -- κέρδος του αρχικού πελάτη ανά φίλο
    days: int = 1              # μέχρι τα μεσάνυχτα της «επόμενης» μέρας
    payout_min: int = 2000     # λεπτά -- ελάχιστο για αποστολή στο Revolut
    months: int = 12           # λήξη υπολοίπου μετά το τελευταίο κέρδος


@dataclass
class Balance:
    code: str
    earned: int = 0
    used: int = 0
    friends: int = 0
    last_earned: datetime | None = None
    expires: datetime | None = None
    expired: bool = False
    owner_email: str = ""
    owner_cards: set = field(default_factory=set)
    anchor_pi: str = ""
    payout_pending: bool = False
    payout_revtag: str = ""
    payout_cents: int = 0
    spent: int = 0

    @property
    def available(self) -> int:
        return 0 if self.expired else max(0, self.earned - self.used)


# ------------------------------------------------------------------ κωδικοί και υπογραφές
def _key(secret: str) -> bytes:
    return hashlib.sha256(("astrocheck-referral:" + (secret or "")).encode()).digest()


def ref_code(email: str, secret: str) -> str:
    """Σταθερός 8ψήφιος κωδικός ανά email (A-Z, 2-7). Δεν αποκαλύπτει το email."""
    mac = hmac.new(_key(secret), email.strip().lower().encode(), hashlib.sha256).digest()
    return base64.b32encode(mac).decode()[:8]


def me_signature(code: str, secret: str) -> str:
    return hmac.new(_key(secret), ("me:" + code).encode(), hashlib.sha256).hexdigest()[:20]


def valid_code(code) -> bool:
    return bool(code) and bool(CODE_RE.match(str(code)))


def valid_me(code, sig, secret) -> bool:
    return valid_code(code) and bool(sig) and hmac.compare_digest(str(sig), me_signature(code, secret))


def deadline(opened: datetime, days: int = 1) -> datetime:
    """Τα μεσάνυχτα (ώρα Κύπρου) της `days`-ής μέρας μετά το άνοιγμα του συνδέσμου (23:59:59)."""
    local = opened.astimezone(CYPRUS)
    end = (local + timedelta(days=days)).replace(hour=23, minute=59, second=59, microsecond=0)
    return end


GREEK_DAYS = ("Δευτέρας", "Τρίτης", "Τετάρτης", "Πέμπτης", "Παρασκευής", "Σαββάτου", "Κυριακής")
GREEK_MONTHS = ("Ιανουαρίου", "Φεβρουαρίου", "Μαρτίου", "Απριλίου", "Μαΐου", "Ιουνίου", "Ιουλίου",
                "Αυγούστου", "Σεπτεμβρίου", "Οκτωβρίου", "Νοεμβρίου", "Δεκεμβρίου")


def format_deadline(d: datetime, lang: str = "el") -> str:
    d = d.astimezone(CYPRUS)
    if lang == "el":
        return f"τα μεσάνυχτα της {GREEK_DAYS[d.weekday()]} {d.day} {GREEK_MONTHS[d.month - 1]}"
    return f"midnight on {d.strftime('%A')} {d.day} {d.strftime('%B')}"


def format_date(d: datetime, lang: str = "el") -> str:
    d = d.astimezone(CYPRUS)
    return f"{d.day}/{d.month}/{d.year}"


# ------------------------------------------------------------------ Stripe
def _search(secret_key, query, http=None):
    out, page = [], None
    for _ in range(10):   # έως 1.000 πληρωμές ανά κωδικό
        params = {"query": query, "limit": "100", "expand[]": "data.latest_charge"}
        if page:
            params["page"] = page
        res = (http or _default_http)("GET", f"{API}/payment_intents/search", secret_key, params)
        out += res.get("data", [])
        if not res.get("has_more") or not res.get("next_page"):
            break
        page = res["next_page"]
    return [p for p in out if p.get("status") == "succeeded"]


def _charge(pi) -> dict:
    ch = pi.get("latest_charge")
    return ch if isinstance(ch, dict) else {}


def _email(pi) -> str:
    ch = _charge(pi)
    return ((ch.get("billing_details") or {}).get("email") or pi.get("receipt_email") or "").strip().lower()


def _card(pi) -> str:
    card = ((_charge(pi).get("payment_method_details") or {}).get("card") or {})
    return card.get("fingerprint") or ""


def _set_metadata(secret_key, pi_id, values: dict, http=None):
    data = {f"metadata[{k}]": str(v) for k, v in values.items()}
    return (http or _default_http)("POST", f"{API}/payment_intents/{pi_id}", secret_key, data)


def ensure_coupon(secret_key, amount_cents: int, http=None, coupon_id: str | None = None,
                  name: str = "AstroCheck") -> str:
    """Κουπόνι Stripe μίας χρήσης. Με `coupon_id` (π.χ. της έκπτωσης φίλου): δημιουργείται μία φορά."""
    h = http or _default_http
    if coupon_id:
        coupon_id = f"{coupon_id}_{int(amount_cents)}"   # αλλαγή ποσού (Secrets) -> νέο κουπόνι
        try:
            got = h("GET", f"{API}/coupons/{coupon_id}", secret_key)
            if got.get("id") == coupon_id and got.get("valid", True):
                return coupon_id
        except PaymentError:
            pass
    data = {"amount_off": str(int(amount_cents)), "currency": "eur", "duration": "once", "name": name}
    if coupon_id:
        data["id"] = coupon_id
    else:
        data["max_redemptions"] = "1"
    res = h("POST", f"{API}/coupons", secret_key, data)
    if not res.get("id"):
        raise PaymentError("Stripe: δεν δημιουργήθηκε κουπόνι")
    return res["id"]


def balance(secret_key, code: str, settings: Settings, http=None, now: datetime | None = None) -> Balance:
    """Υπόλοιπο ενός κωδικού -- υπολογίζεται κάθε φορά από τις πληρωμές του Stripe."""
    b = Balance(code)
    if not valid_code(code):
        return b
    owners = sorted(_search(secret_key, f"metadata['ref_owner']:'{code}'", http), key=lambda p: p.get("created", 0))
    own_emails = {_email(p) for p in owners} - {""}
    own_cards = {_card(p) for p in owners} - {""}
    b.owner_cards = own_cards
    if owners:
        a = owners[0]
        md = a.get("metadata") or {}
        b.owner_email, b.anchor_pi = _email(a), a.get("id", "")
        b.spent = int(md.get("spent") or 0)
        b.payout_pending = md.get("payout_pending") == "1"
        b.payout_revtag = md.get("payout_revtag", "")
        b.payout_cents = int(md.get("payout_cents") or 0)
    for p in _search(secret_key, f"metadata['ref']:'{code}'", http):
        if _charge(p).get("refunded") or int(_charge(p).get("amount_refunded") or 0) > 0:
            continue   # v22.50: αγορά φίλου που επιστράφηκε -> δεν μετρά
        if _email(p) in own_emails or (_card(p) and _card(p) in own_cards):
            continue   # ο «φίλος» είναι ο ίδιος: ο φίλος κράτησε την έκπτωση, ο κωδικός δεν κερδίζει
        b.friends += 1
        b.earned += settings.reward
        when = datetime.fromtimestamp(int(p.get("created", 0)), tz=timezone.utc)
        b.last_earned = max(b.last_earned, when) if b.last_earned else when
    used = sum(int((p.get("metadata") or {}).get("credit_used") or 0)
               for p in _search(secret_key, f"metadata['credit_used_by']:'{code}'", http))
    b.used = used + b.spent
    if b.last_earned:
        b.expires = b.last_earned + timedelta(days=round(settings.months * 30.44))
        b.expired = (now or datetime.now(timezone.utc)) > b.expires
    return b


@dataclass
class PurchaseInfo:
    pi_id: str = ""
    email: str = ""
    code: str = ""                 # ο προσωπικός κωδικός του αγοραστή
    referrer_code: str = ""        # ποιος τον έστειλε (αν υπάρχει)
    referrer_rewarded: bool = False
    referrer_email: str = ""
    referrer_balance: int = 0
    self_referral: bool = False
    notes: list = field(default_factory=list)


def after_purchase(secret_key, session_id: str, secret: str, settings: Settings, http=None) -> PurchaseInfo:
    """Μετά από επιβεβαιωμένη πληρωμή: (1) ο αγοραστής γίνεται «αρχικός πελάτης» (ref_owner)·
    (2) αν ήρθε από σύνδεσμο φίλου, βρίσκουμε τον φίλο για το email «Κέρδισες 2 €» (μία φορά).
    Όλα «best effort»: αποτυχία εδώ ΔΕΝ εμποδίζει την αναφορά."""
    h = http or _default_http
    info = PurchaseInfo()
    cs = h("GET", f"{API}/checkout/sessions/{session_id}", secret_key,
           {"expand[]": "payment_intent.latest_charge"})
    pi = cs.get("payment_intent")
    if not isinstance(pi, dict) or pi.get("status") != "succeeded":
        return info
    md = pi.get("metadata") or {}
    info.pi_id = pi.get("id", "")
    info.email = _email(pi) or ((cs.get("customer_details") or {}).get("email") or "").strip().lower()
    if info.email:
        info.code = ref_code(info.email, secret)
        if md.get("ref_owner") != info.code:
            _set_metadata(secret_key, info.pi_id, {"ref_owner": info.code}, h)
    ref = md.get("ref", "")
    if valid_code(ref) and md.get("ref_notified") != "1":
        info.referrer_code = ref
        b = balance(secret_key, ref, settings, h)
        own = {b.owner_email} - {""}
        card = _card(pi)
        if (info.email and info.email in own) or (card and card in b.owner_cards):
            info.self_referral = True
        else:
            info.referrer_rewarded = True
            info.referrer_email = b.owner_email
            # η τρέχουσα πληρωμή ίσως δεν έχει ακόμη ευρετηριαστεί στην αναζήτηση του Stripe (έως ~1′)
            counted = any(True for p in _search(secret_key, f"metadata['ref']:'{ref}'", h) if p.get("id") == info.pi_id)
            info.referrer_balance = b.available + (0 if counted else settings.reward)
        _set_metadata(secret_key, info.pi_id, {"ref_notified": "1"}, h)
    return info


def spend(secret_key, b: Balance, cents: int, http=None):
    """Δωρεάν αναφορά ή πληρωμή Revolut: προσθέτει στο «spent» της άγκυρας."""
    if not b.anchor_pi:
        raise PaymentError("δεν βρέθηκε η πληρωμή του αρχικού πελάτη")
    _set_metadata(secret_key, b.anchor_pi, {"spent": b.spent + int(cents)}, http)


def request_payout(secret_key, b: Balance, revtag: str, http=None):
    revtag = revtag.strip()
    if not REVTAG_RE.match(revtag):
        raise PaymentError("άκυρο Revtag ή κινητό")
    _set_metadata(secret_key, b.anchor_pi, {"payout_pending": "1", "payout_revtag": revtag,
                                            "payout_cents": b.available}, http)


def pending_payouts(secret_key, http=None) -> list[dict]:
    return [{"pi": p.get("id"), "code": (p.get("metadata") or {}).get("ref_owner", ""),
             "email": _email(p), "revtag": (p.get("metadata") or {}).get("payout_revtag", ""),
             "cents": int((p.get("metadata") or {}).get("payout_cents") or 0),
             "spent": int((p.get("metadata") or {}).get("spent") or 0)}
            for p in _search(secret_key, "metadata['payout_pending']:'1'", http)]


def mark_paid(secret_key, row: dict, http=None):
    _set_metadata(secret_key, row["pi"], {"payout_pending": "0", "spent": row["spent"] + row["cents"],
                                          "payout_cents": "0"}, http)
