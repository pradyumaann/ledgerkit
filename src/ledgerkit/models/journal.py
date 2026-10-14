import datetime as dt
from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, String, event, inspect
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from ledgerkit.errors import DomainError
from ledgerkit.models.account import Account
from ledgerkit.models.base import Base, utcnow


class EntryStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    entry_date: Mapped[dt.date] = mapped_column(index=True)
    memo: Mapped[str | None] = mapped_column(String(500), default=None)
    status: Mapped[str] = mapped_column(String(10), default=EntryStatus.DRAFT)
    # What produced this entry, e.g. ("invoice", 12). None for manual entries.
    source_type: Mapped[str | None] = mapped_column(String(30), default=None)
    source_id: Mapped[int | None] = mapped_column(default=None)
    reversal_of_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"), default=None)
    created_by: Mapped[str | None] = mapped_column(String(100), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)
    posted_at: Mapped[dt.datetime | None] = mapped_column(default=None)

    lines: Mapped[list["JournalLine"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", order_by="JournalLine.id"
    )


class JournalLine(Base):
    __tablename__ = "journal_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    debit: Mapped[int] = mapped_column(BigInteger, default=0)
    credit: Mapped[int] = mapped_column(BigInteger, default=0)
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"), default=None)
    description: Mapped[str | None] = mapped_column(String(500), default=None)

    entry: Mapped[JournalEntry] = relationship(back_populates="lines")
    account: Mapped[Account] = relationship()


def _committed_status(entry: JournalEntry) -> str | None:
    """The entry's status as stored in the database, ignoring unflushed changes."""
    state = inspect(entry)
    if not state.persistent:
        return None
    history = state.attrs.status.history
    return history.deleted[0] if history.deleted else entry.status


def _immutable(entry: JournalEntry) -> DomainError:
    return DomainError(
        "posted_entry_immutable",
        f"Journal entry {entry.number} is posted and cannot be changed or deleted. Post a reversing entry instead.",
    )


@event.listens_for(Session, "before_flush")
def _guard_posted_entries(session, _flush_context, _instances):
    """Posted entries are immutable regardless of which code path touches them."""
    for obj in session.deleted:
        if isinstance(obj, JournalEntry) and _committed_status(obj) == EntryStatus.POSTED:
            raise _immutable(obj)
        if isinstance(obj, JournalLine) and obj.entry and _committed_status(obj.entry) == EntryStatus.POSTED:
            raise _immutable(obj.entry)
    for obj in session.dirty:
        if not session.is_modified(obj):
            continue
        if isinstance(obj, JournalEntry) and _committed_status(obj) == EntryStatus.POSTED:
            raise _immutable(obj)
        if isinstance(obj, JournalLine) and obj.entry and _committed_status(obj.entry) == EntryStatus.POSTED:
            raise _immutable(obj.entry)
    for obj in session.new:
        if isinstance(obj, JournalLine) and obj.entry and _committed_status(obj.entry) == EntryStatus.POSTED:
            raise _immutable(obj.entry)
