import { ArrowLeft, MagnifyingGlass, Plus, UsersThree } from "@phosphor-icons/react";
import { useDeferredValue, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useCurrency, useTool, useToolMutation } from "../../api/hooks";
import type { InvoiceSummary, Party } from "../../api/types";
import { Input } from "../../design/Form";
import { type FieldSpec, FormDialog } from "../../design/FormDialog";
import {
  Amount,
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  Monogram,
  PageHeader,
  Skeleton,
  StatusBadge,
} from "../../design/primitives";
import { type Column, Table } from "../../design/Table";
import { formatDate } from "../../lib/dates";
import { formatMoney } from "../../lib/money";
import { displayStatus } from "../invoices/kinds";

type Role = "customer" | "vendor";

const ROLES = {
  customer: {
    base: "/customers",
    title: "Customers",
    description: "The people and businesses you sell to.",
    createTool: "create_customer",
    docs: "sales",
    docBase: "/invoices",
    docTitle: "Invoices",
  },
  vendor: {
    base: "/vendors",
    title: "Vendors",
    description: "The suppliers you buy from.",
    createTool: "create_vendor",
    docs: "purchase",
    docBase: "/bills",
    docTitle: "Bills",
  },
} as const;

const FIELDS: FieldSpec[] = [
  { name: "name", label: "Name", required: true, wide: true },
  { name: "email", label: "Email", type: "email" },
  { name: "phone", label: "Phone" },
  { name: "tax_id", label: "Tax number", hint: "Tax or VAT registration, if any" },
  { name: "address", label: "Address", type: "textarea" },
];

export function PartyList({ role }: { role: Role }) {
  const config = ROLES[role];
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const query = useDeferredValue(search.trim());
  const list = useTool<{ parties: Party[] }>("search_parties", { role, limit: 200, ...(query ? { query } : {}) });
  const create = useToolMutation<Party>(config.createTool, {
    success: (party) => `${party.name} added`,
    onSuccess: () => setCreating(false),
  });

  const columns: Column<Party>[] = [
    {
      id: "name",
      header: "Name",
      cell: (row) => (
        <span className="flex items-center gap-2.5 font-medium text-ink">
          <Monogram name={row.name} />
          {row.name}
        </span>
      ),
    },
    { id: "email", header: "Email", cell: (row) => row.email ?? <span className="text-ink-3">None</span> },
    { id: "phone", header: "Phone", cell: (row) => row.phone ?? <span className="text-ink-3">None</span> },
    { id: "tax", header: "Tax number", cell: (row) => row.tax_id ?? <span className="text-ink-3">None</span> },
  ];

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title={config.title}
        description={config.description}
        actions={
          <Button variant="primary" trailing={Plus} onClick={() => setCreating(true)}>
            New {role}
          </Button>
        }
      />
      <div className="relative max-w-sm">
        <MagnifyingGlass size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" />
        <Input
          aria-label={`Search ${config.title.toLowerCase()}`}
          placeholder="Search by name or email"
          className="pl-9"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>
      <Card>
        {list.error ? (
          <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />
        ) : list.data?.parties.length === 0 ? (
          <EmptyState
            icon={UsersThree}
            title={query ? "No matches" : `No ${config.title.toLowerCase()} yet`}
            body={query ? "Try a different name or email." : `Add your first ${role} to start creating documents for them.`}
          />
        ) : (
          <div className="pb-2">
            <Table
              columns={columns}
              rows={list.data?.parties}
              rowKey={(row) => row.id}
              rowLabel={(row) => `Open ${row.name}`}
              onRowClick={(row) => navigate(`${config.base}/${row.id}`)}
              loading={list.isPending}
              stale={list.isPlaceholderData}
            />
          </div>
        )}
      </Card>
      <FormDialog
        open={creating}
        onClose={() => setCreating(false)}
        title={`New ${role}`}
        fields={FIELDS}
        submitLabel={`Add ${role}`}
        pending={create.isPending}
        onSubmit={(values) => create.mutate(values)}
      />
    </div>
  );
}

type PartyDetails = Party & { notes: string | null; receivable: string; payable: string };

export function PartyDetail({ role }: { role: Role }) {
  const config = ROLES[role];
  const { id = "" } = useParams();
  const navigate = useNavigate();
  const currency = useCurrency();
  const party = useTool<PartyDetails>("get_party", { party_id: Number(id) });
  const documents = useTool<{ invoices: InvoiceSummary[] }>("list_invoices", {
    party_id: Number(id),
    kind: config.docs,
    limit: 100,
  });

  const back = (
    <Link to={config.base} className="inline-flex items-center gap-1.5 text-ink-2 transition-colors hover:text-ink">
      <ArrowLeft size={15} />
      {config.title}
    </Link>
  );
  if (party.error) {
    return (
      <div className="space-y-4">
        {back}
        <ErrorState message={party.error.message} onRetry={() => void party.refetch()} />
      </div>
    );
  }
  const data = party.data;
  const owed = role === "customer" ? data?.receivable : data?.payable;

  const columns: Column<InvoiceSummary>[] = [
    { id: "number", header: "Number", cell: (row) => <span className="whitespace-nowrap font-medium text-ink">{row.number}</span> },
    { id: "date", header: "Date", cell: (row) => <span className="text-ink-2">{formatDate(row.invoice_date)}</span> },
    { id: "status", header: "Status", cell: (row) => <StatusBadge status={displayStatus(row)} /> },
    { id: "total", header: "Total", numeric: true, cell: (row) => formatMoney(row.total, currency) },
    { id: "outstanding", header: "Outstanding", numeric: true, cell: (row) => formatMoney(row.outstanding, currency) },
  ];

  return (
    <div className="stagger space-y-6">
      {back}
      <PageHeader title={data?.name ?? " "} description={data?.email ?? undefined} />
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-4">
          <Card tone="lavender">
            <div className="p-5">
              <p className="text-[13px] text-ink-2">{role === "customer" ? "Owes you" : "You owe"}</p>
              {owed === undefined ? (
                <Skeleton className="mt-2 h-9 w-36" />
              ) : (
                <p className="mt-1.5 text-[30px] font-[420] leading-tight tracking-[-0.015em] text-ink">
                  <Amount value={owed} currency={currency} />
                </p>
              )}
            </div>
          </Card>
          <Card>
            <dl className="px-5 py-3">
              {[
                ["Email", data?.email],
                ["Phone", data?.phone],
                ["Tax number", data?.tax_id],
                ["Address", data?.address],
              ].map(([label, value]) => (
                <div key={label} className="flex items-baseline justify-between gap-4 border-t border-line py-2.5 first:border-t-0">
                  <dt className="text-ink-3">{label}</dt>
                  <dd className="text-right text-ink">{value ?? <span className="text-ink-3">None</span>}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </div>
        <Card className="lg:col-span-8">
          <CardHeader title={config.docTitle} />
          {documents.data?.invoices.length === 0 ? (
            <p className="px-5 pb-5 pt-2 text-ink-2">Nothing yet for this {role}.</p>
          ) : (
            <div className="pb-2">
              <Table
                columns={columns}
                rows={documents.data?.invoices}
                rowKey={(row) => row.number}
                rowLabel={(row) => `Open ${row.number}`}
                onRowClick={(row) => navigate(`${config.docBase}/${row.number}`)}
                loading={documents.isPending}
              />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
