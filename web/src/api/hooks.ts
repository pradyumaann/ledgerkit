import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "../app/session";
import { useToast } from "../design/Toast";
import type { Currency } from "../lib/money";
import { callTool, PendingApproval, ToolError } from "./client";
import type { CompanySettings } from "./types";

/** Read data with a tool. While the input changes, the previous result stays on screen. */
export function useTool<T>(name: string, input: object = {}, options: { enabled?: boolean } = {}) {
  const { actAs, token } = useSession();
  return useQuery<T, ToolError>({
    queryKey: [name, input, actAs, token],
    queryFn: () => callTool<T>(name, input),
    placeholderData: keepPreviousData,
    enabled: options.enabled ?? true,
  });
}

type MutationOptions<T> = {
  /** Shown when the tool runs, e.g. "Invoice posted". */
  success?: string | ((data: T) => string);
  onSuccess?: (data: T) => void;
  /** Called when the action was held for approval instead of running. */
  onHeld?: () => void;
};

/**
 * Change data with a tool. Handles the three outcomes in one place: success refreshes
 * every query, a held action tells the user it awaits approval, and a refusal shows the
 * tool's own message.
 */
export function useToolMutation<T = unknown, Input extends object = object>(
  name: string,
  options: MutationOptions<T> = {},
) {
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation<T, ToolError | PendingApproval, Input>({
    mutationFn: (input) => callTool<T>(name, input),
    onSuccess: (data) => {
      void queryClient.invalidateQueries();
      const message = typeof options.success === "function" ? options.success(data) : options.success;
      if (message) toast({ tone: "good", title: message });
      options.onSuccess?.(data);
    },
    onError: (error) => {
      if (error instanceof PendingApproval) {
        void queryClient.invalidateQueries();
        toast({
          tone: "warning",
          title: "Sent for approval",
          body: "As an agent you can prepare this, but a person has to approve it before it runs.",
          link: { to: "/approvals", label: "Open approvals" },
        });
        options.onHeld?.();
      } else {
        toast({ tone: "critical", title: "That did not go through", body: error.message });
      }
    },
  });
}

export function useCompany() {
  return useTool<CompanySettings>("get_company_settings");
}

export function useCurrency(): Currency {
  const { data } = useCompany();
  return { code: data?.base_currency ?? "USD", decimals: data?.currency_decimals ?? 2 };
}
