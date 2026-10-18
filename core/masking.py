"""Field-level protection. Every sensitive field in every tool has one entry here.

Values render masked everywhere (tables, detail pages, audit log). A user with a reveal role
can see one value by giving a reason; each reveal is an audit event.
Changing a policy below changes every page and tool that shows that field.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from markupsafe import escape
from sqlalchemy.orm import Session

from core import audit
from core.auth import CurrentUser, current_user
from core.db import Base, get_db
from core.errors import AppError, NotFound, PermissionDenied, ValidationError

MIN_REASON_LENGTH = 5


@dataclass(frozen=True)
class Policy:
    mask: Callable[[str], str]
    reveal_roles: tuple[str, ...]


def last4(value: str) -> str:
    return "••••" + value[-4:]


def redact_all(value: str) -> str:
    return "••••••"


def year_only(value: str) -> str:
    return value[:4] + "-••-••"


def email(value: str) -> str:
    name, _, domain = value.partition("@")
    return f"{name[:1]}•••@{domain}" if domain else redact_all(value)


# "<table name>.<column>" -> Policy
FIELD_POLICIES: dict[str, Policy] = {
    "refunds.bank_account": Policy(mask=last4, reveal_roles=("refund_approver",)),
    "kyc_cases.government_id": Policy(mask=last4, reveal_roles=("kyc_analyst", "kyc_supervisor")),
    "kyc_cases.date_of_birth": Policy(
        mask=year_only, reveal_roles=("kyc_analyst", "kyc_supervisor")
    ),
    "template_items.contact_email": Policy(mask=email, reveal_roles=("engineer",)),
}


def policy_for(entity: str, field: str) -> Policy | None:
    return FIELD_POLICIES.get(f"{entity}.{field}")


def mask(entity: str, field: str, value) -> str:
    if value is None:
        return ""
    policy = policy_for(entity, field)
    return policy.mask(str(value)) if policy else str(value)


def can_reveal(entity: str, field: str, user: CurrentUser | None) -> bool:
    policy = policy_for(entity, field)
    return bool(policy and user and user.has_role(*policy.reveal_roles))


def redact(entity: str, data: dict | None) -> dict | None:
    if not data:
        return data
    return {k: (mask(entity, k, v) if policy_for(entity, k) else v) for k, v in data.items()}


def model_for(entity: str) -> type:
    for mapper in Base.registry.mappers:
        if mapper.local_table.name == entity:
            return mapper.class_
    raise NotFound(f"Unknown entity {entity!r}")


def reveal(
    db: Session, user: CurrentUser, entity: str, entity_id: int, field: str, reason: str
) -> str:
    policy = policy_for(entity, field)
    if policy is None:
        raise NotFound(f"{entity}.{field} is not a protected field")
    if not user.has_role(*policy.reveal_roles):
        raise PermissionDenied(
            f"Revealing {field} needs the {' or '.join(policy.reveal_roles)} role."
        )
    reason = (reason or "").strip()
    if len(reason) < MIN_REASON_LENGTH:
        raise ValidationError(
            "Give a reason to reveal this value. It is recorded in the audit log."
        )
    obj = db.get(model_for(entity), entity_id)
    if obj is None:
        raise NotFound()
    audit.record(db, user, "reveal", entity, entity_id, after={"field": field}, reason=reason)
    db.commit()
    return str(getattr(obj, field))


router = APIRouter()


@router.post("/reveal/{entity}/{entity_id}/{field}", response_class=HTMLResponse)
def reveal_route(
    entity: str,
    entity_id: int,
    field: str,
    request: Request,
    reason: str = Form(""),
    user: CurrentUser = Depends(current_user),
    db: Session = Depends(get_db),
):
    target = f"mf-{entity}-{entity_id}-{field}"
    try:
        value = reveal(db, user, entity, entity_id, field, reason)
    except AppError as exc:
        return HTMLResponse(
            f'<span id="{target}" class="masked"><span class="error">{escape(exc.message)}</span>'
            "</span>",
            status_code=exc.status_code,
        )
    return HTMLResponse(
        f'<span id="{target}" class="masked revealed"><code>{escape(value)}</code> '
        "<small>Revealed. This view is in the audit log.</small></span>"
    )
