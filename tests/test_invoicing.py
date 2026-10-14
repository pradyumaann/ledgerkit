def _balances(call, as_of="2026-12-31"):
    rows = call("trial_balance", as_of=as_of)["accounts"]
    return {r["code"]: (r["debit"], r["credit"]) for r in rows}


def _sales_invoice(call, catalogue, **overrides):
    payload = {
        "customer_id": catalogue["customer"],
        "invoice_date": "2026-03-01",
        "lines": [{"item_sku": "WIDGET", "quantity": 3}, {"item_sku": "HOUR", "quantity": "2.5"}],
    }
    return call("create_sales_invoice_draft", **(payload | overrides))


def test_draft_invoice_computes_totals_and_leaves_ledger_untouched(call, catalogue):
    invoice = _sales_invoice(call, catalogue)
    assert invoice["status"] == "draft"
    assert invoice["subtotal"] == "675.00"  # 3 x 100 + 2.5 x 150
    assert invoice["tax_total"] == "30.00"  # 10% on the widgets only
    assert invoice["total"] == "705.00"
    assert invoice["due_date"] == "2026-03-31"
    assert _balances(call) == {}


def test_posting_sales_invoice_creates_correct_journal_lines(call, catalogue):
    invoice = _sales_invoice(call, catalogue)
    posted = call("post_invoice", number=invoice["number"])
    assert posted["status"] == "posted"
    assert posted["outstanding"] == "705.00"
    assert _balances(call) == {
        "1100": ("705.00", "0.00"),  # receivable: total including tax
        "1200": ("0.00", "180.00"),  # inventory relieved at standard cost, 3 x 60
        "2100": ("0.00", "30.00"),  # tax payable
        "4000": ("0.00", "300.00"),  # product revenue
        "4100": ("0.00", "375.00"),  # service revenue
        "5000": ("180.00", "0.00"),  # cost of goods sold
    }


def test_posting_vendor_bill_creates_correct_journal_lines(call, catalogue):
    bill = call(
        "create_vendor_bill_draft",
        vendor_id=catalogue["vendor"],
        bill_date="2026-03-02",
        lines=[
            {"item_sku": "WIDGET", "quantity": 10},
            {"description": "Rent", "account_code": "6100", "unit_price": "800.00"},
        ],
    )
    assert bill["total"] == "1460.00"  # 600 stock + 60 tax + 800 rent
    call("post_invoice", number=bill["number"])
    assert _balances(call) == {
        "1200": ("600.00", "0.00"),
        "1300": ("60.00", "0.00"),
        "2000": ("0.00", "1460.00"),
        "6100": ("800.00", "0.00"),
    }


def test_vendor_bill_line_without_item_needs_an_account(raw_call, catalogue):
    result = raw_call(
        "create_vendor_bill_draft",
        vendor_id=catalogue["vendor"],
        lines=[{"description": "Something", "unit_price": 10}],
    )
    assert result["status"] == "error"
    assert "account_code is required" in result["error"]["message"]


def test_sales_invoice_rejects_a_vendor(raw_call, catalogue):
    result = raw_call("create_sales_invoice_draft", customer_id=catalogue["vendor"], lines=[{"item_sku": "WIDGET"}])
    assert result["error"]["code"] == "wrong_party_role"


def test_partial_then_full_payment(call, catalogue):
    invoice = call("post_invoice", number=_sales_invoice(call, catalogue)["number"])
    first = call(
        "record_payment",
        direction="inbound",
        party_id=catalogue["customer"],
        amount="200.00",
        payment_date="2026-03-10",
    )
    assert first["allocations"] == [{"invoice_number": invoice["number"], "amount": "200.00"}]
    after_first = call("get_invoice", number=invoice["number"])
    assert (after_first["payment_status"], after_first["outstanding"]) == ("partial", "505.00")

    call(
        "record_payment",
        direction="inbound",
        party_id=catalogue["customer"],
        amount="505.00",
        payment_date="2026-03-20",
    )
    after_second = call("get_invoice", number=invoice["number"])
    assert (after_second["payment_status"], after_second["outstanding"]) == ("paid", "0.00")
    balances = _balances(call)
    assert balances["1000"] == ("705.00", "0.00")
    assert "1100" not in balances  # receivable fully cleared


def test_payment_auto_allocates_oldest_first_and_keeps_the_rest_unallocated(call, catalogue):
    older = call("post_invoice", number=_sales_invoice(call, catalogue, invoice_date="2026-01-05")["number"])
    newer = call("post_invoice", number=_sales_invoice(call, catalogue, invoice_date="2026-02-05")["number"])
    payment = call("record_payment", direction="inbound", party_id=catalogue["customer"], amount="1500.00")
    assert payment["allocations"] == [
        {"invoice_number": older["number"], "amount": "705.00"},
        {"invoice_number": newer["number"], "amount": "705.00"},
    ]
    assert payment["unallocated"] == "90.00"


def test_cannot_overpay_an_invoice(raw_call, call, catalogue):
    invoice = call("post_invoice", number=_sales_invoice(call, catalogue)["number"])
    result = raw_call(
        "record_payment",
        direction="inbound",
        party_id=catalogue["customer"],
        amount="800.00",
        allocations=[{"invoice_number": invoice["number"], "amount": "800.00"}],
    )
    assert result["error"]["code"] == "invalid_allocation"
    assert "705.00 USD is outstanding" in result["error"]["message"]


def test_void_requires_payments_to_be_voided_first(raw_call, call, catalogue):
    invoice = call("post_invoice", number=_sales_invoice(call, catalogue)["number"])
    payment = call("record_payment", direction="inbound", party_id=catalogue["customer"], amount="705.00")
    assert raw_call("void_invoice", number=invoice["number"])["error"]["code"] == "has_payments"

    call("void_payment", payment_number=payment["number"])
    assert call("get_invoice", number=invoice["number"])["outstanding"] == "705.00"
    assert call("void_invoice", number=invoice["number"])["status"] == "void"
    assert _balances(call) == {}  # everything reversed


def test_amount_with_too_many_decimals_is_rejected(raw_call, catalogue):
    result = raw_call(
        "create_sales_invoice_draft",
        customer_id=catalogue["customer"],
        lines=[{"description": "Odd", "unit_price": "10.005"}],
    )
    assert result["error"]["code"] == "invalid_amount"


def test_quote_to_order_to_invoice_flow(call, raw_call, catalogue):
    opportunity = call("create_opportunity", title="Big deal", party_id=catalogue["customer"], expected_value=1000)
    quotation = call(
        "create_quotation",
        customer_id=catalogue["customer"],
        opportunity_id=opportunity["id"],
        lines=[{"item_sku": "WIDGET", "quantity": 10, "unit_price": "90.00"}],
    )
    assert quotation["total"] == "990.00"
    order = call("convert_quotation_to_order", quotation_number=quotation["number"])
    assert (order["kind"], order["status"], order["total"]) == ("order", "open", "990.00")
    assert (
        raw_call("convert_quotation_to_order", quotation_number=quotation["number"])["error"]["code"]
        == "invalid_status"
    )

    pipeline = call("pipeline_summary")
    assert pipeline["won_count"] == 1 and pipeline["open_count"] == 0

    invoice = call("invoice_sales_order", order_number=order["number"], invoice_date="2026-04-01")
    assert (invoice["status"], invoice["total"], invoice["reference"]) == ("draft", "990.00", order["number"])
    assert raw_call("invoice_sales_order", order_number=order["number"])["error"]["code"] == "invalid_status"
