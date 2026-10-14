"""Customer receipts and vendor payments, allocated against invoices."""

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledgerkit.errors import DomainError
from ledgerkit.models import (
    Account,
    AccountSubtype,
    Invoice,
    InvoiceKind,
    InvoiceStatus,
    JournalEntry,
    Party,
    Payment,
    PaymentAllocation,
    PaymentDirection,
    PaymentStatus,
)
from ledgerkit.money import fmt
from ledgerkit.services import ledger
from ledgerkit.services.company import get_company, next_number, system_account


def _invoice_kind(direction: str) -> str:
    return InvoiceKind.SALES if direction == PaymentDirection.INBOUND else InvoiceKind.PURCHASE


def record_payment(
    session: Session,
    *,
    direction: str,
    party: Party,
    payment_date: dt.date,
    amount: int,
    bank_account: Account | None = None,
    allocations: list[tuple[Invoice, int]] | None = None,
    method: str | None = None,
    reference: str | None = None,
    created_by: str | None = None,
) -> Payment:
    """Record and post a payment.

    With allocations=None the amount is applied to the party's oldest open invoices first.
    Anything left unallocated stays on the party's receivable/payable balance as a credit.
    """
    company = get_company(session)
    if amount <= 0:
        raise DomainError("invalid_amount", "The payment amount must be greater than zero.")
    kind = _invoice_kind(direction)
    bank_account = bank_account or system_account(session, AccountSubtype.BANK)
    if bank_account.subtype != AccountSubtype.BANK:
        raise DomainError(
            "invalid_account", f"Account {bank_account.code} {bank_account.name} is not a bank or cash account."
        )

    if allocations is None:
        allocations = []
        remaining = amount
        open_invoices = session.scalars(
            select(Invoice)
            .where(
                Invoice.party_id == party.id,
                Invoice.kind == kind,
                Invoice.status == InvoiceStatus.POSTED,
                Invoice.amount_paid < Invoice.total,
            )
            .order_by(Invoice.due_date, Invoice.id)
        )
        for invoice in open_invoices:
            if not remaining:
                break
            applied = min(remaining, invoice.outstanding)
            allocations.append((invoice, applied))
            remaining -= applied
    else:
        for invoice, applied in allocations:
            if invoice.party_id != party.id or invoice.kind != kind:
                raise DomainError(
                    "invalid_allocation",
                    f"{invoice.number} is not a {kind} invoice for {party.name}, "
                    "so this payment cannot be applied to it.",
                )
            if invoice.status != InvoiceStatus.POSTED:
                raise DomainError(
                    "invalid_allocation", f"{invoice.number} is {invoice.status}; only posted invoices can be paid."
                )
            if applied <= 0 or applied > invoice.outstanding:
                raise DomainError(
                    "invalid_allocation",
                    f"Cannot apply {fmt(applied, company)} to {invoice.number}: "
                    f"only {fmt(invoice.outstanding, company)} is outstanding.",
                )
        if len({invoice.id for invoice, _ in allocations}) != len(allocations):
            raise DomainError("invalid_allocation", "Each invoice can appear only once in the allocations.")
        allocated = sum(applied for _, applied in allocations)
        if allocated > amount:
            raise DomainError(
                "invalid_allocation",
                f"Allocations total {fmt(allocated, company)}, more than the payment of {fmt(amount, company)}.",
            )

    inbound = direction == PaymentDirection.INBOUND
    control = system_account(session, AccountSubtype.RECEIVABLE if inbound else AccountSubtype.PAYABLE)
    payment = Payment(
        number=next_number(session, f"payment_{direction}", "RCPT" if inbound else "PAY"),
        direction=direction,
        party_id=party.id,
        payment_date=payment_date,
        amount=amount,
        bank_account_id=bank_account.id,
        method=method,
        reference=reference,
        status=PaymentStatus.POSTED,
        created_by=created_by,
    )
    payment.allocations = [PaymentAllocation(invoice_id=invoice.id, amount=applied) for invoice, applied in allocations]
    session.add(payment)
    session.flush()

    bank_line = ledger.LineInput(account_id=bank_account.id, description=payment.number)
    control_line = ledger.LineInput(account_id=control.id, party_id=party.id, description=payment.number)
    if inbound:
        bank_line.debit, control_line.credit = amount, amount
    else:
        bank_line.credit, control_line.debit = amount, amount
    entry = ledger.create_and_post(
        session,
        entry_date=payment_date,
        memo=f"{'Receipt from' if inbound else 'Payment to'} {party.name} - {payment.number}",
        lines=[bank_line, control_line],
        source_type="payment",
        source_id=payment.id,
        created_by=created_by,
    )
    payment.journal_entry_id = entry.id
    for invoice, applied in allocations:
        invoice.amount_paid += applied
    session.flush()
    return payment


def void_payment(
    session: Session, payment: Payment, *, void_date: dt.date | None = None, created_by: str | None = None
) -> Payment:
    if payment.status == PaymentStatus.VOID:
        raise DomainError("already_void", f"Payment {payment.number} is already void.")
    entry = session.get(JournalEntry, payment.journal_entry_id)
    ledger.reverse_entry(
        session,
        entry,
        entry_date=void_date or payment.payment_date,
        memo=f"Void {payment.number}",
        created_by=created_by,
    )
    for allocation in payment.allocations:
        allocation.invoice.amount_paid -= allocation.amount
    payment.status = PaymentStatus.VOID
    session.flush()
    return payment
