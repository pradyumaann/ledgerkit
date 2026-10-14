import { Package, Percent, Plus } from "@phosphor-icons/react";
import { useState } from "react";
import { useCurrency, useTool, useToolMutation } from "../../api/hooks";
import type { Account, Item, TaxRate } from "../../api/types";
import { type FieldSpec, FormDialog } from "../../design/FormDialog";
import { Button, Card, EmptyState, ErrorState, PageHeader } from "../../design/primitives";
import { type Column, Table } from "../../design/Table";
import { formatMoney, isZero } from "../../lib/money";

export function Items() {
  const currency = useCurrency();
  const [creating, setCreating] = useState(false);
  const list = useTool<{ items: Item[] }>("list_items", { limit: 500 });
  const taxRates = useTool<{ tax_rates: TaxRate[] }>("list_tax_rates");
  const incomeAccounts = useTool<{ accounts: Account[] }>("list_accounts", { type: "income" });
  const create = useToolMutation<Item>("create_item", {
    success: (item) => `${item.name} added`,
    onSuccess: () => setCreating(false),
  });

  const fields: FieldSpec[] = [
    { name: "name", label: "Name", required: true },
    { name: "sku", label: "SKU", required: true, hint: "A short unique code" },
    {
      name: "kind",
      label: "Kind",
      type: "select",
      required: true,
      initial: "product",
      options: [
        { value: "product", label: "Product" },
        { value: "service", label: "Service" },
      ],
    },
    { name: "sale_price", label: `Sale price (${currency.code})`, type: "decimal", required: true },
    {
      name: "standard_cost",
      label: `Standard cost (${currency.code})`,
      type: "decimal",
      hint: "Products only. Used as cost of goods sold.",
    },
    {
      name: "income_account_code",
      label: "Income account",
      type: "select",
      required: true,
      initial: "4000",
      options: incomeAccounts.data?.accounts.map((a) => ({ value: a.code, label: `${a.code} ${a.name}` })),
    },
    {
      name: "tax_rate",
      label: "Default tax",
      type: "select",
      options: taxRates.data?.tax_rates.map((rate) => ({ value: rate.name, label: rate.name })),
    },
  ];

  const columns: Column<Item>[] = [
    { id: "name", header: "Name", cell: (row) => <span className="font-medium text-ink">{row.name}</span> },
    { id: "sku", header: "SKU", cell: (row) => <span className="font-mono text-[12.5px] text-ink-2">{row.sku}</span> },
    { id: "kind", header: "Kind", cell: (row) => (row.kind === "product" ? "Product" : "Service") },
    { id: "tax", header: "Default tax", cell: (row) => row.tax_rate ?? <span className="text-ink-3">None</span> },
    { id: "price", header: "Sale price", numeric: true, cell: (row) => formatMoney(row.sale_price, currency) },
    {
      id: "cost",
      header: "Standard cost",
      numeric: true,
      cell: (row) =>
        isZero(row.standard_cost) ? <span className="text-ink-3">None</span> : formatMoney(row.standard_cost, currency),
    },
  ];

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Items"
        description="The products and services you put on quotations, invoices and bills."
        actions={
          <Button variant="primary" trailing={Plus} onClick={() => setCreating(true)}>
            New item
          </Button>
        }
      />
      <Card>
        {list.error ? (
          <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />
        ) : list.data?.items.length === 0 ? (
          <EmptyState icon={Package} title="No items yet" body="Add what you sell so documents can fill in prices and tax for you." />
        ) : (
          <div className="pb-2">
            <Table columns={columns} rows={list.data?.items} rowKey={(row) => row.sku} loading={list.isPending} />
          </div>
        )}
      </Card>
      <FormDialog
        open={creating}
        onClose={() => setCreating(false)}
        title="New item"
        fields={fields}
        submitLabel="Add item"
        pending={create.isPending}
        onSubmit={(values) => create.mutate(values)}
      />
    </div>
  );
}

export function TaxRates() {
  const [creating, setCreating] = useState(false);
  const list = useTool<{ tax_rates: TaxRate[] }>("list_tax_rates");
  const close = () => setCreating(false);
  const create = useToolMutation<TaxRate>("create_tax_rate", {
    success: (rate) => `${rate.name} added`,
    onSuccess: close,
    onHeld: close,
  });

  const columns: Column<TaxRate>[] = [
    { id: "name", header: "Name", cell: (row) => <span className="font-medium text-ink">{row.name}</span> },
    { id: "rate", header: "Rate", numeric: true, cell: (row) => `${row.rate_pct}%` },
  ];

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Tax rates"
        description="Sales or value-added tax rates that can be applied to document lines."
        actions={
          <Button variant="primary" trailing={Plus} onClick={() => setCreating(true)}>
            New tax rate
          </Button>
        }
      />
      <Card className="max-w-2xl">
        {list.error ? (
          <ErrorState message={list.error.message} onRetry={() => void list.refetch()} />
        ) : list.data?.tax_rates.length === 0 ? (
          <EmptyState icon={Percent} title="No tax rates yet" body="Add a rate if you charge sales tax or VAT." />
        ) : (
          <div className="pb-2">
            <Table columns={columns} rows={list.data?.tax_rates} rowKey={(row) => row.name} loading={list.isPending} />
          </div>
        )}
      </Card>
      <FormDialog
        open={creating}
        onClose={close}
        title="New tax rate"
        description="Tax collected is booked to the tax payable account, and tax paid on purchases to the input tax account."
        fields={[
          { name: "name", label: "Name", required: true, hint: "For example VAT 20%" },
          { name: "rate_pct", label: "Rate (%)", type: "decimal", required: true },
        ]}
        submitLabel="Add tax rate"
        pending={create.isPending}
        onSubmit={(values) => create.mutate(values)}
      />
    </div>
  );
}
