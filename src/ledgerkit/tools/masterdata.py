"""Customers, vendors, items and tax rates."""

from decimal import Decimal
from typing import Literal

from pydantic import Field
from sqlalchemy import func, select

from ledgerkit.models import Invoice, InvoiceKind, InvoiceStatus, Item, ItemKind, TaxRate
from ledgerkit.money import Minor, round_half_up
from ledgerkit.services import lookup, masterdata
from ledgerkit.tools import serializers
from ledgerkit.tools.accounting import Empty
from ledgerkit.tools.context import ToolContext
from ledgerkit.tools.registry import ToolInput, registry


class CreateParty(ToolInput):
    name: str = Field(min_length=1, max_length=200)
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    tax_id: str | None = Field(None, description="Tax or VAT registration number.")
    notes: str | None = None


def _create_party(ctx: ToolContext, p: CreateParty, *, is_customer: bool, is_vendor: bool):
    party = masterdata.create_party(ctx.session, is_customer=is_customer, is_vendor=is_vendor, **p.model_dump())
    return serializers.party(party)


@registry.tool(
    name="create_customer",
    description="Create a customer. Search with search_parties first to avoid duplicates. If a vendor "
    "with the same name exists, it is also marked as a customer.",
    input_model=CreateParty,
    mutating=True,
)
def create_customer(ctx: ToolContext, p: CreateParty):
    return _create_party(ctx, p, is_customer=True, is_vendor=False)


@registry.tool(
    name="create_vendor",
    description="Create a vendor (supplier). Search with search_parties first to avoid duplicates. If a "
    "customer with the same name exists, it is also marked as a vendor.",
    input_model=CreateParty,
    mutating=True,
)
def create_vendor(ctx: ToolContext, p: CreateParty):
    return _create_party(ctx, p, is_customer=False, is_vendor=True)


class SearchParties(ToolInput):
    query: str | None = Field(None, description="Part of a name or email. Omit to list everyone.")
    role: Literal["customer", "vendor"] | None = None
    limit: int = Field(25, ge=1, le=200)


@registry.tool(
    name="search_parties",
    description="Find customers and vendors by name or email. Returns their party ids, which other tools need.",
    input_model=SearchParties,
)
def search_parties(ctx: ToolContext, p: SearchParties):
    found = masterdata.search_parties(ctx.session, query=p.query, role=p.role, limit=p.limit)
    return {"parties": [serializers.party(x) for x in found], "truncated": len(found) == p.limit}


class CreateTaxRate(ToolInput):
    name: str = Field(min_length=1, max_length=100, description="e.g. 'VAT 20%' or 'GST 18%'.")
    rate_pct: Decimal = Field(ge=0, le=100, decimal_places=2, description="Percentage, e.g. 18 or 7.5.")
    sales_account_code: str | None = Field(
        None, description="Liability account for tax collected on sales. Defaults to the tax payable account."
    )
    purchase_account_code: str | None = Field(
        None, description="Asset account for tax paid on purchases. Defaults to the input tax account."
    )


@registry.tool(
    name="create_tax_rate",
    description="Define a sales or value-added tax rate that can be applied to invoice and bill lines.",
    input_model=CreateTaxRate,
    mutating=True,
    requires_approval=True,
)
def create_tax_rate(ctx: ToolContext, p: CreateTaxRate):
    tax = masterdata.create_tax_rate(
        ctx.session,
        name=p.name,
        rate_bp=round_half_up(p.rate_pct * 100),
        sales_account=lookup.account(ctx.session, p.sales_account_code) if p.sales_account_code else None,
        purchase_account=lookup.account(ctx.session, p.purchase_account_code) if p.purchase_account_code else None,
    )
    return serializers.tax_rate(tax)


@registry.tool(
    name="list_tax_rates",
    description="List the tax rates that can be applied to document lines.",
    input_model=Empty,
)
def list_tax_rates(ctx: ToolContext, p: Empty):
    rates = ctx.session.scalars(select(TaxRate).order_by(TaxRate.name))
    return {"tax_rates": [serializers.tax_rate(t) for t in rates]}


class CreateItem(ToolInput):
    sku: str = Field(min_length=1, max_length=50, description="Unique code for the item.")
    name: str = Field(min_length=1, max_length=200)
    kind: ItemKind = Field(description="'product' for goods with a unit cost, 'service' for work or subscriptions.")
    sale_price: Decimal = Field(ge=0, description="Default selling price per unit, before tax.")
    standard_cost: Decimal = Field(
        Decimal(0),
        ge=0,
        description="Products only: what one unit costs the business. It is used as the cost of goods "
        "sold whenever the product is invoiced, so margins depend on it being realistic.",
    )
    income_account_code: str = Field("4000", description="Income account credited when the item is sold.")
    tax_rate: str | None = Field(None, description="Name of the tax rate charged by default.")


@registry.tool(
    name="create_item",
    description="Create a product or service that can be put on quotations, invoices and bills.",
    input_model=CreateItem,
    mutating=True,
)
def create_item(ctx: ToolContext, p: CreateItem):
    item = masterdata.create_item(
        ctx.session,
        sku=p.sku,
        name=p.name,
        kind=p.kind,
        sale_price=ctx.minor(p.sale_price),
        standard_cost=ctx.minor(p.standard_cost),
        income_account=lookup.account(ctx.session, p.income_account_code),
        tax_rate=lookup.tax_rate(ctx.session, p.tax_rate) if p.tax_rate else None,
    )
    return serializers.item(item)


class ListItems(ToolInput):
    query: str | None = Field(None, description="Part of a SKU or name.")
    limit: int = Field(100, ge=1, le=500)


@registry.tool(
    name="list_items",
    description="List products and services with their SKU, price, standard cost and default tax rate.",
    input_model=ListItems,
)
def list_items(ctx: ToolContext, p: ListItems):
    stmt = select(Item).where(Item.is_active).order_by(Item.sku).limit(p.limit)
    if p.query:
        like = f"%{p.query}%"
        stmt = stmt.where(Item.sku.ilike(like) | Item.name.ilike(like))
    found = list(ctx.session.scalars(stmt))
    return {"items": [serializers.item(i) for i in found], "truncated": len(found) == p.limit}


class PartyId(ToolInput):
    party_id: int


@registry.tool(
    name="get_party",
    description="Show one customer or vendor with what they currently owe the business (receivable) "
    "and what the business owes them (payable).",
    input_model=PartyId,
)
def get_party(ctx: ToolContext, p: PartyId):
    party = lookup.party(ctx.session, p.party_id)

    def outstanding(kind: InvoiceKind) -> Minor:
        total = ctx.session.scalar(
            select(func.sum(Invoice.total - Invoice.amount_paid)).where(
                Invoice.party_id == party.id, Invoice.kind == kind, Invoice.status == InvoiceStatus.POSTED
            )
        )
        return Minor(total or 0)

    return {
        **serializers.party(party),
        "notes": party.notes,
        "receivable": outstanding(InvoiceKind.SALES),
        "payable": outstanding(InvoiceKind.PURCHASE),
    }
