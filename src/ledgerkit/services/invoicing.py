"""Sales invoices and vendor bills: draft, post to the ledger, void."""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledgerkit.errors import DomainError
from ledgerkit.models import (
    Account,
    AccountSubtype,
    AccountType,
    Invoice,
    InvoiceKind,
    InvoiceLine,
    InvoiceStatus,
    Item,
    ItemKind,
    JournalEntry,
    Party,
    SalesDoc,
    SalesDocStatus,
    TaxRate,
)
from ledgerkit.money import round_half_up
from ledgerkit.services import ledger
from ledgerkit.services.company import next_number, system_account

DEFAULT_PAYMENT_TERMS_DAYS = 30


@dataclass
class DocLineInput:
    item_id: int | None = None
    description: str | None = None
    quantity: Decimal = Decimal(1)
    unit_price: int | None = None
    account_id: int | None = None
    tax_rate_id: int | None = None
    # True forces no tax even when the item has a default tax rate.
    no_tax: bool = False


@dataclass
class ResolvedLine:
    item: Item | None
    description: str
    quantity: Decimal
    unit_price: int
    account_id: int
    tax_rate: TaxRate | None
    line_subtotal: int
    tax_amount: int
    unit_cost: int
    cost_total: int


def resolve_line(session: Session, kind: str, line: DocLineInput, index: int) -> ResolvedLine:
    """Fill a line's defaults from its item and compute its amounts."""
    where = f"Line {index}"
    if line.quantity <= 0:
        raise DomainError("invalid_line", f"{where}: quantity must be greater than zero.")
    item = session.get(Item, line.item_id) if line.item_id is not None else None
    if line.item_id is not None and item is None:
        raise DomainError("not_found", f"{where}: item id {line.item_id} does not exist.")
    if item is not None and not item.is_active:
        raise DomainError("inactive_item", f"{where}: item {item.sku} is inactive.")

    description = line.description or (item.name if item else None)
    if not description:
        raise DomainError("invalid_line", f"{where}: give either an item or a description.")

    unit_price = line.unit_price
    if unit_price is None and item is not None:
        unit_price = item.sale_price if kind == InvoiceKind.SALES else item.standard_cost
    if unit_price is None:
        raise DomainError("invalid_line", f"{where}: unit_price is required when no item is given.")
    if unit_price < 0:
        raise DomainError("invalid_line", f"{where}: unit_price cannot be negative.")

    account_id = line.account_id
    if account_id is None:
        if kind == InvoiceKind.SALES:
            account_id = item.income_account_id if item else _default_income_account(session).id
        elif item is not None and item.kind == ItemKind.PRODUCT:
            account_id = system_account(session, AccountSubtype.INVENTORY).id
        else:
            raise DomainError(
                "invalid_line",
                f"{where}: account_code is required on a vendor bill line unless the line is for a product "
                "item (which goes to Inventory). Use an expense account such as rent or utilities.",
            )

    tax_rate = None
    if not line.no_tax:
        tax_rate_id = line.tax_rate_id or (item.tax_rate_id if item else None)
        if tax_rate_id is not None:
            tax_rate = session.get(TaxRate, tax_rate_id)
            if tax_rate is None:
                raise DomainError("not_found", f"{where}: tax rate id {tax_rate_id} does not exist.")

    line_subtotal = round_half_up(line.quantity * unit_price)
    tax_amount = round_half_up(Decimal(line_subtotal) * tax_rate.rate_bp / 10000) if tax_rate else 0
    # Cost of goods sold is only tracked for products sold; a service's costs are operating expenses.
    unit_cost = item.standard_cost if item and item.kind == ItemKind.PRODUCT and kind == InvoiceKind.SALES else 0
    return ResolvedLine(
        item=item,
        description=description,
        quantity=line.quantity,
        unit_price=unit_price,
        account_id=account_id,
        tax_rate=tax_rate,
        line_subtotal=line_subtotal,
        tax_amount=tax_amount,
        unit_cost=unit_cost,
        cost_total=round_half_up(line.quantity * unit_cost),
    )


def _default_income_account(session: Session) -> Account:
    account = session.scalars(
        select(Account).where(Account.type == AccountType.INCOME, Account.is_active).order_by(Account.code).limit(1)
    ).first()
    if account is None:
        raise DomainError(
            "missing_system_account", "There is no active income account. Create one with create_account."
        )
    return account


def check_party_role(party: Party, kind: str) -> None:
    if kind == InvoiceKind.SALES and not party.is_customer:
        raise DomainError(
            "wrong_party_role",
            f"{party.name} (id {party.id}) is not a customer, so it cannot receive a sales document.",
        )
    if kind == InvoiceKind.PURCHASE and not party.is_vendor:
        raise DomainError(
            "wrong_party_role", f"{party.name} (id {party.id}) is not a vendor, so it cannot issue a bill."
        )


