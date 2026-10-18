"""Business rules. Every function: check role -> check rules -> change -> audit -> commit."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core import audit
from core.auth import CurrentUser, ensure_role
from core.concurrency import update_versioned
from core.errors import NotFound, ValidationError
from core.workflow import StateMachine
from tools._template.models import Item

ENTITY = Item.__tablename__

OPEN, DONE = "OPEN", "DONE"
FLOW = StateMachine({OPEN: {DONE}})

VIEW_ROLES = ("engineer", "auditor")
EDIT_ROLES = ("engineer",)


def list_items(db: Session, user: CurrentUser) -> list[Item]:
    ensure_role(user, *VIEW_ROLES)
    return list(db.scalars(select(Item).order_by(Item.id.desc())))


def get_item(db: Session, user: CurrentUser, item_id: int) -> Item:
    ensure_role(user, *VIEW_ROLES)
    item = db.get(Item, item_id)
    if item is None:
        raise NotFound(f"Item {item_id} not found")
    return item


def create_item(db: Session, user: CurrentUser, *, title: str, contact_email: str) -> Item:
    ensure_role(user, *EDIT_ROLES)
    if not title.strip() or "@" not in contact_email:
        raise ValidationError("A title and a valid contact email are required.")
    item = Item(title=title.strip(), contact_email=contact_email.strip(), owner=user.username)
    db.add(item)
    db.flush()
    audit.record(db, user, "create", ENTITY, item.id, after=audit.snapshot(item))
    db.commit()
    return item


def complete_item(db: Session, user: CurrentUser, item_id: int, expected_version: int) -> Item:
    ensure_role(user, *EDIT_ROLES)
    item = get_item(db, user, item_id)
    FLOW.check(item.status, DONE)
    before = update_versioned(db, item, expected_version, status=DONE)
    audit.record(db, user, "complete", ENTITY, item.id, before=before, after={"status": DONE})
    db.commit()
    return item
