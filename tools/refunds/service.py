"""Refund business rules. Every function: check role -> check rules -> change -> audit -> commit."""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from core import audit, integrations
from core.auth import CurrentUser, ensure_role
from core.concurrency import update_versioned
from core.errors import InvalidTransition, NotFound, ValidationError
from core.workflow import ApprovalPolicy, StateMachine
from tools.refunds.models import Refund, RefundApproval
from tools.refunds.provider import MODES, PaymentDeclined, ProviderTimeout

ENTITY = Refund.__tablename__

REQUESTED, APPROVED, REJECTED = "REQUESTED", "APPROVED", "REJECTED"
SUBMITTED, SUCCEEDED, FAILED, UNKNOWN = "SUBMITTED", "SUCCEEDED", "FAILED", "UNKNOWN"

FLOW = StateMachine(
    {
        REQUESTED: {APPROVED, REJECTED},
        APPROVED: {SUBMITTED},
        SUBMITTED: {SUCCEEDED, FAILED, UNKNOWN},
        UNKNOWN: {SUBMITTED, SUCCEEDED, FAILED},  # retry with the same key, or reconcile
    }
)

THRESHOLD_CENTS = 100_000  # $1,000
APPROVALS = ApprovalPolicy(threshold=THRESHOLD_CENTS, above_threshold=2)

VIEW_ROLES = ("support_agent", "refund_approver", "auditor")
REQUEST_ROLES = ("support_agent",)
APPROVE_ROLES = ("refund_approver",)


def parse_amount(text: str) -> int:
    try:
        cents = int((Decimal(text.replace(",", "").replace("$", "").strip()) * 100).to_integral())
    except (InvalidOperation, AttributeError):
        raise ValidationError("Amount must be a number, e.g. 125.00") from None
    return cents


def list_refunds(db: Session, user: CurrentUser, status: str | None = None) -> list[Refund]:
    ensure_role(user, *VIEW_ROLES)
    query = select(Refund).order_by(Refund.id.desc())
    if status:
        query = query.where(Refund.status == status)
    return list(db.scalars(query))


def get_refund(db: Session, user: CurrentUser, refund_id: int) -> Refund:
    ensure_role(user, *VIEW_ROLES)
    refund = db.get(Refund, refund_id)
    if refund is None:
        raise NotFound(f"Refund {refund_id} not found")
    return refund


def create_refund(
    db: Session,
    user: CurrentUser,
    *,
    txn_id: str,
    customer_name: str,
    bank_account: str,
    amount_cents: int,
    reason: str,
) -> Refund:
    ensure_role(user, *REQUEST_ROLES)
    values = {
        "txn_id": txn_id.strip(),
        "customer_name": customer_name.strip(),
        "bank_account": bank_account.replace(" ", "").strip(),
        "reason": reason.strip(),
    }
    if not all(values.values()):
        raise ValidationError("Transaction, customer, bank account and reason are all required.")
    if amount_cents <= 0:
        raise ValidationError("Amount must be greater than zero.")
    refund = Refund(
        **values, amount_cents=amount_cents, status=REQUESTED, requested_by=user.username
    )
    db.add(refund)
    db.flush()
    audit.record(db, user, "create", ENTITY, refund.id, after=audit.snapshot(refund))
    db.commit()
    return refund


def approve(db: Session, user: CurrentUser, refund_id: int, expected_version: int) -> Refund:
    ensure_role(user, *APPROVE_ROLES)
    refund = get_refund(db, user, refund_id)
    FLOW.check(refund.status, APPROVED)
    existing = [a.approver for a in refund.approvals]
    APPROVALS.check(approver=user.username, requester=refund.requested_by, existing=existing)
    refund.approvals.append(RefundApproval(approver=user.username))
    approvers = [*existing, user.username]
    status = APPROVED if APPROVALS.satisfied(refund.amount_cents, approvers) else refund.status
    before = update_versioned(db, refund, expected_version, status=status)
    required = APPROVALS.required(refund.amount_cents)
    after = {"status": status, "approvals": f"{len(approvers)} of {required}"}
    audit.record(db, user, "approve", ENTITY, refund.id, before=before, after=after)
    db.commit()
    return refund


