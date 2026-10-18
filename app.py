"""FastAPI app: platform routes + every tools/<name>/router.py, discovered automatically.

Run: make run  (uvicorn app:create_app --factory)
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from core import audit, auth, errors, masking, registry, sso
from core.auth import CurrentUser, require_role
from core.db import Base, get_db, make_engine, make_sessionmaker
from core.ui import page

TOOLS_DIR = Path(__file__).resolve().parent / "tools"

audit_router = APIRouter()


@audit_router.get("/audit")
def audit_log(
    request: Request,
    entity: str = "",
    actor: str = "",
    action: str = "",
    user: CurrentUser = Depends(require_role("auditor")),
    db: Session = Depends(get_db),
):
    return page(
        request,
        "audit.html",
        events=audit.search(db, entity or None, actor or None, action or None),
        entities=audit.distinct(db, "entity"),
        actors=audit.distinct(db, "actor"),
        actions=audit.distinct(db, "action"),
        f_entity=entity,
        f_actor=actor,
        f_action=action,
    )


def discover_tools(include_template: bool = False) -> list[str]:
    """tools/<name>/ with a router.py. `_template` is only mounted when asked (tests)."""
    return sorted(
        p.name
        for p in TOOLS_DIR.iterdir()
        if (p / "router.py").exists() and (include_template or not p.name.startswith("_"))
    )


def create_app(
    database_url: str | None = None,
    *,
    include_template: bool = False,
    seed_data: bool = True,
    fake_data: bool | None = None,
    sso_config: sso.SsoConfig | None = None,
) -> FastAPI:
    app = FastAPI(title="Internal Tools")
    app.add_middleware(
        SessionMiddleware,
        secret_key=os.environ.get("SESSION_SECRET", "dev-only-not-a-secret"),
        same_site="lax",
        max_age=8 * 3600,
        https_only=os.environ.get("SESSION_HTTPS_ONLY") == "1",
    )
    errors.install(app)
    app.state.sso = sso_config or sso.config_from_env()
    if app.state.sso:
        app.include_router(sso.build_router(app.state.sso))
    for router in (auth.router, masking.router, registry.router, audit_router):
        app.include_router(router)
    for name in discover_tools(include_template):
        app.include_router(importlib.import_module(f"tools.{name}.router").router)

    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    app.state.engine = engine
    app.state.SessionLocal = make_sessionmaker(engine)
    if seed_data:
        import seed

        with app.state.SessionLocal() as db:
            if fake_data is None:
                fake_data = os.environ.get("FAKE_DATA", "1") == "1"
            seed.seed(db, fake_data=fake_data)
    return app
