"""
return_token.py
===============
v22.56 -- «Εισιτήριο» επιστροφής από το Stripe: τα στοιχεία γέννησης ΚΡΥΠΤΟΓΡΑΦΗΜΕΝΑ (Fernet, AES-128 + HMAC)
μέσα στο URL επιστροφής. Δεν κρατιούνται σε μνήμη ή αρχείο της εφαρμογής, άρα αντέχουν επανεκκίνηση και
καθυστερημένη επιστροφή· το Stripe κρατά μόνο ένα κρυπτογραφημένο κείμενο που δεν μπορεί να διαβάσει.
Το κλειδί προκύπτει από μυστικό των Secrets (RETURN_SECRET, αλλιώς το κλειδί του Stripe).
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import date, time

from cryptography.fernet import Fernet, InvalidToken


def _fernet(secret: str) -> Fernet:
    key = hashlib.sha256(("astrocheck-return:" + (secret or "")).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def seal(raw: tuple, secret: str, extra: dict | None = None) -> str:
    """raw = (name, date, time, lat, lon, tz, manual_offset, label, fold) όπως στη φόρμα."""
    name, bdate, btime, lat, lon, tz, offset, label, fold = raw
    data = {"n": name, "d": bdate.isoformat(), "t": btime.strftime("%H:%M"), "la": lat, "lo": lon, "z": tz,
            "o": offset, "l": label, "f": fold, **(extra or {})}
    return _fernet(secret).encrypt(json.dumps(data, ensure_ascii=False).encode()).decode()


def unseal(token: str, secret: str):
    """(raw, extra) ή None αν το εισιτήριο είναι άκυρο/αλλοιωμένο."""
    try:
        data = json.loads(_fernet(secret).decrypt(str(token or "").encode()).decode())
        h, m = (int(x) for x in data["t"].split(":"))
        raw = (data["n"], date.fromisoformat(data["d"]), time(h, m), data["la"], data["lo"], data["z"],
               data["o"], data["l"], data["f"])
    except (InvalidToken, ValueError, KeyError, TypeError):
        return None
    extra = {k: v for k, v in data.items() if k not in ("n", "d", "t", "la", "lo", "z", "o", "l", "f")}
    return raw, extra


def rebuild(raw: tuple):
    """Ξαναϋπολογίζει τον χάρτη (ντετερμινιστικά) -> (input_key, chart)."""
    from .birth_input import birth_case_key, chart_from_birth
    name, bdate, btime, lat, lon, tz, offset, label, fold = raw
    chart, moment = chart_from_birth(name, bdate, btime, lat, lon, tz, label, offset, fold)
    return birth_case_key(name, bdate, btime, lat, lon, moment.offset_hours), chart
