import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TrendMonth } from "../../api/types";
import { formatMonth, formatMonthYear } from "../../lib/dates";
import { type Currency, formatMoney } from "../../lib/money";

/**
 * Monthly revenue (columns) against net profit (line), both on one shared axis.
 * Geometry uses plain numbers; every figure a reader sees is formatted from the
 * API's exact decimal string.
 */

type Point = TrendMonth & { revenueValue: number; netProfitValue: number };

const SERIES = [
  { key: "revenue", label: "Revenue", color: "var(--series-1)", mark: "bar" },
  { key: "net_profit", label: "Net profit", color: "var(--series-2)", mark: "line" },
] as const;

export function TrendLegend() {
  return (
    <ul className="flex items-center gap-4 text-[13px] text-ink-2">
      {SERIES.map((series) => (
        <li key={series.key} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className={series.mark === "bar" ? "h-2.5 w-2.5 rounded-[3px]" : "h-0.5 w-3.5 rounded-full"}
            style={{ background: series.color }}
          />
          {series.label}
        </li>
      ))}
    </ul>
  );
}

function TrendTooltip({ active, payload, currency }: { active?: boolean; payload?: { payload: Point }[]; currency: Currency }) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <div className="rounded-xl bg-surface px-3.5 py-3 shadow-float ring-1 ring-line">
      <p className="text-[12.5px] text-ink-3">{formatMonthYear(point.month)}</p>
      <dl className="mt-1.5 space-y-1">
        {SERIES.map((series) => (
          <div key={series.key} className="flex items-center gap-2">
            <span aria-hidden className="h-0.5 w-3 rounded-full" style={{ background: series.color }} />
            <dd className="figures font-medium text-ink">{formatMoney(point[series.key], currency)}</dd>
            <dt className="text-[12.5px] text-ink-3">{series.label}</dt>
          </div>
        ))}
        <div className="flex items-center gap-2 pl-5">
          <dd className="figures text-ink-2">{point.net_margin_pct == null ? "n/a" : `${point.net_margin_pct}%`}</dd>
          <dt className="text-[12.5px] text-ink-3">Net margin</dt>
        </div>
      </dl>
    </div>
  );
}

export function TrendChart({ months, currency }: { months: TrendMonth[]; currency: Currency }) {
  const data: Point[] = months.map((month) => ({
    ...month,
    revenueValue: Number(month.revenue),
    netProfitValue: Number(month.net_profit),
  }));
  const compact = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 });

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }} barCategoryGap="30%">
        <CartesianGrid vertical={false} stroke="var(--grid)" />
        <XAxis
          dataKey="month"
          tickFormatter={formatMonth}
          tickLine={false}
          axisLine={{ stroke: "var(--axis)" }}
          tick={{ fill: "var(--ink-3)", fontSize: 12 }}
          tickMargin={8}
        />
        <YAxis
          tickFormatter={(value: number) => compact.format(value)}
          tickLine={false}
          axisLine={false}
          width={44}
          tick={{ fill: "var(--ink-3)", fontSize: 12 }}
          className="figures"
        />
        <Tooltip
          content={<TrendTooltip currency={currency} />}
          cursor={{ fill: "var(--wash)" }}
          isAnimationActive={false}
        />
        <Bar
          dataKey="revenueValue"
          name="Revenue"
          fill="var(--series-1)"
          radius={[4, 4, 0, 0]}
          maxBarSize={24}
          isAnimationActive={false}
        />
        <Line
          dataKey="netProfitValue"
          name="Net profit"
          type="monotone"
          stroke="var(--series-2)"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          dot={{ r: 4, fill: "var(--series-2)", stroke: "var(--surface)", strokeWidth: 2 }}
          activeDot={{ r: 5, fill: "var(--series-2)", stroke: "var(--surface)", strokeWidth: 2 }}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
