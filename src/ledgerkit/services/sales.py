"""Quotations and sales orders. These never touch the ledger; only invoices do."""

import datetime as dt

from sqlalchemy.orm import Session

from ledgerkit.errors import DomainError
from ledgerkit.models import (
    OPEN_STAGES,
    Invoice,
    InvoiceKind,
    Opportunity,
    OpportunityStage,
    Party,
    SalesDoc,
    SalesDocKind,
    SalesDocLine,
    SalesDocStatus,
)
from ledgerkit.models.base import utcnow
from ledgerkit.services import invoicing
from ledgerkit.services.company import next_number
from ledgerkit.services.invoicing import DocLineInput


def create_quotation(
    session: Session,
    *,
    party: Party,
    doc_date: dt.date,
    lines: list[DocLineInput],
    valid_until: dt.date | None = None,
    opportunity: Opportunity | None = None,
    notes: str | None = None,
    created_by: str | None = None,
) -> SalesDoc:
    invoicing.check_party_role(party, InvoiceKind.SALES)
    if not lines:
        raise DomainError("invalid_document", "A quotation needs at least one line.")
    resolved = [invoicing.resolve_line(session, InvoiceKind.SALES, line, i) for i, line in enumerate(lines, 1)]
    quotation = SalesDoc(
        kind=SalesDocKind.QUOTATION,
        number=next_number(session, "quotation", "QUO"),
        party_id=party.id,
        doc_date=doc_date,
        valid_until=valid_until,
        status=SalesDocStatus.DRAFT,
        opportunity_id=opportunity.id if opportunity else None,
        subtotal=sum(r.line_subtotal for r in resolved),
        tax_total=sum(r.tax_amount for r in resolved),
        notes=notes,
        created_by=created_by,
    )
    quotation.total = quotation.subtotal + quotation.tax_total
    quotation.lines = [
        SalesDocLine(
            item_id=r.item.id if r.item else None,
            description=r.description,
            quantity=r.quantity,
            unit_price=r.unit_price,
            tax_rate_id=r.tax_rate.id if r.tax_rate else None,
            line_subtotal=r.line_subtotal,
            tax_amount=r.tax_amount,
        )
        for r in resolved
    ]
    session.add(quotation)
    session.flush()
    return quotation


def convert_quotation_to_order(
    session: Session, quotation: SalesDoc, *, order_date: dt.date, created_by: str | None = None
) -> SalesDoc:
    """The customer accepted the quotation: create the sales order and mark the opportunity won."""
    if quotation.status != SalesDocStatus.DRAFT:
        raise DomainError(
            "invalid_status", f"Quotation {quotation.number} is {quotation.status} and cannot be converted again."
        )
    order = SalesDoc(
        kind=SalesDocKind.ORDER,
        number=next_number(session, "sales_order", "SO"),
        party_id=quotation.party_id,
        doc_date=order_date,
        status=SalesDocStatus.OPEN,
        opportunity_id=quotation.opportunity_id,
        source_doc_id=quotation.id,
        subtotal=quotation.subtotal,
        tax_total=quotation.tax_total,
        total=quotation.total,
        notes=quotation.notes,
        created_by=created_by,
    )
    order.lines = [
        SalesDocLine(
            item_id=line.item_id,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            tax_rate_id=line.tax_rate_id,
            line_subtotal=line.line_subtotal,
            tax_amount=line.tax_amount,
        )
        for line in quotation.lines
    ]
    quotation.status = SalesDocStatus.ACCEPTED
    session.add(order)
    if quotation.opportunity_id is not None:
        opportunity = session.get(Opportunity, quotation.opportunity_id)
        if opportunity is not None and opportunity.stage in OPEN_STAGES:
            opportunity.stage = OpportunityStage.WON
            opportunity.probability_pct = 100
            opportunity.closed_at = utcnow()
    session.flush()
    return order


def invoice_sales_order(
    session: Session,
    order: SalesDoc,
    *,
    invoice_date: dt.date,
    due_date: dt.date | None = None,
    created_by: str | None = None,
) -> Invoice:
    """Create a draft sales invoice for the whole order."""
    if order.status != SalesDocStatus.OPEN:
        raise DomainError("invalid_status", f"Sales order {order.number} is {order.status} and cannot be invoiced.")
    invoice = invoicing.create_invoice_draft(
        session,
        kind=InvoiceKind.SALES,
        party=order.party,
        invoice_date=invoice_date,
        due_date=due_date,
        lines=[
            DocLineInput(
                item_id=line.item_id,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                tax_rate_id=line.tax_rate_id,
                no_tax=line.tax_rate_id is None,
            )
            for line in order.lines
        ],
        reference=order.number,
        sales_order_id=order.id,
        created_by=created_by,
    )
    order.status = SalesDocStatus.INVOICED
    session.flush()
    return invoice
