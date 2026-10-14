"""
Fix (πρόβλημα #11 από τη σταθερή λίστα ελέγχου): πριν, κάθε σφάλμα κατά την
αυτόματη δημιουργία (ληγμένο API key, χωρίς σύνδεση internet, όριο
αιτημάτων, timeout, σφάλμα διακομιστή του OpenAI) έδειχνε το ΙΔΙΟ γενικό
μήνυμα "Η αυτόματη δημιουργία απέτυχε" -- αδιακρίτως από αποτυχία validation,
που είχε το δικό της, σαφές μήνυμα. Αυτά τα tests επιβεβαιώνουν ότι κάθε
γνωστός τύπος σφάλματος OpenAI API ταξινομείται στο σωστό, ξεχωριστό κλειδί.
"""
try:
    import httpx
except ImportError:  # αυτή η έκδοση του openai SDK χρησιμοποιεί εσωτερικά το httpx2
    import httpx2 as httpx
import openai
import pytest

from core.generator import classify_generation_error


def _response(status_code=500):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return httpx.Response(status_code, request=request, json={"error": {"message": "test"}})


@pytest.mark.parametrize(
    "exc, expected",
    [
        (openai.AuthenticationError("bad key", response=_response(401), body=None), "auth"),
        (openai.RateLimitError("rate limited", response=_response(429), body=None), "rate_limit"),
        (openai.InternalServerError("server broke", response=_response(500), body=None), "server"),
    ],
)
def test_status_based_errors_classified_correctly(exc, expected):
    assert classify_generation_error(exc) == expected


def test_timeout_error_classified_as_timeout_not_connection():
    """Το APITimeoutError είναι υποκλάση του APIConnectionError -- πρέπει να
    ταξινομείται ως "timeout" (πιο συγκεκριμένο), όχι ως "connection"."""
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    exc = openai.APITimeoutError(request=request)
    assert classify_generation_error(exc) == "timeout"


def test_connection_error_classified_as_connection():
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    exc = openai.APIConnectionError(request=request)
    assert classify_generation_error(exc) == "connection"


def test_unrelated_exception_classified_as_other():
    """Ένα σφάλμα που δεν είναι γνωστός τύπος OpenAI API (π.χ. bug στον
    δικό μας κώδικα) πρέπει να ταξινομείται ως "other" -- γενικό μήνυμα,
    με το τεχνικό detail ορατό όπως πριν."""
    assert classify_generation_error(ValueError("κάτι άσχετο")) == "other"
    assert classify_generation_error(TimeoutError("timeout του Python, όχι του openai")) == "other"


# v17: τα ίδια κλειδιά ισχύουν και για τον πάροχο Anthropic (Claude).
import anthropic


def _a_response(status_code):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx.Response(status_code, request=request, json={"error": {"message": "test"}})


@pytest.mark.parametrize(
    "exc, expected",
    [
        (anthropic.AuthenticationError("bad key", response=_a_response(401), body=None), "auth"),
        (anthropic.RateLimitError("rate limited", response=_a_response(429), body=None), "rate_limit"),
        (anthropic.InternalServerError("server broke", response=_a_response(500), body=None), "server"),
        (anthropic.APIStatusError("overloaded", response=_a_response(529), body=None), "server"),
        (anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com")), "timeout"),
        (anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")), "connection"),
    ],
)
def test_anthropic_errors_classified_correctly(exc, expected):
    assert classify_generation_error(exc) == expected


# v18: μόνιμα σφάλματα -- ο κύκλος σταματά αμέσως αντί να ξαναδοκιμάζει.
def test_openai_insufficient_quota_is_no_credit_not_rate_limit():
    exc = openai.RateLimitError("You exceeded your current quota", response=_response(429),
                                body={"code": "insufficient_quota"})
    assert classify_generation_error(exc) == "no_credit"


def test_model_not_found_both_providers():
    assert classify_generation_error(openai.NotFoundError("model does not exist", response=_response(404), body=None)) == "model_not_found"
    assert classify_generation_error(anthropic.NotFoundError("model: x", response=_a_response(404), body=None)) == "model_not_found"


def test_anthropic_low_credit_is_no_credit():
    exc = anthropic.BadRequestError("Your credit balance is too low to access the Anthropic API.",
                                    response=_a_response(400), body=None)
    assert classify_generation_error(exc) == "no_credit"
