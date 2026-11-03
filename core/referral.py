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
    max_per_year: int = 50     # v22.59: ανώτατο φίλων που ανταμείβονται ανά ημερολογιακό έτος (0 = χωρίς όριο)


@dataclass
class Balance:
    code: str
    earned: int = 0
    used: int = 0
    capped: int = 0                # v22.59: φίλοι πάνω από το ετήσιο όριο (δεν ανταμείβονται)
    friend_ids: list = field(default_factory=list)   # v22.59: πληρωμές φίλων που ανταμείφθηκαν
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

    reserved: int = 0              # v22.56: πίστωση δεσμευμένη σε ανοιχτή (μη πληρωμένη) πληρωμή

    @property
    def available(self) -> int:
        """Διαθέσιμο = κερδισμένα − χρησιμοποιημένα − δεσμευμένα σε ανοιχτές πληρωμές − αίτημα Revolut σε αναμονή."""
        if self.expired:
            return 0
        pending = self.payout_cents if self.payout_pending else 0
        return max(0, self.earned - self.used - self.reserved - pending)


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
    rewarded = []
    for p in _search(secret_key, f"metadata['ref']:'{code}'", http):
        if _charge(p).get("refunded") or int(_charge(p).get("amount_refunded") or 0) > 0:
            continue   # v22.50: αγορά φίλου που επιστράφηκε -> δεν μετρά
        if _email(p) in own_emails or (_card(p) and _card(p) in own_cards):
            continue   # ο «φίλος» είναι ο ίδιος: ο φίλος κράτησε την έκπτωση, ο κωδικός δεν κερδίζει
        when = datetime.fromtimestamp(int(p.get("created", 0)), tz=timezone.utc)
        rewarded.append((when, p))
    b.friend_ids = []
    # v22.59: ανώτατο ανά έτος -- μετρούν οι πρώτοι max_per_year φίλοι κάθε ημερολογιακού έτους
    per_year: dict = {}
    for when, p in sorted(rewarded, key=lambda w: w[0]):
        per_year[when.year] = per_year.get(when.year, 0) + 1
        if settings.max_per_year and per_year[when.year] > settings.max_per_year:
            b.capped += 1
            continue
        b.friends += 1
        b.earned += settings.reward
        b.friend_ids.append(p.get("id", ""))
        b.last_earned = max(b.last_earned, when) if b.last_earned else when
    used = sum(int((p.get("metadata") or {}).get("credit_used") or 0)
               for p in _search(secret_key, f"metadata['credit_used_by']:'{code}'", http))
    b.used = used + b.spent
    try:   # v22.56: ανοιχτές πληρωμές με πίστωση (λήγουν σε 30′) -- να μη χρησιμοποιηθεί το ίδιο ποσό δύο φορές
        res = (http or _default_http)("GET", f"{API}/checkout/sessions", secret_key, {"status": "open", "limit": "100"})
        b.reserved = sum(int((cs.get("metadata") or {}).get("credit_used") or 0) for cs in res.get("data", [])
                         if (cs.get("metadata") or {}).get("credit_used_by") == code)
    except PaymentError:
        b.reserved = 0
    if b.last_earned:
        b.expires = b.last_earned + timedelta(days=round(settings.months * 30.44))
        b.expired = (now or datetime.now(timezone.utc)) > b.expires
    return b


def _would_reward(secret_key, ref, pi_id, settings: Settings, b: Balance, http) -> bool:
    """v22.59: ανταμείβεται αυτή η αγορά φίλου; (ετήσιο όριο max_per_year)"""
    if not settings.max_per_year:
        return True
    if any(True for p in _search(secret_key, f"metadata['ref']:'{ref}'", http) if p.get("id") == pi_id):
        return pi_id in b.friend_ids          # ήδη ευρετηριασμένη: η balance() το αποφάσισε
    year = datetime.now(timezone.utc).year
    this_year = sum(1 for p in _search(secret_key, f"metadata['ref']:'{ref}'", http)
                    if p.get("id") in b.friend_ids and
                    datetime.fromtimestamp(int(p.get("created", 0)), tz=timezone.utc).year == year)
    return this_year < settings.max_per_year


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
    capped: bool = False
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
        elif not _would_reward(secret_key, ref, info.pi_id, settings, b, h):
            info.capped = True     # v22.59: ετήσιο όριο -- χωρίς ανταμοιβή, χωρίς email «Κέρδισες»
        else:
            info.referrer_rewarded = True
            info.referrer_email = b.owner_email
            # η τρέχουσα πληρωμή ίσως δεν έχει ακόμη ευρετηριαστεί στην αναζήτηση του Stripe (έως ~1′)
            counted = any(True for p in _search(secret_key, f"metadata['ref']:'{ref}'", h) if p.get("id") == info.pi_id)
            info.referrer_balance = b.available + (0 if counted else settings.reward)
        _set_metadata(secret_key, info.pi_id, {"ref_notified": "1"}, h)
    return info


# v22.65: «κλείδωμα» ανά κωδικό, ώστε η ίδια πίστωση να ΜΗ χρησιμοποιηθεί από δύο καρτέλες ταυτόχρονα.
# Χωρίς βάση δεδομένων: γράφουμε ένα τυχαίο «εισιτήριο» στην πληρωμή-άγκυρα, περιμένουμε λίγο και το ξαναδιαβάζουμε.
# Αν δύο καρτέλες γράψουν σχεδόν μαζί, μένει ΜΟΝΟ του τελευταίου -- η άλλη βλέπει ξένο εισιτήριο και σταματά.
LOCK_WAIT = 1.5      # δευτερόλεπτα (στα tests 0)
LOCK_TTL = 120       # ένα ξεχασμένο κλείδωμα λήγει μόνο του


class CreditBusy(PaymentError):
    """Η ίδια πίστωση χρησιμοποιείται αυτή τη στιγμή αλλού."""


def acquire_lock(secret_key, b: Balance, http=None) -> str:
    import secrets as _s
    import time as _t
    h = http or _default_http
    if not b.anchor_pi:
        raise PaymentError("δεν βρέθηκε η πληρωμή του αρχικού πελάτη")
    md = (h("GET", f"{API}/payment_intents/{b.anchor_pi}", secret_key) or {}).get("metadata") or {}
    now = int(_t.time())
    if md.get("lock") and now - int(md.get("lock_ts") or 0) < LOCK_TTL:
        raise CreditBusy("πίστωση σε χρήση")
    nonce = _s.token_hex(8)
    _set_metadata(secret_key, b.anchor_pi, {"lock": nonce, "lock_ts": now}, h)
    if LOCK_WAIT:
        _t.sleep(LOCK_WAIT)
    md = (h("GET", f"{API}/payment_intents/{b.anchor_pi}", secret_key) or {}).get("metadata") or {}
    if md.get("lock") != nonce:
        raise CreditBusy("πίστωση σε χρήση")
    return nonce


def release_lock(secret_key, b: Balance, nonce: str, http=None):
    h = http or _default_http
    try:
        md = (h("GET", f"{API}/payment_intents/{b.anchor_pi}", secret_key) or {}).get("metadata") or {}
        if md.get("lock") == nonce:
            _set_metadata(secret_key, b.anchor_pi, {"lock": "", "lock_ts": "0"}, h)
    except PaymentError:
        pass   # λήγει μόνο του σε LOCK_TTL


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
