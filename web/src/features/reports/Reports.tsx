import { type ReactNode, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { useCompany, useCurrency, useTool } from "../../api/hooks";
import type {
  AccountRow,
  Aging,
  AgingBucket,
  CustomerMargin,
  MarginReport,
  MarginRow,
  PeriodComparison,
  ProfitAndLoss,
  Section,
} from "../../api/types";
import { Input } from "../../design/Form";
import { Amount, Card, cx, ErrorState, PageHeader, Segmented, Skeleton, StatusBadge } from "../../design/primitives";
import { type Column, Table } from "../../design/Table";
import { formatDate, type Period, PERIOD_PRESETS, type PeriodPreset, resolvePeriod, today } from "../../lib/dates";
import { type Currency, formatMoney, formatPercent, isZero } from "../../lib/money";

const REPORTS = [
  { id: "profit-and-loss", label: "Profit and loss", dated: "period" },
  { id: "balance-sheet", label: "Balance sheet", dated: "as-of" },
  { id: "items", label: "Margin by item", dated: "period" },
  { id: "customers", label: "Margin by customer", dated: "period" },
  { id: "expenses", label: "Expenses", dated: "period" },
  { id: "break-even", label: "Break-even", dated: "period" },
  { id: "comparison", label: "Comparison", dated: "period" },
  { id: "receivables", label: "Receivables", dated: "as-of" },
  { id: "payables", label: "Payables", dated: "as-of" },
] as const;

type ReportId = (typeof REPORTS)[number]["id"];

/** Wraps a report query with the shared loading and error states. */
function Loaded<T>({
  query,
  children,
}: {
  query: { data: T | undefined; error: { message: string } | null; isPlaceholderData: boolean; refetch: () => unknown };
  children: (data: T) => ReactNode;
}) {
  if (query.error) return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  if (!query.data) return <Skeleton className="m-5 h-64" />;
  return <div className={cx("transition-opacity duration-300", query.isPlaceholderData && "opacity-60")}>{children(query.data)}</div>;
}

/* ---------------------------------------------------------------- statements */

function StatementSection({ title, section, currency }: { title: string; section: Section; currency: Currency }) {
  return (
    <>
      <tr>
        <th scope="colgroup" colSpan={2} className="px-5 pb-1 pt-5 text-left text-[13px] font-normal text-ink-3">
          {title}
        </th>
      </tr>
      {section.accounts.map((row: AccountRow) => (
        <tr key={`${row.code}-${row.name}`}>
          <td className="px-5 py-1.5 text-ink">
            {row.code && <span className="mr-2 font-mono text-[12.5px] text-ink-3">{row.code}</span>}
            {row.name}
          </td>
          <td className="figures px-5 py-1.5 text-right">{formatMoney(row.amount, currency)}</td>
        </tr>
      ))}
      <tr className="border-t border-line">
        <td className="px-5 py-2 text-ink-2">Total {title.toLowerCase()}</td>
        <td className="figures px-5 py-2 text-right text-ink">{formatMoney(section.total, currency)}</td>
      </tr>
    </>
  );
}

function ResultRow({ label, amount, note, currency }: { label: string; amount: string; note?: string; currency: Currency }) {
  return (
    <tr className="border-y border-line bg-tint">
      <td className="px-5 py-3 font-medium text-ink">
        {label}
        {note && <span className="ml-3 font-normal text-ink-2">{note}</span>}
      </td>
      <td className="figures px-5 py-3 text-right font-medium text-ink">{formatMoney(amount, currency)}</td>
    </tr>
  );
}

function ProfitAndLossReport({ period, currency }: { period: Period; currency: Currency }) {
  const query = useTool<ProfitAndLoss>("profit_and_loss", period);
  return (
    <Loaded query={query}>
      {(pl) => (
        <table className="w-full">
          <tbody>
            <StatementSection title="Revenue" section={pl.revenue} currency={currency} />
            <StatementSection title="Cost of goods sold" section={pl.cost_of_goods_sold} currency={currency} />
            <ResultRow label="Gross profit" amount={pl.gross_profit} note={`${formatPercent(pl.gross_margin_pct)} margin`} currency={currency} />
            <StatementSection title="Operating expenses" section={pl.operating_expenses} currency={currency} />
            <ResultRow label="Net profit" amount={pl.net_profit} note={`${formatPercent(pl.net_margin_pct)} margin`} currency={currency} />
          </tbody>
        </table>
      )}
    </Loaded>
  );
}

type BalanceSheet = {
  assets: Section;
  liabilities: Section;
  equity: Section;
  total_liabilities_and_equity: string;
  balanced: boolean;
};

function BalanceSheetReport({ asOf, currency }: { asOf: string; currency: Currency }) {
  const query = useTool<BalanceSheet>("balance_sheet", { as_of: asOf });
  return (
    <Loaded query={query}>
      {(sheet) => (
        <>
          <table className="w-full">
            <tbody>
              <StatementSection title="Assets" section={sheet.assets} currency={currency} />
              <ResultRow label="Total assets" amount={sheet.assets.total} currency={currency} />
              <StatementSection title="Liabilities" section={sheet.liabilities} currency={currency} />
              <StatementSection title="Equity" section={sheet.equity} currency={currency} />
              <ResultRow label="Total liabilities and equity" amount={sheet.total_liabilities_and_equity} currency={currency} />
            </tbody>
          </table>
          <div className="px-5 py-4">
            <StatusBadge status={sheet.balanced ? "balanced" : "unbalanced"} />
          </div>
        </>
      )}
    </Loaded>
  );
}

/* ---------------------------------------------------------------- margins */

type ItemMargin = MarginRow & { sku: string | null; name: string; kind: string | null; quantity: string };

function MarginBar({ value, best }: { value: string; best: number }) {
  const share = best > 0 ? Math.max((Number(value) / best) * 100, 0) : 0;
  return <div aria-hidden className="h-1.5 rounded-full bg-[var(--series-1)]" style={{ width: `${Math.max(share, 1.5)}%` }} />;
}

function MarginReportView<Row extends MarginRow & { name: string }>({
  tool,
  period,
  currency,
  first,
  rowKey,
}: {
  tool: string;
  period: Period;
  currency: Currency;
  first: Column<Row>[];
  rowKey: (row: Row) => string | number;
}) {
  const query = useTool<MarginReport<Row>>(tool, period);
  const best = Math.max(...(query.data?.rows.map((row) => Number(row.gross_margin)) ?? []), 0);
  const columns: Column<Row>[] = [
    ...first,
    { id: "revenue", header: "Revenue", numeric: true, cell: (row) => formatMoney(row.revenue, currency) },
    { id: "cost", header: "Cost", numeric: true, cell: (row) => formatMoney(row.cost, currency) },
    { id: "margin", header: "Gross margin", numeric: true, cell: (row) => formatMoney(row.gross_margin, currency) },
    { id: "pct", header: "Margin %", numeric: true, cell: (row) => formatPercent(row.gross_margin_pct) },
    { id: "share", header: "Share of revenue", numeric: true, cell: (row) => formatPercent(row.share_of_revenue_pct) },
    { id: "bar", header: "", className: "w-40", cell: (row) => <MarginBar value={row.gross_margin} best={best} /> },
  ];
  return (
    <Loaded query={query}>
      {(report) =>
        report.rows.length === 0 ? (
          <p className="p-5 text-ink-2">No posted sales in this period.</p>
        ) : (
          <Table
            columns={columns}
            rows={report.rows}
            rowKey={rowKey}
            footer={
              <tr className="border-t border-line font-medium text-ink">
                <td className="px-5 py-3" colSpan={first.length}>
                  Total
                </td>
                <td className="figures px-5 py-3 text-right">{formatMoney(report.total_revenue, currency)}</td>
                <td className="figures px-5 py-3 text-right">{formatMoney(report.total_cost, currency)}</td>
                <td className="figures px-5 py-3 text-right">{formatMoney(report.total_gross_margin, currency)}</td>
                <td className="figures px-5 py-3 text-right">{formatPercent(report.gross_margin_pct)}</td>
                <td colSpan={2} />
              </tr>
            }
          />
        )
      }
    </Loaded>
  );
}

/* ---------------------------------------------------------------- expenses, break-even, comparison */

type Expenses = {
  expenses: (AccountRow & { category: string; share_of_expenses_pct: string | null; pct_of_revenue: string | null })[];
  total_expenses: string;
};

function ExpensesReport({ period, currency }: { period: Period; currency: Currency }) {
  const query = useTool<Expenses>("expense_breakdown", period);
  const columns: Column<Expenses["expenses"][number]>[] = [
    {
      id: "name",
      header: "Account",
      cell: (row) => (
        <span className="text-ink">
          <span className="mr-2 font-mono text-[12.5px] text-ink-3">{row.code}</span>
          {row.name}
        </span>
      ),
    },
    { id: "category", header: "Kind", cell: (row) => <span className="text-ink-2">{row.category === "operating" ? "Operating" : "Cost of goods sold"}</span> },
    { id: "amount", header: "Amount", numeric: true, cell: (row) => formatMoney(row.amount, currency) },
    { id: "share", header: "Share of expenses", numeric: true, cell: (row) => formatPercent(row.share_of_expenses_pct) },
    { id: "revenue", header: "Of revenue", numeric: true, cell: (row) => formatPercent(row.pct_of_revenue) },
  ];
  return (
    <Loaded query={query}>
      {(report) => (
        <Table
          columns={columns}
          rows={report.expenses}
          rowKey={(row) => `${row.code}`}
          footer={
            <tr className="border-t border-line font-medium text-ink">
              <td className="px-5 py-3" colSpan={2}>
                Total
              </td>
              <td className="figures px-5 py-3 text-right">{formatMoney(report.total_expenses, currency)}</td>
              <td colSpan={2} />
            </tr>
          }
        />
      )}
    </Loaded>
  );
}

type BreakEven = {
  revenue: string;
  variable_costs: string;
  contribution_margin: string;
  contribution_margin_pct: string | null;
  fixed_costs: string;
  break_even_revenue: string | null;
  margin_of_safety: string | null;
  margin_of_safety_pct: string | null;
  net_profit: string;
  assumptions: string;
};

function BreakEvenReport({ period, currency }: { period: Period; currency: Currency }) {
  const query = useTool<BreakEven>("break_even", period);
  return (
    <Loaded query={query}>
      {(report) => (
        <div className="p-6">
          <p className="text-[13px] text-ink-3">Revenue needed to break even</p>
          <p className="mt-2 text-[44px] font-[380] leading-none tracking-[-0.02em] text-ink">
            {report.break_even_revenue === null ? "Not reachable" : <Amount value={report.break_even_revenue} currency={currency} />}
          </p>
          <p className="mt-3 max-w-[65ch] text-ink-2">
            {report.break_even_revenue === null
              ? "There is no revenue in this period, or each sale does not cover its own cost."
              : report.margin_of_safety && !report.margin_of_safety.startsWith("-")
                ? `Revenue was ${formatMoney(report.margin_of_safety, currency)} above this point, a ${formatPercent(report.margin_of_safety_pct)} margin of safety.`
                : `Revenue fell ${formatMoney((report.margin_of_safety ?? "0").replace("-", ""), currency)} short of this point.`}
          </p>
          <dl className="mt-6 grid gap-x-8 sm:grid-cols-2">
            {[
              ["Revenue", formatMoney(report.revenue, currency)],
              ["Variable costs", formatMoney(report.variable_costs, currency)],
              ["Contribution margin", `${formatMoney(report.contribution_margin, currency)} (${formatPercent(report.contribution_margin_pct)})`],
              ["Fixed costs", formatMoney(report.fixed_costs, currency)],
              ["Net profit", formatMoney(report.net_profit, currency)],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between gap-4 border-t border-line py-2.5">
                <dt className="text-ink-2">{label}</dt>
                <dd className="figures text-ink">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-5 max-w-[75ch] text-[13px] text-ink-3">{report.assumptions}</p>
        </div>
      )}
    </Loaded>
  );
}

function ComparisonReport({ period, currency }: { period: Period; currency: Currency }) {
  const query = useTool<PeriodComparison & { current_period: { from: string; to: string } }>("period_comparison", period);
  const rows = [
    ["Revenue", "revenue"],
    ["Cost of goods sold", "cost_of_goods_sold"],
    ["Gross profit", "gross_profit"],
    ["Operating expenses", "operating_expenses"],
    ["Net profit", "net_profit"],
  ] as const;
  return (
    <Loaded query={query}>
      {(report) => (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-[12.5px] text-ink-3">
                <th scope="col" className="px-5 pb-2.5 pt-4 text-left font-normal" />
                <th scope="col" className="px-5 pb-2.5 pt-4 text-right font-normal">
                  {formatDate(report.current_period.from)} to {formatDate(report.current_period.to)}
                </th>
                <th scope="col" className="px-5 pb-2.5 pt-4 text-right font-normal">
                  {formatDate(report.previous_period.from)} to {formatDate(report.previous_period.to)}
                </th>
                <th scope="col" className="px-5 pb-2.5 pt-4 text-right font-normal">
                  Change
                </th>
                <th scope="col" className="px-5 pb-2.5 pt-4 text-right font-normal">
                  Change %
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([label, key]) => (
                <tr key={key} className="border-t border-line">
                  <th scope="row" className="px-5 py-3 text-left font-normal text-ink">
                    {label}
                  </th>
                  <td className="figures px-5 py-3 text-right">{formatMoney(report[key].current, currency)}</td>
                  <td className="figures px-5 py-3 text-right text-ink-2">{formatMoney(report[key].previous, currency)}</td>
                  <td className="figures px-5 py-3 text-right">{formatMoney(report[key].change, currency)}</td>
                  <td className="figures px-5 py-3 text-right">{formatPercent(report[key].change_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Loaded>
  );
}

/* ---------------------------------------------------------------- aging */

const BUCKETS: { id: AgingBucket; label: string }[] = [
  { id: "current", label: "Not yet due" },
  { id: "1_30", label: "1 to 30" },
  { id: "31_60", label: "31 to 60" },
  { id: "61_90", label: "61 to 90" },
  { id: "over_90", label: "Over 90" },
];

function AgingReport({ tool, asOf, currency }: { tool: string; asOf: string; currency: Currency }) {
  const query = useTool<Aging>(tool, { as_of: asOf });
  const columns: Column<Aging["by_party"][number]>[] = [
    { id: "name", header: "Name", cell: (row) => <span className="text-ink">{row.name}</span> },
    ...BUCKETS.map(
      (bucket): Column<Aging["by_party"][number]> => ({
        id: bucket.id,
        header: bucket.label,
        numeric: true,
        cell: (row) => (isZero(row[bucket.id]) ? "" : formatMoney(row[bucket.id], currency)),
      }),
    ),
    { id: "total", header: "Total", numeric: true, cell: (row) => <span className="font-medium text-ink">{formatMoney(row.total, currency)}</span> },
  ];
  return (
    <Loaded query={query}>
      {(report) =>
        report.by_party.length === 0 ? (
          <p className="p-5 text-ink-2">Nothing is outstanding.</p>
        ) : (
          <Table
            columns={columns}
            rows={report.by_party}
            rowKey={(row) => row.party_id}
            footer={
              <tr className="border-t border-line font-medium text-ink">
                <td className="px-5 py-3">Total</td>
                {BUCKETS.map((bucket) => (
                  <td key={bucket.id} className="figures px-5 py-3 text-right">
                    {formatMoney(report.buckets[bucket.id], currency)}
                  </td>
                ))}
                <td className="figures px-5 py-3 text-right">{formatMoney(report.total_outstanding, currency)}</td>
              </tr>
            }
          />
        )
      }
    </Loaded>
  );
}

/* ---------------------------------------------------------------- screen */

export function Reports() {
  const { report = "profit-and-loss" } = useParams();
  const navigate = useNavigate();
  const company = useCompany();
  const currency = useCurrency();
  const [preset, setPreset] = useState<PeriodPreset>("fytd");
  const [asOf, setAsOf] = useState(today());
  const fiscalStart = company.data?.fiscal_year_start_month ?? 1;
  const period = useMemo(() => resolvePeriod(preset, fiscalStart), [preset, fiscalStart]);
  const active = REPORTS.find((candidate) => candidate.id === report) ?? REPORTS[0];
  const id: ReportId = active.id;

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Reports"
        description={
          active.dated === "period"
            ? `${formatDate(period.date_from)} to ${formatDate(period.date_to)}. Figures come from posted records.`
            : `As of ${formatDate(asOf)}. Figures come from posted records.`
        }
        actions={
          active.dated === "period" ? (
            <Segmented label="Period" options={PERIOD_PRESETS} value={preset} onChange={setPreset} />
          ) : (
            <Input aria-label="As of" type="date" className="w-40" value={asOf} onChange={(e) => e.target.value && setAsOf(e.target.value)} />
          )
        }
      />
      <Segmented
        label="Report"
        options={REPORTS.map(({ id: reportId, label }) => ({ id: reportId, label }))}
        value={id}
        onChange={(next) => navigate(`/reports/${next}`)}
      />
      <Card>
        {id === "profit-and-loss" && <ProfitAndLossReport period={period} currency={currency} />}
        {id === "balance-sheet" && <BalanceSheetReport asOf={asOf} currency={currency} />}
        {id === "items" && (
          <MarginReportView<ItemMargin>
            tool="margin_by_item"
            period={period}
            currency={currency}
            rowKey={(row) => row.sku ?? row.name}
            first={[
              { id: "name", header: "Item", cell: (row) => <span className="text-ink">{row.name}</span> },
              { id: "quantity", header: "Quantity", numeric: true, cell: (row) => row.quantity },
            ]}
          />
        )}
        {id === "customers" && (
          <MarginReportView<CustomerMargin>
            tool="margin_by_customer"
            period={period}
            currency={currency}
            rowKey={(row) => row.party_id}
            first={[
              { id: "name", header: "Customer", cell: (row) => <span className="text-ink">{row.name}</span> },
              { id: "invoices", header: "Invoices", numeric: true, cell: (row) => row.invoice_count },
            ]}
          />
        )}
        {id === "expenses" && <ExpensesReport period={period} currency={currency} />}
        {id === "break-even" && <BreakEvenReport period={period} currency={currency} />}
        {id === "comparison" && <ComparisonReport period={period} currency={currency} />}
        {id === "receivables" && <AgingReport tool="ar_aging" asOf={asOf} currency={currency} />}
        {id === "payables" && <AgingReport tool="ap_aging" asOf={asOf} currency={currency} />}
      </Card>
    </div>
  );
}
