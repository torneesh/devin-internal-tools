"""Feature flags: permissions per action, one test per rule, stale writes, audit, history UI."""

import pytest

from core import audit, integrations
from core.errors import (
    InvalidTransition,
    NotFound,
    PermissionDenied,
    RuleViolation,
    StaleWrite,
    ValidationError,
)
from tools.flags import service
from tools.flags.flag_service import MockFlagService

PREFIX = "/flags"


@pytest.fixture
def svc():
    """A fresh mock flag service, also used by the routes for the duration of the test."""
    with integrations.override("flag_service", MockFlagService()) as mock:
        yield mock


def new_flag(db, user, svc, key="test.flag"):
    return service.create_flag(db, user("frank"), key=key, description="Test", flag_service=svc)


def turn_on(db, actor, flag, env, svc):
    state = flag.state(env)
    return service.set_enabled(db, actor, flag.id, env, state.version, True, flag_service=svc)


def set_pct(db, actor, flag, env, pct, svc):
    state = flag.state(env)
    return service.set_rollout(db, actor, flag.id, env, state.version, pct, flag_service=svc)


# --- Permissions (one per action) ---


def test_view_requires_engineer_release_manager_or_auditor(login):
    assert login("alice").get(PREFIX).status_code == 403
    for name in ("frank", "grace", "ivan"):
        assert login(name).get(PREFIX).status_code == 200


def test_create_requires_engineer(login, svc):
    form = {"key": "new.flag", "description": "x"}
    assert login("ivan").post(PREFIX, data=form).status_code == 403
    assert login("grace").post(PREFIX, data=form).status_code == 403
    response = login("frank").post(PREFIX, data=form)
    assert response.status_code == 200 and "new.flag" in response.text


def test_engineer_can_change_staging(db, user, svc):
    flag = new_flag(db, user, svc)
    state = turn_on(db, user("frank"), flag, "staging", svc)
    state = set_pct(db, user("frank"), flag, "staging", 30, svc)
    assert (state.enabled, state.rollout_pct) == (True, 30)


def test_auditor_cannot_change_anything(db, user, login, svc):
    flag = new_flag(db, user, svc)
    client = login("ivan")
    version = flag.state("staging").version
    url = f"{PREFIX}/{flag.id}/staging"
    assert (
        client.post(f"{url}/toggle", data={"version": version, "enabled": "true"}).status_code
        == 403
    )
    assert (
        client.post(f"{url}/rollout", data={"version": version, "rollout_pct": "5"}).status_code
        == 403
    )
    change_id = service.history(db, user("ivan"), flag.id, "staging")[0].id
    assert (
        client.post(
            f"{url}/rollback", data={"version": version, "change_id": change_id}
        ).status_code
        == 403
    )
    assert client.post(f"{url}/retry", data={"version": version}).status_code == 403
    assert client.post(f"{PREFIX}/service-mode", data={"available": "down"}).status_code == 403


def test_production_change_restricted_to_release_managers(db, user, login, svc):
    flag = new_flag(db, user, svc)
    frank = user("frank")
    with pytest.raises(PermissionDenied):
        turn_on(db, frank, flag, "production", svc)
    with pytest.raises(PermissionDenied):
        set_pct(db, frank, flag, "production", 10, svc)
    state = flag.state("production")
    form = {"version": state.version, "enabled": "true"}
    assert (
        login("frank").post(f"{PREFIX}/{flag.id}/production/toggle", data=form).status_code == 403
    )
    db.refresh(state)
    assert (state.enabled, state.rollout_pct) == (False, 0)
    assert svc.get("production", flag.key).enabled is False

    state = turn_on(db, user("grace"), flag, "production", svc)
    assert state.enabled and svc.get("production", flag.key).enabled


def test_production_rollback_and_retry_restricted_to_release_managers(db, user, svc):
    flag = new_flag(db, user, svc)
    first = service.history(db, user("grace"), flag.id, "production")[-1]
    state = turn_on(db, user("grace"), flag, "production", svc)
    with pytest.raises(PermissionDenied):
        service.rollback(
            db, user("frank"), flag.id, "production", state.version, first.id, flag_service=svc
        )
    svc.available = False
    state = set_pct(db, user("grace"), flag, "production", 20, svc)
    with pytest.raises(PermissionDenied):
        service.retry_push(db, user("frank"), flag.id, "production", state.version, svc)


# --- Business rules ---


