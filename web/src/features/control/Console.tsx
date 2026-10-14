import { MagnifyingGlass, Play } from "@phosphor-icons/react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { callTool, getTools, PendingApproval, ToolError, type ToolSchema } from "../../api/client";
import { useSession } from "../../app/session";
import { Field, Input, Select, Textarea } from "../../design/Form";
import { Button, Card, cx, ErrorState, Json, PageHeader, Skeleton, StatusBadge } from "../../design/primitives";
import { buildInput, fieldsFromSchema, type SchemaField } from "../../lib/schema";

type Outcome = { status: "ok" | "error" | "pending_approval"; body: unknown };

function access(tool: ToolSchema): string {
  if (tool.requires_approval) return "Needs approval from agents";
  return tool.mutating ? "Changes data" : "Read only";
}

function ToolForm({ tool }: { tool: ToolSchema }) {
  const queryClient = useQueryClient();
  const fields = useMemo(() => fieldsFromSchema(tool.input_schema), [tool]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    setValues(Object.fromEntries(fields.map((field) => [field.name, field.initial])));
    setErrors({});
    setOutcome(null);
  }, [fields]);

  async function run(event: FormEvent) {
    event.preventDefault();
    const built = buildInput(fields, values);
    setErrors(built.errors);
    if (Object.keys(built.errors).length > 0) return;
    setRunning(true);
    try {
      setOutcome({ status: "ok", body: await callTool(tool.name, built.input) });
    } catch (error) {
      if (error instanceof PendingApproval) {
        setOutcome({ status: "pending_approval", body: { pending_action_id: error.actionId } });
      } else if (error instanceof ToolError) {
        setOutcome({ status: "error", body: { code: error.code, message: error.message, details: error.details } });
      } else {
        throw error;
      }
    } finally {
      setRunning(false);
      if (tool.mutating) void queryClient.invalidateQueries();
    }
  }

  const control = (field: SchemaField, id: string) => {
    const common = { id, value: values[field.name] ?? "", "aria-invalid": Boolean(errors[field.name]) };
    const set = (value: string) => setValues((current) => ({ ...current, [field.name]: value }));
    if (field.kind === "enum" || field.kind === "boolean") {
      const options = field.kind === "boolean" ? ["true", "false"] : (field.options ?? []);
      return (
        <Select {...common} onChange={(event) => set(event.target.value)}>
          <option value="">{field.required ? "Choose one" : "Default"}</option>
          {options.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </Select>
      );
    }
    if (field.kind === "json") {
      return <Textarea {...common} spellCheck={false} className="font-mono text-[12.5px]" onChange={(event) => set(event.target.value)} />;
    }
    return (
      <Input
        {...common}
        type={field.kind === "date" ? "date" : "text"}
        inputMode={field.kind === "integer" ? "numeric" : field.kind === "number" ? "decimal" : undefined}
        onChange={(event) => set(event.target.value)}
      />
    );
  };

  return (
    <div className="p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h2 className="font-mono text-[16px] text-ink">{tool.name}</h2>
        <span className="rounded-full bg-wash px-2.5 py-0.5 text-[12.5px] text-ink-2">{access(tool)}</span>
      </div>
      <p className="mt-2 max-w-[75ch] text-ink-2">{tool.description}</p>
      <form onSubmit={run} className="mt-6 grid gap-4 sm:grid-cols-2">
        {fields.length === 0 && <p className="text-ink-3 sm:col-span-2">This tool takes no input.</p>}
        {fields.map((field) => (
          <Field
            key={field.name}
            label={field.required ? `${field.name} (required)` : field.name}
            hint={field.description}
            error={errors[field.name]}
            className={cx(field.kind === "json" && "sm:col-span-2")}
          >
            {(id) => control(field, id)}
          </Field>
        ))}
        <div className="sm:col-span-2">
          <Button type="submit" variant="primary" icon={Play} loading={running}>
            Run tool
          </Button>
        </div>
      </form>
      {outcome && (
        <div className="mt-6 border-t border-line pt-5" aria-live="polite">
          <StatusBadge status={outcome.status} />
          <Json value={outcome.body} className="mt-3 max-h-[28rem]" />
        </div>
      )}
    </div>
  );
}

export function Console() {
  const { token, actAs } = useSession();
  const tools = useQuery<ToolSchema[], ToolError>({ queryKey: ["tools", token], queryFn: getTools });
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState("profit_and_loss");
  const visible = tools.data?.filter((tool) => tool.name.includes(search.trim().toLowerCase().replaceAll(" ", "_")));
  const tool = tools.data?.find((candidate) => candidate.name === selected);

  return (
    <div className="stagger space-y-6">
      <PageHeader
        title="Tool console"
        description={`Every screen in this app is built from these tools, and so is anything an AI agent does. Run any of them directly${actAs === "agent" ? ", as an agent" : ""}.`}
      />
      {tools.error ? (
        <ErrorState message={tools.error.message} onRetry={() => void tools.refetch()} />
      ) : (
        <div className="grid items-start gap-4 lg:grid-cols-12">
          <Card className="lg:col-span-4">
            <div className="p-3">
              <div className="relative">
                <MagnifyingGlass size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" />
                <Input
                  aria-label="Search tools"
                  placeholder={`Search ${tools.data?.length ?? ""} tools`}
                  className="pl-9"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </div>
              <ul className="mt-2 max-h-[34rem] overflow-y-auto [scrollbar-width:thin]">
                {!tools.data && <Skeleton className="h-64" />}
                {visible?.map((candidate) => (
                  <li key={candidate.name}>
                    <button
                      type="button"
                      aria-current={candidate.name === selected}
                      onClick={() => setSelected(candidate.name)}
                      className={cx(
                        "flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left font-mono text-[12.5px] transition-colors duration-200",
                        candidate.name === selected ? "bg-primary-wash text-ink" : "text-ink-2 hover:bg-tint hover:text-ink",
                      )}
                    >
                      <span className="min-w-0 flex-1 truncate">{candidate.name}</span>
                      {candidate.mutating && (
                        <span className="font-sans text-[11.5px] text-ink-3">{candidate.requires_approval ? "approval" : "write"}</span>
                      )}
                    </button>
                  </li>
                ))}
                {visible?.length === 0 && <li className="px-3 py-6 text-center text-ink-3">No tool matches.</li>}
              </ul>
            </div>
          </Card>
          <Card className="lg:col-span-8">{tool ? <ToolForm tool={tool} /> : <Skeleton className="m-6 h-64" />}</Card>
        </div>
      )}
    </div>
  );
}
