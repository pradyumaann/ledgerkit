import { ArrowLeft, Check, CurrencyCircleDollar, Prohibit } from "@phosphor-icons/react";
import { type FormEvent, type ReactNode, useState } from "react";
import { Link, useParams } from "react-router";
import { useCurrency, useTool, useToolMutation } from "../../api/hooks";
import type { Invoice } from "../../api/types";
import { Dialog } from "../../design/Dialog";
import { Field, Input, Select } from "../../design/Form";
import { Button, Card, CardHeader, ErrorState, Skeleton, StatusBadge } from "../../design/primitives";
import { formatDate, today } from "../../lib/dates";
import { type Currency, formatMoney, isZero } from "../../lib/money";
import { type DocKind, displayStatus, KINDS } from "./kinds";

function PaymentDialog({
  invoice,
  kind,
  currency,
  open,
  onClose,
}: {
  invoice: Invoice;
  kind: DocKind;
  currency: Currency;
  open: boolean;
  onClose: () => void;
}) {
  const config = KINDS[kind];
  const [amount, setAmount] = useState(invoice.outstanding);
  const [date, setDate] = useState(today());
  const [method, setMethod] = useState("bank transfer");
  const [reference, setReference] = useState("");
  const record = useToolMutation("record_payment", { success: "Payment recorded", onSuccess: onClose, onHeld: onClose });

  function submit(event: FormEvent) {
    event.preventDefault();
    record.mutate({
      direction: config.direction,
      party_id: invoice.party_id,
      amount,
      payment_date: date,
      method,
      ...(reference ? { reference } : {}),
      allocations: [{ invoice_number: invoice.number, amount }],
    });
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={config.paymentVerb}
      description={`${formatMoney(invoice.outstanding, currency)} is outstanding on ${invoice.number}.`}
    >
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label={`Amount (${currency.code})`}>
          {(id) => (
            <Input id={id} inputMode="decimal" required value={amount} onChange={(e) => setAmount(e.target.value)} />
          )}
        </Field>
        <Field label="Date">
          {(id) => <Input id={id} type="date" required value={date} onChange={(e) => setDate(e.target.value)} />}
        </Field>
        <Field label="Method">
          {(id) => (
            <Select id={id} value={method} onChange={(e) => setMethod(e.target.value)}>
              <option value="bank transfer">Bank transfer</option>
              <option value="card">Card</option>
              <option value="cash">Cash</option>
              <option value="cheque">Cheque</option>
            </Select>
          )}
        </Field>
        <Field label="Reference" hint="Optional">
          {(id) => <Input id={id} value={reference} onChange={(e) => setReference(e.target.value)} />}
        </Field>
        <div className="mt-2 flex justify-end gap-2 sm:col-span-2">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={record.isPending}>
            Record payment
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-t border-line py-2.5 first:border-t-0">
      <dt className="text-ink-3">{label}</dt>
      <dd className="text-right text-ink">{children}</dd>
    </div>
  );
}

