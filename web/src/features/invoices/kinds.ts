import type { InvoiceSummary } from "../../api/types";
import { today } from "../../lib/dates";

/** Sales invoices and vendor bills share their screens; this is everything that differs. */
export type DocKind = "sales" | "purchase";
/** Quotations reuse the document form but have their own list. */
export type FormKind = DocKind | "quotation";

export const KINDS = {
  sales: {
    base: "/invoices",
    title: "Invoices",
    description: "What you have billed your customers.",
    noun: "invoice",
    party: "Customer",
    partyRole: "customer",
    partyPath: "/customers",
    createTool: "create_sales_invoice_draft",
    partyField: "customer_id",
    dateField: "invoice_date",
    direction: "inbound",
    paymentVerb: "Record payment received",
    referenceHint: "Their purchase order number, if they gave one.",
    dueField: "due_date",
    dueLabel: "Due date",
    dueHint: "Leave empty for 30 days",
  },
  purchase: {
    base: "/bills",
    title: "Bills",
    description: "What your vendors have billed you.",
    noun: "bill",
    party: "Vendor",
    partyRole: "vendor",
    partyPath: "/vendors",
    createTool: "create_vendor_bill_draft",
    partyField: "vendor_id",
    dateField: "bill_date",
    direction: "outbound",
    paymentVerb: "Record payment made",
    referenceHint: "The number printed on the vendor's bill.",
    dueField: "due_date",
    dueLabel: "Due date",
    dueHint: "Leave empty for 30 days",
  },
  quotation: {
    base: "/quotations",
    title: "Quotations",
    description: "Prices offered to customers. A quotation never touches the books.",
    noun: "quotation",
    party: "Customer",
    partyRole: "customer",
    partyPath: "/customers",
    createTool: "create_quotation",
    partyField: "customer_id",
    dateField: "quotation_date",
    direction: "inbound",
    paymentVerb: "",
    referenceHint: "",
    dueField: "valid_until",
    dueLabel: "Valid until",
    dueHint: "Optional",
  },
} as const;

/** One status for display, combining the document's state with how far it is paid. */
export function displayStatus(invoice: Pick<InvoiceSummary, "status" | "payment_status" | "due_date">): string {
  if (invoice.status !== "posted") return invoice.status;
  if (invoice.payment_status === "paid") return "paid";
  if (invoice.due_date < today()) return "overdue";
  return invoice.payment_status;
}
