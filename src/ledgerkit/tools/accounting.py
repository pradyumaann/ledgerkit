"""Chart of accounts, journal entries and ledger queries."""

import datetime as dt
from decimal import Decimal

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ledgerkit.analysis import statements
from ledgerkit.errors import DomainError
from ledgerkit.models import AccountSubtype, AccountType, EntryStatus, JournalEntry
from ledgerkit.money import Minor
from ledgerkit.services import ledger, lookup, masterdata
from ledgerkit.tools import serializers
from ledgerkit.tools.common import MONEY_NOTE, AsOfInput, PeriodInput
from ledgerkit.tools.context import ToolContext
from ledgerkit.tools.registry import ToolInput, registry


class Empty(ToolInput):
    pass


@registry.tool(
    name="get_company_settings",
    description="Get the company name, base currency, fiscal year start month and lock date. "
    "Call this first if you do not know the currency or the fiscal year.",
    input_model=Empty,
)
def get_company_settings(ctx: ToolContext, p: Empty):
    c = ctx.company
    return {
        "name": c.name,
        "base_currency": c.base_currency,
        "currency_decimals": c.currency_decimals,
        "fiscal_year_start_month": c.fiscal_year_start_month,
        "lock_date": c.lock_date,
        "today": ctx.today,
    }


class SetLockDate(ToolInput):
    lock_date: dt.date | None = Field(
        description="Nothing can be posted on or before this date. Pass null to remove the lock."
    )


@registry.tool(
    name="set_lock_date",
    description="Lock the books up to and including a date, typically after a period has been reviewed "
    "and closed. Posting, voiding and reversing on or before that date is then refused.",
    input_model=SetLockDate,
    mutating=True,
    requires_approval=True,
)
def set_lock_date(ctx: ToolContext, p: SetLockDate):
    ctx.company.lock_date = p.lock_date
    return {"lock_date": p.lock_date}


class ListAccounts(ToolInput):
    type: AccountType | None = Field(None, description="Only accounts of this type.")
    include_inactive: bool = False


@registry.tool(
    name="list_accounts",
    description="List the chart of accounts with each account's code, name, type and subtype. "
    "Other tools refer to accounts by code.",
    input_model=ListAccounts,
)
def list_accounts(ctx: ToolContext, p: ListAccounts):
    accounts = masterdata.list_accounts(ctx.session, type=p.type, include_inactive=p.include_inactive)
    return {"accounts": [serializers.account(a) for a in accounts]}


class CreateAccount(ToolInput):
    code: str = Field(min_length=1, max_length=20, description="Unique account code, e.g. '6350'.")
    name: str = Field(min_length=1, max_length=200)
    type: AccountType
    subtype: AccountSubtype | None = Field(
        None,
        description="Only set this for an account the system should post to automatically: 'bank' for a "
        "bank or cash account, 'cogs' for cost of goods sold, and so on. Leave empty for ordinary accounts.",
    )


@registry.tool(
    name="create_account",
    description="Add an account to the chart of accounts.",
    input_model=CreateAccount,
    mutating=True,
    requires_approval=True,
)
def create_account(ctx: ToolContext, p: CreateAccount):
    return serializers.account(
        masterdata.create_account(ctx.session, code=p.code, name=p.name, type=p.type, subtype=p.subtype)
    )


class JournalLineIn(ToolInput):
    account_code: str
    debit: Decimal = Field(Decimal(0), ge=0)
    credit: Decimal = Field(Decimal(0), ge=0)
    party_id: int | None = Field(None, description="Customer or vendor this line relates to, if any.")
    description: str | None = None


class CreateJournalEntryDraft(ToolInput):
    entry_date: dt.date | None = Field(None, description="Defaults to today.")
    memo: str = Field(min_length=1, max_length=500, description="What this entry is for.")
    lines: list[JournalLineIn] = Field(
        min_length=2, description="Each line has either a debit or a credit. Total debits must equal total credits."
    )


@registry.tool(
    name="create_journal_entry_draft",
    description="Create a manual journal entry as a draft. A draft does not change any balance until it "
    "is posted with post_journal_entry. Use this for things that are not invoices, bills or payments, "
    "such as salaries, depreciation, owner contributions or corrections. " + MONEY_NOTE,
    input_model=CreateJournalEntryDraft,
    mutating=True,
)
def create_journal_entry_draft(ctx: ToolContext, p: CreateJournalEntryDraft):
    lines = [
        ledger.LineInput(
            account_id=lookup.account(ctx.session, line.account_code).id,
            debit=ctx.minor(line.debit),
            credit=ctx.minor(line.credit),
            party_id=lookup.party(ctx.session, line.party_id).id if line.party_id is not None else None,
            description=line.description,
        )
        for line in p.lines
    ]
    entry = ledger.create_entry(
        ctx.session, entry_date=p.entry_date or ctx.today, memo=p.memo, lines=lines, created_by=ctx.actor.label
    )
    result = serializers.journal_entry(entry)
    result["balanced"] = result["total_debit"] == result["total_credit"]
    return result


class EntryNumber(ToolInput):
    entry_number: str = Field(description="Journal entry number, e.g. 'JE-00012'.")


