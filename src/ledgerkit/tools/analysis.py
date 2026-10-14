"""Financial statements and profitability analysis.

Every figure these tools return is computed from posted records. A model using them
should quote and interpret the figures, not recalculate them.
"""

import datetime as dt

from pydantic import Field

from ledgerkit.analysis import profitability, receivables, statements
from ledgerkit.errors import DomainError
from ledgerkit.models import InvoiceKind
from ledgerkit.tools.common import AsOfInput, PeriodInput
from ledgerkit.tools.context import ToolContext
from ledgerkit.tools.registry import registry

COMPUTED = "All figures are computed from posted records; quote them as given rather than recalculating."


@registry.tool(
    name="profit_and_loss",
    description="Income statement for a period: revenue, cost of goods sold, gross profit, operating "
    "expenses and net profit, by account, with gross and net margin percentages. " + COMPUTED,
    input_model=PeriodInput,
)
def profit_and_loss(ctx: ToolContext, p: PeriodInput):
    return statements.profit_and_loss(ctx.session, *ctx.period(p.date_from, p.date_to))


@registry.tool(
    name="balance_sheet",
    description="Assets, liabilities and equity as of a date, by account. " + COMPUTED,
    input_model=AsOfInput,
)
def balance_sheet(ctx: ToolContext, p: AsOfInput):
    return statements.balance_sheet(ctx.session, p.as_of or ctx.today)


@registry.tool(
    name="margin_by_item",
    description="Profitability of each product and service for a period: quantity sold, revenue, cost, "
    "gross margin, margin percentage and share of revenue, most profitable first. Use it to find "
    "which items make or lose money. " + COMPUTED,
    input_model=PeriodInput,
)
def margin_by_item(ctx: ToolContext, p: PeriodInput):
    return profitability.margin_by_item(ctx.session, *ctx.period(p.date_from, p.date_to))


@registry.tool(
    name="margin_by_customer",
    description="Profitability of each customer for a period: number of invoices, revenue, cost, gross "
    "margin, margin percentage and share of revenue, most profitable first. Use it to find the most "
    "and least valuable customers and how concentrated revenue is. " + COMPUTED,
    input_model=PeriodInput,
)
def margin_by_customer(ctx: ToolContext, p: PeriodInput):
    return profitability.margin_by_customer(ctx.session, *ctx.period(p.date_from, p.date_to))


@registry.tool(
    name="revenue_trend",
    description="Month-by-month revenue, cost of goods sold, gross profit, operating expenses and net "
    "profit across a period. Use it to see growth, seasonality or margin drift. " + COMPUTED,
    input_model=PeriodInput,
)
def revenue_trend(ctx: ToolContext, p: PeriodInput):
    return profitability.revenue_trend(ctx.session, *ctx.period(p.date_from, p.date_to))


@registry.tool(
    name="expense_breakdown",
    description="Every expense account for a period, largest first, with its share of total expenses "
    "and its size relative to revenue. Use it to see where the money goes. " + COMPUTED,
    input_model=PeriodInput,
)
def expense_breakdown(ctx: ToolContext, p: PeriodInput):
    return profitability.expense_breakdown(ctx.session, *ctx.period(p.date_from, p.date_to))


@registry.tool(
    name="break_even",
    description="Break-even analysis for a period: contribution margin, fixed costs, the revenue needed "
    "to break even and the margin of safety. Read the 'assumptions' field before drawing conclusions. " + COMPUTED,
    input_model=PeriodInput,
)
def break_even(ctx: ToolContext, p: PeriodInput):
    return profitability.break_even(ctx.session, *ctx.period(p.date_from, p.date_to))


class PeriodComparison(PeriodInput):
    previous_from: dt.date | None = Field(
        None,
        description="First day of the period to compare against. Defaults to the period of equal length "
        "immediately before date_from.",
    )
    previous_to: dt.date | None = Field(None, description="Last day of the comparison period, inclusive.")


@registry.tool(
    name="period_comparison",
    description="Compare revenue, costs, profit and margins between two periods, with the change and "
    "percentage change for each. By default it compares the period given with the equally long period "
    "just before it. " + COMPUTED,
    input_model=PeriodComparison,
)
def period_comparison(ctx: ToolContext, p: PeriodComparison):
    date_from, date_to = ctx.period(p.date_from, p.date_to)
    if (p.previous_from is None) != (p.previous_to is None):
        raise DomainError("invalid_input", "Give both previous_from and previous_to, or neither.")
    if p.previous_from is None:
        previous_to = date_from - dt.timedelta(days=1)
        previous_from = previous_to - (date_to - date_from)
    else:
        previous_from, previous_to = p.previous_from, p.previous_to
        if previous_from > previous_to:
            raise DomainError("invalid_input", "previous_from is after previous_to.")
    return statements.period_comparison(ctx.session, date_from, date_to, previous_from, previous_to)


@registry.tool(
    name="ar_aging",
    description="Accounts receivable aging: what customers owe as of a date, by customer and by how far "
    "past due it is, with the individual invoices. Use it for collections and cash-flow risk. " + COMPUTED,
    input_model=AsOfInput,
)
def ar_aging(ctx: ToolContext, p: AsOfInput):
    return receivables.aging(ctx.session, InvoiceKind.SALES, p.as_of or ctx.today)


@registry.tool(
    name="ap_aging",
    description="Accounts payable aging: what the business owes vendors as of a date, by vendor and by "
    "how far past due it is, with the individual bills. " + COMPUTED,
    input_model=AsOfInput,
)
def ap_aging(ctx: ToolContext, p: AsOfInput):
    return receivables.aging(ctx.session, InvoiceKind.PURCHASE, p.as_of or ctx.today)
