"""Golden checks: every report must reconcile with the ledger and with each other."""

import datetime as dt
from decimal import Decimal

import pytest

from ledgerkit.demo import seed_demo_data
from ledgerkit.errors import DomainError
from ledgerkit.tools import registry
from tests.conftest import USER, new_database

TODAY = dt.date(2026, 9, 20)
START = "2026-04-01"
PERIOD = {"date_from": START, "date_to": TODAY.isoformat()}


@pytest.fixture(scope="module")
def demo_factory(tmp_path_factory):
    """One seeded database shared by this module; the tests below only read from it."""
    engine, factory = new_database(tmp_path_factory.mktemp("demo") / "demo.db")
    seed_demo_data(factory, today=TODAY)
    yield factory
    engine.dispose()


@pytest.fixture
def demo(demo_factory):
    def _call(tool: str, **payload):
        result = registry.call(demo_factory, tool, payload, USER)
        assert result["status"] == "ok", result
        return result["data"]

    return _call


def D(value: str) -> Decimal:
    return Decimal(value)


def test_seed_refuses_a_database_with_data(demo_factory):
    with pytest.raises(DomainError) as exc:
        seed_demo_data(demo_factory, today=TODAY)
    assert exc.value.code == "not_empty"


def test_trial_balance_balances(demo):
    tb = demo("trial_balance", as_of=TODAY.isoformat())
    assert tb["balanced"] is True
    assert tb["total_debit"] == tb["total_credit"]
    assert D(tb["total_debit"]) > 0


def test_balance_sheet_balances_and_profit_equals_change_in_equity(demo):
    bs = demo("balance_sheet", as_of=TODAY.isoformat())
    assert bs["balanced"] is True
    assert bs["assets"]["total"] == bs["total_liabilities_and_equity"]

    pl = demo("profit_and_loss", **PERIOD)
    equity = {row["name"]: D(row["amount"]) for row in bs["equity"]["accounts"]}
    # Equity started at zero: the only owner contribution was 60,000, the rest is profit.
    assert equity["Owner's Equity"] == D("60000.00")
    assert D(bs["equity"]["total"]) - D("60000.00") == D(pl["net_profit"])


def test_profit_and_loss_adds_up(demo):
    pl = demo("profit_and_loss", **PERIOD)
    revenue, cogs, opex = (
        D(pl["revenue"]["total"]),
        D(pl["cost_of_goods_sold"]["total"]),
        D(pl["operating_expenses"]["total"]),
    )
    assert revenue == sum(D(a["amount"]) for a in pl["revenue"]["accounts"])
    assert D(pl["gross_profit"]) == revenue - cogs
    assert D(pl["net_profit"]) == revenue - cogs - opex
    assert D(pl["gross_margin_pct"]) == (100 * (revenue - cogs) / revenue).quantize(D("0.01"))


def test_margin_reports_reconcile_to_the_profit_and_loss(demo):
    pl = demo("profit_and_loss", **PERIOD)
    by_item = demo("margin_by_item", **PERIOD)
    by_customer = demo("margin_by_customer", **PERIOD)
    for report in (by_item, by_customer):
        assert report["total_revenue"] == pl["revenue"]["total"]
        assert report["total_cost"] == pl["cost_of_goods_sold"]["total"]
        assert report["total_gross_margin"] == pl["gross_profit"]
        assert sum(D(r["gross_margin"]) for r in report["rows"]) == D(pl["gross_profit"])
        margins = [D(r["gross_margin"]) for r in report["rows"]]
        assert margins == sorted(margins, reverse=True)


def test_margin_by_item_figures(demo):
    rows = {r["sku"]: r for r in demo("margin_by_item", **PERIOD)["rows"]}
    # Services carry no cost of goods sold.
    assert rows["CONSULT"]["cost"] == "0.00" and rows["CONSULT"]["gross_margin_pct"] == "100.00"
    # Widgets at 120: Acme 30+6i and Initech 15, for six months. Umbrella buys 10+4i at 95, but its
    # September invoice is dated the 22nd, after TODAY, so only five months exist. Cost is 70 each.
    full_price = sum(30 + 6 * i + 15 for i in range(6))
    discounted = sum(10 + 4 * i for i in range(5))
    quantity = full_price + discounted
    revenue = full_price * 120 + discounted * 95
    assert rows["WIDGET"]["quantity"] == str(quantity)
    assert D(rows["WIDGET"]["revenue"]) == revenue
    assert D(rows["WIDGET"]["cost"]) == quantity * 70


