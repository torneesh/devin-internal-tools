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
from tools._template import service

TOOL = Path(__file__).parent.name  # the folder name is the URL prefix
T = f"{TOOL}/templates"

router = APIRouter(prefix=f"/{TOOL}")
register_tool(
    name="Template",
    path=f"/{TOOL}",
    roles=service.VIEW_ROLES,
    description="Copy-me example tool.",
)


@router.get("")
def list_page(
    request: Request,
    user: CurrentUser = Depends(require_role(*service.VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    return page(request, f"{T}/list.html", items=service.list_items(db, user), tool=TOOL)


@router.post("")
def create(
    request: Request,
    title: str = Form(...),
    contact_email: str = Form(...),
    user: CurrentUser = Depends(require_role(*service.EDIT_ROLES)),
    db: Session = Depends(get_db),
):
    item = service.create_item(db, user, title=title, contact_email=contact_email)
    flash(request, f"Item #{item.id} created.")
    return RedirectResponse(f"/{TOOL}/{item.id}", status_code=303)


@router.get("/{item_id}")
def detail_page(
    item_id: int,
    request: Request,
    user: CurrentUser = Depends(require_role(*service.VIEW_ROLES)),
    db: Session = Depends(get_db),
):
    item = service.get_item(db, user, item_id)
    trail = audit.trail(db, service.ENTITY, item.id)
    return page(request, f"{T}/detail.html", item=item, trail=trail, tool=TOOL)


@router.post("/{item_id}/complete")
def complete(
    item_id: int,
    request: Request,
    version: int = Form(...),
    user: CurrentUser = Depends(require_role(*service.EDIT_ROLES)),
    db: Session = Depends(get_db),
):
    service.complete_item(db, user, item_id, version)
    flash(request, "Marked done.")
    return RedirectResponse(f"/{TOOL}/{item_id}", status_code=303)
