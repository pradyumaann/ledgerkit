"""Quotations and sales orders."""

import datetime as dt

from pydantic import Field
from sqlalchemy import select

from ledgerkit.models import SalesDoc, SalesDocKind, SalesDocStatus
from ledgerkit.services import lookup, sales
from ledgerkit.tools import serializers
from ledgerkit.tools.common import MONEY_NOTE, LineIn, to_doc_lines
from ledgerkit.tools.context import ToolContext
from ledgerkit.tools.registry import ToolInput, registry


class CreateQuotation(ToolInput):
    customer_id: int = Field(description="Party id of the customer. Find it with search_parties.")
    quotation_date: dt.date | None = Field(None, description="Defaults to today.")
    valid_until: dt.date | None = None
    lines: list[LineIn] = Field(min_length=1)
    opportunity_id: int | None = Field(None, description="Opportunity this quotation belongs to, if any.")
    notes: str | None = None


@registry.tool(
    name="create_quotation",
    description="Create a price quotation for a customer. A quotation has no effect on the books. "
    "When the customer accepts it, use convert_quotation_to_order. " + MONEY_NOTE,
    input_model=CreateQuotation,
    mutating=True,
)
def create_quotation(ctx: ToolContext, p: CreateQuotation):
    quotation = sales.create_quotation(
        ctx.session,
        party=lookup.party(ctx.session, p.customer_id),
        doc_date=p.quotation_date or ctx.today,
        valid_until=p.valid_until,
        lines=to_doc_lines(ctx, p.lines),
        opportunity=lookup.opportunity(ctx.session, p.opportunity_id) if p.opportunity_id is not None else None,
        notes=p.notes,
        created_by=ctx.actor.label,
    )
    return serializers.sales_doc(quotation)


class ConvertQuotation(ToolInput):
    quotation_number: str = Field(description="e.g. 'QUO-00003'.")
    order_date: dt.date | None = Field(None, description="Defaults to today.")


@registry.tool(
    name="convert_quotation_to_order",
    description="The customer accepted a quotation: create the sales order from it. The quotation is "
    "marked accepted and its opportunity, if any, is marked won. Returns the new sales order.",
    input_model=ConvertQuotation,
    mutating=True,
)
def convert_quotation_to_order(ctx: ToolContext, p: ConvertQuotation):
    quotation = lookup.sales_doc(ctx.session, p.quotation_number, SalesDocKind.QUOTATION)
    order = sales.convert_quotation_to_order(
        ctx.session, quotation, order_date=p.order_date or ctx.today, created_by=ctx.actor.label
    )
    return serializers.sales_doc(order)


class InvoiceSalesOrder(ToolInput):
    order_number: str = Field(description="e.g. 'SO-00002'.")
    invoice_date: dt.date | None = Field(None, description="Defaults to today.")
    due_date: dt.date | None = Field(None, description="Defaults to 30 days after the invoice date.")


@registry.tool(
    name="invoice_sales_order",
    description="Create a draft sales invoice for the whole of an open sales order. The invoice still "
    "has to be posted with post_invoice. Returns the draft invoice.",
    input_model=InvoiceSalesOrder,
    mutating=True,
)
def invoice_sales_order(ctx: ToolContext, p: InvoiceSalesOrder):
    order = lookup.sales_doc(ctx.session, p.order_number, SalesDocKind.ORDER)
    invoice = sales.invoice_sales_order(
        ctx.session, order, invoice_date=p.invoice_date or ctx.today, due_date=p.due_date, created_by=ctx.actor.label
    )
    return serializers.invoice(invoice)


class ListSalesDocuments(ToolInput):
    kind: SalesDocKind | None = None
    status: SalesDocStatus | None = Field(
        None, description="Quotations are draft, accepted or rejected. Orders are open, invoiced or cancelled."
    )
    customer_id: int | None = None
    limit: int = Field(50, ge=1, le=500)


@registry.tool(
    name="list_sales_documents",
    description="List quotations and sales orders, newest first, with their lines.",
    input_model=ListSalesDocuments,
)
def list_sales_documents(ctx: ToolContext, p: ListSalesDocuments):
    stmt = select(SalesDoc).order_by(SalesDoc.doc_date.desc(), SalesDoc.id.desc()).limit(p.limit)
    if p.kind:
        stmt = stmt.where(SalesDoc.kind == p.kind)
    if p.status:
        stmt = stmt.where(SalesDoc.status == p.status)
    if p.customer_id is not None:
        stmt = stmt.where(SalesDoc.party_id == p.customer_id)
    found = list(ctx.session.scalars(stmt))
    return {"documents": [serializers.sales_doc(d) for d in found], "truncated": len(found) == p.limit}
