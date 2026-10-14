import { ClockCounterClockwise, SealCheck } from "@phosphor-icons/react";
import { type FormEvent, useState } from "react";
import { useCompany, useTool, useToolMutation } from "../../api/hooks";
import type { PendingAction } from "../../api/types";
import { useSession } from "../../app/session";
import { Dialog } from "../../design/Dialog";
import { Field, Input } from "../../design/Form";
import { FormDialog } from "../../design/FormDialog";
import { Button, Card, CardHeader, EmptyState, ErrorState, Json, PageHeader, Segmented, Skeleton, StatusBadge } from "../../design/primitives";
import { type Column, Table } from "../../design/Table";
import { formatDate } from "../../lib/dates";

const timeFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const formatTime = (iso: string) => timeFormat.format(new Date(iso));

/** "post_invoice" -> "Post invoice" */
const toolLabel = (tool: string) => tool[0].toUpperCase() + tool.slice(1).replaceAll("_", " ");

/* ----------------------------------------------------------------------------------
   Approvals
---------------------------------------------------------------------------------- */

type ApprovalFilter = "pending" | "approved" | "rejected";
const APPROVAL_FILTERS: { id: ApprovalFilter; label: string }[] = [
  { id: "pending", label: "Waiting" },
  { id: "approved", label: "Approved" },
  { id: "rejected", label: "Rejected" },
];

