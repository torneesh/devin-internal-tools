"""Optimistic locking: every mutation states which version it was based on."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from core.errors import StaleWrite


def update_versioned(db: Session, obj: Any, expected_version: int | str | None, **changes) -> dict:
    """Apply `changes` to `obj` only if it is still at `expected_version`.

    Returns the previous values of the changed fields (pass them to audit.record as `before`).
    Raises StaleWrite if the caller's version is out of date, either from the in-memory
    check or from the `WHERE version = old` guard on the UPDATE (a concurrent writer won).
    """
    if expected_version is None or int(expected_version) != obj.version:
        raise StaleWrite()
    before = {field: getattr(obj, field) for field in changes}
    for field, value in changes.items():
        setattr(obj, field, value)
    obj.version = obj.version + 1
    try:
        db.flush()
    except StaleDataError as exc:
        db.rollback()
        raise StaleWrite() from exc
    return before
