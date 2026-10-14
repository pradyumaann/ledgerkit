import { CheckCircle, Hourglass, WarningCircle, X } from "@phosphor-icons/react";
import { createContext, type ReactNode, useCallback, useContext, useRef, useState } from "react";
import { Link } from "react-router";

type Tone = "good" | "warning" | "critical";
export type ToastInput = { tone: Tone; title: string; body?: string; link?: { to: string; label: string } };
type ToastItem = ToastInput & { id: number };

const ToastContext = createContext<(toast: ToastInput) => void>(() => {});

export function useToast() {
  return useContext(ToastContext);
}

const ICONS = { good: CheckCircle, warning: Hourglass, critical: WarningCircle };
const ICON_COLOR = { good: "text-good", warning: "text-warning", critical: "text-critical" };
const LIFETIME_MS = { good: 4000, warning: 9000, critical: 9000 };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((t) => t.id !== id)), []);

  const push = useCallback(
    (toast: ToastInput) => {
      const id = nextId.current++;
      setToasts((current) => [...current.slice(-3), { ...toast, id }]);
      window.setTimeout(() => dismiss(id), LIFETIME_MS[toast.tone]);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2" role="status">
        {toasts.map((toast) => {
          const Icon = ICONS[toast.tone];
          return (
            <div
              key={toast.id}
              className="pointer-events-auto flex w-full max-w-sm animate-rise items-start gap-3 rounded-2xl bg-surface p-4 shadow-float ring-1 ring-line"
            >
              <Icon size={20} weight="fill" className={`mt-px shrink-0 ${ICON_COLOR[toast.tone]}`} />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-ink">{toast.title}</p>
                {toast.body && <p className="mt-0.5 text-ink-2">{toast.body}</p>}
                {toast.link && (
                  <Link
                    to={toast.link.to}
                    onClick={() => dismiss(toast.id)}
                    className="mt-1.5 inline-block font-medium text-primary-ink underline-offset-4 hover:underline"
                  >
                    {toast.link.label}
                  </Link>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismiss(toast.id)}
                aria-label="Dismiss"
                className="-m-1 rounded-full p-1 text-ink-3 transition-colors hover:bg-wash hover:text-ink"
              >
                <X size={16} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