def create_invoice_draft(
    session: Session,
    *,
    kind: str,
    party: Party,
    invoice_date: dt.date,
    lines: list[DocLineInput],
    due_date: dt.date | None = None,
    reference: str | None = None,
    notes: str | None = None,
    sales_order_id: int | None = None,
    created_by: str | None = None,
) -> Invoice:
    check_party_role(party, kind)
    if not lines:
        raise DomainError("invalid_invoice", "An invoice needs at least one line.")
    due_date = due_date or invoice_date + dt.timedelta(days=DEFAULT_PAYMENT_TERMS_DAYS)
    if due_date < invoice_date:
        raise DomainError("invalid_invoice", "due_date cannot be before the invoice date.")

    resolved = [resolve_line(session, kind, line, i) for i, line in enumerate(lines, 1)]
    is_sales = kind == InvoiceKind.SALES
    invoice = Invoice(
        kind=kind,
        number=next_number(session, f"invoice_{kind}", "INV" if is_sales else "BILL"),
        party_id=party.id,
        invoice_date=invoice_date,
        due_date=due_date,
        status=InvoiceStatus.DRAFT,
        subtotal=sum(r.line_subtotal for r in resolved),
        tax_total=sum(r.tax_amount for r in resolved),
        reference=reference,
        notes=notes,
        sales_order_id=sales_order_id,
        created_by=created_by,
    )
    invoice.total = invoice.subtotal + invoice.tax_total
    invoice.lines = [
        InvoiceLine(
            item_id=r.item.id if r.item else None,
            description=r.description,
            quantity=r.quantity,
            unit_price=r.unit_price,
            account_id=r.account_id,
            tax_rate_id=r.tax_rate.id if r.tax_rate else None,
            line_subtotal=r.line_subtotal,
            tax_amount=r.tax_amount,
            unit_cost=r.unit_cost,
            cost_total=r.cost_total,
        )
        for r in resolved
    ]
    session.add(invoice)
    session.flush()
    return invoice


def post_invoice(session: Session, invoice: Invoice, *, created_by: str | None = None) -> Invoice:
    """Post a draft invoice or bill, creating its journal entry.

    Sales:    Dr Receivable / Cr Income, Cr Tax payable; and Dr COGS / Cr Inventory at standard cost.
    Purchase: Dr Expense or Inventory, Dr Input tax / Cr Payable.
    """
    if invoice.status != InvoiceStatus.DRAFT:
        raise DomainError("not_draft", f"{invoice.number} is {invoice.status}; only a draft can be posted.")
    if invoice.total <= 0:
        raise DomainError("invalid_invoice", f"{invoice.number} has a zero total and cannot be posted.")

    is_sales = invoice.kind == InvoiceKind.SALES
    by_account: dict[int, int] = defaultdict(int)
    by_tax_account: dict[int, int] = defaultdict(int)
    for line in invoice.lines:
        by_account[line.account_id] += line.line_subtotal
        if line.tax_amount:
            tax = line.tax_rate
            by_tax_account[tax.sales_account_id if is_sales else tax.purchase_account_id] += line.tax_amount

    def amounts(amount: int, *, natural_debit: bool) -> dict:
        return {"debit": amount} if natural_debit else {"credit": amount}

    control = system_account(session, AccountSubtype.RECEIVABLE if is_sales else AccountSubtype.PAYABLE)
    entry_lines = [
        ledger.LineInput(
            account_id=control.id,
            party_id=invoice.party_id,
            description=invoice.number,
            **amounts(invoice.total, natural_debit=is_sales),
        )
    ]
    for account_id, amount in list(by_account.items()) + list(by_tax_account.items()):
        if amount:
            entry_lines.append(
                ledger.LineInput(
                    account_id=account_id, description=invoice.number, **amounts(amount, natural_debit=not is_sales)
                )
            )
    cost = sum(line.cost_total for line in invoice.lines)
    if is_sales and cost:
        cogs = system_account(session, AccountSubtype.COGS)
        inventory = system_account(session, AccountSubtype.INVENTORY)
        entry_lines.append(ledger.LineInput(account_id=cogs.id, debit=cost, description=f"Cost of {invoice.number}"))
        entry_lines.append(
            ledger.LineInput(account_id=inventory.id, credit=cost, description=f"Cost of {invoice.number}")
        )

    entry = ledger.create_and_post(
        session,
        entry_date=invoice.invoice_date,
        memo=f"{'Sales invoice' if is_sales else 'Vendor bill'} {invoice.number} - {invoice.party.name}",
        lines=entry_lines,
        source_type="invoice",
        source_id=invoice.id,
        created_by=created_by,
    )
    invoice.status = InvoiceStatus.POSTED
    invoice.journal_entry_id = entry.id
    session.flush()
    return invoice


def void_invoice(
    session: Session, invoice: Invoice, *, void_date: dt.date | None = None, created_by: str | None = None
) -> Invoice:
    """Cancel an invoice. A posted one is cancelled by reversing its journal entry."""
    if invoice.status == InvoiceStatus.VOID:
        raise DomainError("already_void", f"{invoice.number} is already void.")
    if invoice.status == InvoiceStatus.POSTED:
        if invoice.amount_paid:
            raise DomainError(
                "has_payments",
                f"{invoice.number} has payments applied to it. Void those payments first with void_payment.",
            )
        entry = session.get(JournalEntry, invoice.journal_entry_id)
        ledger.reverse_entry(
            session,
            entry,
            entry_date=void_date or invoice.invoice_date,
            memo=f"Void {invoice.number}",
            created_by=created_by,
        )
    invoice.status = InvoiceStatus.VOID
    if invoice.sales_order_id is not None:
        order = session.get(SalesDoc, invoice.sales_order_id)
        if order is not None and order.status == SalesDocStatus.INVOICED:
            order.status = SalesDocStatus.OPEN
    session.flush()
    return invoice


def list_invoices(
    session: Session,
    *,
    kind: str | None = None,
    status: str | None = None,
    party_id: int | None = None,
    unpaid_only: bool = False,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    limit: int = 50,
) -> list[Invoice]:
    stmt = select(Invoice).order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).limit(limit)
    if kind:
        stmt = stmt.where(Invoice.kind == kind)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if party_id is not None:
        stmt = stmt.where(Invoice.party_id == party_id)
    if unpaid_only:
        stmt = stmt.where(Invoice.status == InvoiceStatus.POSTED, Invoice.amount_paid < Invoice.total)
    if date_from is not None:
        stmt = stmt.where(Invoice.invoice_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Invoice.invoice_date <= date_to)
    return list(session.scalars(stmt))
