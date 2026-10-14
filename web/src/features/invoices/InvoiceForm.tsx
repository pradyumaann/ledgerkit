import { ArrowLeft, Plus, Trash } from "@phosphor-icons/react";
import { type FormEvent, useRef, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useCurrency, useTool, useToolMutation } from "../../api/hooks";
import type { Account, Invoice, Item, Party, TaxRate } from "../../api/types";
import { Field, Input, Select, Textarea } from "../../design/Form";
import { Button, Card, PageHeader } from "../../design/primitives";
import { today } from "../../lib/dates";
import { formatMoney, lineTotal, sumMoney } from "../../lib/money";
import { type FormKind, KINDS } from "./kinds";

type Line = {
  key: number;
  item_sku: string;
  description: string;
  quantity: string;
  unit_price: string;
  /** "" follows the item's own tax rate; "none" charges no tax. */
  tax_rate: string;
  account_code: string;
};

const NO_ITEM = "";

export function InvoiceForm({ kind }: { kind: FormKind }) {
  const config = KINDS[kind];
  const currency = useCurrency();
  const navigate = useNavigate();
  const nextKey = useRef(2);

  const parties = useTool<{ parties: Party[] }>("search_parties", { role: config.partyRole, limit: 200 });
  const items = useTool<{ items: Item[] }>("list_items", { limit: 500 });
  const taxRates = useTool<{ tax_rates: TaxRate[] }>("list_tax_rates");
  const accounts = useTool<{ accounts: Account[] }>("list_accounts", { type: "expense" }, { enabled: kind === "purchase" });

  const [partyId, setPartyId] = useState("");
  const [date, setDate] = useState(today());
  const [dueDate, setDueDate] = useState("");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([blankLine(1)]);

  const create = useToolMutation<Invoice>(config.createTool, {
    success: (invoice) => `Draft ${invoice.number} created`,
    onSuccess: (invoice) => navigate(kind === "quotation" ? config.base : `${config.base}/${invoice.number}`),
  });

  function blankLine(key: number): Line {
    return { key, item_sku: NO_ITEM, description: "", quantity: "1", unit_price: "", tax_rate: "", account_code: "" };
  }

  function change(key: number, changes: Partial<Line>) {
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...changes } : line)));
  }

  function chooseItem(key: number, sku: string) {
    const item = items.data?.items.find((candidate) => candidate.sku === sku);
    if (!item) return change(key, { item_sku: NO_ITEM });
    change(key, {
      item_sku: sku,
      description: item.name,
      unit_price: kind === "purchase" ? item.standard_cost : item.sale_price,
      tax_rate: "",
    });
  }

  const totals = lines.map((line) => lineTotal(line.quantity, line.unit_price, currency.decimals));
  const subtotal = totals.every((total) => total !== null) ? sumMoney(totals as string[], currency.decimals) : null;

  function submit(event: FormEvent) {
    event.preventDefault();
    create.mutate({
      [config.partyField]: Number(partyId),
      [config.dateField]: date,
      ...(dueDate ? { [config.dueField]: dueDate } : {}),
      ...(reference && kind !== "quotation" ? { reference } : {}),
      ...(notes ? { notes } : {}),
      lines: lines.map((line) => ({
        ...(line.item_sku ? { item_sku: line.item_sku } : {}),
        ...(line.description ? { description: line.description } : {}),
        quantity: line.quantity,
        ...(line.unit_price ? { unit_price: line.unit_price } : {}),
        ...(line.tax_rate ? { tax_rate: line.tax_rate } : {}),
        ...(line.account_code ? { account_code: line.account_code } : {}),
      })),
    });
  }

  const noParties = parties.data?.parties.length === 0;

  return (
    <form onSubmit={submit} className="space-y-6">
      <Link to={config.base} className="inline-flex items-center gap-1.5 text-ink-2 transition-colors hover:text-ink">
        <ArrowLeft size={15} />
        {config.title}
      </Link>
      <PageHeader
        title={`New ${config.noun}`}
        description={
          kind === "quotation"
            ? "A quotation has no effect on the books. Convert it to an order when the customer accepts."
            : "This creates a draft. Nothing reaches the books until you post it."
        }
      />

      <Card>
        <div className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-4">
          <Field
            label={config.party}
            className="sm:col-span-2"
            hint={noParties ? `Add a ${config.partyRole} first, under ${config.party}s.` : undefined}
          >
            {(id) => (
              <Select id={id} required value={partyId} onChange={(e) => setPartyId(e.target.value)}>
                <option value="" disabled>
                  Choose a {config.partyRole}
                </option>
                {parties.data?.parties.map((party) => (
                  <option key={party.id} value={party.id}>
                    {party.name}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="Date">
            {(id) => <Input id={id} type="date" required value={date} onChange={(e) => setDate(e.target.value)} />}
          </Field>
          <Field label={config.dueLabel} hint={config.dueHint}>
            {(id) => <Input id={id} type="date" min={date} value={dueDate} onChange={(e) => setDueDate(e.target.value)} />}
          </Field>
          {kind !== "quotation" && (
            <Field label="Reference" hint={config.referenceHint} className="sm:col-span-2">
              {(id) => <Input id={id} value={reference} onChange={(e) => setReference(e.target.value)} />}
            </Field>
          )}
        </div>
      </Card>

      <Card>
        <div className="space-y-4 p-5">
          <h2 className="text-[15px] text-ink">Lines</h2>
          {lines.map((line, index) => (
            <fieldset key={line.key} className="grid gap-3 border-t border-line pt-4 first-of-type:border-t-0 first-of-type:pt-0 lg:grid-cols-12">
              <legend className="sr-only">Line {index + 1}</legend>
              <Field label="Item" className="lg:col-span-3">
                {(id) => (
                  <Select id={id} value={line.item_sku} onChange={(e) => chooseItem(line.key, e.target.value)}>
                    <option value={NO_ITEM}>No item</option>
                    {items.data?.items.map((item) => (
                      <option key={item.sku} value={item.sku}>
                        {item.name}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="Description" className={kind === "purchase" ? "lg:col-span-2" : "lg:col-span-4"}>
                {(id) => (
                  <Input
                    id={id}
                    required={!line.item_sku}
                    value={line.description}
                    onChange={(e) => change(line.key, { description: e.target.value })}
                  />
                )}
              </Field>
              {kind === "purchase" && (
                <Field label="Expense account" className="lg:col-span-2">
                  {(id) => (
                    <Select
                      id={id}
                      value={line.account_code}
                      onChange={(e) => change(line.key, { account_code: e.target.value })}
                    >
                      <option value="">Inventory (products)</option>
                      {accounts.data?.accounts.map((account) => (
                        <option key={account.code} value={account.code}>
                          {account.code} {account.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
              )}
              <Field label="Quantity" className="lg:col-span-1">
                {(id) => (
                  <Input
                    id={id}
                    inputMode="decimal"
                    required
                    className="figures text-right"
                    value={line.quantity}
                    onChange={(e) => change(line.key, { quantity: e.target.value })}
                  />
                )}
              </Field>
              <Field label="Unit price" className="lg:col-span-2">
                {(id) => (
                  <Input
                    id={id}
                    inputMode="decimal"
                    required={!line.item_sku}
                    className="figures text-right"
                    value={line.unit_price}
                    onChange={(e) => change(line.key, { unit_price: e.target.value })}
                  />
                )}
              </Field>
              <Field label="Tax" className="lg:col-span-2">
                {(id) => (
                  <div className="flex gap-2">
                    <Select
                      id={id}
                      className="min-w-0 flex-1"
                      value={line.tax_rate}
                      onChange={(e) => change(line.key, { tax_rate: e.target.value })}
                    >
                      <option value="">{line.item_sku ? "Item default" : "No tax"}</option>
                      {line.item_sku && <option value="none">No tax</option>}
                      {taxRates.data?.tax_rates.map((rate) => (
                        <option key={rate.name} value={rate.name}>
                          {rate.name}
                        </option>
                      ))}
                    </Select>
                    <button
                      type="button"
                      aria-label={`Remove line ${index + 1}`}
                      disabled={lines.length === 1}
                      onClick={() => setLines((current) => current.filter((candidate) => candidate.key !== line.key))}
                      className="flex size-9 shrink-0 items-center justify-center rounded-full text-ink-3 transition-colors hover:bg-wash hover:text-ink disabled:opacity-40"
                    >
                      <Trash size={16} />
                    </button>
                  </div>
                )}
              </Field>
            </fieldset>
          ))}
          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-line pt-4">
            <Button
              variant="tint"
              size="sm"
              icon={Plus}
              onClick={() => setLines((current) => [...current, blankLine(nextKey.current++)])}
            >
              Add line
            </Button>
            <p className="text-ink-2">
              Subtotal before tax{" "}
              <span className="figures ml-2 text-[16px] font-medium text-ink">
                {subtotal === null ? "Check the quantities and prices" : formatMoney(subtotal, currency)}
              </span>
            </p>
          </div>
        </div>
      </Card>

      <Card>
        <div className="p-5">
          <Field label="Notes" hint="Optional. Shown on the document.">
            {(id) => <Textarea id={id} value={notes} onChange={(e) => setNotes(e.target.value)} />}
          </Field>
        </div>
      </Card>

      <div className="flex justify-end gap-2">
        <Button to={config.base}>Cancel</Button>
        <Button type="submit" variant="primary" loading={create.isPending} disabled={noParties}>
          {kind === "quotation" ? "Create quotation" : "Create draft"}
        </Button>
      </div>
    </form>
  );
}
