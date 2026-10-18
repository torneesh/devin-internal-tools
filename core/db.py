"""Engine, sessions, and the VersionedMixin every tool model uses.

SQLite locally; keep SQL portable so DATABASE_URL can point at Postgres later.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy import DateTime, Engine, create_engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    declared_attr,
    mapped_column,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

DEFAULT_DATABASE_URL = "sqlite:///./app.db"


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class VersionedMixin:
    """id, version, created_at, updated_at.

    Every UPDATE is issued as `... WHERE id = :id AND version = :old_version`, so a write
    based on a stale read fails instead of silently overwriting (see core.concurrency).
    """

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    @declared_attr.directive
    def __mapper_args__(cls) -> dict:
        return {"version_id_col": cls.version, "version_id_generator": False}


def make_engine(url: str | None = None) -> Engine:
    url = url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    if not url.startswith("sqlite"):
        return create_engine(url)
    kwargs: dict = {"connect_args": {"check_same_thread": False}}
    if url in ("sqlite://", "sqlite:///:memory:"):
        kwargs["poolclass"] = StaticPool
    return create_engine(url, **kwargs)


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one session per request. Uncommitted work is rolled back on close."""
    db = request.app.state.SessionLocal()
    try:
        yield db
    finally:
        db.close()
