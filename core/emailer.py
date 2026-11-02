"""
emailer.py
==========
v22.43 -- Αποστολή της αναφοράς με email μέσω Resend (https://resend.com), χωρίς εξωτερική βιβλιοθήκη.
Κλειδί (RESEND_API_KEY) και αποστολέας (EMAIL_FROM) ΜΟΝΟ στα Secrets.
Χωρίς δικό σας domain, το Resend στέλνει ΜΟΝΟ στο email του λογαριασμού Resend (κατάλληλο για δοκιμές).
"""
from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request

API = "https://api.resend.com/emails"
_EMAIL = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")


class EmailError(RuntimeError):
    pass


def valid_email(addr) -> bool:
    return bool(addr) and bool(_EMAIL.match(str(addr).strip()))


def _default_http(payload: dict, api_key: str, timeout=30) -> dict:
    req = urllib.request.Request(API, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "AstroCheck-Career/22")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            msg = json.loads(exc.read().decode("utf-8")).get("message", "")
        except Exception:  # noqa: BLE001
            msg = ""
        raise EmailError(f"Resend {exc.code}: {msg}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise EmailError(f"Resend: {exc}") from None


def send_report(api_key: str, *, sender: str, to: str, subject: str, html: str,
                filename: str, content: bytes, extra: list | None = None, http=None) -> str:
    if not valid_email(to):
        raise EmailError("άκυρο email παραλήπτη")
    payload = {
        "from": sender,
        "to": [to.strip()],
        "subject": subject,
        "html": html,
        "attachments": [{"filename": fn, "content": base64.b64encode(data).decode("ascii")}
                        for fn, data in [(filename, content)] + list(extra or [])],   # v22.52: και PDF
    }
    res = (http or _default_http)(payload, api_key)
    if not res.get("id"):
        raise EmailError("Resend: άκυρη απάντηση")
    return res["id"]


def send_email(api_key: str, *, sender: str, to: str, subject: str, html: str, http=None) -> str:
    """v22.49: απλό email χωρίς συνημμένο (π.χ. «Κέρδισες 2 €»)."""
    if not valid_email(to):
        raise EmailError("άκυρο email παραλήπτη")
    res = (http or _default_http)({"from": sender, "to": [to.strip()], "subject": subject, "html": html}, api_key)
    if not res.get("id"):
        raise EmailError("Resend: άκυρη απάντηση")
    return res["id"]
