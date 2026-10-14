import { Kanban, Plus, UserPlus } from "@phosphor-icons/react";
import { useState } from "react";
import { useCurrency, useTool, useToolMutation } from "../../api/hooks";
import type { Party, PipelineSummary } from "../../api/types";
import { Select } from "../../design/Form";
import { type FieldSpec, FormDialog } from "../../design/FormDialog";
import { Button, Card, EmptyState, ErrorState, PageHeader, Skeleton, StatusBadge } from "../../design/primitives";
import { type Column, Table } from "../../design/Table";
import { formatDate } from "../../lib/dates";
import { formatMoney } from "../../lib/money";

type Opportunity = {
  id: number;
  title: string;
  party_id: number | null;
  lead_id: number | null;
  customer: string | null;
  stage: string;
  expected_value: string;
  probability_pct: number;
  expected_close: string | null;
  lost_reason: string | null;
};

type Lead = {
  id: number;
  name: string;
  company_name: string | null;
  email: string | null;
  phone: string | null;
  source: string | null;
  status: string;
};

const OPEN_STAGES = [
  { id: "prospecting", label: "Prospecting" },
  { id: "proposal", label: "Proposal" },
  { id: "negotiation", label: "Negotiation" },
];

export function Pipeline() {
  const currency = useCurrency();
  const [creating, setCreating] = useState(false);
  const [losing, setLosing] = useState<Opportunity | null>(null);
  const list = useTool<{ opportunities: Opportunity[] }>("list_opportunities");
  const summary = useTool<PipelineSummary>("pipeline_summary");
  const customers = useTool<{ parties: Party[] }>("search_parties", { role: "customer", limit: 200 });
  const leads = useTool<{ leads: Lead[] }>("list_leads", { limit: 200 });

  const create = useToolMutation("create_opportunity", { success: "Deal added", onSuccess: () => setCreating(false) });
  const move = useToolMutation("update_opportunity_stage", { success: "Deal updated", onSuccess: () => setLosing(null) });

  const fields: FieldSpec[] = [
    { name: "title", label: "Deal name", required: true, wide: true },
    { name: "expected_value", label: `Expected value (${currency.code})`, type: "decimal", required: true },
    { name: "expected_close", label: "Expected close", type: "date" },
    {
      name: "party_id",
      label: "Customer",
      type: "select",
      hint: "Choose a customer or a lead",
      options: customers.data?.parties.map((party) => ({ value: String(party.id), label: party.name })),
    },
    {
      name: "lead_id",
      label: "Lead",
      type: "select",
      hint: "If they are not a customer yet",
      options: leads.data?.leads.map((lead) => ({ value: String(lead.id), label: lead.company_name ?? lead.name })),
    },
    { name: "stage", label: "Stage", type: "select", required: true, initial: "prospecting", options: OPEN_STAGES.map((s) => ({ value: s.id, label: s.label })) },
  ];

  function changeStage(opportunity: Opportunity, stage: string) {
    if (stage === opportunity.stage) return;
    if (stage === "lost") return setLosing(opportunity);
    move.mutate({ opportunity_id: opportunity.id, stage });
  }

  const opportunities = list.data?.opportunities ?? [];
  const closed = opportunities.filter((o) => o.stage === "won" || o.stage === "lost");

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Pipeline"
        description={
          summary.data
            ? `${formatMoney(summary.data.open_weighted_value, currency)} weighted across ${summary.data.open_count} open ${summary.data.open_count === 1 ? "deal" : "deals"}`
            : undefined
        }
        actions={
          <Button variant="primary" trailing={Plus} onClick={() => setCreating(true)}>
            New deal
          </Button>
        }
      />
      {list.error ? (
        <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />
      ) : list.data && opportunities.length === 0 ? (
        <Card>
          <EmptyState icon={Kanban} title="No deals yet" body="Add a deal to track it from first contact to won or lost." />
        </Card>
      ) : (
        <div className="grid gap-4 lg:grid-cols-3">
          {OPEN_STAGES.map((stage) => {
            const inStage = opportunities.filter((o) => o.stage === stage.id);
            const total = summary.data?.stages.find((s) => s.stage === stage.id)?.expected_value;
            return (
              <section key={stage.id} className="rounded-[22px] bg-wash p-2 ring-1 ring-line">
                <header className="flex items-baseline justify-between px-3 pb-2 pt-2">
                  <h2 className="text-[14px] text-ink">
                    {stage.label} <span className="figures ml-1 text-ink-3">{inStage.length}</span>
                  </h2>
                  {total && <span className="figures text-[13px] text-ink-2">{formatMoney(total, currency)}</span>}
                </header>
                <ul className="space-y-2">
                  {!list.data && <Skeleton className="h-28 rounded-2xl" />}
                  {inStage.map((opportunity) => (
                    <li key={opportunity.id} className="rounded-2xl bg-surface p-4 shadow-card">
                      <p className="font-medium text-ink">{opportunity.title}</p>
                      <p className="mt-0.5 text-[13px] text-ink-2">{opportunity.customer ?? "No customer"}</p>
                      <p className="mt-3 text-[20px] leading-tight text-ink">{formatMoney(opportunity.expected_value, currency)}</p>
                      <p className="mt-0.5 text-[13px] text-ink-3">
                        {opportunity.probability_pct}% likely
                        {opportunity.expected_close ? `, closing ${formatDate(opportunity.expected_close)}` : ""}
                      </p>
                      <Select
                        aria-label={`Move ${opportunity.title}`}
                        className="mt-3"
                        value={opportunity.stage}
                        onChange={(event) => changeStage(opportunity, event.target.value)}
                      >
                        {OPEN_STAGES.map((option) => (
                          <option key={option.id} value={option.id}>
                            {option.label}
                          </option>
                        ))}
                        <option value="won">Close as won</option>
                        <option value="lost">Close as lost</option>
                      </Select>
                    </li>
                  ))}
                  {list.data && inStage.length === 0 && <li className="px-3 py-6 text-center text-[13px] text-ink-3">Nothing here</li>}
                </ul>
              </section>
            );
          })}
        </div>
      )}
      {closed.length > 0 && (
        <Card>
          <h2 className="px-5 pt-5 text-[15px] text-ink">Closed deals</h2>
          <ul className="px-5 pb-3 pt-2">
            {closed.map((opportunity) => (
              <li key={opportunity.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line py-2.5 first:border-t-0">
                <span className="min-w-0 flex-1 text-ink">
                  {opportunity.title}
                  <span className="ml-2 text-ink-3">{opportunity.customer}</span>
                </span>
                {opportunity.lost_reason && <span className="text-[13px] text-ink-2">{opportunity.lost_reason}</span>}
                <StatusBadge status={opportunity.stage} />
                <span className="figures w-28 text-right text-ink">{formatMoney(opportunity.expected_value, currency)}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <FormDialog
        open={creating}
        onClose={() => setCreating(false)}
        title="New deal"
        fields={fields}
        submitLabel="Add deal"
        pending={create.isPending}
        onSubmit={(values) =>
          create.mutate({
            ...values,
            ...(values.party_id ? { party_id: Number(values.party_id) } : {}),
            ...(values.lead_id ? { lead_id: Number(values.lead_id) } : {}),
          })
        }
      />
      <FormDialog
        open={Boolean(losing)}
        onClose={() => setLosing(null)}
        title={`Close ${losing?.title ?? "deal"} as lost`}
        description="A closed deal cannot be reopened."
        fields={[{ name: "lost_reason", label: "Why was it lost?", required: true, wide: true }]}
        submitLabel="Close as lost"
        pending={move.isPending}
        onSubmit={(values) => losing && move.mutate({ opportunity_id: losing.id, stage: "lost", ...values })}
      />
    </div>
  );
}

export function Leads() {
  const currency = useCurrency();
  const [creating, setCreating] = useState(false);
  const [qualifying, setQualifying] = useState<Lead | null>(null);
  const list = useTool<{ leads: Lead[] }>("list_leads", { limit: 200 });
  const create = useToolMutation("create_lead", { success: "Lead added", onSuccess: () => setCreating(false) });
  const open = useToolMutation("create_opportunity", { success: "Deal opened in the pipeline", onSuccess: () => setQualifying(null) });

  const columns: Column<Lead>[] = [
    { id: "name", header: "Name", cell: (row) => <span className="font-medium text-ink">{row.name}</span> },
    { id: "company", header: "Company", cell: (row) => row.company_name ?? <span className="text-ink-3">None</span> },
    { id: "source", header: "Source", cell: (row) => row.source ?? <span className="text-ink-3">None</span> },
    { id: "status", header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
    {
      id: "action",
      header: "",
      align: "right",
      cell: (row) =>
        row.status === "new" || row.status === "qualified" ? (
          <Button size="sm" variant="tint" onClick={() => setQualifying(row)}>
            Open a deal
          </Button>
        ) : null,
    },
  ];

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Leads"
        description="People who have shown interest but are not customers yet."
        actions={
          <Button variant="primary" trailing={Plus} onClick={() => setCreating(true)}>
            New lead
          </Button>
        }
      />
      <Card>
        {list.error ? (
          <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />
        ) : list.data?.leads.length === 0 ? (
          <EmptyState icon={UserPlus} title="No leads yet" body="Record a lead when someone first shows interest." />
        ) : (
          <div className="pb-2">
            <Table columns={columns} rows={list.data?.leads} rowKey={(row) => row.id} loading={list.isPending} />
          </div>
        )}
      </Card>
      <FormDialog
        open={creating}
        onClose={() => setCreating(false)}
        title="New lead"
        fields={[
          { name: "name", label: "Name", required: true },
          { name: "company_name", label: "Company" },
          { name: "email", label: "Email", type: "email" },
          { name: "phone", label: "Phone" },
          { name: "source", label: "Source", hint: "For example website or referral", wide: true },
        ]}
        submitLabel="Add lead"
        pending={create.isPending}
        onSubmit={(values) => create.mutate(values)}
      />
      <FormDialog
        open={Boolean(qualifying)}
        onClose={() => setQualifying(null)}
        title={`Open a deal for ${qualifying?.company_name ?? qualifying?.name ?? "this lead"}`}
        fields={[
          { name: "title", label: "Deal name", required: true, wide: true },
          { name: "expected_value", label: `Expected value (${currency.code})`, type: "decimal", required: true },
          { name: "expected_close", label: "Expected close", type: "date" },
        ]}
        submitLabel="Open deal"
        pending={open.isPending}
        onSubmit={(values) => qualifying && open.mutate({ ...values, lead_id: qualifying.id })}
      />
    </div>
  );
}
