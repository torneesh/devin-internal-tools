"""Real SSO over OpenID Connect (Keycloak locally; Entra ID or Okta in production).

Enabled when OIDC_ISSUER is set. The identity provider owns who a user is and which groups
they are in; each group name is a role here. Users are created or updated on every sign-in,
so a group change in the IdP changes access at the next login, and the change is audited.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlencode

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from core import audit
from core.auth import CurrentUser, User, _to_current
from core.db import get_db
from core.errors import NotAuthenticated


@dataclass(frozen=True)
class SsoConfig:
    issuer: str
    client_id: str
    client_secret: str
    metadata_url: str  # may differ from the issuer when the app reaches the IdP on a private URL
    base_url: str | None = None  # public URL of this app, for the redirect URI behind a proxy


def config_from_env() -> SsoConfig | None:
    issuer = os.environ.get("OIDC_ISSUER")
    if not issuer:
        return None
    return SsoConfig(
        issuer=issuer,
        client_id=os.environ["OIDC_CLIENT_ID"],
        client_secret=os.environ["OIDC_CLIENT_SECRET"],
        metadata_url=os.environ.get(
            "OIDC_METADATA_URL", f"{issuer.rstrip('/')}/.well-known/openid-configuration"
        ),
        base_url=os.environ.get("APP_BASE_URL"),
    )


def provision(db: Session, claims: dict, issuer: str) -> CurrentUser:
    """Create or update the local user from ID-token claims, auditing any role change."""
    username = claims.get("preferred_username") or claims["sub"]
    display_name = claims.get("name") or username
    roles = sorted(set(claims.get("groups") or []))
    user = db.scalar(select(User).where(User.username == username))
    before = None
    if user is None:
        user = User(username=username, display_name=display_name, roles=roles)
        db.add(user)
    else:
        before = {"roles": sorted(user.roles or [])}
        user.display_name, user.roles = display_name, roles
    db.flush()
    current = _to_current(user)
    after = {"roles": roles}
    audit.record(
        db,
        current,
        "login",
        "users",
        username,
        before=before if before != after else None,
        after=after if before != after else None,
        reason=f"SSO via {issuer}",
    )
    db.commit()
    return current


def build_router(config: SsoConfig) -> APIRouter:
    oauth = OAuth()
    oauth.register(
        "idp",
        client_id=config.client_id,
        client_secret=config.client_secret,
        server_metadata_url=config.metadata_url,
        client_kwargs={"scope": "openid profile email", "code_challenge_method": "S256"},
    )
    router = APIRouter()

    def _url(request: Request, name: str) -> str:
        if config.base_url:
            return config.base_url.rstrip("/") + request.app.url_path_for(name)
        return str(request.url_for(name))

    @router.get("/auth/login")
    async def sso_login(request: Request):
        return await oauth.idp.authorize_redirect(request, _url(request, "sso_callback"))

    @router.get("/auth/callback", name="sso_callback")
    async def sso_callback(request: Request, db: Session = Depends(get_db)):
        try:
            token = await oauth.idp.authorize_access_token(request)
        except OAuthError as exc:
            raise NotAuthenticated(f"Sign-in failed: {exc.description or exc.error}") from exc
        user = provision(db, token["userinfo"], config.issuer)
        request.session.clear()
        request.session.update(user=user.username, id_token=token.get("id_token"))
        return RedirectResponse("/", status_code=303)

    @router.get("/auth/logout")
    async def sso_logout(request: Request):
        id_token = request.session.get("id_token")
        request.session.clear()
        metadata = await oauth.idp.load_server_metadata()
        end_session = metadata.get("end_session_endpoint")
        if not end_session:
            return RedirectResponse("/login", status_code=303)
        params = {
            "client_id": config.client_id,
            "post_logout_redirect_uri": _url(request, "login_page"),
        }
        if id_token:
            params["id_token_hint"] = id_token
        return RedirectResponse(f"{end_session}?{urlencode(params)}", status_code=303)

    return router
