import datetime as dt

import pytest

from ledgerkit.errors import DomainError
from ledgerkit.models import EntryStatus, JournalEntry, JournalLine
from ledgerkit.services import ledger, lookup
from ledgerkit.services.company import get_company

DAY = dt.date(2026, 3, 15)


def _lines(session, *rows):
    return [
        ledger.LineInput(account_id=lookup.account(session, code).id, debit=debit, credit=credit)
        for code, debit, credit in rows
    ]


def _posted(session, amount=10000):
    entry = ledger.create_and_post(
        session, entry_date=DAY, memo="Capital", lines=_lines(session, ("1000", amount, 0), ("3000", 0, amount))
    )
    session.commit()
    return entry


def test_balanced_entry_posts_and_updates_balances(session):
    _posted(session)
    balances = {a.code: (d, c) for a, d, c in ledger.balances(session)}
    assert balances == {"1000": (10000, 0), "3000": (0, 10000)}


def test_draft_does_not_affect_balances(session):
    ledger.create_entry(
        session, entry_date=DAY, memo="Draft", lines=_lines(session, ("1000", 500, 0), ("3000", 0, 500))
    )
    session.commit()
    assert ledger.balances(session) == []


def test_unbalanced_entry_cannot_be_posted(session):
    entry = ledger.create_entry(
        session, entry_date=DAY, memo="Bad", lines=_lines(session, ("1000", 10000, 0), ("3000", 0, 8750))
    )
    with pytest.raises(DomainError) as exc:
        ledger.post_entry(session, entry)
    assert exc.value.code == "unbalanced"
    assert "12.50 USD" in exc.value.message
    assert entry.status == EntryStatus.DRAFT


@pytest.mark.parametrize("debit,credit", [(100, 100), (0, 0), (-5, 0)])
def test_line_needs_exactly_one_positive_side(session, debit, credit):
    with pytest.raises(DomainError) as exc:
        ledger.create_entry(
            session, entry_date=DAY, memo="Bad", lines=_lines(session, ("1000", debit, credit), ("3000", 0, 100))
        )
    assert exc.value.code == "invalid_line"


def test_posted_entry_cannot_be_modified(session):
    entry = _posted(session)
    entry.memo = "changed"
    with pytest.raises(DomainError) as exc:
        session.commit()
    assert exc.value.code == "posted_entry_immutable"


def test_posted_line_cannot_be_modified(session):
    entry = _posted(session)
    entry.lines[0].debit = 1
    with pytest.raises(DomainError) as exc:
        session.commit()
    assert exc.value.code == "posted_entry_immutable"


def test_line_cannot_be_added_to_posted_entry(session):
    entry = _posted(session)
    session.add(JournalLine(entry=entry, account_id=entry.lines[0].account_id, debit=5))
    with pytest.raises(DomainError) as exc:
        session.commit()
    assert exc.value.code == "posted_entry_immutable"


def test_posted_entry_cannot_be_deleted(session):
    entry = _posted(session)
    session.delete(entry)
    with pytest.raises(DomainError) as exc:
        session.commit()
    assert exc.value.code == "posted_entry_immutable"
    session.rollback()
    assert session.get(JournalEntry, entry.id) is not None


def test_reversal_cancels_entry_and_cannot_be_repeated(session):
    entry = _posted(session)
    reversal = ledger.reverse_entry(session, entry, entry_date=DAY)
    session.commit()
    assert reversal.reversal_of_id == entry.id
    assert all(debit == credit for _, debit, credit in ledger.balances(session))
    with pytest.raises(DomainError) as exc:
        ledger.reverse_entry(session, entry, entry_date=DAY)
    assert exc.value.code == "already_reversed"


def test_cannot_post_into_locked_period(session):
    get_company(session).lock_date = DAY
    session.commit()
    entry = ledger.create_entry(
        session, entry_date=DAY, memo="Late", lines=_lines(session, ("1000", 100, 0), ("3000", 0, 100))
    )
    with pytest.raises(DomainError) as exc:
        ledger.post_entry(session, entry)
    assert exc.value.code == "period_locked"

    entry.entry_date = DAY + dt.timedelta(days=1)
    assert ledger.post_entry(session, entry).status == EntryStatus.POSTED
