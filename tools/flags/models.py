from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base, VersionedMixin

ENVIRONMENTS = ("staging", "production")
NOT_SET = "NOT_SET"  # sync status of an environment nobody has set yet: nothing pushed


class Flag(VersionedMixin, Base):
    __tablename__ = "flags"

    key: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(64))

    states: Mapped[list[FlagState]] = relationship(
        back_populates="flag", order_by="FlagState.id", lazy="selectin"
    )

    def state(self, environment: str) -> FlagState:
        return next(s for s in self.states if s.environment == environment)

    @property
    def staging(self) -> str:
        return self.state("staging").summary

    @property
    def production(self) -> str:
        return self.state("production").summary


class FlagState(VersionedMixin, Base):
    """The desired value of one flag in one environment. The flag service mirrors it."""

    __tablename__ = "flag_states"
    __table_args__ = (UniqueConstraint("flag_id", "environment"),)

    flag_id: Mapped[int] = mapped_column(ForeignKey("flags.id"))
    environment: Mapped[str] = mapped_column(String(20))
    enabled: Mapped[bool] = mapped_column(default=False)
    rollout_pct: Mapped[int] = mapped_column(default=0)
    sync_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    sync_note: Mapped[str | None] = mapped_column(Text)
    pushed_revision: Mapped[int | None]

    flag: Mapped[Flag] = relationship(back_populates="states")

    @property
    def is_set(self) -> bool:
        return self.sync_status != NOT_SET

    @property
    def summary(self) -> str:
        if not self.is_set:
            return "not set"
        return f"{'ON' if self.enabled else 'OFF'} · {self.rollout_pct}%"


class FlagChange(VersionedMixin, Base):
    """Append-only value history per flag and environment. Rollback targets one of these rows.

    The id doubles as the revision sent to the flag service, so out-of-order pushes are ignored.
    """

    __tablename__ = "flag_changes"

    flag_id: Mapped[int] = mapped_column(ForeignKey("flags.id"), index=True)
    environment: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(20))  # create | toggle | rollout | rollback
    enabled: Mapped[bool]
    rollout_pct: Mapped[int]
    changed_by: Mapped[str] = mapped_column(String(64))
    rolled_back_to: Mapped[int | None]
