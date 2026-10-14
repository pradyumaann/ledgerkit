import { type FormEvent, useState } from "react";
import { Dialog } from "./Dialog";
import { Field, Input, Select, Textarea } from "./Form";
import { Button, cx } from "./primitives";

export type FieldSpec = {
  name: string;
  label: string;
  /** "decimal" keeps the value as a string so amounts stay exact; "integer" sends a number. */
  type?: "text" | "email" | "date" | "decimal" | "integer" | "select" | "textarea";
  required?: boolean;
  hint?: string;
  options?: { value: string; label: string }[];
  initial?: string;
  /** Take the full width of the two-column grid. */
  wide?: boolean;
};

export type FormValues = Record<string, string | number>;

function Fields({
  fields,
  submitLabel,
  pending,
  onCancel,
  onSubmit,
}: {
  fields: FieldSpec[];
  submitLabel: string;
  pending: boolean;
  onCancel: () => void;
  onSubmit: (values: FormValues) => void;
}) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((field) => [field.name, field.initial ?? ""])),
  );
  const set = (name: string, value: string) => setValues((current) => ({ ...current, [name]: value }));

  function submit(event: FormEvent) {
    event.preventDefault();
    const result: FormValues = {};
    for (const field of fields) {
      const value = values[field.name].trim();
      if (value === "") continue;
      result[field.name] = field.type === "integer" ? Number(value) : value;
    }
    onSubmit(result);
  }

  return (
    <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
      {fields.map((field, index) => (
        <Field
          key={field.name}
          label={field.label}
          hint={field.hint ?? (field.required ? undefined : "Optional")}
          className={cx((field.wide || field.type === "textarea") && "sm:col-span-2")}
        >
          {(id) => {
            const common = {
              id,
              required: field.required,
              value: values[field.name],
              autoFocus: index === 0,
            };
            if (field.type === "select") {
              return (
                <Select {...common} onChange={(event) => set(field.name, event.target.value)}>
                  <option value="">{field.required ? "Choose one" : "None"}</option>
                  {field.options?.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              );
            }
            if (field.type === "textarea") {
              return <Textarea {...common} onChange={(event) => set(field.name, event.target.value)} />;
            }
            const numeric = field.type === "decimal" || field.type === "integer";
            return (
              <Input
                {...common}
                type={field.type === "date" || field.type === "email" ? field.type : "text"}
                inputMode={field.type === "decimal" ? "decimal" : field.type === "integer" ? "numeric" : undefined}
                pattern={field.type === "integer" ? "\\d+" : field.type === "decimal" ? "\\d*\\.?\\d*" : undefined}
                className={numeric ? "figures" : undefined}
                onChange={(event) => set(field.name, event.target.value)}
              />
            );
          }}
        </Field>
      ))}
      <div className="mt-2 flex justify-end gap-2 sm:col-span-2">
        <Button onClick={onCancel}>Cancel</Button>
        <Button type="submit" variant="primary" loading={pending}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

/** A dialog holding a short form described by a list of fields. Empty fields are left out. */
export function FormDialog({
  open,
  onClose,
  title,
  description,
  fields,
  submitLabel,
  pending,
  onSubmit,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  fields: FieldSpec[];
  submitLabel: string;
  pending: boolean;
  onSubmit: (values: FormValues) => void;
}) {
  return (
    <Dialog open={open} onClose={onClose} title={title} description={description}>
      {/* Mounted only while open, so the form starts fresh each time. */}
      <Fields fields={fields} submitLabel={submitLabel} pending={pending} onCancel={onClose} onSubmit={onSubmit} />
    </Dialog>
  );
}

/** A yes/no confirmation for actions that cannot be undone. */
export function ConfirmDialog({
  open,
  onClose,
  title,
  description,
  confirmLabel,
  pending,
  onConfirm,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description: string;
  confirmLabel: string;
  pending: boolean;
  onConfirm: () => void;
}) {
  return (
    <Dialog open={open} onClose={onClose} title={title} description={description}>
      <div className="flex justify-end gap-2">
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" loading={pending} onClick={onConfirm}>
          {confirmLabel}
        </Button>
      </div>
    </Dialog>
  );
}
