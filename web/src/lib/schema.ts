/**
 * Turns a tool's JSON Schema into a flat list of form fields, and form values back
 * into tool input. Scalars get proper controls; arrays and nested objects are edited
 * as JSON, which keeps this small while still reaching every tool.
 */

export type JsonSchema = {
  type?: string;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  description?: string;
  default?: unknown;
  enum?: unknown[];
  format?: string;
  anyOf?: JsonSchema[];
  $ref?: string;
  $defs?: Record<string, JsonSchema>;
  items?: JsonSchema;
};

export type SchemaField = {
  name: string;
  kind: "text" | "number" | "integer" | "boolean" | "date" | "enum" | "json";
  required: boolean;
  description?: string;
  options?: string[];
  initial: string;
};

function resolve(schema: JsonSchema, root: JsonSchema): JsonSchema {
  if (schema.$ref) {
    const name = schema.$ref.split("/").pop() ?? "";
    return resolve(root.$defs?.[name] ?? {}, root);
  }
  if (schema.anyOf) {
    const options = schema.anyOf.map((option) => resolve(option, root)).filter((option) => option.type !== "null");
    // An exact decimal is offered as number-or-string; edit it as text so it is not rounded.
    const preferred = options.find((option) => option.type === "string") ?? options[0] ?? {};
    return { ...preferred, description: schema.description ?? preferred.description, default: schema.default };
  }
  return schema;
}

function kindOf(schema: JsonSchema): SchemaField["kind"] {
  if (schema.enum) return "enum";
  if (schema.type === "boolean") return "boolean";
  if (schema.type === "integer") return "integer";
  if (schema.type === "number") return "number";
  if (schema.type === "string") return schema.format === "date" ? "date" : "text";
  return "json";
}

export function fieldsFromSchema(schema: JsonSchema): SchemaField[] {
  const required = new Set(schema.required ?? []);
  return Object.entries(schema.properties ?? {}).map(([name, raw]) => {
    const property = resolve(raw, schema);
    const kind = kindOf(property);
    const fallback = raw.default ?? property.default;
    let initial = "";
    if (fallback !== undefined && fallback !== null) {
      initial = kind === "json" ? JSON.stringify(fallback, null, 2) : String(fallback);
    } else if (kind === "json" && required.has(name)) {
      initial = property.type === "array" ? "[]" : "{}";
    }
    return {
      name,
      kind,
      required: required.has(name),
      description: raw.description ?? property.description,
      options: property.enum?.map(String),
      initial,
    };
  });
}

/** Build tool input from form values. Empty fields are left out so defaults apply. */
export function buildInput(
  fields: SchemaField[],
  values: Record<string, string>,
): { input: Record<string, unknown>; errors: Record<string, string> } {
  const input: Record<string, unknown> = {};
  const errors: Record<string, string> = {};
  for (const field of fields) {
    const value = (values[field.name] ?? "").trim();
    if (value === "") {
      if (field.required) errors[field.name] = "This is required.";
      continue;
    }
    switch (field.kind) {
      case "integer":
      case "number": {
        const parsed = Number(value);
        if (!Number.isFinite(parsed) || (field.kind === "integer" && !Number.isInteger(parsed))) {
          errors[field.name] = field.kind === "integer" ? "Enter a whole number." : "Enter a number.";
        } else {
          input[field.name] = parsed;
        }
        break;
      }
      case "boolean":
        input[field.name] = value === "true";
        break;
      case "json":
        try {
          input[field.name] = JSON.parse(value);
        } catch {
          errors[field.name] = "This is not valid JSON.";
        }
        break;
      default:
        input[field.name] = value;
    }
  }
  return { input, errors };
}
