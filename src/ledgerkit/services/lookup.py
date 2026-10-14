"""Fetch records by their natural keys, with errors that tell the caller how to recover."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledgerkit.errors import DomainError
from ledgerkit.models import (
    Account,
    Invoice,
    Item,
    JournalEntry,
    Lead,
    Opportunity,
    Party,
    Payment,
    SalesDoc,
    TaxRate,
)


def _one(session: Session, stmt, what: str, hint: str):
    obj = session.scalars(stmt).first()
    if obj is None:
        raise DomainError("not_found", f"{what} was not found. {hint}")
    return obj


def account(session: Session, code: str) -> Account:
    return _one(
        session,
        select(Account).where(Account.code == code),
        f"Account with code '{code}'",
        "Use list_accounts to see valid codes.",
    )


def item(session: Session, sku: str) -> Item:
    return _one(
        session, select(Item).where(Item.sku == sku), f"Item with SKU '{sku}'", "Use list_items to see valid SKUs."
    )


def tax_rate(session: Session, name: str) -> TaxRate:
    return _one(
        session,
        select(TaxRate).where(TaxRate.name == name),
        f"Tax rate named '{name}'",
        "Use list_tax_rates to see valid names.",
    )


def party(session: Session, party_id: int) -> Party:
    return _one(
        session, select(Party).where(Party.id == party_id), f"Party {party_id}", "Use search_parties to find ids."
    )


def invoice(session: Session, number: str) -> Invoice:
    return _one(
        session,
        select(Invoice).where(Invoice.number == number),
        f"Invoice or bill '{number}'",
        "Use list_invoices to see valid numbers.",
    )


def journal_entry(session: Session, number: str) -> JournalEntry:
    return _one(
        session,
        select(JournalEntry).where(JournalEntry.number == number),
        f"Journal entry '{number}'",
        "Check the number returned when the entry was created.",
    )


def payment(session: Session, number: str) -> Payment:
    return _one(
        session,
        select(Payment).where(Payment.number == number),
        f"Payment '{number}'",
        "Check the number returned by record_payment.",
    )


def sales_doc(session: Session, number: str, kind: str) -> SalesDoc:
    return _one(
        session,
        select(SalesDoc).where(SalesDoc.number == number, SalesDoc.kind == kind),
        f"{kind.capitalize()} '{number}'",
        "Check the number returned when it was created.",
    )


def lead(session: Session, lead_id: int) -> Lead:
    return _one(
        session, select(Lead).where(Lead.id == lead_id), f"Lead {lead_id}", "Check the id returned by create_lead."
    )


def opportunity(session: Session, opportunity_id: int) -> Opportunity:
    return _one(
        session,
        select(Opportunity).where(Opportunity.id == opportunity_id),
        f"Opportunity {opportunity_id}",
        "Use pipeline_summary to see open opportunities.",
    )