export function InvoiceDetail({ kind }: { kind: DocKind }) {
  const config = KINDS[kind];
  const { number = "" } = useParams();
  const currency = useCurrency();
  const query = useTool<Invoice>("get_invoice", { number });
  const [paying, setPaying] = useState(false);
  const [voiding, setVoiding] = useState(false);
  const post = useToolMutation("post_invoice", { success: `${number} posted to the books` });
  const voidInvoice = useToolMutation("void_invoice", {
    success: `${number} voided`,
    onSuccess: () => setVoiding(false),
    onHeld: () => setVoiding(false),
  });

  const back = (
    <Link to={config.base} className="inline-flex items-center gap-1.5 text-ink-2 transition-colors hover:text-ink">
      <ArrowLeft size={15} />
      {config.title}
    </Link>
  );

  if (query.error) {
    return (
      <div className="space-y-4">
        {back}
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      </div>
    );
  }
  const invoice = query.data;
  if (!invoice) {
    return (
      <div className="space-y-6">
        {back}
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-80" />
      </div>
    );
  }

  const isDraft = invoice.status === "draft";
  const canPay = invoice.status === "posted" && !isZero(invoice.outstanding);
  const canVoid = invoice.status !== "void";

  return (
    <div className="space-y-6">
      {back}
      <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-[30px] leading-tight text-ink">{invoice.number}</h1>
            <StatusBadge status={displayStatus(invoice)} />
          </div>
          <p className="mt-1 text-ink-2">
            {invoice.party}, dated {formatDate(invoice.invoice_date)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canVoid && (
            <Button icon={Prohibit} onClick={() => setVoiding(true)}>
              {isDraft ? "Discard draft" : "Void"}
            </Button>
          )}
          {isDraft && (
            <Button
              variant="primary"
              icon={Check}
              loading={post.isPending}
              onClick={() => post.mutate({ number: invoice.number })}
            >
              Post to the books
            </Button>
          )}
          {canPay && (
            <Button variant="primary" icon={CurrencyCircleDollar} onClick={() => setPaying(true)}>
              Record payment
            </Button>
          )}
        </div>
      </header>

      {isDraft && (
        <p className="rounded-2xl bg-lavender px-4 py-3 text-ink">
          This is a draft. It does not affect the books or what is owed until you post it.
        </p>
      )}

      <div className="grid items-start gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-8">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-[12.5px] text-ink-3">
                  <th scope="col" className="px-5 pb-2.5 pt-4 text-left font-normal">
                    Description
                  </th>
                  <th scope="col" className="px-3 pb-2.5 pt-4 text-right font-normal">
                    Quantity
                  </th>
                  <th scope="col" className="px-3 pb-2.5 pt-4 text-right font-normal">
                    Unit price
                  </th>
                  <th scope="col" className="px-3 pb-2.5 pt-4 text-left font-normal">
                    Tax
                  </th>
                  <th scope="col" className="px-5 pb-2.5 pt-4 text-right font-normal">
                    Amount
                  </th>
                </tr>
              </thead>
              <tbody>
                {invoice.lines.map((line, index) => (
                  <tr key={index} className="border-t border-line align-top">
                    <td className="px-5 py-3">
                      <p className="text-ink">{line.description}</p>
                      <p className="text-[12.5px] text-ink-3">
                        {[line.item_sku, `Account ${line.account_code}`].filter(Boolean).join(", ")}
                      </p>
                    </td>
                    <td className="figures px-3 py-3 text-right">{line.quantity}</td>
                    <td className="figures whitespace-nowrap px-3 py-3 text-right">
                      {formatMoney(line.unit_price, currency)}
                    </td>
                    <td className="whitespace-nowrap px-3 py-3 text-ink-2">{line.tax_rate ?? "None"}</td>
                    <td className="figures whitespace-nowrap px-5 py-3 text-right">
                      {formatMoney(line.line_subtotal, currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <dl className="ml-auto w-full max-w-xs border-t border-line px-5 py-4">
            <div className="flex justify-between py-1 text-ink-2">
              <dt>Subtotal</dt>
              <dd className="figures">{formatMoney(invoice.subtotal, currency)}</dd>
            </div>
            <div className="flex justify-between py-1 text-ink-2">
              <dt>Tax</dt>
              <dd className="figures">{formatMoney(invoice.tax_total, currency)}</dd>
            </div>
            <div className="flex justify-between py-1 text-[16px] font-medium text-ink">
              <dt>Total</dt>
              <dd className="figures">{formatMoney(invoice.total, currency)}</dd>
            </div>
            {invoice.status === "posted" && (
              <>
                <div className="flex justify-between py-1 text-ink-2">
                  <dt>Paid</dt>
                  <dd className="figures">{formatMoney(invoice.amount_paid, currency)}</dd>
                </div>
                <div className="flex justify-between py-1 text-ink">
                  <dt>Outstanding</dt>
                  <dd className="figures">{formatMoney(invoice.outstanding, currency)}</dd>
                </div>
              </>
            )}
          </dl>
          {invoice.notes && <p className="border-t border-line px-5 py-4 text-ink-2">{invoice.notes}</p>}
        </Card>

        <div className="space-y-4 lg:col-span-4">
          <Card>
            <dl className="px-5 py-3">
              <Detail label={config.party}>{invoice.party}</Detail>
              <Detail label="Date">{formatDate(invoice.invoice_date)}</Detail>
              <Detail label="Due">{formatDate(invoice.due_date)}</Detail>
              {invoice.reference && <Detail label="Reference">{invoice.reference}</Detail>}
              {invoice.journal_entry_number && <Detail label="Journal entry">{invoice.journal_entry_number}</Detail>}
            </dl>
          </Card>
          <Card>
            <CardHeader title="Payments" />
            {invoice.payments.length === 0 ? (
              <p className="px-5 pb-5 pt-2 text-ink-2">
                {invoice.status === "posted" ? "No payments recorded yet." : "Payments can be recorded once this is posted."}
              </p>
            ) : (
              <ul className="px-5 pb-3 pt-2">
                {invoice.payments.map((payment) => (
                  <li key={payment.number} className="flex items-baseline gap-3 border-t border-line py-2.5 first:border-t-0">
                    <div className="min-w-0 flex-1">
                      <p className="text-ink">{formatDate(payment.payment_date)}</p>
                      <p className="truncate text-[12.5px] text-ink-3">
                        {[payment.number, payment.method].filter(Boolean).join(", ")}
                      </p>
                    </div>
                    <span className="figures text-ink">{formatMoney(payment.amount, currency)}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>

      {paying && <PaymentDialog invoice={invoice} kind={kind} currency={currency} open onClose={() => setPaying(false)} />}

      <Dialog
        open={voiding}
        onClose={() => setVoiding(false)}
        title={isDraft ? `Discard ${invoice.number}?` : `Void ${invoice.number}?`}
        description={
          isDraft
            ? "The draft is cancelled. Nothing was posted, so the books are unaffected."
            : "The entry is reversed in the ledger and nothing remains owed. This cannot be undone."
        }
      >
        <div className="flex justify-end gap-2">
          <Button onClick={() => setVoiding(false)}>Keep it</Button>
          <Button
            variant="primary"
            loading={voidInvoice.isPending}
            onClick={() => voidInvoice.mutate({ number: invoice.number })}
          >
            {isDraft ? "Discard draft" : `Void ${config.noun}`}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
