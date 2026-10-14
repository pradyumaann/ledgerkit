"""Input shapes shared by several tools."""

import datetime as dt
from decimal import Decimal

from pydantic import Field

from ledgerkit.services import lookup
from ledgerkit.services.invoicing import DocLineInput
from ledgerkit.tools.context import ToolContext
from ledgerkit.tools.registry import ToolInput

MONEY_NOTE = "Amounts are in the company's base currency, e.g. 1250.00."


class PeriodInput(ToolInput):
    date_from: dt.date | None = Field(
        None, description="First day of the period (YYYY-MM-DD). Defaults to the start of the current fiscal year."
    )
    date_to: dt.date | None = Field(
        None, description="Last day of the period, inclusive (YYYY-MM-DD). Defaults to today."
    )


class AsOfInput(ToolInput):
    as_of: dt.date | None = Field(None, description="Report date (YYYY-MM-DD). Defaults to today.")


class LineIn(ToolInput):
    item_sku: str | None = Field(
        None, description="SKU of the item sold or bought. Fills in description, price, account and tax."
    )
    description: str | None = Field(None, description="Line text. Required when item_sku is not given.")
    quantity: Decimal = Field(Decimal(1), gt=0, decimal_places=4, description="Quantity; up to 4 decimal places.")
    unit_price: Decimal | None = Field(
        None, ge=0, description="Price per unit before tax. Defaults to the item's price. Required without item_sku."
    )
    tax_rate: str | None = Field(
        None,
        description="Name of the tax rate to apply. Defaults to the item's tax rate. Pass 'none' to charge no tax.",
    )


class InvoiceLineIn(LineIn):
    account_code: str | None = Field(
        None,
        description="Account to book the line to. On a sales invoice it defaults to the item's income "
        "account. On a vendor bill it is required (an expense account) unless item_sku is a product, "
        "which goes to Inventory.",
    )


def to_doc_lines(ctx: ToolContext, lines: list[LineIn]) -> list[DocLineInput]:
    result = []
    for line in lines:
        no_tax = line.tax_rate is not None and line.tax_rate.strip().lower() == "none"
        account_code = getattr(line, "account_code", None)
        result.append(
            DocLineInput(
                item_id=lookup.item(ctx.session, line.item_sku).id if line.item_sku else None,
                description=line.description,
                quantity=line.quantity,
                unit_price=None if line.unit_price is None else ctx.minor(line.unit_price),
                account_id=lookup.account(ctx.session, account_code).id if account_code else None,
                tax_rate_id=lookup.tax_rate(ctx.session, line.tax_rate).id if line.tax_rate and not no_tax else None,
                no_tax=no_tax,
            )
        )
    return result
