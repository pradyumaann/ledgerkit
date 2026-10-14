import { Invoice as InvoiceIcon, Plus } from "@phosphor-icons/react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { useCurrency, useTool } from "../../api/hooks";
import type { InvoiceSummary } from "../../api/types";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  Monogram,
  PageHeader,
  Segmented,
  StatusBadge,
} from "../../design/primitives";
import { type Column, Table } from "../../design/Table";
import { formatDate } from "../../lib/dates";
import { formatMoney, isZero } from "../../lib/money";
import { type DocKind, displayStatus, KINDS } from "./kinds";

type Filter = "all" | "draft" | "open" | "overdue" | "paid";

const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "draft", label: "Drafts" },
  { id: "open", label: "Awaiting payment" },
  { id: "overdue", label: "Overdue" },
  { id: "paid", label: "Paid" },
];

function matches(invoice: InvoiceSummary, filter: Filter): boolean {
  const status = displayStatus(invoice);
  switch (filter) {
    case "all":
      return true;
    case "draft":
      return status === "draft";
    case "open":
      return status === "unpaid" || status === "partial" || status === "overdue";
    case "overdue":
      return status === "overdue";
    case "paid":
      return status === "paid";
  }
}

const PAGE_LIMIT = 300;

export function InvoiceList({ kind }: { kind: DocKind }) {
  const config = KINDS[kind];
  const currency = useCurrency();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>("all");
  const list = useTool<{ invoices: InvoiceSummary[]; truncated: boolean }>("list_invoices", { kind, limit: PAGE_LIMIT });

  const rows = list.data?.invoices.filter((invoice) => matches(invoice, filter));

  const columns: Column<InvoiceSummary>[] = [
    { id: "number", header: "Number", cell: (row) => <span className="whitespace-nowrap font-medium text-ink">{row.number}</span> },
    {
      id: "party",
      header: config.party,
      className: "min-w-44",
      cell: (row) => (
        <span className="flex items-center gap-2.5">
          <Monogram name={row.party} />
          {row.party}
        </span>
      ),
    },
    { id: "date", header: "Date", cell: (row) => <span className="whitespace-nowrap text-ink-2">{formatDate(row.invoice_date)}</span> },
    { id: "due", header: "Due", cell: (row) => <span className="whitespace-nowrap text-ink-2">{formatDate(row.due_date)}</span> },
    { id: "status", header: "Status", cell: (row) => <StatusBadge status={displayStatus(row)} /> },
    { id: "total", header: "Total", numeric: true, cell: (row) => formatMoney(row.total, currency) },
    {
      id: "outstanding",
      header: "Outstanding",
      numeric: true,
      cell: (row) =>
        row.status === "posted" && !isZero(row.outstanding) ? (
          formatMoney(row.outstanding, currency)
        ) : (
          <span className="text-ink-3">None</span>
        ),
    },
  ];

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title={config.title}
        description={config.description}
        actions={
          <Button variant="primary" trailing={Plus} to={`${config.base}/new`}>
            New {config.noun}
          </Button>
        }
      />
      <Segmented label="Filter by status" options={FILTERS} value={filter} onChange={setFilter} />
      <Card>
        {list.error ? (
          <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />
        ) : rows && rows.length === 0 ? (
          <EmptyState
            icon={InvoiceIcon}
            title={filter === "all" ? `No ${config.noun}s yet` : `No ${config.noun}s match this filter`}
            body={
              filter === "all"
                ? `Create a draft, check it, then post it to the books.`
                : "Choose another filter to see the rest."
            }
            action={
              filter === "all" ? (
                <Button variant="tint" icon={Plus} to={`${config.base}/new`}>
                  New {config.noun}
                </Button>
              ) : undefined
            }
          />
        ) : (
          <div className="pb-2">
            <Table
              columns={columns}
              rows={rows}
              rowKey={(row) => row.number}
              rowLabel={(row) => `Open ${row.number}`}
              onRowClick={(row) => navigate(`${config.base}/${row.number}`)}
              loading={list.isPending}
              stale={list.isPlaceholderData}
            />
            {list.data?.truncated && (
              <p className="px-5 py-3 text-[13px] text-ink-3">Showing the most recent {PAGE_LIMIT}.</p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
