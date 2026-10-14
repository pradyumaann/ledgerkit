"""The general ledger. This is the only module that creates journal lines."""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ledgerkit.errors import DomainError
from ledgerkit.models import Account, EntryStatus, JournalEntry, JournalLine
from ledgerkit.models.base import utcnow
from ledgerkit.money import fmt
from ledgerkit.services.company import check_period_open, get_company, next_number


@dataclass
class LineInput:
    account_id: int
    debit: int = 0
    credit: int = 0
    party_id: int | None = None
    description: str | None = None


def create_entry(
    session: Session,
    *,
    entry_date: dt.date,
    memo: str | None,
    lines: list[LineInput],
    source_type: str | None = None,
    source_id: int | None = None,
    created_by: str | None = None,
    reversal_of_id: int | None = None,
) -> JournalEntry:
    """Create a draft entry. It does not affect any balance until it is posted."""
    if not lines:
        raise DomainError("invalid_entry", "A journal entry needs at least two lines.")
    accounts = {
        a.id: a for a in session.scalars(select(Account).where(Account.id.in_({line.account_id for line in lines})))
    }
    for i, line in enumerate(lines, 1):
        account = accounts.get(line.account_id)
        if account is None:
            raise DomainError("not_found", f"Line {i}: account id {line.account_id} does not exist.")
        if not account.is_active:
            raise DomainError(
                "inactive_account", f"Line {i}: account {account.code} {account.name} is inactive and cannot be used."
            )
        if line.debit < 0 or line.credit < 0 or (line.debit > 0) == (line.credit > 0):
            raise DomainError(
                "invalid_line",
                f"Line {i} ({account.code} {account.name}) must have either a positive debit or a "
                "positive credit: not both, and not neither.",
            )
    entry = JournalEntry(
        number=next_number(session, "journal_entry", "JE"),
        entry_date=entry_date,
        memo=memo,
        status=EntryStatus.DRAFT,
        source_type=source_type,
        source_id=source_id,
        created_by=created_by,
        reversal_of_id=reversal_of_id,
    )
    entry.lines = [
        JournalLine(
            account_id=line.account_id,
            debit=line.debit,
            credit=line.credit,
            party_id=line.party_id,
            description=line.description,
        )
        for line in lines
    ]
    session.add(entry)
    session.flush()
    return entry


def post_entry(session: Session, entry: JournalEntry) -> JournalEntry:
    company = get_company(session)
    if entry.status != EntryStatus.DRAFT:
        raise DomainError("not_draft", f"Journal entry {entry.number} is already {entry.status}.")
    if len(entry.lines) < 2:
        raise DomainError("invalid_entry", f"Journal entry {entry.number} needs at least two lines to be posted.")
    debits = sum(line.debit for line in entry.lines)
    credits = sum(line.credit for line in entry.lines)
    if debits != credits:
        raise DomainError(
            "unbalanced",
            f"Journal entry {entry.number} is unbalanced by {fmt(abs(debits - credits), company)}: "
            f"debits total {fmt(debits, company)} and credits total {fmt(credits, company)}.",
        )
    check_period_open(company, entry.entry_date)
    entry.status = EntryStatus.POSTED
    entry.posted_at = utcnow()
    session.flush()
    return entry


def create_and_post(session: Session, **kwargs) -> JournalEntry:
    return post_entry(session, create_entry(session, **kwargs))


def reverse_entry(
    session: Session,
    entry: JournalEntry,
    *,
    entry_date: dt.date,
    memo: str | None = None,
    created_by: str | None = None,
) -> JournalEntry:
    """Post a mirror-image entry that cancels a posted one."""
    if entry.status != EntryStatus.POSTED:
        raise DomainError("not_posted", f"Journal entry {entry.number} is not posted, so there is nothing to reverse.")
    already = session.scalars(select(JournalEntry).where(JournalEntry.reversal_of_id == entry.id)).first()
    if already is not None:
        raise DomainError("already_reversed", f"Journal entry {entry.number} was already reversed by {already.number}.")
    return create_and_post(
        session,
        entry_date=entry_date,
        memo=memo or f"Reversal of {entry.number}",
        lines=[
            LineInput(
                account_id=line.account_id,
                debit=line.credit,
                credit=line.debit,
                party_id=line.party_id,
                description=line.description,
            )
            for line in entry.lines
        ],
        source_type=entry.source_type,
        source_id=entry.source_id,
        created_by=created_by,
        reversal_of_id=entry.id,
    )


def balances(
    session: Session, *, date_from: dt.date | None = None, date_to: dt.date | None = None
) -> list[tuple[Account, int, int]]:
    """(account, total debit, total credit) from posted entries, for accounts with activity."""
    stmt = (
        select(Account, func.sum(JournalLine.debit), func.sum(JournalLine.credit))
        .join(JournalLine, JournalLine.account_id == Account.id)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(JournalEntry.status == EntryStatus.POSTED)
        .group_by(Account.id)
        .order_by(Account.code)
    )
    if date_from is not None:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    return [(account, int(debit or 0), int(credit or 0)) for account, debit, credit in session.execute(stmt)]


def account_lines(
    session: Session, account: Account, *, date_from: dt.date | None, date_to: dt.date | None, limit: int
) -> tuple[int, list[tuple[JournalLine, JournalEntry]]]:
    """Opening balance (debit minus credit) before date_from, and the posted lines in the range."""
    opening = 0
    if date_from is not None:
        debit, credit = session.execute(
            select(func.sum(JournalLine.debit), func.sum(JournalLine.credit))
            .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
            .where(
                JournalLine.account_id == account.id,
                JournalEntry.status == EntryStatus.POSTED,
                JournalEntry.entry_date < date_from,
            )
        ).one()
        opening = int(debit or 0) - int(credit or 0)
    stmt = (
        select(JournalLine, JournalEntry)
        .join(JournalEntry, JournalLine.entry_id == JournalEntry.id)
        .where(JournalLine.account_id == account.id, JournalEntry.status == EntryStatus.POSTED)
        .order_by(JournalEntry.entry_date, JournalEntry.id, JournalLine.id)
        .limit(limit)
    )
    if date_from is not None:
        stmt = stmt.where(JournalEntry.entry_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(JournalEntry.entry_date <= date_to)
    return opening, [(line, entry) for line, entry in session.execute(stmt)]
