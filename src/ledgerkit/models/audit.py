import datetime as dt
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from ledgerkit.models.base import Base, utcnow


class AuditLog(Base):
    """One row per mutating tool call, whether it succeeded, failed, or was held for approval."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[dt.datetime] = mapped_column(default=utcnow, index=True)
    actor_type: Mapped[str] = mapped_column(String(10))
    actor_id: Mapped[str] = mapped_column(String(100))
    tool: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20))
    input: Mapped[Any] = mapped_column(JSON)
    result: Mapped[Any] = mapped_column(JSON, default=None)


class ActionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PendingAction(Base):
    """A tool call an agent asked for that a human must approve before it runs."""

    __tablename__ = "pending_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tool: Mapped[str] = mapped_column(String(64))
    input: Mapped[Any] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10), default=ActionStatus.PENDING, index=True)
    requested_by: Mapped[str] = mapped_column(String(100))
    requested_at: Mapped[dt.datetime] = mapped_column(default=utcnow)
    decided_by: Mapped[str | None] = mapped_column(String(100), default=None)
    decided_at: Mapped[dt.datetime | None] = mapped_column(default=None)
    reason: Mapped[str | None] = mapped_column(String(500), default=None)