def test_flag_key_must_be_valid_and_unique(db, user, svc):
    for bad in ("", "ab", "Has Caps", "9starts-with-digit", "spaces not ok"):
        with pytest.raises(ValidationError):
            new_flag(db, user, svc, key=bad)
    new_flag(db, user, svc, key="unique.key")
    with pytest.raises(RuleViolation, match="already exists"):
        new_flag(db, user, svc, key="unique.key")


def test_new_flag_starts_off_everywhere_and_is_pushed(db, user, svc):
    flag = new_flag(db, user, svc)
    for env in ("staging", "production"):
        state = flag.state(env)
        assert (state.enabled, state.rollout_pct, state.sync_status) == (False, 0, service.SYNCED)
        assert svc.get(env, flag.key).enabled is False


def test_rollout_must_be_between_0_and_100(db, user, svc):
    flag = new_flag(db, user, svc)
    for pct in (-1, 101):
        with pytest.raises(ValidationError):
            set_pct(db, user("frank"), flag, "staging", pct, svc)
    with pytest.raises(ValidationError):
        service.parse_pct("half")
    assert service.parse_pct("25%") == 25


def test_no_op_change_rejected(db, user, svc):
    flag = new_flag(db, user, svc)
    state = flag.state("staging")
    with pytest.raises(RuleViolation, match="No change"):
        service.set_enabled(db, user("frank"), flag.id, "staging", state.version, False, svc)


def test_unknown_environment_rejected(db, user, svc):
    flag = new_flag(db, user, svc)
    with pytest.raises(NotFound):
        service.set_enabled(db, user("admin"), flag.id, "qa", 1, True, flag_service=svc)


def test_staging_change_does_not_touch_production(db, user, svc):
    flag = new_flag(db, user, svc)
    set_pct(db, user("frank"), flag, "staging", 40, svc)
    assert flag.state("production").rollout_pct == 0
    assert svc.get("production", flag.key).rollout_pct == 0
    assert svc.get("staging", flag.key).rollout_pct == 40


def test_change_is_pushed_to_flag_service(db, user, svc):
    flag = new_flag(db, user, svc)
    state = turn_on(db, user("frank"), flag, "staging", svc)
    state = set_pct(db, user("frank"), flag, "staging", 15, svc)
    live = svc.get("staging", flag.key)
    assert (live.enabled, live.rollout_pct) == (True, 15)
    assert state.sync_status == service.SYNCED and state.pushed_revision == live.revision


def test_rollback_restores_previous_value(db, user, svc):
    flag = new_flag(db, user, svc)
    turn_on(db, user("frank"), flag, "staging", svc)
    set_pct(db, user("frank"), flag, "staging", 50, svc)
    good = service.history(db, user("frank"), flag.id, "staging")[0]  # ON at 50%
    state = set_pct(db, user("frank"), flag, "staging", 100, svc)

    state = service.rollback(
        db, user("frank"), flag.id, "staging", state.version, good.id, flag_service=svc
    )
    assert (state.enabled, state.rollout_pct) == (True, 50)
    assert (svc.get("staging", flag.key).rollout_pct, state.sync_status) == (50, service.SYNCED)
    latest = service.history(db, user("frank"), flag.id, "staging")[0]
    assert (latest.action, latest.rolled_back_to) == ("rollback", good.id)


def test_rollback_target_must_be_same_flag_and_environment(db, user, svc):
    flag = new_flag(db, user, svc)
    other = new_flag(db, user, svc, key="other.flag")
    state = turn_on(db, user("admin"), flag, "staging", svc)
    prod_change = service.history(db, user("admin"), flag.id, "production")[0]
    other_change = service.history(db, user("admin"), other.id, "staging")[0]
    for change_id in (prod_change.id, other_change.id, 999_999):
        with pytest.raises(RuleViolation, match="same flag in the same environment"):
            service.rollback(
                db, user("admin"), flag.id, "staging", state.version, change_id, flag_service=svc
            )


def test_rollback_to_current_value_rejected(db, user, svc):
    flag = new_flag(db, user, svc)
    state = flag.state("staging")
    current = service.history(db, user("frank"), flag.id, "staging")[0]
    with pytest.raises(RuleViolation, match="No change"):
        service.rollback(
            db, user("frank"), flag.id, "staging", state.version, current.id, flag_service=svc
        )


