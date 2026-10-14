"""Turn records into plain dicts for tool output. Money is wrapped in Minor so the
registry renders it as a decimal string."""

from ledgerkit.models import (
    Account,
    Invoice,
    InvoiceKind,
    Item,
    JournalEntry,
    Lead,
    Opportunity,
    Party,
    Payment,
    PendingAction,
    SalesDoc,
    TaxRate,
)
from ledgerkit.money import Minor, from_minor, trim


def account(a: Account) -> dict:
    return {"code": a.code, "name": a.name, "type": a.type, "subtype": a.subtype, "is_active": a.is_active}


def journal_entry_summary(e: JournalEntry) -> dict:
    return {
        "number": e.number,
        "entry_date": e.entry_date,
        "memo": e.memo,
        "status": e.status,
        "source_type": e.source_type,
        "created_by": e.created_by,
        "total_debit": Minor(sum(line.debit for line in e.lines)),
        "total_credit": Minor(sum(line.credit for line in e.lines)),
    }


def journal_entry(e: JournalEntry) -> dict:
    return {
        **journal_entry_summary(e),
        "lines": [
            {
                "account_code": line.account.code,
                "account_name": line.account.name,
                "debit": Minor(line.debit),
                "credit": Minor(line.credit),
                "party_id": line.party_id,
                "description": line.description,
            }
            for line in e.lines
        ],
    }


def party(p: Party) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "is_customer": p.is_customer,
        "is_vendor": p.is_vendor,
        "email": p.email,
        "phone": p.phone,
        "address": p.address,
        "tax_id": p.tax_id,
    }


def tax_rate(t: TaxRate) -> dict:
    return {"name": t.name, "rate_pct": trim(from_minor(t.rate_bp, 2)), "is_active": t.is_active}


def item(i: Item) -> dict:
    return {
        "sku": i.sku,
        "name": i.name,
        "kind": i.kind,
        "sale_price": Minor(i.sale_price),
        "standard_cost": Minor(i.standard_cost),
        "income_account_code": i.income_account.code,
        "tax_rate": i.tax_rate.name if i.tax_rate else None,
        "is_active": i.is_active,
    }


def _doc_line(line) -> dict:
    return {
        "item_sku": line.item.sku if line.item else None,
        "description": line.description,
        "quantity": trim(line.quantity),
        "unit_price": Minor(line.unit_price),
        "tax_rate": line.tax_rate.name if line.tax_rate else None,
        "line_subtotal": Minor(line.line_subtotal),
        "tax_amount": Minor(line.tax_amount),
    }


def invoice_summary(inv: Invoice) -> dict:
    return {
        "number": inv.number,
        "kind": "sales_invoice" if inv.kind == InvoiceKind.SALES else "vendor_bill",
        "party_id": inv.party_id,
        "party": inv.party.name,
        "invoice_date": inv.invoice_date,
        "due_date": inv.due_date,
        "status": inv.status,
        "payment_status": inv.payment_status,
        "total": Minor(inv.total),
        "amount_paid": Minor(inv.amount_paid),
        "outstanding": Minor(inv.outstanding),
        "reference": inv.reference,
    }


def invoice(inv: Invoice) -> dict:
    return {
        **invoice_summary(inv),
        "subtotal": Minor(inv.subtotal),
        "tax_total": Minor(inv.tax_total),
        "notes": inv.notes,
        "lines": [{**_doc_line(line), "account_code": line.account.code} for line in inv.lines],
    }


def payment(p: Payment) -> dict:
    return {
        "number": p.number,
        "direction": p.direction,
        "party_id": p.party_id,
        "party": p.party.name,
        "payment_date": p.payment_date,
        "amount": Minor(p.amount),
        "bank_account_code": p.bank_account.code,
        "method": p.method,
        "reference": p.reference,
        "status": p.status,
        "allocations": [{"invoice_number": a.invoice.number, "amount": Minor(a.amount)} for a in p.allocations],
        "unallocated": Minor(p.unallocated),
    }


def sales_doc(d: SalesDoc) -> dict:
    return {
        "number": d.number,
        "kind": d.kind,
        "party_id": d.party_id,
        "party": d.party.name,
        "date": d.doc_date,
        "valid_until": d.valid_until,
        "status": d.status,
        "opportunity_id": d.opportunity_id,
        "subtotal": Minor(d.subtotal),
        "tax_total": Minor(d.tax_total),
        "total": Minor(d.total),
        "notes": d.notes,
        "lines": [_doc_line(line) for line in d.lines],
    }


def lead(lead_: Lead) -> dict:
    return {
        "id": lead_.id,
        "name": lead_.name,
        "company_name": lead_.company_name,
        "email": lead_.email,
        "phone": lead_.phone,
        "source": lead_.source,
        "status": lead_.status,
        "notes": lead_.notes,
    }


def opportunity(o: Opportunity) -> dict:
    return {
        "id": o.id,
        "title": o.title,
        "party_id": o.party_id,
        "lead_id": o.lead_id,
        "customer": o.party.name if o.party else (o.lead.company_name or o.lead.name if o.lead else None),
        "stage": o.stage,
        "expected_value": Minor(o.expected_value),
        "probability_pct": o.probability_pct,
        "expected_close": o.expected_close,
        "lost_reason": o.lost_reason,
    }


def pending_action(a: PendingAction) -> dict:
    return {
        "id": a.id,
        "tool": a.tool,
        "input": a.input,
        "status": a.status,
        "requested_by": a.requested_by,
        "requested_at": a.requested_at,
        "decided_by": a.decided_by,
        "decided_at": a.decided_at,
        "reason": a.reason,
    }
