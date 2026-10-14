"""
generator.py
============
Κλήση του γλωσσικού μοντέλου για την αυτόματη δημιουργία.

Πάροχοι: "anthropic" (Claude, προεπιλογή) και "openai" (GPT).
Το μοντέλο αλλάζει χωρίς αλλαγή κώδικα: ANTHROPIC_MODEL / OPENAI_MODEL.

Από τη v18 κάθε κλήση επιστρέφει GenerationResult με το κείμενο ΚΑΙ τα
tokens που χρεώθηκαν (για τον μετρητή κόστους) και αν η απάντηση κόπηκε
λόγω ορίου μήκους.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import openai

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


PROVIDERS = ("anthropic", "openai")
PROVIDER_LABELS = {"anthropic": "Claude (Anthropic)", "openai": "OpenAI (GPT)"}
DEFAULT_PROVIDER = "anthropic"
DEFAULT_MODELS = {"anthropic": "claude-opus-5-5", "openai": "gpt-5.4"}
API_KEY_NAMES = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}

# Η απάντηση περιέχει ΚΑΙ το καθαρό παραδοτέο ΚΑΙ το πλήρες τεχνικό δελτίο.
ANTHROPIC_MAX_TOKENS = 32000


@dataclass
class GenerationResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    truncated: bool = False   # κόπηκε λόγω ορίου μήκους


def default_model(provider: str) -> str:
    env_name = "ANTHROPIC_MODEL" if provider == "anthropic" else "OPENAI_MODEL"
    return os.environ.get(env_name) or DEFAULT_MODELS[provider]


def _generate_openai(api_key: str, prompt: str, model: str, max_output_tokens: int | None = None) -> GenerationResult:
    client = openai.OpenAI(api_key=api_key)
    extra = {"max_output_tokens": max_output_tokens} if max_output_tokens else {}
    response = client.responses.create(
        model=model, input=prompt,
        reasoning={"effort": "high"}, text={"verbosity": "high"}, **extra,
    )
    usage = getattr(response, "usage", None)
    details = getattr(response, "incomplete_details", None)
    truncated = getattr(response, "status", "") == "incomplete" and (
        details is None or getattr(details, "reason", "") == "max_output_tokens")
    return GenerationResult(
        text=response.output_text or "", model=model,
        # Τα reasoning tokens περιλαμβάνονται ήδη στα output_tokens -- χρεώνονται.
        input_tokens=getattr(usage, "input_tokens", 0) or 0,
        output_tokens=getattr(usage, "output_tokens", 0) or 0,
        truncated=truncated,
    )


def _generate_anthropic(api_key: str, prompt: str, model: str, max_output_tokens: int | None = None) -> GenerationResult:
    if anthropic is None:
        raise RuntimeError("Λείπει η βιβλιοθήκη 'anthropic' -- πρόσθεσέ τη στο requirements.txt.")
    client = anthropic.Anthropic(api_key=api_key)
    # Streaming: οι μεγάλες απαντήσεις μπορεί να ξεπεράσουν το χρονικό όριο
    # ενός απλού αιτήματος.
    with client.messages.stream(
        model=model, max_tokens=min(ANTHROPIC_MAX_TOKENS, max_output_tokens or ANTHROPIC_MAX_TOKENS),
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()
    text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
    usage = message.usage
    return GenerationResult(
        text=text, model=model,
        input_tokens=(usage.input_tokens or 0) + (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        + (getattr(usage, "cache_read_input_tokens", 0) or 0),
        output_tokens=usage.output_tokens or 0,
        truncated=message.stop_reason == "max_tokens",
    )


def generate(api_key: str, prompt: str, model: str | None = None, provider: str = DEFAULT_PROVIDER,
             max_output_tokens: int | None = None) -> GenerationResult:
    """max_output_tokens: ανώτατο όριο εξόδου για ΑΥΤΗ την κλήση (το
    χρησιμοποιεί το όριο κόστους). Για το OpenAI περιλαμβάνει και τα
    reasoning tokens -- όπως ακριβώς χρεώνονται."""
    if provider not in PROVIDERS:
        raise ValueError(f"Άγνωστος πάροχος: {provider}")
    model = model or default_model(provider)
    if provider == "anthropic":
        return _generate_anthropic(api_key, prompt, model, max_output_tokens)
    return _generate_openai(api_key, prompt, model, max_output_tokens)


def count_input_tokens(api_key: str, prompt: str, model: str | None = None,
                       provider: str = DEFAULT_PROVIDER) -> int | None:
    """Ακριβής καταμέτρηση tokens εισόδου ΠΡΙΝ την κλήση (μόνο Anthropic,
    endpoint count_tokens). Επιστρέφει None αν δεν είναι διαθέσιμη ή
    αποτύχει -- τότε το όριο κόστους χρησιμοποιεί το μαθηματικό ανώτατο
    όριο (costs.input_token_upper_bound). Καλείται μόνο όταν υπάρχει όριο."""
    if provider != "anthropic" or anthropic is None:
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        result = client.messages.count_tokens(
            model=model or default_model(provider),
            messages=[{"role": "user", "content": prompt}],
        )
        return int(result.input_tokens)
    except Exception:  # noqa: BLE001 -- ποτέ μη σταματά τη δουλειά για καταμέτρηση
        return None


def generate_analysis(api_key: str, prompt: str, model: str | None = None, provider: str = "openai") -> str:
    """Συμβατότητα με παλιό κώδικα: επιστρέφει μόνο το κείμενο."""
    return generate(api_key, prompt, model=model, provider=provider).text


# ---------------------------------------------------------------- σφάλματα

def _classes(name):
    out = [getattr(openai, name)] if hasattr(openai, name) else []
    if anthropic is not None and hasattr(anthropic, name):
        out.append(getattr(anthropic, name))
    return tuple(out)


def is_api_error(exc: BaseException) -> bool:
    return isinstance(exc, _classes("APIError"))


# Σφάλματα που ΔΕΝ διορθώνονται με αναμονή/νέα δοκιμή -- ο κύκλος σταματά αμέσως.
PERMANENT_ERROR_KEYS = {"auth", "model_not_found", "no_credit", "bad_request"}
# Σφάλματα που συνήθως περνούν μόνα τους -- νέα δοκιμή μετά από αναμονή.
TRANSIENT_ERROR_KEYS = {"rate_limit", "server", "timeout", "connection"}


def _error_text(exc) -> str:
    body = getattr(exc, "body", None)
    return f"{exc} {body}".lower()


def classify_generation_error(exc: BaseException) -> str:
    """Αντιστοιχίζει μια εξαίρεση σε κλειδί μηνύματος (auto_error_<key>).

    Η σειρά έχει σημασία: APITimeoutError ⊂ APIConnectionError, και όλα τα
    σφάλματα κατάστασης ⊂ APIStatusError ⊂ APIError.

    Σημαντικό (v18): το OpenAI επιστρέφει «χωρίς υπόλοιπο» (insufficient_quota)
    ως RateLimitError 429 -- ίδια κλάση με το προσωρινό «πολλά αιτήματα».
    Πριν ξαναδοκιμαζόταν άσκοπα· τώρα αναγνωρίζεται ως μόνιμο (no_credit).
    Το Anthropic επιστρέφει το χαμηλό υπόλοιπο ως 400 «credit balance».
    """
    text = _error_text(exc) if is_api_error(exc) else ""
    if isinstance(exc, _classes("AuthenticationError") + _classes("PermissionDeniedError")):
        return "auth"
    if isinstance(exc, _classes("RateLimitError")):
        if getattr(exc, "code", None) == "insufficient_quota" or "insufficient_quota" in text:
            return "no_credit"
        return "rate_limit"
    if isinstance(exc, _classes("NotFoundError")):
        return "model_not_found"
    if isinstance(exc, _classes("APITimeoutError")):
        return "timeout"
    if isinstance(exc, _classes("APIConnectionError")):
        return "connection"
    if isinstance(exc, _classes("InternalServerError")):
        return "server"
    if isinstance(exc, _classes("APIStatusError")):
        status = getattr(exc, "status_code", None)
        if status == 529:  # Anthropic "overloaded"
            return "server"
        if status == 402 or "credit balance" in text or "billing" in text:
            return "no_credit"
        if status in (400, 404, 422):
            return "model_not_found" if "model" in text and ("not found" in text or "does not exist" in text) else "bad_request"
    return "other"