def test_failed_push_keeps_change_marks_out_of_sync_and_retry_fixes_it(db, user, svc):
    flag = new_flag(db, user, svc)
    svc.available = False
    state = turn_on(db, user("frank"), flag, "staging", svc)
    assert state.enabled and state.sync_status == service.FAILED
    assert svc.get("staging", flag.key).enabled is False  # not live yet

    with pytest.raises(PermissionDenied):  # still nothing an engineer can do in production
        service.retry_push(db, user("frank"), flag.id, "production", 1, svc)
    state = service.retry_push(db, user("frank"), flag.id, "staging", state.version, svc)
    assert state.sync_status == service.FAILED  # still down

    svc.available = True
    state = service.retry_push(db, user("frank"), flag.id, "staging", state.version, svc)
    assert state.sync_status == service.SYNCED and svc.get("staging", flag.key).enabled
    with pytest.raises(InvalidTransition, match="already in sync"):
        service.retry_push(db, user("frank"), flag.id, "staging", state.version, svc)


def test_late_push_cannot_overwrite_newer_value():
    svc = MockFlagService()
    svc.push("staging", "k.flag", enabled=True, rollout_pct=80, revision=7)
    live = svc.push("staging", "k.flag", enabled=True, rollout_pct=10, revision=6)
    assert (live.rollout_pct, live.revision) == (80, 7)


# --- Concurrency, audit, UI ---


def test_stale_update_rejected(db, user, login, svc):
    flag = new_flag(db, user, svc)
    stale = flag.state("staging").version
    turn_on(db, user("frank"), flag, "staging", svc)
    with pytest.raises(StaleWrite):
        service.set_rollout(db, user("frank"), flag.id, "staging", stale, 20, flag_service=svc)
    form = {"version": stale, "rollout_pct": "20"}
    response = login("frank").post(f"{PREFIX}/{flag.id}/staging/rollout", data=form)
    assert response.status_code == 409


def test_every_mutation_audited(db, user, svc):
    flag = new_flag(db, user, svc)
    first = service.history(db, user("frank"), flag.id, "staging")[0]
    turn_on(db, user("frank"), flag, "staging", svc)
    state = set_pct(db, user("grace"), flag, "production", 5, svc)
    svc.available = False
    state = service.rollback(
        db, user("frank"), flag.id, "staging", flag.state("staging").version, first.id, svc
    )
    svc.available = True
    service.retry_push(db, user("frank"), flag.id, "staging", state.version, svc)
    service.set_service_available(db, user("frank"), False, svc)

    events = [(e.action, e.actor) for e in audit.trail(db, service.ENTITY, flag.id)]
    assert events == [
        ("create", "frank"),
        ("push_result", "frank"),
        ("push_result", "frank"),
        ("toggle", "frank"),
        ("push_result", "frank"),
        ("rollout", "grace"),
        ("push_result", "grace"),
        ("rollback", "frank"),
        ("push_result", "frank"),
        ("retry_push", "frank"),
        ("push_result", "frank"),
    ]
    trail = audit.trail(db, service.ENTITY, flag.id)
    rollout = trail[5]
    assert (rollout.before, rollout.after) == (
        {"production.rollout_pct": 0},
        {"production.rollout_pct": 5},
    )
    assert trail[7].after["staging.rolled_back_to_change"] == first.id
    assert trail[8].after == {"staging.sync_status": service.FAILED}
    outage = audit.trail(db, "flag_service", "mock")[-1]
    assert (outage.actor, outage.after) == ("frank", {"available": False})


def test_detail_page_shows_history_and_rollback_by_role(db, user, login, svc):
    flag = new_flag(db, user, svc)
    turn_on(db, user("frank"), flag, "staging", svc)
    turn_on(db, user("grace"), flag, "production", svc)
    frank_page = login("frank").get(f"{PREFIX}/{flag.id}").text
    assert "Change history" in frank_page and "Audit trail" in frank_page
    assert f"/flags/{flag.id}/staging/rollback" in frank_page
    assert f"/flags/{flag.id}/production/rollback" not in frank_page
    assert "Changing production needs the release_manager role" in frank_page
    grace_page = login("grace").get(f"{PREFIX}/{flag.id}").text
    assert f"/flags/{flag.id}/production/rollback" in grace_page


def test_one_click_rollback_route(db, user, login, svc):
    flag = new_flag(db, user, svc)
    first = service.history(db, user("frank"), flag.id, "staging")[0]
    state = turn_on(db, user("frank"), flag, "staging", svc)
    form = {"version": state.version, "change_id": first.id}
    response = login("frank").post(f"{PREFIX}/{flag.id}/staging/rollback", data=form)
    assert response.status_code == 200 and "Rolled staging back" in response.text
    db.refresh(state)
    assert state.enabled is False and svc.get("staging", flag.key).enabled is False


def test_seeded_flags_are_live(client, login):
    page = login("frank").get(PREFIX).text
    assert "checkout.new-flow" in page and "ON · 25%" in page
