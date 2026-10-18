from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, VersionedMixin


class Item(VersionedMixin, Base):
    __tablename__ = "template_items"  # rename: <tool>_<things>

    title: Mapped[str] = mapped_column(String(200))
    owner: Mapped[str] = mapped_column(String(64))
    contact_email: Mapped[str] = mapped_column(String(200))  # protected: core.masking
    status: Mapped[str] = mapped_column(String(20), default="OPEN")
    notes: Mapped[str | None] = mapped_column(Text)
