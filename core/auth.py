"""Mock SSO and role-based access.

The session cookie holds a username picked on /login (the "user switcher"). In production,
replace `login_submit` with an OIDC callback (Entra ID / Okta) that maps IdP groups to roles.
Everything downstream depends only on `current_user` / `require_role`, so nothing else changes.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import JSON, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from core import audit
from core.db import Base, get_db
from core.errors import NotAuthenticated, PermissionDenied


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    roles: Mapped[list[str]] = mapped_column(JSON, default=list)


@dataclass(frozen=True)
class CurrentUser:
    username: str
    display_name: str
    roles: frozenset[str]

    def has_role(self, *roles: str) -> bool:
        return bool(self.roles.intersection(roles))


def _to_current(user: User) -> CurrentUser:
    return CurrentUser(user.username, user.display_name, frozenset(user.roles or []))


def load_user(db: Session, username: str) -> CurrentUser | None:
    user = db.scalar(select(User).where(User.username == username))
    return _to_current(user) if user else None


def list_users(db: Session) -> list[CurrentUser]:
    return [_to_current(u) for u in db.scalars(select(User).order_by(User.id))]


def ensure_role(user: CurrentUser, *roles: str) -> None:
    """Call at the top of every service function that needs a role."""
    if not user.has_role(*roles):
        raise PermissionDenied(
            f"This needs the {' or '.join(roles)} role. "
            f"{user.username} has: {', '.join(sorted(user.roles)) or 'no roles'}."
        )


def current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    username = request.session.get("user")
    user = load_user(db, username) if username else None
    if user is None:
        request.session.pop("user", None)
        raise NotAuthenticated()
    request.state.user = user
    return user


def require_role(*roles: str):
    """Route dependency: `user: CurrentUser = Depends(require_role("refund_approver"))`."""

    def dependency(user: CurrentUser = Depends(current_user)) -> CurrentUser:
        ensure_role(user, *roles)
        return user

    return dependency


router = APIRouter()


@router.get("/login")
def login_page(request: Request, db: Session = Depends(get_db)):
    from core.ui import page

    return page(request, "login.html", users=list_users(db))


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    next: str = Form("/"),
    db: Session = Depends(get_db),
):
    user = load_user(db, username)
    if user is None:
        raise NotAuthenticated(f"Unknown user {username!r}")
    request.session["user"] = user.username
    audit.record(db, user, "login", "users", user.username)
    db.commit()
    target = next if next.startswith("/") and not next.startswith("//") else "/"
    return RedirectResponse(target, status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
