from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base, VersionedMixin


class Refund(VersionedMixin, Base):
    __tablename__ = "refunds"

    txn_id: Mapped[str] = mapped_column(String(64))
    customer_name: Mapped[str] = mapped_column(String(200))
    bank_account: Mapped[str] = mapped_column(String(64))  # protected: core.masking
    amount_cents: Mapped[int]
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="REQUESTED", index=True)
    requested_by: Mapped[str] = mapped_column(String(64))
    idempotency_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    provider_ref: Mapped[str | None] = mapped_column(String(64))
    provider_note: Mapped[str | None] = mapped_column(Text)
    provider_mode: Mapped[str] = mapped_column(String(32), default="ok")  # demo only
    decision_reason: Mapped[str | None] = mapped_column(Text)

    approvals: Mapped[list[RefundApproval]] = relationship(
        back_populates="refund", order_by="RefundApproval.id", lazy="selectin"
    )


class RefundApproval(VersionedMixin, Base):
    __tablename__ = "refund_approvals"
    __table_args__ = (UniqueConstraint("refund_id", "approver"),)

    refund_id: Mapped[int] = mapped_column(ForeignKey("refunds.id"))
    approver: Mapped[str] = mapped_column(String(64))

    refund: Mapped[Refund] = relationship(back_populates="approvals")
