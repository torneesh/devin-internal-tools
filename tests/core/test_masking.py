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
