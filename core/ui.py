"""Shared Jinja environment. Tools render with `page(request, "<tool>/templates/x.html", ...)`."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import Environment, FileSystemLoader, select_autoescape

from core import masking, registry
from core.auth import list_users

ROOT = Path(__file__).resolve().parent.parent

env = Environment(
    loader=FileSystemLoader([str(ROOT / "core" / "templates"), str(ROOT / "tools")]),
    autoescape=select_autoescape(["html"]),
)
templates = Jinja2Templates(env=env)


def money(cents: int | None) -> str:
    return "" if cents is None else f"${cents / 100:,.2f}"


def dt(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else ""


def changes(before: dict | None, after: dict | None) -> str:
    before, after = before or {}, after or {}
    parts = []
    for key in dict.fromkeys([*before, *after]):
        if key in before and key in after:
            parts.append(f"{key}: {before[key]} → {after[key]}")
        elif key in after:
            parts.append(f"{key}: {after[key]}")
        else:
            parts.append(f"{key}: {before[key]} → (removed)")
    return "; ".join(parts)


env.filters.update(money=money, dt=dt, changes=changes)
env.globals.update(
    mask_value=masking.mask,
    can_reveal=masking.can_reveal,
    has_policy=lambda entity, field: masking.policy_for(entity, field) is not None,
)


def flash(request: Request, message: str, kind: str = "success") -> None:
    request.session["_flash"] = [
        *request.session.get("_flash", []),
        {"message": message, "kind": kind},
    ]


def page(request: Request, template: str, status_code: int = 200, **context):
    user = getattr(request.state, "user", None)
    with request.app.state.SessionLocal() as db:
        users = list_users(db)
    context = {
        "user": user,
        "all_users": users,
        "nav_tools": registry.visible_tools(user),
        "flashes": request.session.pop("_flash", []),
        "sso": getattr(request.app.state, "sso", None),
        **context,
    }
    return templates.TemplateResponse(request, template, context, status_code=status_code)
