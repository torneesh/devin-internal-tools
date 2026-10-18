import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from core import audit


def test_audit_is_append_only(db):
    audit.record(db, "frank", "test", "things", 1, after={"x": 1})
    db.commit()
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("UPDATE audit_events SET actor = 'mallory'"))
    db.rollback()
    with pytest.raises(DBAPIError, match="append-only"):
        db.execute(text("DELETE FROM audit_events"))


def test_audit_rolls_back_with_the_change(db):
    audit.record(db, "frank", "never-committed", "things", 2)
    db.rollback()
    assert audit.search(db, action="never-committed") == []


def test_sensitive_values_are_masked_in_audit(db):
    event = audit.record(
        db, "frank", "create", "refunds", 3, after={"bank_account": "GB00123456789", "amount": 5}
    )
    assert event.after == {"bank_account": "••••6789", "amount": 5}
