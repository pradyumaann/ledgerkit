"""Financial statements, computed from posted ledger lines."""

import datetime as dt

from sqlalchemy.orm import Session

from ledgerkit.models import Account, AccountSubtype, AccountType
from ledgerkit.money import Minor, pct
from ledgerkit.services import ledger
from ledgerkit.services.company import get_company


def _row(account: Account, amount: int) -> dict:
    return {"code": account.code, "name": account.name, "amount": Minor(amount)}


def _section(rows: list[dict]) -> dict:
    return {"accounts": rows, "total": Minor(sum(r["amount"] for r in rows))}


def trial_balance(session: Session, as_of: dt.date) -> dict:
    rows, total_debit, total_credit = [], 0, 0
    for account, debit, credit in ledger.balances(session, date_to=as_of):
        net = debit - credit
        if not net:
            continue
        total_debit += max(net, 0)
        total_credit += max(-net, 0)
        rows.append(
            {
                "code": account.code,
                "name": account.name,
                "type": account.type,
                "subtype": account.subtype,
                "debit": Minor(max(net, 0)),
                "credit": Minor(max(-net, 0)),
            }
        )
    return {
        "as_of": as_of,
        "currency": get_company(session).base_currency,
        "accounts": rows,
        "total_debit": Minor(total_debit),
        "total_credit": Minor(total_credit),
        "balanced": total_debit == total_credit,
    }


def profit_and_loss(session: Session, date_from: dt.date, date_to: dt.date) -> dict:
    revenue, cogs, opex = [], [], []
    for account, debit, credit in ledger.balances(session, date_from=date_from, date_to=date_to):
        if account.type == AccountType.INCOME:
            revenue.append(_row(account, credit - debit))
        elif account.type == AccountType.EXPENSE:
            (cogs if account.subtype == AccountSubtype.COGS else opex).append(_row(account, debit - credit))
    total_revenue = sum(r["amount"] for r in revenue)
    total_cogs = sum(r["amount"] for r in cogs)
    total_opex = sum(r["amount"] for r in opex)
    gross_profit = total_revenue - total_cogs
    net_profit = gross_profit - total_opex
    return {
        "period": {"from": date_from, "to": date_to},
        "currency": get_company(session).base_currency,
        "revenue": _section(revenue),
        "cost_of_goods_sold": _section(cogs),
        "gross_profit": Minor(gross_profit),
        "gross_margin_pct": pct(gross_profit, total_revenue),
        "operating_expenses": _section(opex),
        "net_profit": Minor(net_profit),
        "net_margin_pct": pct(net_profit, total_revenue),
    }


def balance_sheet(session: Session, as_of: dt.date) -> dict:
    assets, liabilities, equity = [], [], []
    earnings = 0
    for account, debit, credit in ledger.balances(session, date_to=as_of):
        if account.type == AccountType.ASSET:
            assets.append(_row(account, debit - credit))
        elif account.type == AccountType.LIABILITY:
            liabilities.append(_row(account, credit - debit))
        elif account.type == AccountType.EQUITY:
            equity.append(_row(account, credit - debit))
        else:
            earnings += credit - debit
    # Income and expense accounts are not closed into Retained Earnings at year end,
    # so their cumulative balance is shown as one equity line.
    equity.append({"code": None, "name": "Accumulated profit (not yet closed to equity)", "amount": Minor(earnings)})
    total_assets = sum(r["amount"] for r in assets)
    total_liabilities = sum(r["amount"] for r in liabilities)
    total_equity = sum(r["amount"] for r in equity)
    return {
        "as_of": as_of,
        "currency": get_company(session).base_currency,
        "assets": _section(assets),
        "liabilities": _section(liabilities),
        "equity": _section(equity),
        "total_liabilities_and_equity": Minor(total_liabilities + total_equity),
        "balanced": total_assets == total_liabilities + total_equity,
    }


def _change(current: int, previous: int) -> dict:
    return {
        "current": Minor(current),
        "previous": Minor(previous),
        "change": Minor(current - previous),
        "change_pct": pct(current - previous, abs(previous)),
    }


def period_comparison(
    session: Session, current_from: dt.date, current_to: dt.date, previous_from: dt.date, previous_to: dt.date
) -> dict:
    current = profit_and_loss(session, current_from, current_to)
    previous = profit_and_loss(session, previous_from, previous_to)

    def compare(key: str) -> dict:
        def value(statement: dict) -> int:
            return statement[key]["total"] if isinstance(statement[key], dict) else statement[key]

        return _change(value(current), value(previous))

    return {
        "current_period": current["period"],
        "previous_period": previous["period"],
        "currency": current["currency"],
        "revenue": compare("revenue"),
        "cost_of_goods_sold": compare("cost_of_goods_sold"),
        "gross_profit": compare("gross_profit"),
        "operating_expenses": compare("operating_expenses"),
        "net_profit": compare("net_profit"),
        "gross_margin_pct": {"current": current["gross_margin_pct"], "previous": previous["gross_margin_pct"]},
        "net_margin_pct": {"current": current["net_margin_pct"], "previous": previous["net_margin_pct"]},
    }
