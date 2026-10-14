/** Shapes of the tool results the screens use. Amounts are decimal strings. */

export type CompanySettings = {
  name: string;
  base_currency: string;
  currency_decimals: number;
  fiscal_year_start_month: number;
  lock_date: string | null;
  today: string;
};

export type AccountRow = { code: string | null; name: string; amount: string };
export type Section = { accounts: AccountRow[]; total: string };

export type ProfitAndLoss = {
  period: { from: string; to: string };
  currency: string;
  revenue: Section;
  cost_of_goods_sold: Section;
  gross_profit: string;
  gross_margin_pct: string | null;
  operating_expenses: Section;
  net_profit: string;
  net_margin_pct: string | null;
};

export type TrendMonth = {
  month: string;
  revenue: string;
  cost_of_goods_sold: string;
  gross_profit: string;
  gross_margin_pct: string | null;
  operating_expenses: string;
  net_profit: string;
  net_margin_pct: string | null;
};
export type RevenueTrend = { months: TrendMonth[] };

export type Change = { current: string; previous: string; change: string; change_pct: string | null };
export type PeriodComparison = {
  previous_period: { from: string; to: string };
  revenue: Change;
  cost_of_goods_sold: Change;
  gross_profit: Change;
  operating_expenses: Change;
  net_profit: Change;
};

export type TrialBalance = {
  accounts: { code: string; name: string; type: string; subtype: string | null; debit: string; credit: string }[];
  balanced: boolean;
};

export type AgingBucket = "current" | "1_30" | "31_60" | "61_90" | "over_90";
export type Aging = {
  buckets: Record<AgingBucket, string>;
  total_outstanding: string;
  total_overdue: string;
  by_party: ({ party_id: number; name: string; total: string } & Record<AgingBucket, string>)[];
  invoices: {
    number: string;
    party: string;
    invoice_date: string;
    due_date: string;
    days_overdue: number;
    bucket: AgingBucket;
    outstanding: string;
  }[];
};

export type MarginRow = {
  revenue: string;
  cost: string;
  gross_margin: string;
  gross_margin_pct: string | null;
  share_of_revenue_pct: string | null;
};
export type CustomerMargin = MarginRow & { party_id: number; name: string; invoice_count: number };
export type MarginReport<Row> = {
  rows: Row[];
  total_revenue: string;
  total_cost: string;
  total_gross_margin: string;
  gross_margin_pct: string | null;
};

export type PipelineSummary = {
  stages: { stage: string; count: number; expected_value: string; weighted_value: string }[];
  open_count: number;
  open_expected_value: string;
  open_weighted_value: string;
  won_count: number;
  lost_count: number;
  win_rate_pct: string | null;
};

export type PendingAction = {
  id: number;
  tool: string;
  input: Record<string, unknown>;
  status: "pending" | "approved" | "rejected";
  requested_by: string;
  requested_at: string;
  decided_by: string | null;
  decided_at: string | null;
  reason: string | null;
};

export type InvoiceStatus = "draft" | "posted" | "void";
export type PaymentStatus = "n/a" | "unpaid" | "partial" | "paid";

export type InvoiceSummary = {
  number: string;
  kind: "sales_invoice" | "vendor_bill";
  party_id: number;
  party: string;
  invoice_date: string;
  due_date: string;
  status: InvoiceStatus;
  payment_status: PaymentStatus;
  total: string;
  amount_paid: string;
  outstanding: string;
  reference: string | null;
};

export type DocLine = {
  item_sku: string | null;
  description: string;
  quantity: string;
  unit_price: string;
  tax_rate: string | null;
  line_subtotal: string;
  tax_amount: string;
};

export type Invoice = InvoiceSummary & {
  subtotal: string;
  tax_total: string;
  notes: string | null;
  lines: (DocLine & { account_code: string })[];
  journal_entry_number: string | null;
  payments: { number: string; payment_date: string; amount: string; method: string | null }[];
};

export type Party = {
  id: number;
  name: string;
  is_customer: boolean;
  is_vendor: boolean;
  email: string | null;
  phone: string | null;
  address: string | null;
  tax_id: string | null;
};

export type Item = {
  sku: string;
  name: string;
  kind: "product" | "service";
  sale_price: string;
  standard_cost: string;
  income_account_code: string;
  tax_rate: string | null;
};

export type TaxRate = { name: string; rate_pct: string; is_active: boolean };
export type Account = { code: string; name: string; type: string; subtype: string | null; is_active: boolean };