def reject(
    db: Session, user: CurrentUser, refund_id: int, expected_version: int, reason: str
) -> Refund:
    ensure_role(user, *APPROVE_ROLES)
    refund = get_refund(db, user, refund_id)
    FLOW.check(refund.status, REJECTED)
    if not reason.strip():
        raise ValidationError("A reason is required to reject a refund.")
    changes = {"status": REJECTED, "decision_reason": reason.strip()}
    before = update_versioned(db, refund, expected_version, **changes)
    audit.record(db, user, "reject", ENTITY, refund.id, before, changes, reason=reason.strip())
    db.commit()
    return refund


def set_provider_mode(
    db: Session, user: CurrentUser, refund_id: int, expected_version: int, mode: str
) -> Refund:
    """Demo control: how the mock provider behaves for this refund."""
    ensure_role(user, *REQUEST_ROLES, *APPROVE_ROLES)
    refund = get_refund(db, user, refund_id)
    if mode not in MODES:
        raise ValidationError(f"Mode must be one of {', '.join(MODES)}")
    before = update_versioned(db, refund, expected_version, provider_mode=mode)
    audit.record(db, user, "set_provider_mode", ENTITY, refund.id, before, {"provider_mode": mode})
    db.commit()
    return refund


def execute(
    db: Session, user: CurrentUser, refund_id: int, expected_version: int, provider=None
) -> Refund:
    """Pay an APPROVED refund, or retry an UNKNOWN one with the same idempotency key."""
    ensure_role(user, *APPROVE_ROLES)
    provider = provider or integrations.get("payments")
    refund = get_refund(db, user, refund_id)
    FLOW.check(refund.status, SUBMITTED)

    key = refund.idempotency_key or f"refund-{refund.id}-{uuid.uuid4().hex[:12]}"
    after = {"status": SUBMITTED, "idempotency_key": key}
    before = update_versioned(db, refund, expected_version, **after)
    audit.record(db, user, "submit", ENTITY, refund.id, before=before, after=after)
    db.commit()  # the key is durable before any money can move

    try:
        payment = provider.pay(key, refund.amount_cents, refund.bank_account, refund.provider_mode)
        changes = {"status": SUCCEEDED, "provider_ref": payment.ref, "provider_note": "Paid"}
    except PaymentDeclined as exc:
        changes = {"status": FAILED, "provider_note": str(exc)}
    except ProviderTimeout as exc:
        note = f"{exc}. The payment may or may not have gone through: reconcile before retrying."
        changes = {"status": UNKNOWN, "provider_note": note}
    return _record_outcome(db, user, refund, "execute_result", refund.version, changes)


def reconcile(
    db: Session, user: CurrentUser, refund_id: int, expected_version: int, provider=None
) -> Refund:
    """Ask the provider what happened to an UNKNOWN refund's key and record the answer."""
    ensure_role(user, *APPROVE_ROLES)
    provider = provider or integrations.get("payments")
    refund = get_refund(db, user, refund_id)
    if refund.status != UNKNOWN:
        raise InvalidTransition("Only refunds in UNKNOWN status need reconciling.")
    payment = provider.lookup(refund.idempotency_key)
    if payment and payment.status == "succeeded":
        note = f"Reconciled: provider confirms payment {payment.ref}"
        changes = {"status": SUCCEEDED, "provider_ref": payment.ref, "provider_note": note}
    else:
        changes = {"status": FAILED, "provider_note": "Reconciled: provider has no payment"}
    return _record_outcome(db, user, refund, "reconcile", expected_version, changes)


def _record_outcome(db, user, refund, action, expected_version, changes) -> Refund:
    FLOW.check(refund.status, changes["status"])
    before = update_versioned(db, refund, expected_version, **changes)
    audit.record(db, user, action, ENTITY, refund.id, before=before, after=changes)
    db.commit()
    return refund
