import { getSession, rejectToken } from "../app/session";
import type { JsonSchema } from "../lib/schema";

/** A tool refused the request: a business rule, a missing record, or invalid input. */
export class ToolError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = "ToolError";
  }
}

/** The tool was not run: it is waiting for a human to approve it. */
export class PendingApproval extends Error {
  constructor(
    readonly actionId: number,
    readonly tool: string,
  ) {
    super(`${tool} is waiting for approval`);
    this.name = "PendingApproval";
  }
}

function headers(): HeadersInit {
  const { token, actAs } = getSession();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(actAs === "agent" ? { "X-Ledgerkit-Actor": "agent" } : {}),
  };
}

type ValidationIssue = { loc: (string | number)[]; msg: string };

async function parse(response: Response): Promise<unknown> {
  let body: any;
  try {
    body = await response.json();
  } catch {
    throw new ToolError("bad_response", `The server returned an unreadable response (HTTP ${response.status}).`);
  }
  if (response.status === 401) {
    rejectToken();
    throw new ToolError("unauthorized", "Sign in with an access token to continue.");
  }
  if (response.status === 422 && Array.isArray(body?.detail)) {
    const issues = (body.detail as ValidationIssue[])
      .map((issue) => `${issue.loc.filter((part) => part !== "body").join(".") || "input"}: ${issue.msg}`)
      .join("; ");
    throw new ToolError("invalid_input", issues, body.detail);
  }
  return body;
}

/** Call a tool. Resolves with its data, or throws ToolError or PendingApproval. */
export async function callTool<T>(name: string, input: object = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/tools/${name}`, { method: "POST", headers: headers(), body: JSON.stringify(input) });
  } catch {
    throw new ToolError("network", "Could not reach the ledgerkit server. Check that it is running.");
  }
  const body: any = await parse(response);
  if (body?.status === "ok") return body.data as T;
  if (body?.status === "pending_approval") throw new PendingApproval(body.data.pending_action_id, name);
  if (body?.status === "error") throw new ToolError(body.error.code, body.error.message, body.error.details);
  throw new ToolError("bad_response", body?.detail ?? `Unexpected response (HTTP ${response.status}).`);
}

export type Me = { actor: "user" | "agent"; auth_required: boolean };

export type ToolSchema = {
  name: string;
  description: string;
  input_schema: JsonSchema;
  mutating: boolean;
  requires_approval: boolean;
};

async function get<T>(path: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { headers: headers() });
  } catch {
    throw new ToolError("network", "Could not reach the ledgerkit server. Check that it is running.");
  }
  return (await parse(response)) as T;
}

export const getTools = () => get<ToolSchema[]>("/api/tools");

export const getMe = () => get<Me>("/api/me");