def test_thin_margin_customer_ranks_last(demo):
    rows = demo("margin_by_customer", **PERIOD)["rows"]
    by_pct = sorted(rows, key=lambda r: D(r["gross_margin_pct"]))
    assert by_pct[0]["name"] == "Umbrella Retail"
    assert sum(D(r["share_of_revenue_pct"]) for r in rows) == pytest.approx(D(100), abs=D("0.05"))


def test_revenue_trend_sums_to_the_period(demo):
    pl = demo("profit_and_loss", **PERIOD)
    months = demo("revenue_trend", **PERIOD)["months"]
    assert [m["month"] for m in months] == ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
    assert sum(D(m["revenue"]) for m in months) == D(pl["revenue"]["total"])
    assert sum(D(m["net_profit"]) for m in months) == D(pl["net_profit"])


def test_expense_breakdown_matches_the_profit_and_loss(demo):
    pl = demo("profit_and_loss", **PERIOD)
    breakdown = demo("expense_breakdown", **PERIOD)
    assert D(breakdown["total_expenses"]) == D(pl["cost_of_goods_sold"]["total"]) + D(pl["operating_expenses"]["total"])
    amounts = [D(e["amount"]) for e in breakdown["expenses"]]
    assert amounts == sorted(amounts, reverse=True)


def test_break_even(demo):
    pl = demo("profit_and_loss", **PERIOD)
    be = demo("break_even", **PERIOD)
    assert be["fixed_costs"] == pl["operating_expenses"]["total"]
    assert be["contribution_margin"] == pl["gross_profit"]
    ratio = D(be["contribution_margin"]) / D(be["revenue"])
    assert D(be["break_even_revenue"]) == pytest.approx(D(be["fixed_costs"]) / ratio, abs=D("0.01"))
    assert D(be["margin_of_safety"]) == D(be["revenue"]) - D(be["break_even_revenue"])


def test_break_even_is_null_without_revenue(call):
    be = call("break_even", date_from="2026-01-01", date_to="2026-01-31")
    assert be["break_even_revenue"] is None and be["contribution_margin_pct"] is None


def test_aging_reconciles_to_the_control_accounts(demo):
    balances = {r["code"]: r for r in demo("trial_balance", as_of=TODAY.isoformat())["accounts"]}
    ar = demo("ar_aging", as_of=TODAY.isoformat())
    ap = demo("ap_aging", as_of=TODAY.isoformat())
    assert ar["total_outstanding"] == balances["1100"]["debit"]
    assert ap["total_outstanding"] == balances["2000"]["credit"]
    assert sum(D(v) for v in ar["buckets"].values()) == D(ar["total_outstanding"])
    assert sum(D(i["outstanding"]) for i in ar["invoices"]) == D(ar["total_outstanding"])
    # Umbrella's unpaid July invoice (22 July, due 21 August) is 30 days late; August's is not yet due.
    umbrella = next(p for p in ar["by_party"] if p["name"] == "Umbrella Retail")
    assert D(umbrella["1_30"]) == D("2299.00")  # 22 widgets at 95, plus 10% tax
    assert D(umbrella["current"]) == D("2717.00")  # 26 widgets at 95, plus 10% tax
    assert D(ar["total_overdue"]) == D(ar["total_outstanding"]) - D(ar["buckets"]["current"])


def test_aging_as_of_an_earlier_date_ignores_later_payments(demo):
    # Acme's April invoice (dated the 6th) was paid on the 26th.
    before = demo("ar_aging", as_of="2026-04-20")
    after = demo("ar_aging", as_of="2026-04-27")
    assert any(i["party"] == "Acme Corp" for i in before["invoices"])
    assert not any(i["party"] == "Acme Corp" for i in after["invoices"])


def test_period_comparison_defaults_to_the_preceding_period(demo):
    result = demo("period_comparison", date_from="2026-08-01", date_to="2026-08-31")
    assert result["previous_period"] == {"from": "2026-07-01", "to": "2026-07-31"}
    july = demo("profit_and_loss", date_from="2026-07-01", date_to="2026-07-31")
    august = demo("profit_and_loss", date_from="2026-08-01", date_to="2026-08-31")
    assert result["revenue"]["current"] == august["revenue"]["total"]
    assert result["revenue"]["previous"] == july["revenue"]["total"]
    assert D(result["net_profit"]["change"]) == D(august["net_profit"]) - D(july["net_profit"])
    assert D(result["revenue"]["change_pct"]) > 0  # the demo business is growing
