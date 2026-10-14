"""
v18 -- αυτόματη διαδικασία (core/pipeline.py): κύκλος διόρθωσης, γύρος
ποιότητας, πρόωρες διακοπές, κόστος, συνέχεια μετά από διακοπή.

Ψεύτικο generate_fn (καμία πραγματική κλήση API) με τα ίδια έγκυρα/άκυρα
κείμενα του test_docx_round_trip.py.
"""
import pytest

try:
    import httpx
except ImportError:  # νεότερο openai SDK
    import httpx2 as httpx
import openai

from core import pipeline
from core.costs import CostTracker
from core.generator import GenerationResult
from core.pipeline import RunState, Settings, run_pipeline
from core.prompts import ORIENTATION_CLIENT_MARKER, ORIENTATION_RESPONSE_DELIMITER
from core.reference_loader import simple_docx_format_issues
from tests.test_docx_round_trip import CHART, _build_audit_text, _build_client_text


def _raw(client, audit):
    return f"{ORIENTATION_CLIENT_MARKER}\n{client}\n{ORIENTATION_RESPONSE_DELIMITER}\n{audit}"


GOOD = _raw(_build_client_text(3), _build_audit_text(3))
# Ίδιο περιεχόμενο, άλλο ύφος στο προφίλ (για τον γύρο ποιότητας).
GOOD_RESTYLED = GOOD.replace("Test. " + " ".join(["λέξη"] * 100), "Test. " + " ".join(["φράση"] * 105))
# «Βελτίωση» ύφους που όμως έκοψε το μισό προφίλ -- πρέπει να απορριφθεί.
GOOD_SHORTENED = GOOD.replace("Test. " + " ".join(["λέξη"] * 100), "Test. " + " ".join(["λέξη"] * 2))
# Μέτρια: σωστό παραδοτέο, τεχνικό δελτίο χωρίς λίστα επαγγελμάτων.
MEDIUM = _raw(_build_client_text(3), _build_audit_text(3).split("ΕΓΚΕΚΡΙΜΕΝΑ ΕΠΑΓΓΕΛΜΑΤΑ")[0])
BAD = "Ένα κείμενο χωρίς καμία από τις απαιτούμενες ενότητες."


def _n_issues(raw):
    check = pipeline.evaluate_response(CHART, "Test", raw)[0]
    return 0 if check.ok else len(check.details_lines())


class FakeModel:
    """Δίνει τις απαντήσεις με τη σειρά· η τελευταία επαναλαμβάνεται."""
    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []
        self.limits = []

    def __call__(self, prompt, max_output_tokens=None):
        self.prompts.append(prompt)
        self.limits.append(max_output_tokens)
        item = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(item, BaseException):
            raise item
        return item


def S(**kw):
    base = dict(stall_rounds=4, fresh_rounds=1, max_failed_requests=5, max_attempts=30,
                max_cost_usd=None, quality_pass=False)
    base.update(kw)
    return Settings(**base)


def run(model, settings=None, **kw):
    return run_pipeline(CHART, "Test", "el", generate_fn=model, settings=settings or S(),
                        sleep_fn=lambda s: None, **kw)


def _conn_error():
    return openai.APIConnectionError(request=httpx.Request("POST", "https://x"))


def _status(cls, status, msg="x", **body):
    return cls(msg, response=httpx.Response(status, request=httpx.Request("POST", "https://x")), body=body or None)


def test_fixtures_are_ordered_as_expected():
    assert _n_issues(GOOD) == 0 and _n_issues(GOOD_RESTYLED) == 0
    assert 0 < _n_issues(MEDIUM) < _n_issues(BAD)


def test_built_client_docx_has_no_forbidden_formatting():
    _, _, _, client_docx, _ = pipeline.evaluate_response(CHART, "Test", GOOD)
    assert simple_docx_format_issues(client_docx) == []


# ---------------------------------------------------------------- κύκλος διόρθωσης

