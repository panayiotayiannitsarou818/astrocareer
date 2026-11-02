"""v22.39: πληρωμή μέσω Stripe Checkout (χωρίς δίκτυο -- ψεύτικο http)."""
import pytest

from core.payments import (PaymentError, case_fingerprint, create_checkout, format_price, is_paid,
                           parse_price)


def test_price_parsing_and_format():
    assert parse_price("20") == 2000
    assert parse_price("19,90") == 1990
    assert parse_price("19.90 €") == 1990
    assert parse_price("abc") == 2000 and parse_price("0") == 2000
    assert format_price(2000) == "20 €" and format_price(1990) == "19,90 €"


def test_fingerprint_is_stable_and_hides_birth_data():
    key = ("Παναγιώτα", "1982-02-11", "01:45", 34.77, 32.42)
    fp = case_fingerprint(key)
    assert fp == case_fingerprint(key) and len(fp) == 40
    assert "1982" not in fp and fp != case_fingerprint(key[:-1])


def test_checkout_sends_no_birth_data_and_returns_url():
    sent = {}

    def http(method, url, key, data=None):
        sent.update(method=method, url=url, key=key, data=data)
        return {"id": "cs_test_123", "url": "https://checkout.stripe.com/c/pay/cs_test_123"}

    fp = case_fingerprint(("x", "1982-02-11"))
    co = create_checkout("sk_test_abc", amount_cents=2000, product_name="AstroCheck", fingerprint=fp,
                         success_url="https://a.app/?paid={CHECKOUT_SESSION_ID}", cancel_url="https://a.app/",
                         http=http)
    assert co.id == "cs_test_123" and co.url.startswith("https://checkout.stripe.com")
    d = sent["data"]
    assert sent["method"] == "POST" and d["mode"] == "payment"
    assert d["line_items[0][price_data][unit_amount]"] == "2000"
    assert d["line_items[0][price_data][currency]"] == "eur"
    assert d["client_reference_id"] == fp and d["allow_promotion_codes"] == "true"
    assert "{CHECKOUT_SESSION_ID}" in d["success_url"]
    assert not any("1982" in str(v) for v in d.values())


def test_is_paid_requires_paid_status_and_same_case():
    fp = case_fingerprint(("a",))
    paid = lambda *a, **k: {"payment_status": "paid", "client_reference_id": fp}
    unpaid = lambda *a, **k: {"payment_status": "unpaid", "client_reference_id": fp}
    other = lambda *a, **k: {"payment_status": "paid", "client_reference_id": "zzz"}
    assert is_paid("sk_test", "cs_test_1", fp, http=paid)
    assert not is_paid("sk_test", "cs_test_1", fp, http=unpaid)
    assert not is_paid("sk_test", "cs_test_1", fp, http=other)    # άλλα στοιχεία: όχι
    assert not is_paid("sk_test", "../evil", fp, http=paid)       # άκυρο id: ούτε κλήση


def test_bad_response_raises():
    with pytest.raises(PaymentError):
        create_checkout("sk_test", amount_cents=2000, product_name="x", fingerprint="f",
                        success_url="u", cancel_url="u", http=lambda *a, **k: {})


def test_app_has_no_hardcoded_stripe_key():
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parents[1]
    for path in list(root.glob("*.py")) + list((root / "core").glob("*.py")):
        assert not re.search(r"[sr]k_(test|live)_[A-Za-z0-9]{8,}", path.read_text(encoding="utf-8")), path


def test_check_paid_returns_customer_email():
    from core.payments import check_paid
    fp = case_fingerprint(("a",))
    http = lambda *a, **k: {"payment_status": "paid", "client_reference_id": fp,
                            "customer_details": {"email": "x@example.com"}}
    assert check_paid("sk_test", "cs_test_1", fp, http=http) == (True, "x@example.com")
    other = lambda *a, **k: {"payment_status": "paid", "client_reference_id": "zz",
                             "customer_details": {"email": "x@example.com"}}
    assert check_paid("sk_test", "cs_test_1", fp, http=other) == (False, "")


def test_email_report_attaches_docx():
    import base64
    from core.emailer import EmailError, send_report
    got = {}

    def http(payload, key):
        got.update(payload=payload, key=key)
        return {"id": "em_1"}

    assert send_report("re_x", sender="A <a@b.cy>", to="x@example.com", subject="S", html="<p>h</p>",
                       filename="r.docx", content=b"DOCX", http=http) == "em_1"
    p = got["payload"]
    assert p["to"] == ["x@example.com"] and p["attachments"][0]["filename"] == "r.docx"
    assert base64.b64decode(p["attachments"][0]["content"]) == b"DOCX"
    with pytest.raises(EmailError):
        send_report("re_x", sender="a", to="not-an-email", subject="", html="", filename="", content=b"", http=http)


def test_checkout_shows_email_note_on_stripe_page():
    sent = {}
    http = lambda m, u, k, d=None: (sent.update(d) or {"id": "cs_test_1", "url": "https://checkout.stripe.com/x"})
    create_checkout("sk_test", amount_cents=2000, product_name="x", fingerprint="f", success_url="u",
                    cancel_url="u", submit_message="📧 email", http=http)
    assert sent["custom_text[submit][message]"] == "📧 email"
    sent.clear()
    create_checkout("sk_test", amount_cents=2000, product_name="x", fingerprint="f", success_url="u",
                    cancel_url="u", http=http)
    assert "custom_text[submit][message]" not in sent