export function Approvals() {
  const { actAs } = useSession();
  const [filter, setFilter] = useState<ApprovalFilter>("pending");
  const [rejecting, setRejecting] = useState<PendingAction | null>(null);
  const list = useTool<{ actions: PendingAction[] }>("list_pending_approvals", { status: filter, limit: 100 });
  const approve = useToolMutation("approve_action", { success: "Approved and run" });
  const reject = useToolMutation("reject_action", { success: "Rejected", onSuccess: () => setRejecting(null) });

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Approvals"
        description="Actions an agent asked for that change the books. Nothing here runs until a person approves it."
      />
      <Segmented label="Filter approvals" options={APPROVAL_FILTERS} value={filter} onChange={setFilter} />
      {actAs === "agent" && filter === "pending" && (
        <p className="rounded-2xl bg-lavender px-4 py-3 text-ink">
          You are acting as an agent, so you can see these but not decide them. Switch back to yourself to approve or reject.
        </p>
      )}
      {list.error ? (
        <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />
      ) : !list.data ? (
        <Skeleton className="h-40 rounded-[22px]" />
      ) : list.data.actions.length === 0 ? (
        <Card>
          <EmptyState
            icon={SealCheck}
            title={filter === "pending" ? "Nothing is waiting" : "Nothing here yet"}
            body={
              filter === "pending"
                ? "When an agent asks to post, pay or void something, it appears here for your decision."
                : "Decisions you make are kept here."
            }
          />
        </Card>
      ) : (
        <ul className="space-y-4">
          {list.data.actions.map((action) => (
            <li key={action.id}>
              <Card>
                <div className="p-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-[16px] text-ink">{toolLabel(action.tool)}</h2>
                      <p className="mt-0.5 text-[13px] text-ink-3">
                        Requested by {action.requested_by} on {formatTime(action.requested_at)}
                      </p>
                    </div>
                    {action.status === "pending" ? (
                      <div className="flex gap-2">
                        <Button disabled={actAs === "agent"} onClick={() => setRejecting(action)}>
                          Reject
                        </Button>
                        <Button
                          variant="tint"
                          disabled={actAs === "agent"}
                          loading={approve.isPending && approve.variables && "action_id" in approve.variables && approve.variables.action_id === action.id}
                          onClick={() => approve.mutate({ action_id: action.id })}
                        >
                          Approve and run
                        </Button>
                      </div>
                    ) : (
                      <StatusBadge status={action.status} />
                    )}
                  </div>
                  <p className="mb-1.5 mt-4 text-[13px] text-ink-3">Exactly what would run</p>
                  <Json value={action.input} />
                  {action.decided_by && (
                    <p className="mt-3 text-[13px] text-ink-2">
                      {action.status === "approved" ? "Approved" : "Rejected"} by {action.decided_by}
                      {action.decided_at ? ` on ${formatTime(action.decided_at)}` : ""}
                      {action.reason ? `. Reason: ${action.reason}` : ""}
                    </p>
                  )}
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}
      <FormDialog
        open={Boolean(rejecting)}
        onClose={() => setRejecting(null)}
        title="Reject this action?"
        description="It will never run. The agent can ask again with a corrected request."
        fields={[{ name: "reason", label: "Reason", wide: true, hint: "Optional, but it helps the agent correct course" }]}
        submitLabel="Reject"
        pending={reject.isPending}
        onSubmit={(values) => rejecting && reject.mutate({ action_id: rejecting.id, ...values })}
      />
    </div>
  );
}

/* ----------------------------------------------------------------------------------
   Audit log
---------------------------------------------------------------------------------- */

type AuditEntry = { id: number; at: string; actor: string; tool: string; status: string; input: unknown; result: unknown };
type AuditFilter = "all" | "agent" | "error" | "pending_approval";
const AUDIT_FILTERS: { id: AuditFilter; label: string }[] = [
  { id: "all", label: "Everything" },
  { id: "agent", label: "By agents" },
  { id: "error", label: "Refused" },
  { id: "pending_approval", label: "Held for approval" },
];

export function AuditLog() {
  const [filter, setFilter] = useState<AuditFilter>("all");
  const [opened, setOpened] = useState<AuditEntry | null>(null);
  const list = useTool<{ entries: AuditEntry[]; truncated: boolean }>("list_audit_log", {
    limit: 200,
    ...(filter === "agent" ? { actor_type: "agent" } : {}),
    ...(filter === "error" || filter === "pending_approval" ? { status: filter } : {}),
  });

  const columns: Column<AuditEntry>[] = [
    { id: "at", header: "When", cell: (row) => <span className="whitespace-nowrap text-ink-2">{formatTime(row.at)}</span> },
    { id: "actor", header: "Who", cell: (row) => row.actor },
    { id: "tool", header: "Action", cell: (row) => <span className="font-medium text-ink">{toolLabel(row.tool)}</span> },
    { id: "status", header: "Outcome", cell: (row) => <StatusBadge status={row.status} /> },
  ];

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Audit log"
        description="Every call that changed or tried to change the books, with who made it and what they sent."
      />
      <Segmented label="Filter the log" options={AUDIT_FILTERS} value={filter} onChange={setFilter} />
      <Card>
        {list.error ? (
          <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />
        ) : list.data?.entries.length === 0 ? (
          <EmptyState icon={ClockCounterClockwise} title="Nothing recorded" body="Changes appear here as soon as they are made." />
        ) : (
          <div className="pb-2">
            <Table
              columns={columns}
              rows={list.data?.entries}
              rowKey={(row) => row.id}
              rowLabel={(row) => `Open ${toolLabel(row.tool)}`}
              onRowClick={setOpened}
              loading={list.isPending}
              stale={list.isPlaceholderData}
            />
            {list.data?.truncated && <p className="px-5 py-3 text-[13px] text-ink-3">Showing the most recent 200.</p>}
          </div>
        )}
      </Card>
      <Dialog
        open={Boolean(opened)}
        onClose={() => setOpened(null)}
        title={opened ? toolLabel(opened.tool) : ""}
        description={opened ? `${opened.actor} on ${formatTime(opened.at)}` : undefined}
      >
        {opened && (
          <div className="space-y-4">
            <StatusBadge status={opened.status} />
            <div>
              <p className="mb-1.5 text-[13px] text-ink-3">Input</p>
              <Json value={opened.input} className="max-h-56" />
            </div>
            <div>
              <p className="mb-1.5 text-[13px] text-ink-3">Result</p>
              <Json value={opened.result} className="max-h-56" />
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}

/* ----------------------------------------------------------------------------------
   Settings
---------------------------------------------------------------------------------- */

export function Settings() {
  const company = useCompany();
  const [lockDate, setLockDate] = useState("");
  const setLock = useToolMutation<{ lock_date: string | null }>("set_lock_date", {
    success: (result) => (result.lock_date ? `Books locked up to ${formatDate(result.lock_date)}` : "Lock removed"),
    onSuccess: () => setLockDate(""),
  });
  const data = company.data;
  const monthName = (month: number) => new Intl.DateTimeFormat(undefined, { month: "long" }).format(new Date(2026, month - 1, 1));

  function submit(event: FormEvent) {
    event.preventDefault();
    if (lockDate) setLock.mutate({ lock_date: lockDate });
  }

  return (
    <div className="stagger space-y-6">
      <PageHeader title="Settings" />
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Company" hint="Set when the database was created with ledgerkit init" />
          {data ? (
            <dl className="px-5 pb-3 pt-2">
              {[
                ["Name", data.name],
                ["Base currency", data.base_currency],
                ["Decimal places", String(data.currency_decimals)],
                ["Fiscal year starts", monthName(data.fiscal_year_start_month)],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4 border-t border-line py-2.5 first:border-t-0">
                  <dt className="text-ink-3">{label}</dt>
                  <dd className="text-ink">{value}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <Skeleton className="m-5 h-32" />
          )}
        </Card>
        <Card>
          <CardHeader
            title="Lock date"
            hint="After a period is reviewed, lock it so nothing can be posted, voided or reversed in it."
          />
          <div className="px-5 pb-5 pt-4">
            <p className="text-ink">
              {data?.lock_date ? `The books are locked up to and including ${formatDate(data.lock_date)}.` : "The books are not locked."}
            </p>
            <form onSubmit={submit} className="mt-4 flex flex-wrap items-end gap-2">
              <Field label="Lock up to and including" className="w-48">
                {(id) => <Input id={id} type="date" required value={lockDate} onChange={(e) => setLockDate(e.target.value)} />}
              </Field>
              <Button type="submit" variant="primary" loading={setLock.isPending}>
                Lock
              </Button>
              {data?.lock_date && (
                <Button loading={setLock.isPending} onClick={() => setLock.mutate({ lock_date: null })}>
                  Remove lock
                </Button>
              )}
            </form>
          </div>
        </Card>
      </div>
    </div>
  );
}
