import { ArrowsLeftRight, Plus } from "@phosphor-icons/react";
import { useState } from "react";
import { useCurrency, useTool, useToolMutation } from "../../api/hooks";
import type { Party } from "../../api/types";
import { ConfirmDialog, type FieldSpec, FormDialog } from "../../design/FormDialog";
import { Button, Card, EmptyState, ErrorState, Monogram, PageHeader, Segmented, StatusBadge } from "../../design/primitives";
import { type Column, Table } from "../../design/Table";
import { formatDate, today } from "../../lib/dates";
import { formatMoney } from "../../lib/money";

type Payment = {
  number: string;
  direction: "inbound" | "outbound";
  party_id: number;
  party: string;
  payment_date: string;
  amount: string;
  method: string | null;
  reference: string | null;
  status: "posted" | "void";
  allocations: { invoice_number: string; amount: string }[];
  unallocated: string;
};

type Filter = "all" | "inbound" | "outbound";
const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "inbound", label: "Received" },
  { id: "outbound", label: "Paid out" },
];

export function Payments() {
  const currency = useCurrency();
  const [filter, setFilter] = useState<Filter>("all");
  const [recording, setRecording] = useState(false);
  const [voiding, setVoiding] = useState<Payment | null>(null);
  const list = useTool<{ payments: Payment[] }>("list_payments", {
    limit: 200,
    ...(filter === "all" ? {} : { direction: filter }),
  });
  const parties = useTool<{ parties: Party[] }>("search_parties", { limit: 200 });
  const closeRecord = () => setRecording(false);
  const closeVoid = () => setVoiding(null);
  const record = useToolMutation<Payment>("record_payment", {
    success: (payment) => `Payment ${payment.number} recorded`,
    onSuccess: closeRecord,
    onHeld: closeRecord,
  });
  const voidPayment = useToolMutation("void_payment", { success: "Payment voided", onSuccess: closeVoid, onHeld: closeVoid });

  const fields: FieldSpec[] = [
    {
      name: "direction",
      label: "Direction",
      type: "select",
      required: true,
      initial: "inbound",
      options: [
        { value: "inbound", label: "Received from a customer" },
        { value: "outbound", label: "Paid to a vendor" },
      ],
    },
    {
      name: "party_id",
      label: "Customer or vendor",
      type: "select",
      required: true,
      options: parties.data?.parties.map((party) => ({ value: String(party.id), label: party.name })),
    },
    { name: "amount", label: `Amount (${currency.code})`, type: "decimal", required: true },
    { name: "payment_date", label: "Date", type: "date", required: true, initial: today() },
    { name: "method", label: "Method", hint: "For example bank transfer or card" },
    { name: "reference", label: "Reference" },
  ];

  const columns: Column<Payment>[] = [
    { id: "number", header: "Number", cell: (row) => <span className="font-medium text-ink">{row.number}</span> },
    {
      id: "party",
      header: "Party",
      className: "min-w-44",
      cell: (row) => (
        <span className="flex items-center gap-2.5">
          <Monogram name={row.party} />
          {row.party}
        </span>
      ),
    },
    { id: "date", header: "Date", cell: (row) => <span className="whitespace-nowrap text-ink-2">{formatDate(row.payment_date)}</span> },
    { id: "direction", header: "Direction", cell: (row) => (row.direction === "inbound" ? "Received" : "Paid out") },
    {
      id: "settles",
      header: "Settles",
      cell: (row) =>
        row.allocations.length ? (
          <span className="text-ink-2">{row.allocations.map((a) => a.invoice_number).join(", ")}</span>
        ) : (
          <span className="text-ink-3">Unallocated</span>
        ),
    },
    { id: "amount", header: "Amount", numeric: true, cell: (row) => formatMoney(row.amount, currency) },
    {
      id: "status",
      header: "",
      align: "right",
      cell: (row) =>
        row.status === "void" ? (
          <StatusBadge status="void" />
        ) : (
          <Button size="sm" onClick={() => setVoiding(row)}>
            Void
          </Button>
        ),
    },
  ];

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Payments"
        description="Money received from customers and paid to vendors."
        actions={
          <Button variant="primary" trailing={Plus} onClick={() => setRecording(true)}>
            Record payment
          </Button>
        }
      />
      <Segmented label="Filter by direction" options={FILTERS} value={filter} onChange={setFilter} />
      <Card>
        {list.error ? (
          <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />
        ) : list.data?.payments.length === 0 ? (
          <EmptyState
            icon={ArrowsLeftRight}
            title="No payments here"
            body="Record a payment and it is applied to the oldest open documents first."
          />
        ) : (
          <div className="pb-2">
            <Table
              columns={columns}
              rows={list.data?.payments}
              rowKey={(row) => row.number}
              loading={list.isPending}
              stale={list.isPlaceholderData}
            />
          </div>
        )}
      </Card>
      <FormDialog
        open={recording}
        onClose={closeRecord}
        title="Record payment"
        description="The amount is applied to that party's oldest open invoices or bills first."
        fields={fields}
        submitLabel="Record payment"
        pending={record.isPending}
        onSubmit={(values) => record.mutate({ ...values, party_id: Number(values.party_id) })}
      />
      <ConfirmDialog
        open={Boolean(voiding)}
        onClose={closeVoid}
        title={`Void ${voiding?.number ?? "payment"}?`}
        description="The ledger entry is reversed and the documents it settled become outstanding again."
        confirmLabel="Void payment"
        pending={voidPayment.isPending}
        onConfirm={() => voiding && voidPayment.mutate({ payment_number: voiding.number })}
      />
    </div>
  );
}
