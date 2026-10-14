import { IconContext } from "@phosphor-icons/react";
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router";
import { getMe, type Me, ToolError } from "./api/client";
import { useSession } from "./app/session";
import { ErrorState } from "./design/primitives";
import { ToastProvider } from "./design/Toast";
import { Accounts, AccountLedger, Journal, TrialBalance } from "./features/accounting/Accounting";
import { Items, TaxRates } from "./features/catalogue/Catalogue";
import { Console } from "./features/control/Console";
import { Approvals, AuditLog, Settings } from "./features/control/Control";
import { Leads, Pipeline } from "./features/crm/Crm";
import { Dashboard } from "./features/dashboard/Dashboard";
import { InvoiceDetail } from "./features/invoices/InvoiceDetail";
import { InvoiceForm } from "./features/invoices/InvoiceForm";
import { InvoiceList } from "./features/invoices/InvoiceList";
import { NotFound } from "./features/NotFound";
import { PartyDetail, PartyList } from "./features/parties/Parties";
import { Payments } from "./features/payments/Payments";
import { Reports } from "./features/reports/Reports";
import { SalesDocList } from "./features/sales/SalesDocs";
import { AppShell } from "./layout/AppShell";
import { SignIn } from "./layout/SignIn";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnWindowFocus: false,
      // A refusal from a tool is an answer, not a transient failure.
      retry: (failures, error) => !(error instanceof ToolError && error.code !== "network") && failures < 2,
    },
  },
});

function Screens() {
  return (
    <AppShell>
      <Routes>
        <Route index element={<Dashboard />} />
        <Route path="invoices" element={<InvoiceList kind="sales" />} />
        <Route path="invoices/new" element={<InvoiceForm kind="sales" />} />
        <Route path="invoices/:number" element={<InvoiceDetail kind="sales" />} />
        <Route path="bills" element={<InvoiceList kind="purchase" />} />
        <Route path="bills/new" element={<InvoiceForm kind="purchase" />} />
        <Route path="bills/:number" element={<InvoiceDetail kind="purchase" />} />
        <Route path="quotations" element={<SalesDocList kind="quotation" />} />
        <Route path="quotations/new" element={<InvoiceForm kind="quotation" />} />
        <Route path="orders" element={<SalesDocList kind="order" />} />
        <Route path="customers" element={<PartyList role="customer" />} />
        <Route path="customers/:id" element={<PartyDetail role="customer" />} />
        <Route path="vendors" element={<PartyList role="vendor" />} />
        <Route path="vendors/:id" element={<PartyDetail role="vendor" />} />
        <Route path="pipeline" element={<Pipeline />} />
        <Route path="leads" element={<Leads />} />
        <Route path="payments" element={<Payments />} />
        <Route path="reports/:report?" element={<Reports />} />
        <Route path="journal" element={<Journal />} />
        <Route path="accounts" element={<Accounts />} />
        <Route path="accounts/:code" element={<AccountLedger />} />
        <Route path="trial-balance" element={<TrialBalance />} />
        <Route path="items" element={<Items />} />
        <Route path="tax-rates" element={<TaxRates />} />
        <Route path="approvals" element={<Approvals />} />
        <Route path="audit" element={<AuditLog />} />
        <Route path="console" element={<Console />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AppShell>
  );
}

/** Decides between the sign-in screen and the app, based on what the server accepts. */
function Gate() {
  const { token, tokenRejected } = useSession();
  const me = useQuery<Me, ToolError>({ queryKey: ["me", token], queryFn: getMe });

  if (me.error?.code === "unauthorized" || (me.data?.auth_required && !token)) {
    return <SignIn rejected={tokenRejected} />;
  }
  if (me.error) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center">
        <ErrorState message={me.error.message} onRetry={() => void me.refetch()} />
      </div>
    );
  }
  if (!me.data) return null;
  return <Screens />;
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <IconContext.Provider value={{ weight: "light" }}>
        <BrowserRouter>
          <ToastProvider>
            <Gate />
          </ToastProvider>
        </BrowserRouter>
      </IconContext.Provider>
    </QueryClientProvider>
  );
}
