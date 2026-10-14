import { afterEach, describe, expect, it, vi } from "vitest";

const session = { token: "secret" as string | null, actAs: "user" as "user" | "agent" };
const rejectToken = vi.fn();
vi.mock("../app/session", () => ({ getSession: () => session, rejectToken: () => rejectToken() }));

const { callTool, PendingApproval, ToolError } = await import("./client");

function respond(status: number, body: unknown) {
  const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  rejectToken.mockClear();
  session.token = "secret";
  session.actAs = "user";
});

describe("callTool", () => {
  it("returns the data of a successful call and sends the token", async () => {
    const fetchMock = respond(200, { status: "ok", data: { number: "INV-00001" } });
    await expect(callTool("get_invoice", { number: "INV-00001" })).resolves.toEqual({ number: "INV-00001" });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/tools/get_invoice");
    expect(init?.body).toBe('{"number":"INV-00001"}');
    expect(init?.headers).toMatchObject({ Authorization: "Bearer secret" });
    expect(init?.headers).not.toHaveProperty("X-Ledgerkit-Actor");
  });

  it("asks to be treated as an agent when acting as one", async () => {
    session.actAs = "agent";
    const fetchMock = respond(200, { status: "ok", data: {} });
    await callTool("list_invoices");
    expect(fetchMock.mock.calls[0][1]?.headers).toMatchObject({ "X-Ledgerkit-Actor": "agent" });
  });

  it("throws PendingApproval when the action is held", async () => {
    respond(202, { status: "pending_approval", data: { pending_action_id: 7, message: "held" } });
    const error = await callTool("post_invoice", { number: "INV-00001" }).catch((e) => e);
    expect(error).toBeInstanceOf(PendingApproval);
    expect(error).toMatchObject({ actionId: 7, tool: "post_invoice" });
  });

  it("throws ToolError carrying the tool's own code and message", async () => {
    respond(400, { status: "error", error: { code: "unbalanced", message: "Entry JE-00002 is unbalanced by 12.50 USD." } });
    const error = await callTool("post_journal_entry", { entry_number: "JE-00002" }).catch((e) => e);
    expect(error).toBeInstanceOf(ToolError);
    expect(error).toMatchObject({ code: "unbalanced", message: "Entry JE-00002 is unbalanced by 12.50 USD." });
  });

  it("turns request validation errors into one readable message", async () => {
    respond(422, {
      detail: [
        { loc: ["body", "lines", 0, "quantity"], msg: "Input should be greater than 0" },
        { loc: ["body", "customer_id"], msg: "Field required" },
      ],
    });
    const error = await callTool("create_sales_invoice_draft", {}).catch((e) => e);
    expect(error).toMatchObject({
      code: "invalid_input",
      message: "lines.0.quantity: Input should be greater than 0; customer_id: Field required",
    });
  });

  it("forgets the token when the server refuses it", async () => {
    respond(401, { detail: "Missing or invalid bearer token." });
    const error = await callTool("list_invoices").catch((e) => e);
    expect(error).toMatchObject({ code: "unauthorized" });
    expect(rejectToken).toHaveBeenCalledOnce();
  });

  it("reports an unreachable server as a network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(callTool("list_invoices")).rejects.toMatchObject({ code: "network" });
  });
});
