import openai


def generate_analysis(api_key: str, prompt: str, model: str = "gpt-5.4") -> str:
    client=openai.OpenAI(api_key=api_key)
    response=client.responses.create(
        model=model,
        input=prompt,
        reasoning={"effort":"high"},
        text={"verbosity":"high"},
    )
    return response.output_text


def classify_generation_error(exc: BaseException) -> str:
    """Αντιστοιχίζει μια εξαίρεση από το generate_analysis() σε ένα από τα
    ειδικά κλειδιά i18n μηνύματος σφάλματος (auto_error_<key>), ή "other"
    για ό,τι δεν είναι ένα από τα γνωστά, χειριζόμενα σφάλματα OpenAI API.

    Fix (πρόβλημα #11 από τη σταθερή λίστα ελέγχου): πριν όλα τα σφάλματα
    API/δικτύου έδειχναν το ΙΔΙΟ γενικό μήνυμα "Η αυτόματη δημιουργία
    απέτυχε" -- ένας χρήστης με ληγμένο API key ή χωρίς σύνδεση internet
    δεν είχε κανέναν τρόπο να καταλάβει τι φταίει. Εξάγεται σε ξεχωριστή
    συνάρτηση ώστε η αντιστοίχιση να ελέγχεται με tests χωρίς να απαιτείται
    ολόκληρη προσομοίωση της διεπαφής Streamlit.

    Η σειρά ελέγχου έχει σημασία: το APITimeoutError είναι υποκλάση του
    APIConnectionError, άρα πρέπει να ελέγχεται πρώτο· τα AuthenticationError/
    RateLimitError/InternalServerError είναι υποκλάσεις του APIStatusError/
    APIError, άρα και αυτά πρέπει να ελέγχονται πριν το γενικό APIError.
    """
    if isinstance(exc, openai.AuthenticationError):
        return "auth"
    if isinstance(exc, openai.RateLimitError):
        return "rate_limit"
    if isinstance(exc, openai.APITimeoutError):
        return "timeout"
    if isinstance(exc, openai.APIConnectionError):
        return "connection"
    if isinstance(exc, openai.InternalServerError):
        return "server"
    return "other"