def test_approved_on_first_attempt():
    r = run(FakeModel([GOOD]))
    assert r.ok and r.attempts == 1 and r.stopped_reason == "approved"
    assert r.client_docx and r.audit_docx


def test_keeps_going_beyond_three_rounds_while_improving():
    r = run(FakeModel([BAD, MEDIUM, MEDIUM, MEDIUM, GOOD]))
    assert r.ok and r.attempts == 5


def test_correction_starts_from_best_attempt_not_last():
    """Η 3η κλήση πρέπει να διορθώνει το MEDIUM (καλύτερο), όχι το BAD (τελευταίο)."""
    model = FakeModel([MEDIUM, BAD, GOOD])
    run(model)
    correction = model.prompts[2].split("Η ΠΡΟΗΓΟΥΜΕΝΗ ΣΟΥ ΑΠΑΝΤΗΣΗ")[1]
    assert "Συνοπτικά, τα ταλέντα" in correction and "Ένα κείμενο χωρίς" not in correction


def test_stops_when_errors_do_not_decrease_and_keeps_best():
    r = run(FakeModel([MEDIUM, BAD]), S(stall_rounds=3))
    assert not r.ok and r.stopped_reason == "stalled"
    assert r.attempts == 4                      # 1 βελτίωση + 3 χωρίς πρόοδο
    assert r.raw == MEDIUM                      # κρατά την καλύτερη, όχι την τελευταία


def test_fresh_round_after_stall_can_still_succeed():
    model = FakeModel([BAD, BAD, GOOD])
    r = run(model, S(stall_rounds=1, fresh_rounds=2))
    assert r.ok
    assert "Η ΠΡΟΗΓΟΥΜΕΝΗ ΣΟΥ ΑΠΑΝΤΗΣΗ" not in model.prompts[2]   # καθαρή νέα γραφή


def test_truncated_answer_is_counted_and_not_used_as_best():
    cut = GenerationResult(text=GOOD[:200], model="claude-opus-5-5", input_tokens=1000, output_tokens=32000, truncated=True)
    model = FakeModel([cut, GOOD])
    r = run(model)
    assert r.ok and r.attempts == 2
    assert r.cost.calls[0]["truncated"] and r.cost.calls[0]["cost_usd"] > 0
    assert "κόπηκε" in model.prompts[1]


# ---------------------------------------------------------------- σφάλματα

def test_permanent_error_stops_immediately_keeping_best():
    r = run(FakeModel([MEDIUM, _status(openai.AuthenticationError, 401)]))
    assert not r.ok and r.stopped_reason == "permanent_error" and r.error_key == "auth"
    assert r.raw == MEDIUM and r.attempts == 1


def test_openai_insufficient_quota_is_permanent_not_retried():
    exc = _status(openai.RateLimitError, 429, code="insufficient_quota")
    exc.code = "insufficient_quota"
    model = FakeModel([exc])
    r = run(model)
    assert r.error_key == "no_credit" and len(model.prompts) == 1


def test_transient_errors_retried_then_stop_after_five_in_a_row():
    model = FakeModel([_conn_error()])
    r = run(model, S(max_failed_requests=5))
    assert r.stopped_reason == "api_failures" and len(model.prompts) == 5 and r.raw is None


def test_transient_error_then_success():
    r = run(FakeModel([_conn_error(), _conn_error(), GOOD]))
    assert r.ok and r.attempts == 1


# ---------------------------------------------------------------- κόστος

def test_cost_counted_per_model():
    res = GenerationResult(text=GOOD, model="claude-opus-5-5", input_tokens=1_000_000, output_tokens=1_000_000)
    r = run(FakeModel([res]))
    assert r.cost.total_usd == pytest.approx(24.0)       # Opus 5.5: 4 + 20
    sonnet = GenerationResult(text=GOOD, model="claude-sonnet-5-5", input_tokens=1_000_000, output_tokens=0)
    assert run(FakeModel([sonnet])).cost.total_usd == pytest.approx(2.0)   # Sonnet 5.5: $2 είσοδος


