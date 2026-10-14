import { ArrowRight, FileText, Plus } from "@phosphor-icons/react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { useCurrency, useTool, useToolMutation } from "../../api/hooks";
import type { DocLine, Invoice } from "../../api/types";
import { Dialog } from "../../design/Dialog";
import { Button, Card, EmptyState, ErrorState, Monogram, PageHeader, StatusBadge } from "../../design/primitives";
import { type Column, Table } from "../../design/Table";
import { formatDate } from "../../lib/dates";
import { formatMoney } from "../../lib/money";

type SalesDoc = {
  number: string;
  kind: "quotation" | "order";
  party_id: number;
  party: string;
  date: string;
  valid_until: string | null;
  status: string;
  subtotal: string;
  tax_total: string;
  total: string;
  notes: string | null;
  lines: DocLine[];
};

const KINDS = {
  quotation: {
    title: "Quotations",
    description: "Prices offered to customers. Convert one to an order when the customer accepts.",
    empty: "Create a quotation to offer a customer a price.",
  },
  order: {
    title: "Orders",
    description: "Accepted quotations waiting to be invoiced.",
    empty: "Orders appear here when a quotation is converted.",
  },
};

export function SalesDocList({ kind }: { kind: "quotation" | "order" }) {
  const config = KINDS[kind];
  const currency = useCurrency();
  const navigate = useNavigate();
  const [openNumber, setOpenNumber] = useState<string | null>(null);
  const list = useTool<{ documents: SalesDoc[] }>("list_sales_documents", { kind, limit: 200 });
  const opened = list.data?.documents.find((doc) => doc.number === openNumber);
  const close = () => setOpenNumber(null);

  const convert = useToolMutation<SalesDoc>("convert_quotation_to_order", {
    success: (order) => `Order ${order.number} created`,
    onSuccess: () => navigate("/orders"),
  });
  const invoice = useToolMutation<Invoice>("invoice_sales_order", {
    success: (draft) => `Draft invoice ${draft.number} created`,
    onSuccess: (draft) => navigate(`/invoices/${draft.number}`),
  });

  const columns: Column<SalesDoc>[] = [
    { id: "number", header: "Number", cell: (row) => <span className="font-medium text-ink">{row.number}</span> },
    {
      id: "party",
      header: "Customer",
      className: "min-w-44",
      cell: (row) => (
        <span className="flex items-center gap-2.5">
          <Monogram name={row.party} />
          {row.party}
        </span>
      ),
    },
    { id: "date", header: "Date", cell: (row) => <span className="whitespace-nowrap text-ink-2">{formatDate(row.date)}</span> },
    { id: "status", header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
    { id: "total", header: "Total", numeric: true, cell: (row) => formatMoney(row.total, currency) },
  ];

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title={config.title}
        description={config.description}
        actions={
          kind === "quotation" ? (
            <Button variant="primary" trailing={Plus} to="/quotations/new">
              New quotation
            </Button>
          ) : undefined
        }
      />
      <Card>
        {list.error ? (
          <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />
        ) : list.data?.documents.length === 0 ? (
          <EmptyState icon={FileText} title={`No ${config.title.toLowerCase()} yet`} body={config.empty} />
        ) : (
          <div className="pb-2">
            <Table
              columns={columns}
              rows={list.data?.documents}
              rowKey={(row) => row.number}
              rowLabel={(row) => `Open ${row.number}`}
              onRowClick={(row) => setOpenNumber(row.number)}
              loading={list.isPending}
            />
          </div>
        )}
      </Card>

      <Dialog
        open={Boolean(opened)}
        onClose={close}
        title={opened?.number ?? ""}
        description={opened ? `${opened.party}, dated ${formatDate(opened.date)}` : undefined}
      >
        {opened && (
          <div>
            <ul>
              {opened.lines.map((line, index) => (
                <li key={index} className="flex items-baseline gap-3 border-t border-line py-2.5 first:border-t-0">
                  <span className="min-w-0 flex-1 text-ink">{line.description}</span>
                  <span className="figures whitespace-nowrap text-[13px] text-ink-3">
                    {line.quantity} at {formatMoney(line.unit_price, currency)}
                  </span>
                  <span className="figures w-24 text-right text-ink">{formatMoney(line.line_subtotal, currency)}</span>
                </li>
              ))}
            </ul>
            <dl className="mt-2 border-t border-line pt-3">
              <div className="flex justify-between py-0.5 text-ink-2">
                <dt>Tax</dt>
                <dd className="figures">{formatMoney(opened.tax_total, currency)}</dd>
              </div>
              <div className="flex justify-between py-0.5 text-[16px] font-medium text-ink">
                <dt>Total</dt>
                <dd className="figures">{formatMoney(opened.total, currency)}</dd>
              </div>
            </dl>
            <div className="mt-5 flex items-center justify-between gap-2">
              <StatusBadge status={opened.status} />
              {kind === "quotation" && opened.status === "draft" && (
                <Button
                  variant="primary"
                  trailing={ArrowRight}
                  loading={convert.isPending}
                  onClick={() => convert.mutate({ quotation_number: opened.number })}
                >
                  Convert to order
                </Button>
              )}
              {kind === "order" && opened.status === "open" && (
                <Button
                  variant="primary"
                  trailing={ArrowRight}
                  loading={invoice.isPending}
                  onClick={() => invoice.mutate({ order_number: opened.number })}
                >
                  Create invoice
                </Button>
              )}
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
