from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from core import audit, integrations
from core.auth import CurrentUser, require_role
from core.db import get_db
from core.registry import register_tool
from core.ui import flash, page
from tools.flags import service
from tools.flags.models import ENVIRONMENTS

TOOL = Path(__file__).parent.name
T = f"{TOOL}/templates"

router = APIRouter(prefix=f"/{TOOL}")
register_tool(
    name="Feature flags",
    path=f"/{TOOL}",
    roles=service.VIEW_ROLES,
    description="Toggle flags and rollout % per environment. Production: release managers only.",
)

EDITORS = require_role(*service.ANY_EDIT_ROLES)


def _back(flag_id: int) -> RedirectResponse:
    return RedirectResponse(f"/{TOOL}/{flag_id}", status_code=303)


def _flash_result(request: Request, state, message: str) -> None:
    if state.sync_status == service.FAILED:
        flash(request, f"{message} Push to flag service FAILED: {state.sync_note}", "error")
    else:
        flash(request, f"{message} {state.sync_note or ''}")


@router.get("")
def list_page(
    request: Request,
    user: CurrentUser = Depends(require_role(*service.VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    return page(
        request,
        f"{T}/list.html",
        flags=service.list_flags(db, user),
        service_available=integrations.get("flag_service").available,
        can_create=user.has_role(*service.CREATE_ROLES),
        can_demo=user.has_role(*service.ANY_EDIT_ROLES),
        tool=TOOL,
    )


@router.post("")
def create(
    request: Request,
    key: str = Form(...),
    description: str = Form(""),
    user: CurrentUser = Depends(require_role(*service.CREATE_ROLES)),
    db: Session = Depends(get_db),
):
    flag = service.create_flag(db, user, key=key, description=description)
    flash(
        request,
        f"Flag {flag.key} created: OFF at 0% in staging. Production is not set and nothing "
        "was pushed there; a release manager's first production change pushes it.",
    )
    return _back(flag.id)


@router.post("/service-mode")
def set_service_mode(
    request: Request,
    available: str = Form(...),
    user: CurrentUser = Depends(EDITORS),
    db: Session = Depends(get_db),
):
    up = available == "up"
    service.set_service_available(db, user, up)
    flash(request, "Mock flag service is " + ("up." if up else "DOWN (simulated outage)."))
    return RedirectResponse(f"/{TOOL}", status_code=303)


@router.get("/{flag_id}")
def detail_page(
    flag_id: int,
    request: Request,
    user: CurrentUser = Depends(require_role(*service.VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    flag = service.get_flag(db, user, flag_id)
    return page(
        request,
        f"{T}/detail.html",
        flag=flag,
        environments=ENVIRONMENTS,
        history={env: service.history(db, user, flag.id, env) for env in ENVIRONMENTS},
        live=service.live_values(user, flag),
        can_edit={env: service.can_edit(user, env) for env in ENVIRONMENTS},
        edit_roles=service.EDIT_ROLES,
        trail=audit.trail(db, service.ENTITY, flag.id),
        tool=TOOL,
    )


@router.post("/{flag_id}/{environment}/toggle")
def toggle(
    flag_id: int,
    environment: str,
    request: Request,
    version: int = Form(...),
    enabled: str = Form(...),
    user: CurrentUser = Depends(EDITORS),
    db: Session = Depends(get_db),
):
    on = enabled == "true"
    state = service.set_enabled(db, user, flag_id, environment, version, on)
    _flash_result(request, state, f"Turned {'ON' if on else 'OFF'} in {environment}.")
    return _back(flag_id)


@router.post("/{flag_id}/{environment}/rollout")
def rollout(
    flag_id: int,
    environment: str,
    request: Request,
    version: int = Form(...),
    rollout_pct: str = Form(...),
    user: CurrentUser = Depends(EDITORS),
    db: Session = Depends(get_db),
):
    pct = service.parse_pct(rollout_pct)
    state = service.set_rollout(db, user, flag_id, environment, version, pct)
    _flash_result(request, state, f"Rollout in {environment} set to {pct}%.")
    return _back(flag_id)


@router.post("/{flag_id}/{environment}/rollback")
def rollback(
    flag_id: int,
    environment: str,
    request: Request,
    version: int = Form(...),
    change_id: int = Form(...),
    user: CurrentUser = Depends(EDITORS),
    db: Session = Depends(get_db),
):
    state = service.rollback(db, user, flag_id, environment, version, change_id)
    _flash_result(
        request, state, f"Rolled {environment} back to change #{change_id} ({state.summary})."
    )
    return _back(flag_id)


@router.post("/{flag_id}/{environment}/retry")
def retry(
    flag_id: int,
    environment: str,
    request: Request,
    version: int = Form(...),
    user: CurrentUser = Depends(EDITORS),
    db: Session = Depends(get_db),
):
    state = service.retry_push(db, user, flag_id, environment, version)
    _flash_result(request, state, f"Retried push for {environment}.")
    return _back(flag_id)
