"""
costs.py
========
Μετρητής κόστους κλήσεων μοντέλου (v18).

Οι τιμές αλλάζουν συχνά, οπότε ΔΕΝ είναι κλειδωμένες στον κώδικα: οι
προεπιλογές παρακάτω αντικαθίστανται από τη μεταβλητή/Secret MODEL_PRICES
(JSON, $ ανά 1 εκατ. tokens), π.χ.
    MODEL_PRICES = '{"claude-opus": [5, 25], "gpt-5.4": [2.5, 15]}'
Το κλειδί είναι ΠΡΟΘΕΜΑ ονόματος μοντέλου· νικά το μακρύτερο που ταιριάζει.

Ισοτιμία: EUR_PER_USD (σταθερή, όχι ζωντανή -- ενδεικτική).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

# $ ανά 1.000.000 tokens: (είσοδος, έξοδος). Το μακρύτερο πρόθεμα νικά.
# Πηγή Anthropic: platform.claude.com/docs (σελίδες Opus 5 / Opus 5.5), Οκτ. 2026.
# Πηγή OpenAI gpt-5.4: δημόσιοι κατάλογοι (οι πηγές διαφωνούν -- κρατήθηκε η
# ακριβότερη). Επιβεβαίωσέ τες και άλλαξέ τες με MODEL_PRICES αν χρειαστεί.
DEFAULT_PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0),
    "claude-opus": (5.0, 25.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-fable": (10.0, 50.0),
    "claude-haiku": (1.0, 5.0),
    "gpt-5.4": (2.5, 15.0),
    "gpt-5": (1.25, 10.0),
}
# Άγνωστο μοντέλο: υπολογίζεται συντηρητικά με την ακριβότερη γνωστή τιμή.
FALLBACK_PRICE = (10.0, 50.0)
# Tokens εισόδου ΠΡΙΝ την κλήση (v18.2 -- εξωτερική κριτική: η παλιά εκτίμηση
# «1 token / 1,5 χαρακτήρα» μπορούσε να υποεκτιμήσει, όριο $1 -> $1,048):
#  1. Αν υπάρχει πραγματική καταμέτρηση (Anthropic count_tokens): αυτή,
#     + COUNT_MARGIN (η καταμέτρηση μπορεί να αποκλίνει ελάχιστα) + σταθερό περιθώριο.
#  2. Αλλιώς: ΜΑΘΗΜΑΤΙΚΟ ανώτατο όριο. Οι tokenizers δουλεύουν σε bytes και
#     κάθε token είναι ≥ 1 byte, άρα tokens ≤ bytes UTF-8 του κειμένου.
#     Υπερεκτιμά πολύ (τα ελληνικά είναι 2 bytes/γράμμα), αλλά ΔΕΝ υποεκτιμά ποτέ.
COUNT_MARGIN = 0.05
FIXED_TOKEN_MARGIN = 100
# Κάτω από αυτό το όριο εξόδου μια απάντηση (παραδοτέο + δελτίο) δεν μπορεί
# να ολοκληρωθεί -- δεν αξίζει να γίνει η κλήση.
MIN_USEFUL_OUTPUT_TOKENS = 6000
DEFAULT_EUR_PER_USD = 0.86


def prices() -> dict:
    table = dict(DEFAULT_PRICES)
    raw = os.environ.get("MODEL_PRICES")
    if raw:
        try:
            for k, v in json.loads(raw).items():
                table[str(k)] = (float(v[0]), float(v[1]))
        except (ValueError, TypeError, IndexError):
            pass
    return table


def price_for(model: str) -> tuple[tuple[float, float], bool]:
    """Επιστρέφει ((είσοδος, έξοδος), γνωστή_τιμή)."""
    table = prices()
    matches = [k for k in table if (model or "").startswith(k)]
    if not matches:
        return FALLBACK_PRICE, False
    return table[max(matches, key=len)], True


def eur_per_usd() -> float:
    try:
        return float(os.environ.get("EUR_PER_USD", DEFAULT_EUR_PER_USD))
    except ValueError:
        return DEFAULT_EUR_PER_USD


def max_cost_usd() -> float | None:
    raw = os.environ.get("AUTO_MAX_COST_USD")
    try:
        value = float(raw) if raw else None
    except ValueError:
        return None
    return value if value and value > 0 else None


def call_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    (p_in, p_out), _ = price_for(model)
    return input_tokens / 1e6 * p_in + output_tokens / 1e6 * p_out


@dataclass
class CostTracker:
    """Κόστος ενός πελάτη/χάρτη. Μεταβλητό αντικείμενο: φυλάσσεται στη
    συνεδρία και ενημερώνεται επί τόπου μετά από ΚΑΘΕ κλήση, οπότε δεν
    χάνεται αν η εκτέλεση διακοπεί. Μετρώνται και οι κομμένες απαντήσεις
    (χρεώνονται κανονικά από τον πάροχο)."""
    calls: list = field(default_factory=list)

    @property
    def total_usd(self) -> float:
        return sum(c["cost_usd"] for c in self.calls)

    @property
    def total_eur(self) -> float:
        return self.total_usd * eur_per_usd()

    @property
    def unknown_price(self) -> bool:
        return any(not c["known_price"] for c in self.calls)

    def add(self, model: str, input_tokens: int, output_tokens: int, kind: str = "", truncated: bool = False):
        _, known = price_for(model)
        self.calls.append({
            "model": model, "kind": kind, "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cost_usd": call_cost(model, input_tokens, output_tokens), "known_price": known,
            "truncated": truncated,
        })

    @staticmethod
    def input_token_upper_bound(prompt: str, counted_tokens: int | None = None) -> int:
        if counted_tokens:
            return int(counted_tokens * (1 + COUNT_MARGIN)) + FIXED_TOKEN_MARGIN
        return len((prompt or "").encode("utf-8")) + FIXED_TOKEN_MARGIN

    def output_budget(self, model: str, prompt: str, limit_usd: float | None,
                      counted_tokens: int | None = None) -> int | None:
        """Πόσα tokens εξόδου χωρούν στο υπόλοιπο του ορίου για την επόμενη
        κλήση (None = χωρίς όριο). Ο καλών ΠΕΡΙΟΡΙΖΕΙ την έξοδο του μοντέλου
        (max_tokens) σε αυτό το νούμερο· η είσοδος υπολογίζεται με ανώτατο
        όριο (βλ. input_token_upper_bound), οπότε το συνολικό κόστος δεν
        μπορεί να ξεπεράσει το όριο."""
        if not limit_usd:
            return None
        (p_in, p_out), _ = price_for(model)
        in_cost = self.input_token_upper_bound(prompt, counted_tokens) / 1e6 * p_in
        remaining = limit_usd - self.total_usd - in_cost
        return max(0, int(remaining / p_out * 1e6)) if remaining > 0 else 0

    def would_exceed(self, model: str, prompt: str, limit_usd: float | None,
                     counted_tokens: int | None = None) -> bool:
        budget = self.output_budget(model, prompt, limit_usd, counted_tokens)
        return budget is not None and budget < MIN_USEFUL_OUTPUT_TOKENS

    def format(self) -> str:
        star = " *" if self.unknown_price else ""
        return f"€{self.total_eur:.2f} / ${self.total_usd:.2f}{star} ({len(self.calls)} κλήσεις)"


# ---------------------------------------------------------------- εκτίμηση ΠΡΙΝ την ανάλυση (v18.7)
import tempfile as _tempfile
from pathlib import Path as _Path

# Τυπική έξοδος μιας απάντησης (παραδοτέο + τεχνικό δελτίο), μέχρι να
# υπάρξουν πραγματικές μετρήσεις.
DEFAULT_OUTPUT_TOKENS_ESTIMATE = 14000
_HISTORY_FILE = _Path(_tempfile.gettempdir()) / "astrocheck_career_costs.json"
_HISTORY_KEEP = 50


def _load_history(path: _Path = _HISTORY_FILE) -> list[dict]:
    try:
        data = json.loads(path.read_text())
        return [d for d in data if isinstance(d, dict)][-_HISTORY_KEEP:]
    except (OSError, ValueError, TypeError):
        return []


def record_report_cost(usd: float, calls: int, avg_output_tokens: float, path: _Path = _HISTORY_FILE) -> None:
    """Κρατά το πραγματικό κόστος κάθε εγκεκριμένης αναφοράς (μόνο αριθμοί --
    κανένα προσωπικό στοιχείο). Στο Streamlit Cloud σβήνεται σε επανεκκίνηση."""
    data = _load_history(path) + [{"usd": round(usd, 4), "calls": calls, "out": round(avg_output_tokens)}]
    try:
        path.write_text(json.dumps(data[-_HISTORY_KEEP:]))
    except OSError:
        pass


def cost_history_summary(path: _Path = _HISTORY_FILE) -> dict | None:
    data = _load_history(path)
    if not data:
        return None
    usd = sorted(d["usd"] for d in data)
    return {
        "n": len(data),
        "avg_usd": sum(usd) / len(usd),
        "min_usd": usd[0],
        "max_usd": usd[-1],
        "avg_calls": sum(d["calls"] for d in data) / len(data),
        "avg_out": sum(d["out"] for d in data) / len(data),
    }


def estimate_report_cost(model: str, prompt: str, counted_tokens: int | None = None,
                         output_tokens: float | None = None) -> dict:
    """Εκτίμηση κόστους ΠΡΙΝ την ανάλυση: από 1 κλήση (εγκρίνεται αμέσως)
    έως 3 κλήσεις (2 διορθώσεις). Κάθε διόρθωση στέλνει πίσω και την
    προηγούμενη απάντηση, άρα έχει μεγαλύτερη είσοδο."""
    in_tok = counted_tokens or int(len(prompt or "") / 2)  # ~2 χαρακτήρες/token για ελληνικά
    out_tok = output_tokens or DEFAULT_OUTPUT_TOKENS_ESTIMATE
    (p_in, p_out), known = price_for(model)
    first = in_tok / 1e6 * p_in + out_tok / 1e6 * p_out
    correction = (in_tok + out_tok) / 1e6 * p_in + out_tok / 1e6 * p_out
    return {"low_usd": first, "high_usd": first + 2 * correction, "input_tokens": in_tok,
            "output_tokens": int(out_tok), "counted": bool(counted_tokens), "known_price": known}
