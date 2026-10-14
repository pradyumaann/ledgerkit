import { ArrowRight, ChartLineUp, SealCheck, Table as TableIcon } from "@phosphor-icons/react";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { useCompany, useCurrency, useTool } from "../../api/hooks";
import type {
  Aging,
  AgingBucket,
  CustomerMargin,
  MarginReport,
  PendingAction,
  PeriodComparison,
  PipelineSummary,
  ProfitAndLoss,
  RevenueTrend,
  TrialBalance,
} from "../../api/types";
import {
  Amount,
  Button,
  Card,
  CardHeader,
  cx,
  Delta,
  EmptyState,
  ErrorState,
  Monogram,
  PageHeader,
  Segmented,
  Skeleton,
} from "../../design/primitives";
import { formatDate, formatMonthYear, PERIOD_PRESETS, type PeriodPreset, resolvePeriod } from "../../lib/dates";
import { type Currency, formatMoney, formatPercent, fromMinor, isNegative, isZero, toMinor } from "../../lib/money";
import { TrendChart, TrendLegend } from "./TrendChart";

/* One-hue ramp for ordered buckets: the longer overdue, the darker. */
const AGING: { id: AgingBucket; label: string; color: string }[] = [
  { id: "current", label: "Not yet due", color: "#86b6ef" },
  { id: "1_30", label: "1 to 30 days late", color: "#5598e7" },
  { id: "31_60", label: "31 to 60 days late", color: "#2a78d6" },
  { id: "61_90", label: "61 to 90 days late", color: "#1c5cab" },
  { id: "over_90", label: "Over 90 days late", color: "#184f95" },
];