def test_cost_limit_checked_before_each_call():
    res = GenerationResult(text=MEDIUM, model="claude-opus-5-5", input_tokens=20000, output_tokens=12000)
    model = FakeModel([res])
    r = run(model, S(max_cost_usd=1.0), model_name="claude-opus-5-5")
    assert r.stopped_reason == "cost_limit"
    assert r.cost.total_usd <= 1.0
    assert r.raw == MEDIUM                              # κρατά την καλύτερη


def test_cost_tracker_is_shared_and_not_reset_between_runs():
    cost = CostTracker()
    res = GenerationResult(text=GOOD, model="gpt-5.4", input_tokens=1_000_000, output_tokens=0)
    run(FakeModel([res]), cost=cost)
    run(FakeModel([res]), cost=cost)
    assert cost.total_usd == pytest.approx(5.0)


# ---------------------------------------------------------------- γύρος ποιότητας

def test_quality_round_kept_when_still_approved_and_complete():
    r = run(FakeModel([GOOD, GOOD_RESTYLED]), S(quality_pass=True))
    assert r.ok and r.quality_applied and r.raw == GOOD_RESTYLED and r.attempts == 2


def test_quality_round_rejected_if_content_shrinks():
    r = run(FakeModel([GOOD, GOOD_SHORTENED]), S(quality_pass=True))
    assert r.ok and not r.quality_applied and r.raw == GOOD


def test_quality_round_rejected_if_it_fails_validation():
    r = run(FakeModel([GOOD, BAD]), S(quality_pass=True))
    assert r.ok and not r.quality_applied and r.raw == GOOD


def test_quality_round_error_keeps_approved_text():
    r = run(FakeModel([GOOD, _status(openai.AuthenticationError, 401)]), S(quality_pass=True))
    assert r.ok and r.raw == GOOD


# ---------------------------------------------------------------- συνέχεια

def test_resume_continues_from_best_without_rewriting():
    state, cost = None, CostTracker()
    first = run(FakeModel([MEDIUM, _conn_error()]), S(max_failed_requests=1), cost=cost)
    assert first.stopped_reason == "api_failures" and first.resumable
    state = first.state
    model = FakeModel([GOOD])
    second = run(model, state=state, cost=cost)
    assert second.ok
    assert "Η ΠΡΟΗΓΟΥΜΕΝΗ ΣΟΥ ΑΠΑΝΤΗΣΗ" in model.prompts[0]    # διόρθωση, όχι νέα γραφή
    assert second.attempts == 2


def test_resume_after_approval_only_runs_quality_round():
    first = run(FakeModel([GOOD, _status(openai.AuthenticationError, 401)]), S(quality_pass=False))
    model = FakeModel([GOOD_RESTYLED])
    second = run(model, S(quality_pass=True), state=first.state)
    assert len(model.prompts) == 1 and "ΓΥΡΟΣ ΠΟΙΟΤΗΤΑΣ" in model.prompts[0]
    assert second.ok


def test_changed_language_restarts_from_scratch():
    first = run(FakeModel([MEDIUM, _conn_error()]), S(max_failed_requests=1))
    model = FakeModel([GOOD])
    run_pipeline(CHART, "Test", "en", generate_fn=model, settings=S(), state=first.state, sleep_fn=lambda s: None)
    assert "YOUR PREVIOUS ANSWER" not in model.prompts[0] and "Η ΠΡΟΗΓΟΥΜΕΝΗ" not in model.prompts[0]


def test_state_is_updated_in_place_for_interruptions():
    """Η πρόοδος γράφεται στο ΙΔΙΟ αντικείμενο αμέσως -- αν η εκτέλεση
    διακοπεί απότομα (π.χ. KeyboardInterrupt/rerun), η βελτίωση έχει ήδη σωθεί."""
    state = RunState(fingerprint=pipeline.fingerprint(CHART, "Test", "el"))

    class Boom(BaseException):
        pass

    with pytest.raises(Boom):
        run(FakeModel([MEDIUM, Boom()]), state=state)
    assert state.best_raw == MEDIUM


