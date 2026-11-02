"""
payments.py
===========
v22.39 -- Πληρωμή της πλήρους αναφοράς μέσω Stripe Checkout.

* Τα στοιχεία κάρτας ΔΕΝ περνούν ποτέ από την εφαρμογή: ο πελάτης πληρώνει στη σελίδα του Stripe
  (κάρτα, Apple Pay, Google Pay -- ό,τι είναι ενεργό στο Stripe Dashboard).
* Στο Stripe ΔΕΝ στέλνονται στοιχεία γέννησης. Στέλνεται μόνο ένα «αποτύπωμα» (hash) των στοιχείων,
  ώστε η πληρωμή να ξεκλειδώνει ΜΙΑ αναφορά -- αυτή για την οποία πληρώθηκε.
* Χωρίς εξωτερική βιβλιοθήκη (μόνο urllib). Το κλειδί (STRIPE_SECRET_KEY) ΜΟΝΟ στα Secrets.
"""
from __future__ import annotations

import base64
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

API = "https://api.stripe.com/v1"


class PaymentError(RuntimeError):
    pass


@dataclass
class Checkout:
    id: str
    url: str


def case_fingerprint(input_key) -> str:
    """Αποτύπωμα των στοιχείων της αναφοράς (μη αναστρέψιμο) -- αυτό μόνο πάει στο Stripe."""
    return hashlib.sha256(repr(input_key).encode("utf-8")).hexdigest()[:40]


def parse_price(value, default: float = 20.0) -> int:
    """'20' / '19.90' / '19,90' -> λεπτά (2000 / 1990). Άκυρη τιμή -> η προεπιλογή."""
    try:
        euros = float(str(value).strip().replace(",", ".").replace("€", ""))
    except (TypeError, ValueError):
        euros = default
    if not 0.5 <= euros <= 1000:
        euros = default
    return int(round(euros * 100))


def format_price(cents: int) -> str:
    euros = cents / 100
    return (f"{euros:.0f}" if cents % 100 == 0 else f"{euros:.2f}".replace(".", ",")) + " €"


def _default_http(method, url, secret_key, data=None, timeout=20):
    if method == "GET" and data:   # v22.49: παράμετροι αναζήτησης στο URL
        url, data = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(data), None
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    token = base64.b64encode(f"{secret_key}:".encode()).decode()
    req.add_header("Authorization", f"Basic {token}")
    if body is not None:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            msg = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:  # noqa: BLE001
            msg = ""
        raise PaymentError(f"Stripe {exc.code}: {msg}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise PaymentError(f"Stripe: {exc}") from None


def create_checkout(secret_key: str, *, amount_cents: int, product_name: str, fingerprint: str,
                    success_url: str, cancel_url: str, locale: str = "el", submit_message: str = "",
                    coupon: str = "", metadata: dict | None = None, http=None) -> Checkout:
    data = {
        "mode": "payment",
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "eur",
        "line_items[0][price_data][unit_amount]": str(int(amount_cents)),
        "line_items[0][price_data][product_data][name]": product_name,
        "client_reference_id": fingerprint,
        "metadata[case]": fingerprint,
        "payment_intent_data[metadata][case]": fingerprint,
        "allow_promotion_codes": "true",      # κουπόνια (και, αργότερα, οι εκπτώσεις παραπομπής)
        "success_url": success_url,
        "cancel_url": cancel_url,
        "locale": locale if locale in ("el", "en") else "auto",
    }
    if submit_message:   # v22.44: μήνυμα πάνω από το κουμπί «Πληρωμή» στη σελίδα του Stripe
        data["custom_text[submit][message]"] = submit_message[:1200]
    if coupon:           # v22.49: έκπτωση παραπομπής / πίστωσης -- το Stripe δεν δέχεται ΚΑΙ τα δύο μαζί
        data.pop("allow_promotion_codes")
        data["discounts[0][coupon]"] = coupon
    for k, v in (metadata or {}).items():
        data[f"metadata[{k}]"] = str(v)
        data[f"payment_intent_data[metadata][{k}]"] = str(v)
    res = (http or _default_http)("POST", f"{API}/checkout/sessions", secret_key, data)
    if not res.get("id") or not res.get("url"):
        raise PaymentError("Stripe: άκυρη απάντηση")
    return Checkout(res["id"], res["url"])


def check_paid(secret_key: str, session_id: str, fingerprint: str, http=None):
    """(πληρώθηκε;, email πελάτη) -- πληρωμένη ΚΑΙ για αυτά ακριβώς τα στοιχεία."""
    if not session_id or not session_id.startswith("cs_") or not session_id.replace("_", "").isalnum():
        return False, ""
    res = (http or _default_http)("GET", f"{API}/checkout/sessions/{session_id}", secret_key)
    ok = res.get("payment_status") == "paid" and res.get("client_reference_id") == fingerprint
    email = ((res.get("customer_details") or {}).get("email") or "") if ok else ""
    return ok, email


def is_paid(secret_key: str, session_id: str, fingerprint: str, http=None) -> bool:
    """True μόνο αν η συνεδρία πληρώθηκε ΚΑΙ αφορά αυτά ακριβώς τα στοιχεία."""
    return check_paid(secret_key, session_id, fingerprint, http=http)[0]