function AgingBar({ aging, currency }: { aging: Aging; currency: Currency }) {
  const total = Number(aging.total_outstanding);
  const present = AGING.filter((bucket) => !isZero(aging.buckets[bucket.id]));
  if (!total || present.length === 0) return null;
  return (
    <div>
      <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full" role="img" aria-label="Receivables by age">
        {present.map((bucket) => (
          <span
            key={bucket.id}
            title={`${bucket.label}: ${formatMoney(aging.buckets[bucket.id], currency)}`}
            className="h-full min-w-1.5"
            style={{ background: bucket.color, flexGrow: Number(aging.buckets[bucket.id]) / total, flexBasis: 0 }}
          />
        ))}
      </div>
      <ul className="mt-3 space-y-1.5">
        {present.map((bucket) => (
          <li key={bucket.id} className="flex items-center gap-2 text-[13px]">
            <span aria-hidden className="size-2 rounded-[3px]" style={{ background: bucket.color }} />
            <span className="flex-1 text-ink-2">{bucket.label}</span>
            <span className="figures text-ink">{formatMoney(aging.buckets[bucket.id], currency)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Figure({
  label,
  value,
  currency,
  note,
  changePct,
  upIsGood,
}: {
  label: string;
  value: string | undefined;
  currency: Currency;
  note?: string;
  changePct?: string | null;
  upIsGood?: boolean;
}) {
  return (
    <div className="px-6 py-4 first:pl-0 sm:py-1">
      <p className="text-[13px] text-ink-3">{label}</p>
      {value === undefined ? (
        <Skeleton className="mt-2 h-8 w-32" />
      ) : (
        <p className="mt-1.5 text-[26px] font-[420] leading-tight tracking-[-0.01em] text-ink">
          <Amount value={value} currency={currency} />
        </p>
      )}
      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-0.5">
        <Delta pct={changePct} upIsGood={upIsGood} />
        {note && <p className="text-[13px] text-ink-2">{note}</p>}
      </div>
    </div>
  );
}

function TrendTable({ trend, currency }: { trend: RevenueTrend; currency: Currency }) {
  return (
    <div className="overflow-x-auto px-5 pb-5">
      <table className="w-full">
        <thead>
          <tr className="text-[12.5px] text-ink-3">
            <th scope="col" className="pb-2 text-left font-normal">
              Month
            </th>
            <th scope="col" className="pb-2 text-right font-normal">
              Revenue
            </th>
            <th scope="col" className="pb-2 text-right font-normal">
              Net profit
            </th>
            <th scope="col" className="pb-2 text-right font-normal">
              Net margin
            </th>
          </tr>
        </thead>
        <tbody>
          {trend.months.map((month) => (
            <tr key={month.month} className="border-t border-line">
              <th scope="row" className="py-2 text-left font-normal text-ink">
                {formatMonthYear(month.month)}
              </th>
              <td className="figures py-2 text-right">{formatMoney(month.revenue, currency)}</td>
              <td className="figures py-2 text-right">{formatMoney(month.net_profit, currency)}</td>
              <td className="figures py-2 text-right text-ink-2">{formatPercent(month.net_margin_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function cashOnHand(trialBalance: TrialBalance, decimals: number): string {
  const total = trialBalance.accounts
    .filter((account) => account.subtype === "bank")
    .reduce((sum, account) => sum + toMinor(account.debit, decimals) - toMinor(account.credit, decimals), 0n);
  return fromMinor(total, decimals);
}

const OPEN_STAGES = ["prospecting", "proposal", "negotiation"];
const STAGE_LABEL: Record<string, string> = { prospecting: "Prospecting", proposal: "Proposal", negotiation: "Negotiation" };

export function Dashboard() {
  const company = useCompany();
  const currency = useCurrency();
  const [preset, setPreset] = useState<PeriodPreset>("6m");
  const [showTable, setShowTable] = useState(false);
  const fiscalStart = company.data?.fiscal_year_start_month ?? 1;
  const period = useMemo(() => resolvePeriod(preset, fiscalStart), [preset, fiscalStart]);

  const statement = useTool<ProfitAndLoss>("profit_and_loss", period);
  const comparison = useTool<PeriodComparison>("period_comparison", period);
  const trend = useTool<RevenueTrend>("revenue_trend", period);
  const customers = useTool<MarginReport<CustomerMargin>>("margin_by_customer", period);
  const trialBalance = useTool<TrialBalance>("trial_balance");
  const receivables = useTool<Aging>("ar_aging");
  const payables = useTool<Aging>("ap_aging");
  const pipeline = useTool<PipelineSummary>("pipeline_summary");
  const approvals = useTool<{ actions: PendingAction[] }>("list_pending_approvals");

  if (statement.error) {
    return <ErrorState message={statement.error.message} onRetry={() => void statement.refetch()} />;
  }

  const pl = statement.data;
  const pendingCount = approvals.data?.actions.length ?? 0;
  const topCustomers = customers.data?.rows.slice(0, 5) ?? [];
  const bestMargin = Math.max(...topCustomers.map((row) => Number(row.gross_margin)), 0);
  const hasActivity = pl ? !isZero(pl.revenue.total) || !isZero(pl.operating_expenses.total) : true;

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Dashboard"
        description={pl ? `${formatDate(pl.period.from)} to ${formatDate(pl.period.to)}` : undefined}
        actions={<Segmented label="Period" options={PERIOD_PRESETS} value={preset} onChange={setPreset} />}
      />

      {pendingCount > 0 && (
        <Link
          to="/approvals"
          className="group flex items-center gap-3 rounded-2xl bg-lavender px-4 py-3 text-ink transition-colors duration-300 ease-out-soft hover:bg-primary-wash"
        >
          <SealCheck size={19} className="shrink-0 text-primary-ink" />
          <span className="flex-1">
            {pendingCount === 1 ? "1 action is" : `${pendingCount} actions are`} waiting for your approval.
          </span>
          <span className="flex items-center gap-1 font-medium text-primary-ink">
            Review
            <ArrowRight size={15} className="transition-transform duration-300 ease-out-soft group-hover:translate-x-0.5" />
          </span>
        </Link>
      )}

      <div className={cx("grid grid-cols-1 gap-4 lg:grid-cols-12", statement.isPlaceholderData && "opacity-60 transition-opacity")}>
        <Card className="lg:col-span-8" tone="night">
          <div className="flex h-full flex-col">
          <div className="flex flex-wrap items-start justify-between gap-4 px-6 pt-6">
            <div>
              <p className="text-[13px] text-ink-2">Net profit</p>
              {pl ? (
                <p className="mt-2 text-[56px] font-[380] leading-none tracking-[-0.025em] text-ink">
                  <Amount value={pl.net_profit} currency={currency} />
                </p>
              ) : (
                <Skeleton className="mt-3 h-14 w-64" />
              )}
              {pl && (
                <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1">
                  <p className="text-ink-2">
                    {pl.net_margin_pct == null
                      ? "No revenue in this period"
                      : `${pl.net_margin_pct}% net margin${isNegative(pl.net_profit) ? ", a loss for the period" : ""}`}
                  </p>
                  <Delta pct={comparison.data?.net_profit.change_pct} />
                </div>
              )}
            </div>
            <div className="flex items-center gap-3">
              {!showTable && <TrendLegend />}
              <Button size="sm" icon={showTable ? ChartLineUp : TableIcon} onClick={() => setShowTable((shown) => !shown)}>
                {showTable ? "Chart" : "Table"}
              </Button>
            </div>
          </div>
          {!hasActivity ? (
            <EmptyState
              icon={ChartLineUp}
              title="Nothing posted in this period"
              body="Post an invoice or a bill and the monthly trend will appear here."
              action={
                <Button variant="tint" to="/invoices/new">
                  Create an invoice
                </Button>
              }
            />
          ) : showTable ? (
            <div className="pt-4">{trend.data && <TrendTable trend={trend.data} currency={currency} />}</div>
          ) : (
            <div className="relative min-h-64 flex-1">
              <div className="absolute inset-0 px-3 pb-4 pt-5">
                {trend.data ? <TrendChart months={trend.data.months} currency={currency} /> : <Skeleton className="h-full" />}
              </div>
            </div>
          )}
          </div>
        </Card>

        <div className="grid gap-4 sm:grid-cols-2 lg:col-span-4 lg:grid-cols-1">
          <Card>
            <div className="p-5">
              <p className="text-[13px] text-ink-3">Cash and bank</p>
              {trialBalance.data ? (
                <p className="mt-1.5 text-[30px] font-[420] leading-tight tracking-[-0.015em] text-ink">
                  <Amount value={cashOnHand(trialBalance.data, currency.decimals)} currency={currency} />
                </p>
              ) : (
                <Skeleton className="mt-2 h-8 w-36" />
              )}
              <p className="mt-1 text-[13px] text-ink-2">
                {payables.data ? `${formatMoney(payables.data.total_outstanding, currency)} owed to vendors` : " "}
              </p>
            </div>
          </Card>
          <Card tone="lavender">
            <div className="p-5">
              <p className="text-[13px] text-ink-2">Owed by customers</p>
              {receivables.data ? (
                <>
                  <p className="mt-1.5 text-[30px] font-[420] leading-tight tracking-[-0.015em] text-ink">
                    <Amount value={receivables.data.total_outstanding} currency={currency} />
                  </p>
                  <p className="mb-4 mt-1 text-[13px] text-ink-2">
                    {isZero(receivables.data.total_overdue)
                      ? "Nothing is overdue"
                      : `${formatMoney(receivables.data.total_overdue, currency)} is overdue`}
                  </p>
                  <AgingBar aging={receivables.data} currency={currency} />
                </>
              ) : (
                <Skeleton className="mt-2 h-8 w-36" />
              )}
            </div>
          </Card>
        </div>
      </div>

      <div className="grid divide-y divide-line border-y border-line py-0 sm:grid-cols-3 sm:divide-x sm:divide-y-0 sm:py-5">
        <Figure
          label="Revenue"
          value={pl?.revenue.total}
          currency={currency}
          changePct={comparison.data?.revenue.change_pct}
        />
        <Figure
          label="Gross profit"
          value={pl?.gross_profit}
          currency={currency}
          changePct={comparison.data?.gross_profit.change_pct}
          note={pl ? `${formatPercent(pl.gross_margin_pct)} margin` : undefined}
        />
        <Figure
          label="Operating expenses"
          value={pl?.operating_expenses.total}
          currency={currency}
          changePct={comparison.data?.operating_expenses.change_pct}
          upIsGood={false}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <Card className="lg:col-span-7">
          <CardHeader
            title="Customers by gross margin"
            hint="Revenue less the cost of the goods sold to each customer"
            action={
              <Button size="sm" to="/reports">
                All reports
              </Button>
            }
          />
          {customers.data && topCustomers.length === 0 ? (
            <EmptyState
              icon={ChartLineUp}
              title="No sales in this period"
              body="Customer margins appear once sales invoices are posted."
            />
          ) : (
            <ul className="px-5 pb-4 pt-3">
              {(customers.data ? topCustomers : Array.from({ length: 4 }, () => null)).map((row, index) => (
                <li key={row?.party_id ?? index} className="border-t border-line py-3 first:border-t-0">
                  {row ? (
                    <>
                      <div className="flex items-center gap-3">
                        <Monogram name={row.name} />
                        <span className="min-w-0 flex-1 truncate text-ink">{row.name}</span>
                        <span className="figures text-[13px] text-ink-2">{formatPercent(row.gross_margin_pct)}</span>
                        <span className="figures w-28 text-right text-ink">{formatMoney(row.gross_margin, currency)}</span>
                      </div>
                      <div
                        aria-hidden
                        className="mt-2 h-1.5 rounded-full bg-[var(--series-1)]"
                        style={{ width: `${bestMargin > 0 ? Math.max((Number(row.gross_margin) / bestMargin) * 100, 1.5) : 0}%` }}
                      />
                    </>
                  ) : (
                    <Skeleton className="h-9" />
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="lg:col-span-5">
          <CardHeader
            title="Sales pipeline"
            hint={
              pipeline.data?.win_rate_pct == null ? "No closed deals yet" : `${pipeline.data.win_rate_pct}% of closed deals won`
            }
            action={
              <Button size="sm" to="/pipeline">
                Open
              </Button>
            }
          />
          <div className="px-5 pb-5 pt-4">
            {pipeline.data ? (
              <>
                <p className="text-[30px] font-[420] leading-tight tracking-[-0.015em] text-ink">
                  <Amount value={pipeline.data.open_weighted_value} currency={currency} />
                </p>
                <p className="mt-1 text-[13px] text-ink-2">
                  Weighted value of {pipeline.data.open_count} open {pipeline.data.open_count === 1 ? "deal" : "deals"}
                </p>
                <dl className="mt-4">
                  {pipeline.data.stages
                    .filter((stage) => OPEN_STAGES.includes(stage.stage))
                    .map((stage) => (
                      <div key={stage.stage} className="flex items-baseline gap-3 border-t border-line py-2.5">
                        <dt className="flex-1 text-ink-2">{STAGE_LABEL[stage.stage]}</dt>
                        <dd className="figures text-[13px] text-ink-3">{stage.count}</dd>
                        <dd className="figures w-28 text-right text-ink">{formatMoney(stage.expected_value, currency)}</dd>
                      </div>
                    ))}
                </dl>
              </>
            ) : (
              <Skeleton className="h-40" />
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
