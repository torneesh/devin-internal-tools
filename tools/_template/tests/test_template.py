"""Required for every tool: a permission test per action, a test per rule, an audit test."""

import pytest

from core import audit
from core.errors import InvalidTransition, StaleWrite
from tools._template import service

PREFIX = "/_template"


def test_create_requires_engineer(login):
    form = {"title": "x", "contact_email": "x@example.com"}
    assert login("alice").post(PREFIX, data=form).status_code == 403
    assert login("frank").post(PREFIX, data=form).status_code == 200


def test_complete_requires_engineer(db, user, login):
    item = service.create_item(db, user("frank"), title="x", contact_email="x@example.com")
    response = login("ivan").post(f"{PREFIX}/{item.id}/complete", data={"version": item.version})
    assert response.status_code == 403


def test_cannot_complete_twice(db, user):
    item = service.create_item(db, user("frank"), title="x", contact_email="x@example.com")
    item = service.complete_item(db, user("frank"), item.id, item.version)
    with pytest.raises(InvalidTransition):
        service.complete_item(db, user("frank"), item.id, item.version)


def test_stale_update_rejected(db, user):
    item = service.create_item(db, user("frank"), title="x", contact_email="x@example.com")
    with pytest.raises(StaleWrite):
        service.complete_item(db, user("frank"), item.id, item.version - 1)


def test_mutations_audited_and_email_masked(db, user, login):
    item = service.create_item(db, user("frank"), title="x", contact_email="dana@example.com")
    service.complete_item(db, user("frank"), item.id, item.version)
    events = audit.trail(db, service.ENTITY, item.id)
    assert [e.action for e in events] == ["create", "complete"]
    assert events[0].after["contact_email"] == "d•••@example.com"
    assert "dana@example.com" not in login("frank").get(f"{PREFIX}/{item.id}").text
