import pytest

from core.concurrency import update_versioned
from core.errors import StaleWrite
from tools._template.models import Item


def test_update_bumps_version_and_returns_before(db):
    item = Item(title="a", owner="frank", contact_email="f@example.com", status="OPEN")
    db.add(item)
    db.commit()
    before = update_versioned(db, item, 1, title="b")
    db.commit()
    assert before == {"title": "a"} and item.version == 2


def test_stale_expected_version_rejected(db):
    item = Item(title="a", owner="frank", contact_email="f@example.com", status="OPEN")
    db.add(item)
    db.commit()
    update_versioned(db, item, 1, title="b")
    db.commit()
    with pytest.raises(StaleWrite):
        update_versioned(db, item, 1, title="c")


def test_concurrent_writer_detected_at_database(app):
    first, second = app.state.SessionLocal(), app.state.SessionLocal()
    item = Item(title="a", owner="frank", contact_email="f@example.com", status="OPEN")
    first.add(item)
    first.commit()
    other = second.get(Item, item.id)
    update_versioned(first, item, 1, title="first wins")
    first.commit()
    with pytest.raises(StaleWrite):  # second read version 1 before first committed
        update_versioned(second, other, 1, title="second loses")
