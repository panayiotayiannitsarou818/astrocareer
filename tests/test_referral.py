"""v22.49: πρόγραμμα παραπομπών (2 € στον φίλο, 2 € στον αρχικό πελάτη, πίστωση/Revolut) -- ψεύτικο Stripe."""
from datetime import datetime, timezone, timedelta

import pytest

from core import referral as REF
from core.payments import PaymentError
from tests.fake_stripe import FakeStripe

SECRET = "sk_test_x"
SET = REF.Settings()


def test_codes_are_stable_and_signed():
    a = REF.ref_code("Maria@Example.com ", SECRET)
    assert a == REF.ref_code("maria@example.com", SECRET) and REF.valid_code(a) and "maria" not in a.lower()
    assert REF.valid_me(a, REF.me_signature(a, SECRET), SECRET)
    assert not REF.valid_me(a, "0" * 20, SECRET) and not REF.valid_code("abc")


def test_deadline_is_midnight_of_next_day_cyprus_time():
    opened = datetime(2026, 11, 3, 19, 0, tzinfo=timezone.utc)          # Τρίτη 21:00 ώρα Κύπρου
    d = REF.deadline(opened, 1)
    assert (d.day, d.hour, d.minute) == (4, 23, 59)
    assert REF.format_deadline(d) == "τα μεσάνυχτα της Τετάρτης 4 Νοεμβρίου"


def test_friend_purchase_earns_credit_and_email_info():
    st = FakeStripe()
    cs_m, _ = st.pay("maria@x.com", "card_M")
    info_m = REF.after_purchase(SECRET, cs_m, SECRET, SET, http=st)
    code = info_m.code
    assert st.pis["pi_1"]["metadata"]["ref_owner"] == code
    cs_e, pi_e = st.pay("eleni@x.com", "card_E", {"ref": code})
    info = REF.after_purchase(SECRET, cs_e, SECRET, SET, http=st)
    assert info.referrer_rewarded and info.referrer_email == "maria@x.com" and info.referrer_balance == 200
    assert st.pis[pi_e]["metadata"]["ref_notified"] == "1"
    again = REF.after_purchase(SECRET, cs_e, SECRET, SET, http=st)     # δεύτερη φορά: όχι νέο email
    assert not again.referrer_rewarded
    for i in range(4):                                                  # 5 φίλοι = 10 €
        st.pay(f"f{i}@x.com", f"card_{i}", {"ref": code})
    b = REF.balance(SECRET, code, SET, http=st)
    assert (b.friends, b.available) == (5, 1000)


def test_self_referral_with_same_card_or_email_does_not_earn():
    st = FakeStripe()
    cs_m, _ = st.pay("maria@x.com", "card_M")
    code = REF.after_purchase(SECRET, cs_m, SECRET, SET, http=st).code
    cs2, _ = st.pay("maria.second@x.com", "card_M", {"ref": code})     # ίδια κάρτα, άλλο email
    info = REF.after_purchase(SECRET, cs2, SECRET, SET, http=st)
    assert info.self_referral and not info.referrer_rewarded
    st.pay("maria@x.com", "card_other", {"ref": code})                 # ίδιο email
    assert REF.balance(SECRET, code, SET, http=st).available == 0


def test_credit_use_free_report_and_revolut_payout():
    st = FakeStripe()
    cs_m, _ = st.pay("maria@x.com", "card_M")
    code = REF.after_purchase(SECRET, cs_m, SECRET, SET, http=st).code
    for i in range(12):
        st.pay(f"f{i}@x.com", f"c{i}", {"ref": code})                  # 24 €
    st.pay("maria@x.com", "card_M", {"credit_used_by": code, "credit_used": "200"})
    b = REF.balance(SECRET, code, SET, http=st)
    assert b.available == 2200
    REF.spend(SECRET, b, 2000, http=st)                                 # δωρεάν αναφορά
    b = REF.balance(SECRET, code, SET, http=st)
    assert b.available == 200
    for i in range(9):
        st.pay(f"g{i}@x.com", f"d{i}", {"ref": code})                  # +18 € = 20 €
    b = REF.balance(SECRET, code, SET, http=st)
    with pytest.raises(PaymentError):
        REF.request_payout(SECRET, b, "όχι έγκυρο!")
    REF.request_payout(SECRET, b, "@maria123", http=st)
    rows = REF.pending_payouts(SECRET, http=st)
    assert rows == [{"pi": b.anchor_pi, "code": code, "email": "maria@x.com", "revtag": "@maria123",
                     "cents": 2000, "spent": 2000}]
    REF.mark_paid(SECRET, rows[0], http=st)
    b = REF.balance(SECRET, code, SET, http=st)
    assert b.available == 0 and not b.payout_pending and REF.pending_payouts(SECRET, http=st) == []


def test_credit_expires_twelve_months_after_last_friend():
    st = FakeStripe()
    cs_m, _ = st.pay("maria@x.com", "card_M")
    code = REF.after_purchase(SECRET, cs_m, SECRET, SET, http=st).code
    st.pay("f@x.com", "cf", {"ref": code})
    b = REF.balance(SECRET, code, SET, http=st)
    assert b.available == 200 and b.expires
    later = b.last_earned + timedelta(days=370)
    assert REF.balance(SECRET, code, SET, http=st, now=later).available == 0


def test_friend_coupon_is_created_once():
    st = FakeStripe()
    a = REF.ensure_coupon(SECRET, 200, http=st, coupon_id="ASTRO_FRIEND")
    b = REF.ensure_coupon(SECRET, 200, http=st, coupon_id="ASTRO_FRIEND")
    assert a == b == "ASTRO_FRIEND_200" and len(st.coupons) == 1
    one = REF.ensure_coupon(SECRET, 500, http=st)                       # πίστωση: μίας χρήσης
    assert one != a and st.coupons[one]["amount_off"] == 500


def test_checkout_with_coupon_has_no_promotion_codes_and_carries_metadata():
    from core.payments import create_checkout
    sent = {}
    http = lambda m, u, k, d=None: (sent.update(d) or {"id": "cs_test_1", "url": "https://checkout.stripe.com/x"})
    create_checkout("sk", amount_cents=2000, product_name="x", fingerprint="f", success_url="u", cancel_url="u",
                    coupon="ASTRO_FRIEND", metadata={"ref": "ABCDEFGH"}, http=http)
    assert sent["discounts[0][coupon]"] == "ASTRO_FRIEND" and "allow_promotion_codes" not in sent
    assert sent["payment_intent_data[metadata][ref]"] == "ABCDEFGH"


def test_refunded_friend_purchase_does_not_count_v22_50():
    st = FakeStripe()
    cs_m, _ = st.pay("maria@x.com", "card_M")
    code = REF.after_purchase(SECRET, cs_m, SECRET, SET, http=st).code
    _, pi = st.pay("f@x.com", "cf", {"ref": code})
    st.pay("g@x.com", "cg", {"ref": code})
    st.pis[pi]["latest_charge"]["refunded"] = True
    assert REF.balance(SECRET, code, SET, http=st).available == 200
