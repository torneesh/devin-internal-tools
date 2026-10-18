"""Feature-flag rules. Every function: check role -> check rules -> change -> audit -> commit.

The database holds the desired value of each flag per environment and is committed first. The
flag service is then sent the full state (never a delta) tagged with the change id as revision,
so retries are safe and late pushes can't overwrite newer ones. If a push fails, the change
stays saved, the state is marked FAILED (out of sync) and anyone allowed to edit can retry.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from core import audit, integrations
from core.auth import CurrentUser, ensure_role
from core.concurrency import update_versioned
from core.errors import InvalidTransition, NotFound, RuleViolation, StaleWrite, ValidationError
from core.workflow import StateMachine
from tools.flags.flag_service import FlagServiceUnavailable, LiveFlag
from tools.flags.models import ENVIRONMENTS, Flag, FlagChange, FlagState

ENTITY = Flag.__tablename__
STAGING, PRODUCTION = ENVIRONMENTS

PENDING, SYNCED, FAILED = "PENDING", "SYNCED", "FAILED"
SYNC_FLOW = StateMachine(
    {
        PENDING: {PENDING, SYNCED, FAILED},  # PENDING -> PENDING: a newer change before the push
        SYNCED: {PENDING},
        FAILED: {PENDING},
    }
)

VIEW_ROLES = ("engineer", "release_manager", "auditor")
CREATE_ROLES = ("engineer",)
EDIT_ROLES = {
    STAGING: ("engineer", "release_manager"),
    PRODUCTION: ("release_manager",),
}
ANY_EDIT_ROLES = tuple(dict.fromkeys(r for roles in EDIT_ROLES.values() for r in roles))

KEY_PATTERN = re.compile(r"^[a-z][a-z0-9._-]{2,63}$")


def can_edit(user: CurrentUser, environment: str) -> bool:
    return user.has_role(*EDIT_ROLES.get(environment, ()))


def parse_pct(text: str) -> int:
    try:
        pct = int(str(text).strip().rstrip("%"))
    except ValueError:
        raise ValidationError("Rollout must be a whole number from 0 to 100.") from None
    return pct


def list_flags(db: Session, user: CurrentUser) -> list[Flag]:
    ensure_role(user, *VIEW_ROLES)
    return list(db.scalars(select(Flag).order_by(Flag.key)))


def get_flag(db: Session, user: CurrentUser, flag_id: int) -> Flag:
    ensure_role(user, *VIEW_ROLES)
    flag = db.get(Flag, flag_id)
    if flag is None:
        raise NotFound(f"Flag {flag_id} not found")
    return flag


def get_state(db: Session, user: CurrentUser, flag_id: int, environment: str) -> FlagState:
    if environment not in ENVIRONMENTS:
        raise NotFound(f"Unknown environment {environment!r}")
    return get_flag(db, user, flag_id).state(environment)


def history(db: Session, user: CurrentUser, flag_id: int, environment: str) -> list[FlagChange]:
    """Every value the flag has had in `environment`, newest first."""
    ensure_role(user, *VIEW_ROLES)
    query = (
        select(FlagChange)
        .where(FlagChange.flag_id == flag_id, FlagChange.environment == environment)
        .order_by(FlagChange.id.desc())
    )
    return list(db.scalars(query))


def live_values(user: CurrentUser, flag: Flag, flag_service=None) -> dict[str, LiveFlag | None]:
    """What the flag service is currently serving, per environment."""
    ensure_role(user, *VIEW_ROLES)
    flag_service = flag_service or integrations.get("flag_service")
    return {env: flag_service.get(env, flag.key) for env in ENVIRONMENTS}


def create_flag(
    db: Session, user: CurrentUser, *, key: str, description: str = "", flag_service=None
) -> Flag:
    """New flags start OFF at 0% in every environment (a no-op for production behaviour)."""
    ensure_role(user, *CREATE_ROLES)
    key = key.strip()
    if not KEY_PATTERN.match(key):
        raise ValidationError(
            "Flag keys are 3-64 characters: lowercase letters, digits, '.', '-' or '_', "
            "starting with a letter (e.g. checkout.new-flow)."
        )
    if db.scalar(select(Flag).where(Flag.key == key)):
        raise RuleViolation(f"A flag with key {key!r} already exists.")
    flag = Flag(key=key, description=description.strip(), created_by=user.username)
    flag.states = [FlagState(environment=env, sync_status=PENDING) for env in ENVIRONMENTS]
    db.add(flag)
    db.flush()
    changes = []
    for state in flag.states:
        change = FlagChange(
            flag_id=flag.id,
            environment=state.environment,
            action="create",
            enabled=state.enabled,
            rollout_pct=state.rollout_pct,
            changed_by=user.username,
        )
        db.add(change)
        changes.append((state, change))
    db.flush()
    after = audit.snapshot(flag, "key", "description", "created_by")
    after.update({s.environment: s.summary for s in flag.states})
    audit.record(db, user, "create", ENTITY, flag.id, after=after)
    db.commit()
    for state, change in changes:
        _push(db, user, flag, state, change, flag_service)
    return flag


def set_enabled(
    db: Session,
    user: CurrentUser,
    flag_id: int,
    environment: str,
    expected_version: int,
    enabled: bool,
    flag_service=None,
) -> FlagState:
    ensure_role(user, *EDIT_ROLES.get(environment, ANY_EDIT_ROLES))
    state = get_state(db, user, flag_id, environment)
    return _change(
        db, user, state, expected_version, "toggle", enabled, state.rollout_pct, flag_service
    )


def set_rollout(
    db: Session,
    user: CurrentUser,
    flag_id: int,
    environment: str,
    expected_version: int,
    rollout_pct: int,
    flag_service=None,
) -> FlagState:
    ensure_role(user, *EDIT_ROLES.get(environment, ANY_EDIT_ROLES))
    state = get_state(db, user, flag_id, environment)
    if not 0 <= rollout_pct <= 100:
        raise ValidationError("Rollout must be a whole number from 0 to 100.")
    return _change(
        db, user, state, expected_version, "rollout", state.enabled, rollout_pct, flag_service
    )


def rollback(
    db: Session,
    user: CurrentUser,
    flag_id: int,
    environment: str,
    expected_version: int,
    change_id: int,
    flag_service=None,
) -> FlagState:
    """Restore the value recorded in history entry `change_id` (one click, no reason needed)."""
    ensure_role(user, *EDIT_ROLES.get(environment, ANY_EDIT_ROLES))
    state = get_state(db, user, flag_id, environment)
    target = db.get(FlagChange, change_id)
    if target is None or (target.flag_id, target.environment) != (flag_id, environment):
        raise RuleViolation(
            "You can only roll back to a previous value of the same flag in the same environment."
        )
    return _change(
        db,
        user,
        state,
        expected_version,
        "rollback",
        target.enabled,
        target.rollout_pct,
        flag_service,
        rolled_back_to=target.id,
    )


def retry_push(
    db: Session,
    user: CurrentUser,
    flag_id: int,
    environment: str,
    expected_version: int,
    flag_service=None,
) -> FlagState:
    """Re-send the current value after a failed (or interrupted) push."""
    ensure_role(user, *EDIT_ROLES.get(environment, ANY_EDIT_ROLES))
    state = get_state(db, user, flag_id, environment)
    if state.sync_status == SYNCED:
        raise InvalidTransition("This environment is already in sync with the flag service.")
    SYNC_FLOW.check(state.sync_status, PENDING)
    change = history(db, user, flag_id, environment)[0]
    before = update_versioned(db, state, expected_version, sync_status=PENDING, sync_note=None)
    audit.record(
        db,
        user,
        "retry_push",
        ENTITY,
        flag_id,
        before=_prefixed(environment, before),
        after=_prefixed(environment, {"sync_status": PENDING}),
    )
    db.commit()
    return _push(db, user, state.flag, state, change, flag_service)


def set_service_available(
    db: Session, user: CurrentUser, available: bool, flag_service=None
) -> None:
    """Demo only: simulate a flag service outage so the FAILED -> retry path can be shown."""
    ensure_role(user, *ANY_EDIT_ROLES)
    flag_service = flag_service or integrations.get("flag_service")
    before = {"available": flag_service.available}
    flag_service.available = available
    audit.record(
        db, user, "set_service_mode", "flag_service", "mock", before, {"available": available}
    )
    db.commit()


def _prefixed(environment: str, data: dict) -> dict:
    return {f"{environment}.{k}": v for k, v in data.items()}


def _change(
    db: Session,
    user: CurrentUser,
    state: FlagState,
    expected_version: int,
    action: str,
    enabled: bool,
    rollout_pct: int,
    flag_service=None,
    rolled_back_to: int | None = None,
) -> FlagState:
    if expected_version is None or int(expected_version) != state.version:
        raise StaleWrite()
    if (state.enabled, state.rollout_pct) == (enabled, rollout_pct):
        raise RuleViolation(f"No change: {state.environment} is already {state.summary}.")
    SYNC_FLOW.check(state.sync_status, PENDING)
    before = update_versioned(
        db,
        state,
        expected_version,
        enabled=enabled,
        rollout_pct=rollout_pct,
        sync_status=PENDING,
        sync_note=None,
    )
    change = FlagChange(
        flag_id=state.flag_id,
        environment=state.environment,
        action=action,
        enabled=enabled,
        rollout_pct=rollout_pct,
        changed_by=user.username,
        rolled_back_to=rolled_back_to,
    )
    db.add(change)
    db.flush()
    changed = [k for k in ("enabled", "rollout_pct") if before[k] != getattr(state, k)]
    after = {k: getattr(state, k) for k in changed}
    if rolled_back_to:
        after["rolled_back_to_change"] = rolled_back_to
    audit.record(
        db,
        user,
        action,
        ENTITY,
        state.flag_id,
        before=_prefixed(state.environment, {k: before[k] for k in changed}),
        after=_prefixed(state.environment, after),
    )
    db.commit()
    return _push(db, user, state.flag, state, change, flag_service)


def _push(
    db: Session, user: CurrentUser, flag: Flag, state: FlagState, change: FlagChange, flag_service
) -> FlagState:
    flag_service = flag_service or integrations.get("flag_service")
    try:
        live = flag_service.push(
            change.environment,
            flag.key,
            enabled=change.enabled,
            rollout_pct=change.rollout_pct,
            revision=change.id,
        )
    except FlagServiceUnavailable as exc:
        result = {
            "sync_status": FAILED,
            "sync_note": f"{exc}. The change is saved here but NOT live: retry the push.",
        }
    else:
        if live.revision != change.id:
            return state  # a newer change already reached the service; its push records sync
        result = {
            "sync_status": SYNCED,
            "sync_note": f"Live in flag service (revision {change.id})",
            "pushed_revision": change.id,
        }
    SYNC_FLOW.check(state.sync_status, result["sync_status"])
    try:
        before = update_versioned(db, state, state.version, **result)
    except StaleWrite:
        db.refresh(state)
        return state  # someone changed it since; their push records the newer sync status
    audit.record(
        db,
        user,
        "push_result",
        ENTITY,
        flag.id,
        before=_prefixed(state.environment, {"sync_status": before["sync_status"]}),
        after=_prefixed(state.environment, {"sync_status": result["sync_status"]}),
        reason=result["sync_note"],
    )
    db.commit()
    return state
