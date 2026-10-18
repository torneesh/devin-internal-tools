from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from core import audit
from core.auth import CurrentUser, require_role
from core.db import get_db
from core.registry import register_tool
from core.ui import flash, page
from tools.kyc import service

TOOL = Path(__file__).parent.name
T = f"{TOOL}/templates"

router = APIRouter(prefix=f"/{TOOL}")
register_tool(
    name="KYC review queue",
    path=f"/{TOOL}",
    roles=service.VIEW_ROLES,
    description="Claim and decide customer verification cases. Escalations go to a supervisor.",
)


def _back(case_id: int) -> RedirectResponse:
    return RedirectResponse(f"/{TOOL}/{case_id}", status_code=303)


@router.get("")
def list_page(
    request: Request,
    queue: str = "all",
    user: CurrentUser = Depends(require_role(*service.VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    cases = service.list_cases(db, user, queue)
    return page(request, f"{T}/list.html", cases=cases, queue=queue, queues=service.QUEUES)


@router.get("/new")
def new_page(request: Request, user: CurrentUser = Depends(require_role(*service.INTAKE_ROLES))):
    return page(request, f"{T}/new.html", document_statuses=service.DOCUMENT_STATUSES)


@router.post("")
def create(
    request: Request,
    customer_name: str = Form(...),
    date_of_birth: str = Form(...),
    government_id: str = Form(...),
    country: str = Form(...),
    document_status: str = Form(...),
    user: CurrentUser = Depends(require_role(*service.INTAKE_ROLES)),
    db: Session = Depends(get_db),
):
    case = service.create_case(
        db,
        user,
        customer_name=customer_name,
        date_of_birth=date_of_birth,
        government_id=government_id,
        country=country,
        document_status=document_status,
    )
    flash(request, f"KYC case #{case.id} opened.")
    return _back(case.id)


@router.get("/{case_id}")
def detail_page(
    case_id: int,
    request: Request,
    user: CurrentUser = Depends(require_role(*service.VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    case = service.get_case(db, user, case_id)
    return page(
        request,
        f"{T}/detail.html",
        case=case,
        trail=audit.trail(db, service.ENTITY, case.id),
        flow=service.FLOW,
    )


@router.post("/{case_id}/claim")
def claim(
    case_id: int,
    request: Request,
    version: int = Form(...),
    user: CurrentUser = Depends(require_role(*service.ANALYST_ROLES)),
    db: Session = Depends(get_db),
):
    service.claim(db, user, case_id, version)
    flash(request, "Case claimed. It's in your queue.")
    return _back(case_id)


@router.post("/{case_id}/release")
def release(
    case_id: int,
    request: Request,
    version: int = Form(...),
    user: CurrentUser = Depends(require_role(*service.ANALYST_ROLES)),
    db: Session = Depends(get_db),
):
    service.release(db, user, case_id, version)
    flash(request, "Case released back to the open queue.")
    return _back(case_id)


@router.post("/{case_id}/approve")
def approve(
    case_id: int,
    request: Request,
    version: int = Form(...),
    reason: str = Form(""),
    user: CurrentUser = Depends(require_role(*service.ANALYST_ROLES)),
    db: Session = Depends(get_db),
):
    service.approve(db, user, case_id, version, reason)
    flash(request, "Case approved.")
    return _back(case_id)


@router.post("/{case_id}/reject")
def reject(
    case_id: int,
    request: Request,
    version: int = Form(...),
    reason: str = Form(""),
    user: CurrentUser = Depends(require_role(*service.ANALYST_ROLES)),
    db: Session = Depends(get_db),
):
    service.reject(db, user, case_id, version, reason)
    flash(request, "Case rejected.")
    return _back(case_id)


@router.post("/{case_id}/escalate")
def escalate(
    case_id: int,
    request: Request,
    version: int = Form(...),
    reason: str = Form(""),
    user: CurrentUser = Depends(require_role(*service.ANALYST_ROLES)),
    db: Session = Depends(get_db),
):
    service.escalate(db, user, case_id, version, reason)
    flash(request, "Case escalated to a supervisor.")
    return _back(case_id)


@router.post("/{case_id}/resolve")
def resolve(
    case_id: int,
    request: Request,
    version: int = Form(...),
    outcome: str = Form(...),
    reason: str = Form(""),
    user: CurrentUser = Depends(require_role(*service.SUPERVISOR_ROLES)),
    db: Session = Depends(get_db),
):
    case = service.resolve(db, user, case_id, version, outcome, reason)
    flash(request, f"Escalation resolved: {case.status}.")
    return _back(case_id)
