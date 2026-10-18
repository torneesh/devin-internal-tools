"""Append-only audit log, written in the same transaction as the change it describes.

Call `record()` before `db.commit()`: if the change rolls back, so does its audit event.
Values of sensitive fields (core.masking.FIELD_POLICIES) are stored masked, never raw.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import DDL, JSON, DateTime, String, Text, event, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from core.db import Base, utcnow


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)


# Enforced by the database, not just the app. (Postgres: a trigger or REVOKE UPDATE, DELETE.)
for _op in ("UPDATE", "DELETE"):
    event.listen(
        AuditEvent.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER audit_events_no_{_op.lower()} BEFORE {_op} ON audit_events "
            "BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END;"
        ).execute_if(dialect="sqlite"),
    )


def _jsonable(data: dict | None) -> dict | None:
    if data is None:
        return None
    return json.loads(json.dumps(data, default=str))


def snapshot(obj: Any, *fields: str) -> dict:
    """Column values of a model instance (all columns unless `fields` are given)."""
    names = fields or tuple(c.key for c in obj.__table__.columns)
    return {name: getattr(obj, name) for name in names}


def record(
    db: Session,
    actor: Any,
    action: str,
    entity: str,
    entity_id: Any,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> AuditEvent:
    from core.masking import redact

    event_ = AuditEvent(
        actor=getattr(actor, "username", actor),
        action=action,
        entity=entity,
        entity_id=str(entity_id),
        before=_jsonable(redact(entity, before)),
        after=_jsonable(redact(entity, after)),
        reason=reason,
    )
    db.add(event_)
    return event_


def trail(db: Session, entity: str, entity_id: Any) -> list[AuditEvent]:
    query = (
        select(AuditEvent)
        .where(AuditEvent.entity == entity, AuditEvent.entity_id == str(entity_id))
        .order_by(AuditEvent.id)
    )
    return list(db.scalars(query))


def search(
    db: Session,
    entity: str | None = None,
    actor: str | None = None,
    action: str | None = None,
    limit: int = 500,
) -> list[AuditEvent]:
    query = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if entity:
        query = query.where(AuditEvent.entity == entity)
    if actor:
        query = query.where(AuditEvent.actor == actor)
    if action:
        query = query.where(AuditEvent.action == action)
    return list(db.scalars(query))


def distinct(db: Session, column: str) -> list[str]:
    col = getattr(AuditEvent, column)
    return list(db.scalars(select(col).distinct().order_by(col)))
