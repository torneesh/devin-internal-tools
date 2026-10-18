import pytest

from core import audit, masking
from core.errors import PermissionDenied, ValidationError
from tools.refunds import service

ACCOUNT = "GB82WEST12345698765432"


def make_refund(db, user):
    return service.create_refund(
        db,
        user("alice"),
        txn_id="TXN-M",
        customer_name="Masking Test",
        bank_account=ACCOUNT,
        amount_cents=100,
        reason="test",
    )


def test_mask_helpers():
    assert masking.last4("1234567890") == "••••7890"
    assert masking.email("dana@example.com") == "d•••@example.com"
    assert masking.mask("refunds", "bank_account", ACCOUNT) == "••••5432"
    assert masking.mask("refunds", "customer_name", "Dana") == "Dana"  # no policy


def test_reveal_requires_role_and_reason_and_is_audited(db, user):
    refund = make_refund(db, user)
    with pytest.raises(PermissionDenied):
        masking.reveal(db, user("alice"), "refunds", refund.id, "bank_account", "a reason")
    with pytest.raises(ValidationError):
        masking.reveal(db, user("bob"), "refunds", refund.id, "bank_account", "  ")
    value = masking.reveal(db, user("bob"), "refunds", refund.id, "bank_account", "payout check")
    assert value == ACCOUNT
    event = audit.trail(db, "refunds", refund.id)[-1]
    assert (event.action, event.actor, event.reason) == ("reveal", "bob", "payout check")


def test_changing_one_policy_changes_every_page(db, user, login, monkeypatch):
    refund = make_refund(db, user)
    monkeypatch.setitem(
        masking.FIELD_POLICIES,
        "refunds.bank_account",
        masking.Policy(mask=masking.redact_all, reveal_roles=("auditor",)),
    )
    client = login("bob")
    for url in ("/refunds", f"/refunds/{refund.id}"):
        html = client.get(url).text
        assert "<code>••••5432</code>" not in html and "<code>••••••</code>" in html
    assert (
        client.post(
            f"/reveal/refunds/{refund.id}/bank_account", data={"reason": "payout check"}
        ).status_code
        == 403
    )


def test_per_record_hook_limits_reveal(db, user, login, monkeypatch):
    small = make_refund(db, user)  # amount_cents=100
    big = service.create_refund(
        db,
        user("alice"),
        txn_id="TXN-B",
        customer_name="Big",
        bank_account=ACCOUNT,
        amount_cents=500_000,
        reason="test",
    )
    calls = []

    def only_small(db_, user_, obj):
        calls.append((db_ is not None, user_.username, obj.id))
        return obj.amount_cents < 1_000

    monkeypatch.setitem(
        masking.FIELD_POLICIES,
        "refunds.bank_account",
        masking.Policy(
            mask=masking.last4, reveal_roles=("refund_approver",), can_reveal=only_small
        ),
    )
    assert masking.reveal(db, user("bob"), "refunds", small.id, "bank_account", "payout") == ACCOUNT
    with pytest.raises(PermissionDenied, match="on this record"):
        masking.reveal(db, user("bob"), "refunds", big.id, "bank_account", "payout check")
    assert [e.action for e in audit.trail(db, "refunds", big.id)] == ["create"]  # no reveal event
    with pytest.raises(PermissionDenied):  # role check still runs first; hook isn't consulted
        masking.reveal(db, user("alice"), "refunds", small.id, "bank_account", "payout check")
    assert all(name == "bob" for _, name, _ in calls) and all(has_db for has_db, _, _ in calls)

    client = login("bob")
    assert "<summary" in client.get(f"/refunds/{small.id}").text  # Reveal button shown
    assert "<summary" not in client.get(f"/refunds/{big.id}").text  # hidden when hook says no
    response = client.post(f"/reveal/refunds/{big.id}/bank_account", data={"reason": "payout"})
    assert response.status_code == 403 and ACCOUNT not in response.text
