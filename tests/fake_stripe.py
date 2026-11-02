"""Ψεύτικο Stripe στη μνήμη -- για τα tests πληρωμών/παραπομπών (χωρίς δίκτυο)."""
import itertools
import re
import time

from core.payments import PaymentError


class FakeStripe:
    def __init__(self):
        self.sessions, self.pis, self.coupons = {}, {}, {}
        self._n = itertools.count(1)
        self.clock = 1_790_000_000

    # βοηθητικό: μια ολοκληρωμένη πληρωμή (όπως μετά το Stripe Checkout)
    def pay(self, email, card, metadata=None, created=None, fingerprint="f"):
        n = next(self._n)
        pi = {"id": f"pi_{n}", "status": "succeeded", "created": created or self.clock + n,
              "metadata": dict(metadata or {}), "receipt_email": email,
              "latest_charge": {"billing_details": {"email": email},
                                "payment_method_details": {"card": {"fingerprint": card}}}}
        self.pis[pi["id"]] = pi
        cs = {"id": f"cs_test_{n}", "payment_status": "paid", "client_reference_id": fingerprint,
              "customer_details": {"email": email}, "payment_intent": pi["id"]}
        self.sessions[cs["id"]] = cs
        return cs["id"], pi["id"]

    def complete(self, cs_id, email, card):
        """Ο πελάτης πλήρωσε στη σελίδα του Stripe."""
        cs = self.sessions[cs_id]
        _, pi = self.pay(email, card, cs["_md"])
        self.sessions.pop(f"cs_test_{pi.split('_')[1]}")   # η βοηθητική συνεδρία του pay()
        cs.update(payment_status="paid", customer_details={"email": email}, payment_intent=pi)

    def __call__(self, method, url, key, data=None, timeout=20):
        path = url.split("/v1", 1)[1]
        data = data or {}
        if path == "/payment_intents/search":
            m = re.fullmatch(r"metadata\['(\w+)'\]:'([^']*)'", data["query"])
            k, v = m.groups()
            return {"data": [p for p in self.pis.values() if p["metadata"].get(k) == v], "has_more": False}
        if path.startswith("/payment_intents/") and method == "POST":
            pi = self.pis[path.rsplit("/", 1)[1]]
            for k, v in data.items():
                pi["metadata"][re.fullmatch(r"metadata\[(\w+)\]", k).group(1)] = v
            return pi
        if path == "/checkout/sessions" and method == "POST":
            n = next(self._n)
            md = {re.fullmatch(r"payment_intent_data\[metadata\]\[(\w+)\]", k).group(1): v
                  for k, v in data.items() if k.startswith("payment_intent_data[metadata]")}
            cs = {"id": f"cs_test_{n}", "payment_status": "unpaid", "client_reference_id": data["client_reference_id"],
                  "customer_details": {}, "payment_intent": None, "_md": md, "_data": dict(data),
                  "url": f"https://checkout.stripe.com/c/pay/cs_test_{n}"}
            self.sessions[cs["id"]] = cs
            return cs
        if path.startswith("/checkout/sessions/"):
            cs = dict(self.sessions[path.rsplit("/", 1)[1]])
            if data.get("expand[]") == "payment_intent.latest_charge":
                cs["payment_intent"] = self.pis[cs["payment_intent"]]
            return cs
        if path.startswith("/coupons/"):
            cid = path.rsplit("/", 1)[1]
            if cid not in self.coupons:
                raise PaymentError("Stripe 404: No such coupon")
            return self.coupons[cid]
        if path == "/coupons":
            cid = data.get("id") or f"co_{next(self._n)}"
            self.coupons[cid] = {"id": cid, "amount_off": int(data["amount_off"]), "valid": True}
            return self.coupons[cid]
        raise AssertionError(f"απρόβλεπτη κλήση {method} {path}")
