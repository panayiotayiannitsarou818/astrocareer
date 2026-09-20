"""
Νέο test, ύστερα από την κριτική: το core/case_state.py εξήχθη ρητά από το
app.py ΓΙΑ να είναι testable χωρίς Streamlit runtime (βλ. το ίδιο του το
docstring) -- ειδικά το πραγματικό περιστατικό που το δικαιολόγησε: session
state να "διαρρέει" δεδομένα προηγούμενου πελάτη όταν κάποιος ανεβάζει
απευθείας νέο PDF, χωρίς προηγούμενο πάτημα "Νέα ανάλυση". Παρ' όλα αυτά δεν
υπήρχε κανένα test. Αυτό το αρχείο καλύπτει reset_case_state() και
handle_pdf_upload() με ένα ελαφρύ ψεύτικο state, όπως προβλέπει το ίδιο το
module -- χωρίς Streamlit, χωρίς πραγματικό PDF.
"""
import pytest

from core.case_state import CASE_STATE_KEYS, handle_pdf_upload, reset_case_state


class FakeState:
    """Ελάχιστο ψεύτικο session_state: attribute get/set + pop(key, default),
    ακριβώς η επιφάνεια που περιμένει το case_state.py."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def pop(self, key, default=None):
        return self.__dict__.pop(key, default)

    def get(self, key, default=None):
        return self.__dict__.get(key, default)


def _populated_state(**extra):
    state = FakeState(chart="OLD_CHART", uploader_gen=2)
    for key in CASE_STATE_KEYS:
        state.__dict__[key] = f"leftover-{key}"
    state.analysis = "κάποιο παλιό κείμενο"
    state.validation = "κάποιο παλιό αποτέλεσμα"
    state.analysis_docx_bytes = b"old-bytes"
    state.analysis_docx_name = "old.docx"
    state.__dict__.update(extra)
    return state


def test_reset_case_state_clears_all_case_keys():
    state = _populated_state()
    reset_case_state(state)
    for key in CASE_STATE_KEYS:
        assert not hasattr(state, key) or key not in state.__dict__


def test_reset_case_state_resets_core_analysis_fields():
    state = _populated_state()
    reset_case_state(state)
    assert state.analysis == ''
    assert state.validation is None
    assert state.analysis_docx_bytes is None
    assert state.analysis_docx_name == ''


def test_reset_case_state_never_touches_chart_or_uploader_gen():
    """reset_case_state αφήνει σκόπιμα το chart/uploader_gen στον καλούντα
    (app.py «Νέα ανάλυση» ή handle_pdf_upload) -- δεν πρέπει ποτέ να τα αγγίξει."""
    state = _populated_state()
    reset_case_state(state)
    assert state.chart == "OLD_CHART"
    assert state.uploader_gen == 2


def _fake_parse_ok(pdf_bytes, pdf_name):
    return f"CHART[{pdf_name}]"


def _fake_parse_fail(pdf_bytes, pdf_name):
    raise ValueError("δεν αναγνωρίστηκε το PDF")


def test_handle_pdf_upload_success_clears_previous_case_and_stores_new_chart():
    """Το πραγματικό bug που δικαιολόγησε το module: απευθείας αντικατάσταση
    PDF (χωρίς «Νέα ανάλυση») δεν πρέπει να αφήνει πίσω όνομα/πλαίσιο/παλιά
    bytes του προηγούμενου πελάτη."""
    state = _populated_state()
    ok, chart, err = handle_pdf_upload(b"bytes", "new.pdf", state=state, parse_fn=_fake_parse_ok)

    assert ok is True
    assert err is None
    assert chart == "CHART[new.pdf]"
    assert state.chart == "CHART[new.pdf]"
    for key in CASE_STATE_KEYS:
        assert not hasattr(state, key) or key not in state.__dict__


def test_handle_pdf_upload_success_increments_uploader_gen():
    state = _populated_state(uploader_gen=2)
    handle_pdf_upload(b"bytes", "new.pdf", state=state, parse_fn=_fake_parse_ok)
    assert state.uploader_gen == 3


def test_handle_pdf_upload_success_from_missing_uploader_gen_starts_at_one():
    state = FakeState()
    handle_pdf_upload(b"bytes", "new.pdf", state=state, parse_fn=_fake_parse_ok)
    assert state.uploader_gen == 1


def test_handle_pdf_upload_failure_leaves_existing_case_completely_untouched():
    """«Σε αποτυχία parsing, ΔΕΝ αγγίζεται καμία υπάρχουσα κατάσταση -- ένα
    λάθος ανέβασμα δεν πρέπει να διαγράψει μια ήδη έγκυρη περίπτωση.» (docstring)"""
    state = _populated_state()
    ok, chart, err = handle_pdf_upload(b"bad-bytes", "bad.pdf", state=state, parse_fn=_fake_parse_fail)

    assert ok is False
    assert chart is None
    assert isinstance(err, ValueError)
    assert state.chart == "OLD_CHART"
    assert state.uploader_gen == 2
    for key in CASE_STATE_KEYS:
        assert key in state.__dict__