@registry.tool(
    name="get_journal_entry",
    description="Show one journal entry with all its lines.",
    input_model=EntryNumber,
)
def get_journal_entry(ctx: ToolContext, p: EntryNumber):
    return serializers.journal_entry(lookup.journal_entry(ctx.session, p.entry_number))


@registry.tool(
    name="post_journal_entry",
    description="Post a draft journal entry to the ledger. This is permanent: a posted entry cannot be "
    "edited or deleted, only reversed. The entry must balance.",
    input_model=EntryNumber,
    mutating=True,
    requires_approval=True,
)
def post_journal_entry(ctx: ToolContext, p: EntryNumber):
    entry = lookup.journal_entry(ctx.session, p.entry_number)
    return serializers.journal_entry(ledger.post_entry(ctx.session, entry))


@registry.tool(
    name="discard_journal_entry_draft",
    description="Delete a journal entry that is still a draft. Posted entries cannot be discarded.",
    input_model=EntryNumber,
    mutating=True,
)
def discard_journal_entry_draft(ctx: ToolContext, p: EntryNumber):
    entry = lookup.journal_entry(ctx.session, p.entry_number)
    if entry.status != EntryStatus.DRAFT:
        raise DomainError(
            "not_draft", f"Journal entry {entry.number} is posted. Use reverse_journal_entry to cancel it."
        )
    ctx.session.delete(entry)
    return {"discarded": entry.number}


class ReverseJournalEntry(ToolInput):
    entry_number: str
    reversal_date: dt.date | None = Field(None, description="Date of the reversing entry. Defaults to today.")
    memo: str | None = None


@registry.tool(
    name="reverse_journal_entry",
    description="Cancel a posted manual journal entry by posting its mirror image. Do not use this for "
    "entries created by an invoice, bill or payment: use void_invoice or void_payment for those.",
    input_model=ReverseJournalEntry,
    mutating=True,
    requires_approval=True,
)
def reverse_journal_entry(ctx: ToolContext, p: ReverseJournalEntry):
    entry = lookup.journal_entry(ctx.session, p.entry_number)
    if entry.source_type is not None:
        raise DomainError(
            "wrong_tool",
            f"Journal entry {entry.number} was created by a {entry.source_type}. "
            f"Void that {entry.source_type} instead so its status stays consistent.",
        )
    reversal = ledger.reverse_entry(
        ctx.session, entry, entry_date=p.reversal_date or ctx.today, memo=p.memo, created_by=ctx.actor.label
    )
    return serializers.journal_entry(reversal)


class GetLedger(PeriodInput):
    account_code: str
    limit: int = Field(200, ge=1, le=1000)


@registry.tool(
    name="get_ledger",
    description="List the posted transactions on one account for a period, with the opening balance and "
    "a running balance. Balances are debit minus credit, so they are negative for accounts that "
    "normally carry a credit balance (liabilities, equity, income).",
    input_model=GetLedger,
)
def get_ledger(ctx: ToolContext, p: GetLedger):
    account = lookup.account(ctx.session, p.account_code)
    date_from, date_to = ctx.period(p.date_from, p.date_to)
    opening, rows = ledger.account_lines(ctx.session, account, date_from=date_from, date_to=date_to, limit=p.limit)
    balance = opening
    lines = []
    for line, entry in rows:
        balance += line.debit - line.credit
        lines.append(
            {
                "date": entry.entry_date,
                "entry_number": entry.number,
                "memo": entry.memo,
                "description": line.description,
                "party_id": line.party_id,
                "debit": Minor(line.debit),
                "credit": Minor(line.credit),
                "balance": Minor(balance),
            }
        )
    return {
        "account": serializers.account(account),
        "period": {"from": date_from, "to": date_to},
        "opening_balance": Minor(opening),
        "lines": lines,
        "closing_balance": Minor(balance),
        "truncated": len(lines) == p.limit,
    }


@registry.tool(
    name="trial_balance",
    description="Net debit or credit balance of every account as of a date. Total debits always equal "
    "total credits; use this to check the books or to look up several balances at once.",
    input_model=AsOfInput,
)
def trial_balance(ctx: ToolContext, p: AsOfInput):
    return statements.trial_balance(ctx.session, p.as_of or ctx.today)


class ListJournalEntries(ToolInput):
    status: EntryStatus | None = None
    manual_only: bool = Field(
        False, description="Only entries made by hand, not those generated by invoices, bills and payments."
    )
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    limit: int = Field(100, ge=1, le=500)


@registry.tool(
    name="list_journal_entries",
    description="List journal entries, newest first, without their lines. "
    "Use get_journal_entry for the lines of one entry.",
    input_model=ListJournalEntries,
)
def list_journal_entries(ctx: ToolContext, p: ListJournalEntries):
    stmt = (
        select(JournalEntry)
        .options(selectinload(JournalEntry.lines))
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
        .limit(p.limit)
    )
    if p.status:
        stmt = stmt.where(JournalEntry.status == p.status)
    if p.manual_only:
        stmt = stmt.where(JournalEntry.source_type.is_(None))
    if p.date_from is not None:
        stmt = stmt.where(JournalEntry.entry_date >= p.date_from)
    if p.date_to is not None:
        stmt = stmt.where(JournalEntry.entry_date <= p.date_to)
    found = list(ctx.session.scalars(stmt))
    return {"entries": [serializers.journal_entry_summary(e) for e in found], "truncated": len(found) == p.limit}