# ---------------------------------------------------------------- διάφορα

def test_english_prompt_contains_english_headings():
    prompt = pipeline.build_auto_prompt(CHART, "Maria", "en")
    assert "Brief Profile" in prompt and 'Client name: "Maria"' in prompt


def test_filenames_keep_greek_names():
    assert pipeline.client_docx_filename("Γαβριέλα Δοε") == "Γαβριέλα_Δοε_AstroCheck_Anadeixi_Talenton.docx"
    assert pipeline.audit_docx_filename("Γαβριέλα Δοε") == "Γαβριέλα_Δοε_Εσωτερικό_Τεχνικό_Δελτίο.docx"


# ---------------------------------------------------------------- v18.1: εξωτερική κριτική #3-#5

def test_resume_after_max_attempts_really_makes_new_calls():
    """Κριτική #3: μετά το όριο κλήσεων, η «Συνέχεια» έκανε ΜΗΔΕΝ νέες κλήσεις."""
    first = run(FakeModel([MEDIUM, BAD, BAD]), S(max_attempts=2, stall_rounds=10))
    assert first.stopped_reason == "max_attempts" and first.resumable
    model = FakeModel([GOOD])
    second = run(model, S(max_attempts=2, stall_rounds=10), state=first.state)
    assert len(model.prompts) == 1 and second.ok


def test_truncated_then_fresh_failure_does_not_crash():
    """Κριτική #4: κομμένη πρώτη απάντηση -> νέα αρχή -> αποτυχία ελέγχου
    έκανε len(None) και κατέρρεε με TypeError."""
    cut = GenerationResult(text=GOOD[:100], model="m", truncated=True)
    r = run(FakeModel([cut, BAD, GOOD]), S(stall_rounds=1, fresh_rounds=3))
    assert r.ok


class BudgetModel:
    """Ψεύτικος πάροχος που σέβεται το max_output_tokens όπως ο πραγματικός:
    θέλει να γράψει 30.000 tokens, κόβεται αν του δοθεί μικρότερο όριο."""
    def __init__(self, text=MEDIUM, wanted=30000):
        self.text, self.wanted, self.limits = text, wanted, []

    def __call__(self, prompt, max_output_tokens=None):
        self.limits.append(max_output_tokens)
        out = self.wanted if max_output_tokens is None else min(self.wanted, max_output_tokens)
        return GenerationResult(text=self.text if out == self.wanted else self.text[:50], model="claude-opus-5-5",
                                input_tokens=len(prompt) // 2, output_tokens=out, truncated=out < self.wanted)


@pytest.mark.parametrize("cap", [0.5, 1.0, 2.0, 5.0])
def test_cost_cap_is_a_real_ceiling(cap):
    """Κριτική #5: με όριο $0,50 μια κλήση εκτιμήθηκε $0,305 αλλά κόστισε
    $0,805. Τώρα το όριο εξόδου κάθε κλήσης περιορίζεται ώστε να χωρά στο
    υπόλοιπο -- το συνολικό κόστος δεν ξεπερνά ποτέ το όριο."""
    model = BudgetModel()
    r = run(model, S(max_cost_usd=cap, stall_rounds=50, max_attempts=50), model_name="claude-opus-5-5")
    assert r.cost.total_usd <= cap + 1e-9, (cap, r.cost.total_usd)
    assert r.stopped_reason == "cost_limit"


def test_opus_5_5_official_price():
    from core.costs import price_for
    assert price_for("claude-opus-5-5")[0] == (4.0, 20.0)
    assert price_for("claude-sonnet-5-5")[0] == (2.0, 10.0)
    assert price_for("claude-opus-5")[0] == (5.0, 25.0)
