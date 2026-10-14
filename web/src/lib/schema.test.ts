import { describe, expect, it } from "vitest";
import { buildInput, fieldsFromSchema, type JsonSchema } from "./schema";

// The shape Pydantic produces for a tool such as record_payment.
const SCHEMA: JsonSchema = {
  type: "object",
  required: ["direction", "party_id", "amount"],
  $defs: { Direction: { type: "string", enum: ["inbound", "outbound"] } },
  properties: {
    direction: { $ref: "#/$defs/Direction", description: "Which way the money moved." },
    party_id: { type: "integer" },
    amount: { anyOf: [{ type: "number" }, { type: "string" }] },
    payment_date: { anyOf: [{ type: "string", format: "date" }, { type: "null" }], default: null },
    unpaid_only: { type: "boolean", default: false },
    limit: { type: "integer", default: 50 },
    allocations: { anyOf: [{ type: "array", items: {} }, { type: "null" }], default: null },
    lines: { type: "array", items: {} },
  },
};

describe("fieldsFromSchema", () => {
  const fields = Object.fromEntries(fieldsFromSchema({ ...SCHEMA, required: [...SCHEMA.required!, "lines"] }).map((f) => [f.name, f]));

  it("picks a control for each kind of property", () => {
    expect(fields.direction).toMatchObject({ kind: "enum", options: ["inbound", "outbound"], required: true });
    expect(fields.direction.description).toBe("Which way the money moved.");
    expect(fields.party_id.kind).toBe("integer");
    expect(fields.payment_date).toMatchObject({ kind: "date", required: false, initial: "" });
    expect(fields.unpaid_only).toMatchObject({ kind: "boolean", initial: "false" });
    expect(fields.limit.initial).toBe("50");
    expect(fields.allocations).toMatchObject({ kind: "json", initial: "" });
  });

  it("edits exact decimals as text, not as a number", () => {
    expect(fields.amount.kind).toBe("text");
  });

  it("starts a required array as an empty list", () => {
    expect(fields.lines).toMatchObject({ kind: "json", required: true, initial: "[]" });
  });
});

describe("buildInput", () => {
  const fields = fieldsFromSchema(SCHEMA);

  it("converts values and leaves empty optional fields out", () => {
    const { input, errors } = buildInput(fields, {
      direction: "inbound",
      party_id: "4",
      amount: "100.10",
      payment_date: "",
      unpaid_only: "true",
      limit: "",
      allocations: '[{"invoice_number": "INV-00001", "amount": "100.10"}]',
      lines: "",
    });
    expect(errors).toEqual({});
    expect(input).toEqual({
      direction: "inbound",
      party_id: 4,
      amount: "100.10",
      unpaid_only: true,
      allocations: [{ invoice_number: "INV-00001", amount: "100.10" }],
    });
  });

  it("reports missing and malformed fields without building them", () => {
    const { input, errors } = buildInput(fields, { direction: "", party_id: "4.5", amount: "10", allocations: "[oops" });
    expect(errors).toEqual({
      direction: "This is required.",
      party_id: "Enter a whole number.",
      allocations: "This is not valid JSON.",
    });
    expect(input).toEqual({ amount: "10" });
  });
});
