"""Mock payment provider. Idempotent by key, like real providers (e.g. Stripe's Idempotency-Key).

Demo modes: "ok", "fail" (declined), "timeout_after_accept" (money moves, then the response is
lost: the dangerous case a retry must not double-pay).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core import integrations

MODES = ("ok", "fail", "timeout_after_accept")


class PaymentDeclined(Exception):
    pass


class ProviderTimeout(Exception):
    pass


@dataclass(frozen=True)
class Payment:
    ref: str
    key: str
    amount_cents: int
    status: str  # "succeeded" | "declined"


@dataclass
class MockPaymentProvider:
    name: str = "payments"
    by_key: dict[str, Payment] = field(default_factory=dict)
    ledger: list[Payment] = field(default_factory=list)  # every time money actually moved

    def pay(self, key: str, amount_cents: int, account: str, mode: str = "ok") -> Payment:
        existing = self.by_key.get(key)
        if existing:  # same key -> same outcome, never a second payment
            if existing.status == "declined":
                raise PaymentDeclined("Declined by provider")
            return existing
        if mode not in MODES:
            raise ValueError(f"Unknown mode {mode!r}")
        status = "declined" if mode == "fail" else "succeeded"
        payment = Payment(f"pay_{len(self.by_key) + 1:05d}", key, amount_cents, status)
        self.by_key[key] = payment
        if mode == "fail":
            raise PaymentDeclined("Declined by provider")
        self.ledger.append(payment)
        if mode == "timeout_after_accept":
            raise ProviderTimeout("No response from provider")
        return payment

    def lookup(self, key: str) -> Payment | None:
        return self.by_key.get(key)

    def times_paid(self, key: str) -> int:
        return sum(1 for p in self.ledger if p.key == key)


integrations.register(MockPaymentProvider())
