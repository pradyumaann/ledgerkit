import { ArrowLeft, Notebook, Plus, Trash } from "@phosphor-icons/react";
import { type FormEvent, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { useCompany, useCurrency, useTool, useToolMutation } from "../../api/hooks";
import type { Account, TrialBalance as TrialBalanceData } from "../../api/types";
import { Dialog } from "../../design/Dialog";
import { Field, Input, Select } from "../../design/Form";
import { FormDialog } from "../../design/FormDialog";
import { Button, Card, EmptyState, ErrorState, PageHeader, Segmented, StatusBadge } from "../../design/primitives";
import { type Column, Table } from "../../design/Table";
import { formatDate, PERIOD_PRESETS, type PeriodPreset, resolvePeriod, today } from "../../lib/dates";
import { type Currency, formatMoney, fromMinor, isZero, toMinor } from "../../lib/money";

/* ----------------------------------------------------------------------------------
   Journal
---------------------------------------------------------------------------------- */

type EntrySummary = {
  number: string;
  entry_date: string;
  memo: string | null;
  status: "draft" | "posted";
  source_type: string | null;
  created_by: string | null;
  total_debit: string;
  total_credit: string;
};
type Entry = EntrySummary & {
  lines: { account_code: string; account_name: string; debit: string; credit: string; description: string | null }[];
};

type DraftLine = { key: number; account_code: string; debit: string; credit: string };

function safeMinor(value: string, decimals: number): bigint | null {
  if (value.trim() === "") return 0n;
  try {
    return toMinor(value, decimals);
  } catch {
    return null;
  }
}

function NewEntryDialog({ open, onClose, currency }: { open: boolean; onClose: () => void; currency: Currency }) {
  const accounts = useTool<{ accounts: Account[] }>("list_accounts", {}, { enabled: open });
  const nextKey = useRef(3);
  const blank = (key: number): DraftLine => ({ key, account_code: "", debit: "", credit: "" });
  const [memo, setMemo] = useState("");
  const [date, setDate] = useState(today());
  const [lines, setLines] = useState<DraftLine[]>([blank(1), blank(2)]);
  const create = useToolMutation<Entry>("create_journal_entry_draft", {
    success: (entry) => `Draft ${entry.number} created`,
    onSuccess: () => {
      setMemo("");
      setLines([blank(nextKey.current++), blank(nextKey.current++)]);
      onClose();
    },
  });

  const change = (key: number, changes: Partial<DraftLine>) =>
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...changes } : line)));

  const debits = lines.map((line) => safeMinor(line.debit, currency.decimals));
  const credits = lines.map((line) => safeMinor(line.credit, currency.decimals));
  const valid = [...debits, ...credits].every((value) => value !== null);
  const totalDebit = valid ? (debits as bigint[]).reduce((a, b) => a + b, 0n) : 0n;
  const totalCredit = valid ? (credits as bigint[]).reduce((a, b) => a + b, 0n) : 0n;
  const difference = totalDebit - totalCredit;

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate({
      memo,
      entry_date: date,
      lines: lines.map((line) => ({
        account_code: line.account_code,
        ...(line.debit.trim() ? { debit: line.debit.trim() } : {}),
        ...(line.credit.trim() ? { credit: line.credit.trim() } : {}),
      })),
    });
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New journal entry"
      description="Saved as a draft. It changes no balance until it is posted."
    >
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="What is this for?" className="sm:col-span-2">
            {(id) => <Input id={id} required value={memo} onChange={(e) => setMemo(e.target.value)} />}
          </Field>
          <Field label="Date">
            {(id) => <Input id={id} type="date" required value={date} onChange={(e) => setDate(e.target.value)} />}
          </Field>
        </div>
        <div className="space-y-2">
          <div className="grid grid-cols-[1fr_5.5rem_5.5rem_2rem] gap-2 text-[12.5px] text-ink-3">
            <span>Account</span>
            <span className="text-right">Debit</span>
            <span className="text-right">Credit</span>
            <span />
          </div>
          {lines.map((line, index) => (
            <div key={line.key} className="grid grid-cols-[1fr_5.5rem_5.5rem_2rem] items-center gap-2">
              <Select
                aria-label={`Account for line ${index + 1}`}
                required
                value={line.account_code}
                onChange={(e) => change(line.key, { account_code: e.target.value })}
              >
                <option value="" disabled>
                  Choose an account
                </option>
                {accounts.data?.accounts.map((account) => (
                  <option key={account.code} value={account.code}>
                    {account.code} {account.name}
                  </option>
                ))}
              </Select>
              <Input
                aria-label={`Debit for line ${index + 1}`}
                inputMode="decimal"
                className="figures text-right"
                value={line.debit}
                onChange={(e) => change(line.key, { debit: e.target.value, credit: e.target.value ? "" : line.credit })}
              />
              <Input
                aria-label={`Credit for line ${index + 1}`}
                inputMode="decimal"
                className="figures text-right"
                value={line.credit}
                onChange={(e) => change(line.key, { credit: e.target.value, debit: e.target.value ? "" : line.debit })}
              />
              <button
                type="button"
                aria-label={`Remove line ${index + 1}`}
                disabled={lines.length <= 2}
                onClick={() => setLines((current) => current.filter((candidate) => candidate.key !== line.key))}
                className="flex size-8 items-center justify-center rounded-full text-ink-3 transition-colors hover:bg-wash hover:text-ink disabled:opacity-40"
              >
                <Trash size={15} />
              </button>
            </div>
          ))}
          <Button size="sm" variant="tint" icon={Plus} onClick={() => setLines((current) => [...current, blank(nextKey.current++)])}>
            Add line
          </Button>
        </div>
        <p className="border-t border-line pt-3 text-ink-2" aria-live="polite">
          {!valid
            ? "Check the amounts: one of them is not a valid number."
            : difference === 0n
              ? `Balanced at ${formatMoney(fromMinor(totalDebit, currency.decimals), currency)}.`
              : `Out of balance by ${formatMoney(fromMinor(difference < 0n ? -difference : difference, currency.decimals), currency)}. It can be saved as a draft but not posted.`}
        </p>
        <div className="flex justify-end gap-2">
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="primary" loading={create.isPending} disabled={!valid}>
            Save draft
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function EntryDialog({ number, onClose, currency }: { number: string | null; onClose: () => void; currency: Currency }) {
  const entry = useTool<Entry>("get_journal_entry", { entry_number: number ?? "" }, { enabled: number !== null });
  const done = { onSuccess: onClose, onHeld: onClose };
  const post = useToolMutation("post_journal_entry", { success: `${number} posted`, ...done });
  const discard = useToolMutation("discard_journal_entry_draft", { success: `${number} discarded`, ...done });
  const reverse = useToolMutation("reverse_journal_entry", { success: `${number} reversed`, ...done });
  const data = number !== null && entry.data?.number === number ? entry.data : undefined;

  return (
    <Dialog
      open={number !== null}
      onClose={onClose}
      title={number ?? ""}
      description={data ? `${data.memo ?? "No memo"}, dated ${formatDate(data.entry_date)}` : undefined}
    >
      {entry.error && <p className="text-ink-2">{entry.error.message}</p>}
      {data && (
        <div>
          <table className="w-full">
            <thead>
              <tr className="text-[12.5px] text-ink-3">
                <th scope="col" className="pb-2 text-left font-normal">
                  Account
                </th>
                <th scope="col" className="pb-2 text-right font-normal">
                  Debit
                </th>
                <th scope="col" className="pb-2 text-right font-normal">
                  Credit
                </th>
              </tr>
            </thead>
            <tbody>
              {data.lines.map((line, index) => (
                <tr key={index} className="border-t border-line">
                  <td className="py-2 text-ink">
                    <span className="mr-2 font-mono text-[12.5px] text-ink-3">{line.account_code}</span>
                    {line.account_name}
                  </td>
                  <td className="figures py-2 text-right">{isZero(line.debit) ? "" : formatMoney(line.debit, currency)}</td>
                  <td className="figures py-2 text-right">{isZero(line.credit) ? "" : formatMoney(line.credit, currency)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-line font-medium text-ink">
                <td className="py-2">Total</td>
                <td className="figures py-2 text-right">{formatMoney(data.total_debit, currency)}</td>
                <td className="figures py-2 text-right">{formatMoney(data.total_credit, currency)}</td>
              </tr>
            </tfoot>
          </table>
          <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
            <StatusBadge status={data.status} />
            <div className="flex gap-2">
              {data.status === "draft" && (
                <>
                  <Button loading={discard.isPending} onClick={() => discard.mutate({ entry_number: data.number })}>
                    Discard
                  </Button>
                  <Button variant="primary" loading={post.isPending} onClick={() => post.mutate({ entry_number: data.number })}>
                    Post to the books
                  </Button>
                </>
              )}
              {data.status === "posted" && data.source_type === null && (
                <Button loading={reverse.isPending} onClick={() => reverse.mutate({ entry_number: data.number })}>
                  Reverse this entry
                </Button>
              )}
              {data.status === "posted" && data.source_type !== null && (
                <p className="text-[13px] text-ink-3">Created by a {data.source_type}. Void that {data.source_type} to cancel it.</p>
              )}
            </div>
          </div>
        </div>
      )}
    </Dialog>
  );
}

type JournalFilter = "all" | "manual" | "draft";
const JOURNAL_FILTERS: { id: JournalFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "manual", label: "Entered by hand" },
  { id: "draft", label: "Drafts" },
];

export function Journal() {
  const currency = useCurrency();
  const [filter, setFilter] = useState<JournalFilter>("all");
  const [creating, setCreating] = useState(false);
  const [opened, setOpened] = useState<string | null>(null);
  const list = useTool<{ entries: EntrySummary[]; truncated: boolean }>("list_journal_entries", {
    limit: 300,
    ...(filter === "manual" ? { manual_only: true } : {}),
    ...(filter === "draft" ? { status: "draft" } : {}),
  });

  const columns: Column<EntrySummary>[] = [
    { id: "number", header: "Number", cell: (row) => <span className="font-medium text-ink">{row.number}</span> },
    { id: "date", header: "Date", cell: (row) => <span className="whitespace-nowrap text-ink-2">{formatDate(row.entry_date)}</span> },
    { id: "memo", header: "Memo", className: "min-w-56", cell: (row) => row.memo },
    {
      id: "source",
      header: "Source",
      cell: (row) => <span className="text-ink-2">{row.source_type ? row.source_type[0].toUpperCase() + row.source_type.slice(1) : "Manual"}</span>,
    },
    { id: "status", header: "Status", cell: (row) => <StatusBadge status={row.status} /> },
    { id: "amount", header: "Amount", numeric: true, cell: (row) => formatMoney(row.total_debit, currency) },
  ];

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Journal"
        description="Every entry in the ledger, including those created by invoices, bills and payments."
        actions={
          <Button variant="primary" trailing={Plus} onClick={() => setCreating(true)}>
            New entry
          </Button>
        }
      />
      <Segmented label="Filter entries" options={JOURNAL_FILTERS} value={filter} onChange={setFilter} />
      <Card>
        {list.error ? (
          <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />
        ) : list.data?.entries.length === 0 ? (
          <EmptyState icon={Notebook} title="No entries here" body="Entries appear as documents are posted, or when you add one by hand." />
        ) : (
          <div className="pb-2">
            <Table
              columns={columns}
              rows={list.data?.entries}
              rowKey={(row) => row.number}
              rowLabel={(row) => `Open ${row.number}`}
              onRowClick={(row) => setOpened(row.number)}
              loading={list.isPending}
              stale={list.isPlaceholderData}
            />
            {list.data?.truncated && <p className="px-5 py-3 text-[13px] text-ink-3">Showing the most recent 300.</p>}
          </div>
        )}
      </Card>
      <NewEntryDialog open={creating} onClose={() => setCreating(false)} currency={currency} />
      <EntryDialog number={opened} onClose={() => setOpened(null)} currency={currency} />
    </div>
  );
}

/* ----------------------------------------------------------------------------------
   Chart of accounts and account ledger
---------------------------------------------------------------------------------- */

const TYPE_ORDER = ["asset", "liability", "equity", "income", "expense"];
const TYPE_LABEL: Record<string, string> = {
  asset: "Assets",
  liability: "Liabilities",
  equity: "Equity",
  income: "Income",
  expense: "Expenses",
};

export function Accounts() {
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const list = useTool<{ accounts: Account[] }>("list_accounts");
  const close = () => setCreating(false);
  const create = useToolMutation<Account>("create_account", {
    success: (account) => `Account ${account.code} added`,
    onSuccess: close,
    onHeld: close,
  });

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Accounts"
        description="The chart of accounts. Open an account to see its transactions."
        actions={
          <Button variant="primary" trailing={Plus} onClick={() => setCreating(true)}>
            New account
          </Button>
        }
      />
      {list.error && <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />}
      <div className="grid items-start gap-4 lg:grid-cols-2">
        {TYPE_ORDER.map((type) => {
          const accounts = list.data?.accounts.filter((account) => account.type === type) ?? [];
          if (list.data && accounts.length === 0) return null;
          return (
            <Card key={type}>
              <h2 className="px-5 pt-5 text-[15px] text-ink">{TYPE_LABEL[type]}</h2>
              <ul className="px-2 pb-2 pt-2">
                {accounts.map((account) => (
                  <li key={account.code}>
                    <button
                      type="button"
                      onClick={() => navigate(`/accounts/${account.code}`)}
                      className="flex w-full items-baseline gap-3 rounded-xl px-3 py-2 text-left transition-colors duration-200 hover:bg-tint"
                    >
                      <span className="w-12 font-mono text-[12.5px] text-ink-3">{account.code}</span>
                      <span className="flex-1 text-ink">{account.name}</span>
                      {account.subtype && <span className="text-[12.5px] text-ink-3">{account.subtype.replace("_", " ")}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          );
        })}
      </div>
      <FormDialog
        open={creating}
        onClose={close}
        title="New account"
        fields={[
          { name: "code", label: "Code", required: true, hint: "For example 6350" },
          { name: "name", label: "Name", required: true },
          {
            name: "type",
            label: "Type",
            type: "select",
            required: true,
            wide: true,
            options: TYPE_ORDER.map((type) => ({ value: type, label: TYPE_LABEL[type] })),
          },
        ]}
        submitLabel="Add account"
        pending={create.isPending}
        onSubmit={(values) => create.mutate(values)}
      />
    </div>
  );
}

type Ledger = {
  account: Account;
  opening_balance: string;
  closing_balance: string;
  truncated: boolean;
  lines: { date: string; entry_number: string; memo: string | null; debit: string; credit: string; balance: string }[];
};

export function AccountLedger() {
  const { code = "" } = useParams();
  const currency = useCurrency();
  const company = useCompany();
  const [preset, setPreset] = useState<PeriodPreset>("fytd");
  const fiscalStart = company.data?.fiscal_year_start_month ?? 1;
  const period = useMemo(() => resolvePeriod(preset, fiscalStart), [preset, fiscalStart]);
  const ledger = useTool<Ledger>("get_ledger", { account_code: code, limit: 500, ...period });

  const columns: Column<Ledger["lines"][number]>[] = [
    { id: "date", header: "Date", cell: (row) => <span className="whitespace-nowrap text-ink-2">{formatDate(row.date)}</span> },
    { id: "entry", header: "Entry", cell: (row) => <span className="font-medium text-ink">{row.entry_number}</span> },
    { id: "memo", header: "Memo", className: "min-w-56", cell: (row) => row.memo },
    { id: "debit", header: "Debit", numeric: true, cell: (row) => (isZero(row.debit) ? "" : formatMoney(row.debit, currency)) },
    { id: "credit", header: "Credit", numeric: true, cell: (row) => (isZero(row.credit) ? "" : formatMoney(row.credit, currency)) },
    { id: "balance", header: "Balance", numeric: true, cell: (row) => formatMoney(row.balance, currency) },
  ];

  return (
    <div className="stagger space-y-6">
      <Link to="/accounts" className="inline-flex items-center gap-1.5 text-ink-2 transition-colors hover:text-ink">
        <ArrowLeft size={15} />
        Accounts
      </Link>
      <PageHeader
        title={ledger.data ? `${ledger.data.account.code} ${ledger.data.account.name}` : code}
        description="Balances are debits less credits, so accounts that normally carry a credit balance show as negative."
        actions={<Segmented label="Period" options={PERIOD_PRESETS} value={preset} onChange={setPreset} />}
      />
      <Card>
        {ledger.error ? (
          <ErrorState message={ledger.error.message} onRetry={() => void ledger.refetch()} />
        ) : (
          <div className="pb-2">
            {ledger.data && (
              <p className="flex justify-between border-b border-line px-5 py-3 text-ink-2">
                Opening balance <span className="figures text-ink">{formatMoney(ledger.data.opening_balance, currency)}</span>
              </p>
            )}
            <Table
              columns={columns}
              rows={ledger.data?.lines}
              rowKey={(row) => `${row.entry_number}-${row.balance}-${row.debit}-${row.credit}`}
              loading={ledger.isPending}
              stale={ledger.isPlaceholderData}
            />
            {ledger.data && (
              <p className="flex justify-between border-t border-line px-5 py-3 font-medium text-ink">
                {ledger.data.truncated ? "Balance after the lines shown" : "Closing balance"}
                <span className="figures">{formatMoney(ledger.data.closing_balance, currency)}</span>
              </p>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}

/* ----------------------------------------------------------------------------------
   Trial balance
---------------------------------------------------------------------------------- */

type TrialRow = TrialBalanceData["accounts"][number];

export function TrialBalance() {
  const currency = useCurrency();
  const [asOf, setAsOf] = useState(today());
  const report = useTool<TrialBalanceData & { total_debit: string; total_credit: string }>("trial_balance", { as_of: asOf });

  const columns: Column<TrialRow>[] = [
    { id: "code", header: "Code", cell: (row) => <span className="font-mono text-[12.5px] text-ink-3">{row.code}</span> },
    { id: "name", header: "Account", cell: (row) => <span className="text-ink">{row.name}</span> },
    { id: "type", header: "Type", cell: (row) => <span className="text-ink-2">{TYPE_LABEL[row.type]}</span> },
    { id: "debit", header: "Debit", numeric: true, cell: (row) => (isZero(row.debit) ? "" : formatMoney(row.debit, currency)) },
    { id: "credit", header: "Credit", numeric: true, cell: (row) => (isZero(row.credit) ? "" : formatMoney(row.credit, currency)) },
  ];

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Trial balance"
        description="The net balance of every account. Total debits always equal total credits."
        actions={
          <div className="flex items-center gap-3">
            {report.data && <StatusBadge status={report.data.balanced ? "balanced" : "unbalanced"} />}
            <Input aria-label="As of" type="date" className="w-40" value={asOf} onChange={(e) => e.target.value && setAsOf(e.target.value)} />
          </div>
        }
      />
      <Card>
        {report.error ? (
          <ErrorState message={report.error.message} onRetry={() => void report.refetch()} />
        ) : (
          <div className="pb-2">
            <Table
              columns={columns}
              rows={report.data?.accounts}
              rowKey={(row) => row.code}
              loading={report.isPending}
              stale={report.isPlaceholderData}
              footer={
                report.data && (
                  <tr className="border-t border-line font-medium text-ink">
                    <td className="px-5 py-3" colSpan={3}>
                      Total
                    </td>
                    <td className="figures px-5 py-3 text-right">{formatMoney(report.data.total_debit, currency)}</td>
                    <td className="figures px-5 py-3 text-right">{formatMoney(report.data.total_credit, currency)}</td>
                  </tr>
                )
              }
            />
          </div>
        )}
      </Card>
    </div>
  );
}
