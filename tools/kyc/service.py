"""KYC review rules. Every function: check role -> check rules -> change -> audit -> commit."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from core import audit
from core.auth import CurrentUser, ensure_role
from core.concurrency import update_versioned
from core.errors import InvalidTransition, NotFound, RuleViolation, ValidationError
from core.workflow import ApprovalPolicy, StateMachine
from tools.kyc.models import KycCase

ENTITY = KycCase.__tablename__

OPEN, IN_REVIEW, ESCALATED = "OPEN", "IN_REVIEW", "ESCALATED"
APPROVED, REJECTED = "APPROVED", "REJECTED"

FLOW = StateMachine(
    {
        OPEN: {IN_REVIEW},
        IN_REVIEW: {OPEN, APPROVED, REJECTED, ESCALATED},  # OPEN = release the claim
        ESCALATED: {APPROVED, REJECTED},
    }
)

# The supervisor who resolves an escalation must not be the person who escalated it.
RESOLUTION = ApprovalPolicy()

DOC_MISSING, DOC_UPLOADED, DOC_UNREADABLE = "MISSING", "UPLOADED", "UNREADABLE"
DOCUMENT_STATUSES = (DOC_MISSING, DOC_UPLOADED, DOC_UNREADABLE)

ANALYST_ROLES = ("kyc_analyst",)
SUPERVISOR_ROLES = ("kyc_supervisor",)
INTAKE_ROLES = SUPERVISOR_ROLES
VIEW_ROLES = (*ANALYST_ROLES, *SUPERVISOR_ROLES, "auditor")

QUEUES = ("all", "open", "mine", "escalated", "closed")


def list_cases(db: Session, user: CurrentUser, queue: str = "all") -> list[KycCase]:
    ensure_role(user, *VIEW_ROLES)
    query = select(KycCase).order_by(KycCase.id)
    if queue == "open":
        query = query.where(KycCase.status == OPEN)
    elif queue == "mine":
        query = query.where(KycCase.status == IN_REVIEW, KycCase.assigned_to == user.username)
    elif queue == "escalated":
        query = query.where(KycCase.status == ESCALATED)
    elif queue == "closed":
        query = query.where(KycCase.status.in_((APPROVED, REJECTED)))
    elif queue != "all":
        raise ValidationError(f"Queue must be one of {', '.join(QUEUES)}")
    return list(db.scalars(query))


def get_case(db: Session, user: CurrentUser, case_id: int) -> KycCase:
    ensure_role(user, *VIEW_ROLES)
    case = db.get(KycCase, case_id)
    if case is None:
        raise NotFound(f"KYC case {case_id} not found")
    return case


def _parse_dob(text: str) -> str:
    try:
        dob = date.fromisoformat(text.strip())
    except ValueError:
        raise ValidationError("Date of birth must be a date like 1990-04-21.") from None
    if dob >= date.today():
        raise ValidationError("Date of birth must be in the past.")
    return dob.isoformat()


def create_case(
    db: Session,
    user: CurrentUser,
    *,
    customer_name: str,
    date_of_birth: str,
    government_id: str,
    country: str,
    document_status: str,
) -> KycCase:
    """Intake. In production cases would arrive from the onboarding system."""
    ensure_role(user, *INTAKE_ROLES)
    values = {
        "customer_name": customer_name.strip(),
        "government_id": government_id.replace(" ", "").strip(),
        "country": country.strip().upper(),
    }
    if not all(values.values()):
        raise ValidationError("Customer name, government ID and country are all required.")
    if len(values["country"]) != 2 or not values["country"].isalpha():
        raise ValidationError("Country must be a two-letter ISO code, e.g. GB.")
    if document_status not in DOCUMENT_STATUSES:
        raise ValidationError(f"Document status must be one of {', '.join(DOCUMENT_STATUSES)}")
    case = KycCase(
        **values,
        date_of_birth=_parse_dob(date_of_birth),
        document_status=document_status,
        status=OPEN,
        created_by=user.username,
    )
    db.add(case)
    db.flush()
    audit.record(db, user, "create", ENTITY, case.id, after=audit.snapshot(case))
    db.commit()
    return case


def _require_reason(reason: str, action: str) -> str:
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError(f"A reason is required to {action} a case.")
    return reason


def _require_claimant(case: KycCase, user: CurrentUser) -> None:
    if case.status != IN_REVIEW:
        raise InvalidTransition(f"Case is {case.status}. Only a case in review can be decided.")
    if case.assigned_to != user.username:
        raise RuleViolation(
            f"Only the analyst who claimed this case ({case.assigned_to}) can act on it."
        )


def _apply(db, user, case, action, expected_version, changes, reason=None) -> KycCase:
    before = update_versioned(db, case, expected_version, **changes)
    audit.record(db, user, action, ENTITY, case.id, before=before, after=changes, reason=reason)
    db.commit()
    return case


def claim(db: Session, user: CurrentUser, case_id: int, expected_version: int) -> KycCase:
    ensure_role(user, *ANALYST_ROLES)
    case = get_case(db, user, case_id)
    if case.status == IN_REVIEW:
        raise InvalidTransition(f"Already claimed by {case.assigned_to}.")
    FLOW.check(case.status, IN_REVIEW)
    return _apply(
        db,
        user,
        case,
        "claim",
        expected_version,
        {"status": IN_REVIEW, "assigned_to": user.username},
    )


def release(db: Session, user: CurrentUser, case_id: int, expected_version: int) -> KycCase:
    """Hand a claimed case back to the open queue."""
    ensure_role(user, *ANALYST_ROLES)
    case = get_case(db, user, case_id)
    _require_claimant(case, user)
    FLOW.check(case.status, OPEN)
    return _apply(
        db, user, case, "release", expected_version, {"status": OPEN, "assigned_to": None}
    )


def approve(
    db: Session, user: CurrentUser, case_id: int, expected_version: int, reason: str
) -> KycCase:
    ensure_role(user, *ANALYST_ROLES)
    case = get_case(db, user, case_id)
    _require_claimant(case, user)
    return _decide(db, user, case, APPROVED, expected_version, reason, "approve")


def reject(
    db: Session, user: CurrentUser, case_id: int, expected_version: int, reason: str
) -> KycCase:
    ensure_role(user, *ANALYST_ROLES)
    case = get_case(db, user, case_id)
    _require_claimant(case, user)
    return _decide(db, user, case, REJECTED, expected_version, reason, "reject")


def escalate(
    db: Session, user: CurrentUser, case_id: int, expected_version: int, reason: str
) -> KycCase:
    ensure_role(user, *ANALYST_ROLES)
    case = get_case(db, user, case_id)
    _require_claimant(case, user)
    FLOW.check(case.status, ESCALATED)
    reason = _require_reason(reason, "escalate")
    changes = {"status": ESCALATED, "escalated_by": user.username, "escalation_reason": reason}
    return _apply(db, user, case, "escalate", expected_version, changes, reason=reason)


def resolve(
    db: Session,
    user: CurrentUser,
    case_id: int,
    expected_version: int,
    outcome: str,
    reason: str,
) -> KycCase:
    """Supervisor decision on an escalated case: outcome is APPROVED or REJECTED."""
    ensure_role(user, *SUPERVISOR_ROLES)
    case = get_case(db, user, case_id)
    if case.status != ESCALATED:
        raise InvalidTransition(f"Case is {case.status}. Only escalated cases are resolved here.")
    if outcome not in (APPROVED, REJECTED):
        raise ValidationError("Outcome must be APPROVED or REJECTED.")
    try:
        RESOLUTION.check(approver=user.username, requester=case.escalated_by)
    except RuleViolation:
        raise RuleViolation("You can't resolve a case you escalated yourself.") from None
    return _decide(db, user, case, outcome, expected_version, reason, "resolve")


def _decide(db, user, case, outcome, expected_version, reason, action) -> KycCase:
    FLOW.check(case.status, outcome)
    reason = _require_reason(reason, "approve" if outcome == APPROVED else "reject")
    if outcome == APPROVED and case.document_status != DOC_UPLOADED:
        raise RuleViolation(
            f"Documents are {case.document_status}. A case can only be approved once its "
            "documents are uploaded and readable."
        )
    changes = {"status": outcome, "decided_by": user.username, "decision_reason": reason}
    return _apply(db, user, case, action, expected_version, changes, reason=reason)
