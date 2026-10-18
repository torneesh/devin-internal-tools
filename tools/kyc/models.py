from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.db import Base, VersionedMixin


class KycCase(VersionedMixin, Base):
    __tablename__ = "kyc_cases"

    customer_name: Mapped[str] = mapped_column(String(200))
    date_of_birth: Mapped[str] = mapped_column(String(10))  # ISO date; protected: core.masking
    government_id: Mapped[str] = mapped_column(String(64))  # protected: core.masking
    country: Mapped[str] = mapped_column(String(2))  # ISO 3166-1 alpha-2
    document_status: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="OPEN", index=True)
    created_by: Mapped[str] = mapped_column(String(64))
    assigned_to: Mapped[str | None] = mapped_column(String(64), index=True)
    escalated_by: Mapped[str | None] = mapped_column(String(64))
    escalation_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[str | None] = mapped_column(String(64))
    decision_reason: Mapped[str | None] = mapped_column(Text)
