"""One test per refund rule (docs/BUILD_SPEC.md section 3)."""

import pytest

from core import audit
from core.errors import InvalidTransition, RuleViolation, StaleWrite
from tools.refunds import service
from tools.refunds.provider import MockPaymentProvider

ACCOUNT = "GB82WEST12345698765432"


def new_refund(db, requester, amount_cents=5_000):
    return service.create_refund(
        db,
        requester,
        txn_id="TXN-T1",
        customer_name="Test Customer",
        bank_account=ACCOUNT,
        amount_cents=amount_cents,
        reason="Test",
    )


def approved_refund(db, user, amount_cents=5_000, mode="ok"):
    refund = new_refund(db, user("alice"), amount_cents)
    refund = service.approve(db, user("bob"), refund.id, refund.version)
    if mode != "ok":
        refund = service.set_provider_mode(db, user("bob"), refund.id, refund.version, mode)
    return refund


def test_requester_cannot_approve_own_refund(db, user):
    admin = user("admin")  # holds both support_agent and refund_approver
    refund = new_refund(db, admin)
    with pytest.raises(RuleViolation, match="own request"):
        service.approve(db, admin, refund.id, refund.version)
    assert db.get(type(refund), refund.id).status == service.REQUESTED


def test_over_threshold_requires_two_distinct_approvers(db, user):
    refund = new_refund(db, user("alice"), amount_cents=150_000)
    refund = service.approve(db, user("bob"), refund.id, refund.version)
    assert refund.status == service.REQUESTED
    with pytest.raises(RuleViolation, match="already approved"):
        service.approve(db, user("bob"), refund.id, refund.version)
    refund = service.approve(db, user("carol"), refund.id, refund.version)
    assert refund.status == service.APPROVED
    assert [a.approver for a in refund.approvals] == ["bob", "carol"]


def test_cannot_execute_unapproved(db, user):
    provider = MockPaymentProvider()
    refund = new_refund(db, user("alice"))
    with pytest.raises(InvalidTransition):
        service.execute(db, user("bob"), refund.id, refund.version, provider=provider)
    assert provider.ledger == []
    assert refund.idempotency_key is None


def test_timeout_marks_unknown_not_failed(db, user):
    provider = MockPaymentProvider()
    refund = approved_refund(db, user, mode="timeout_after_accept")
    refund = service.execute(db, user("bob"), refund.id, refund.version, provider=provider)
    assert refund.status == service.UNKNOWN
    assert provider.times_paid(refund.idempotency_key) == 1  # the money did move


def test_reconcile_resolves_unknown(db, user):
    provider = MockPaymentProvider()
    refund = approved_refund(db, user, mode="timeout_after_accept")
    refund = service.execute(db, user("bob"), refund.id, refund.version, provider=provider)
    refund = service.reconcile(db, user("carol"), refund.id, refund.version, provider=provider)
    assert refund.status == service.SUCCEEDED
    assert refund.provider_ref == provider.lookup(refund.idempotency_key).ref

    # The provider never received the other one, so reconciling marks it FAILED.
    lost = approved_refund(db, user, mode="timeout_after_accept")
    lost = service.execute(db, user("bob"), lost.id, lost.version, provider=provider)
    lost = service.reconcile(db, user("bob"), lost.id, lost.version, provider=MockPaymentProvider())
    assert lost.status == service.FAILED


def test_retry_never_pays_twice(db, user):
    provider = MockPaymentProvider()
    refund = approved_refund(db, user, mode="timeout_after_accept")
    refund = service.execute(db, user("bob"), refund.id, refund.version, provider=provider)
    key = refund.idempotency_key
    refund = service.execute(db, user("bob"), refund.id, refund.version, provider=provider)
    assert refund.status == service.SUCCEEDED
    assert refund.idempotency_key == key
    assert provider.times_paid(key) == 1
    with pytest.raises(InvalidTransition):
        service.execute(db, user("bob"), refund.id, refund.version, provider=provider)
    assert provider.times_paid(key) == 1


def test_stale_update_rejected(db, user, login):
    refund = new_refund(db, user("alice"), amount_cents=150_000)
    stale_version = refund.version
    service.approve(db, user("bob"), refund.id, stale_version)
    with pytest.raises(StaleWrite):
        service.approve(db, user("carol"), refund.id, stale_version)
    response = login("carol").post(f"/refunds/{refund.id}/approve", data={"version": stale_version})
    assert response.status_code == 409


def test_every_mutation_audited(db, user):
    provider = MockPaymentProvider()
    refund = approved_refund(db, user, mode="timeout_after_accept")
    refund = service.execute(db, user("bob"), refund.id, refund.version, provider=provider)
    refund = service.reconcile(db, user("bob"), refund.id, refund.version, provider=provider)
    rejected = new_refund(db, user("alice"))
    service.reject(db, user("carol"), rejected.id, rejected.version, "Not eligible")

    events = audit.trail(db, service.ENTITY, refund.id)
    assert [(e.action, e.actor) for e in events] == [
        ("create", "alice"),
        ("approve", "bob"),
        ("set_provider_mode", "bob"),
        ("submit", "bob"),
        ("execute_result", "bob"),
        ("reconcile", "bob"),
    ]
    assert events[-1].before == {
        "status": "UNKNOWN",
        "provider_ref": None,
        "provider_note": events[-1].before["provider_note"],
    }
    reject_event = audit.trail(db, service.ENTITY, rejected.id)[-1]
    assert (reject_event.action, reject_event.reason) == ("reject", "Not eligible")


def test_bank_account_masked_and_reveal_audited(db, user, login):
    refund = new_refund(db, user("alice"))
    client = login("bob")
    page = client.get(f"/refunds/{refund.id}").text
    assert ACCOUNT not in page and "••••5432" in page
    assert ACCOUNT not in client.get("/refunds").text

    url = f"/reveal/refunds/{refund.id}/bank_account"
    assert client.post(url, data={"reason": ""}).status_code == 422
    response = client.post(url, data={"reason": "Verifying payee before payout"})
    assert response.status_code == 200 and ACCOUNT in response.text

    reveal = audit.trail(db, service.ENTITY, refund.id)[-1]
    assert (reveal.action, reveal.actor, reveal.reason) == (
        "reveal",
        "bob",
        "Verifying payee before payout",
    )
    create = audit.trail(db, service.ENTITY, refund.id)[0]
    assert create.after["bank_account"] == "••••5432"  # audit never stores the raw value

    assert login("alice").post(url, data={"reason": "Just curious"}).status_code == 403


def test_wrong_role_forbidden(db, user, login):
    refund = new_refund(db, user("alice"))
    assert (
        login("alice")
        .post(f"/refunds/{refund.id}/approve", data={"version": refund.version})
        .status_code
        == 403
    )
    form = {
        "txn_id": "T",
        "customer_name": "C",
        "bank_account": ACCOUNT,
        "amount": "10",
        "reason": "r",
    }
    assert login("bob").post("/refunds", data=form).status_code == 403
    assert login("frank").get("/refunds").status_code == 403
    assert login("ivan").get(f"/refunds/{refund.id}").status_code == 200  # auditor: read-only
    assert (
        login("ivan")
        .post(f"/refunds/{refund.id}/execute", data={"version": refund.version})
        .status_code
        == 403
    )
