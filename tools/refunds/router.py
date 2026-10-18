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
from tools.refunds import service
from tools.refunds.provider import MODES

TOOL = Path(__file__).parent.name
T = f"{TOOL}/templates"

router = APIRouter(prefix=f"/{TOOL}")
register_tool(
    name="Refunds",
    path=f"/{TOOL}",
    roles=service.VIEW_ROLES,
    description="Request, approve and pay customer refunds. Dual approval over $1,000.",
)


def _back(refund_id: int) -> RedirectResponse:
    return RedirectResponse(f"/{TOOL}/{refund_id}", status_code=303)


@router.get("")
def list_page(
    request: Request,
    status: str = "",
    user: CurrentUser = Depends(require_role(*service.VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    refunds = service.list_refunds(db, user, status or None)
    return page(
        request, f"{T}/list.html", refunds=refunds, status=status, statuses=service.FLOW.states
    )


@router.get("/new")
def new_page(request: Request, user: CurrentUser = Depends(require_role(*service.REQUEST_ROLES))):
    return page(request, f"{T}/new.html")


@router.post("")
def create(
    request: Request,
    txn_id: str = Form(...),
    customer_name: str = Form(...),
    bank_account: str = Form(...),
    amount: str = Form(...),
    reason: str = Form(...),
    user: CurrentUser = Depends(require_role(*service.REQUEST_ROLES)),
    db: Session = Depends(get_db),
):
    refund = service.create_refund(
        db,
        user,
        txn_id=txn_id,
        customer_name=customer_name,
        bank_account=bank_account,
        amount_cents=service.parse_amount(amount),
        reason=reason,
    )
    flash(request, f"Refund #{refund.id} requested.")
    return RedirectResponse(f"/{TOOL}/{refund.id}", status_code=303)


@router.get("/{refund_id}")
def detail_page(
    refund_id: int,
    request: Request,
    user: CurrentUser = Depends(require_role(*service.VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    refund = service.get_refund(db, user, refund_id)
    return page(
        request,
        f"{T}/detail.html",
        refund=refund,
        trail=audit.trail(db, service.ENTITY, refund.id),
        required=service.APPROVALS.required(refund.amount_cents),
        flow=service.FLOW,
        modes=MODES,
    )


@router.post("/{refund_id}/approve")
def approve(
    refund_id: int,
    request: Request,
    version: int = Form(...),
    user: CurrentUser = Depends(require_role(*service.APPROVE_ROLES)),
    db: Session = Depends(get_db),
):
    refund = service.approve(db, user, refund_id, version)
    flash(request, f"Approved. Status: {refund.status}.")
    return _back(refund_id)


@router.post("/{refund_id}/reject")
def reject(
    refund_id: int,
    request: Request,
    version: int = Form(...),
    reason: str = Form(""),
    user: CurrentUser = Depends(require_role(*service.APPROVE_ROLES)),
    db: Session = Depends(get_db),
):
    service.reject(db, user, refund_id, version, reason)
    flash(request, "Refund rejected.")
    return _back(refund_id)


@router.post("/{refund_id}/mode")
def set_mode(
    refund_id: int,
    request: Request,
    version: int = Form(...),
    mode: str = Form(...),
    user: CurrentUser = Depends(require_role(*service.REQUEST_ROLES, *service.APPROVE_ROLES)),
    db: Session = Depends(get_db),
):
    service.set_provider_mode(db, user, refund_id, version, mode)
    flash(request, f"Mock provider mode set to {mode}.")
    return _back(refund_id)


@router.post("/{refund_id}/execute")
def execute(
    refund_id: int,
    request: Request,
    version: int = Form(...),
    user: CurrentUser = Depends(require_role(*service.APPROVE_ROLES)),
    db: Session = Depends(get_db),
):
    refund = service.execute(db, user, refund_id, version)
    kind = "success" if refund.status == service.SUCCEEDED else "error"
    flash(request, f"Execution result: {refund.status}. {refund.provider_note or ''}", kind)
    return _back(refund_id)


@router.post("/{refund_id}/reconcile")
def reconcile(
    refund_id: int,
    request: Request,
    version: int = Form(...),
    user: CurrentUser = Depends(require_role(*service.APPROVE_ROLES)),
    db: Session = Depends(get_db),
):
    refund = service.reconcile(db, user, refund_id, version)
    flash(request, f"Reconciled: {refund.status}.")
    return _back(refund_id)
