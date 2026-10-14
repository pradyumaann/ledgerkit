import { CaretDown } from "@phosphor-icons/react";
import { type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes, useId } from "react";
import { cx } from "./primitives";

const CONTROL =
  "w-full rounded-[10px] bg-surface text-ink ring-1 ring-line transition-shadow duration-200 " +
  "placeholder:text-ink-3 hover:ring-[color-mix(in_oklab,var(--ink)_22%,transparent)] " +
  "focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-60";

/** Label above, optional hint, error below. Pass the generated id to the control. */
export function Field({
  label,
  hint,
  error,
  className,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  className?: string;
  children: (id: string) => ReactNode;
}) {
  const id = useId();
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-[13px] text-ink-2">
        {label}
      </label>
      {children(id)}
      {hint && !error && <p className="text-[12.5px] text-ink-3">{hint}</p>}
      {error && (
        <p className="text-[12.5px] text-critical" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cx(CONTROL, "h-9 px-3", className)} {...rest} />;
}

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cx(CONTROL, "min-h-20 px-3 py-2", className)} {...rest} />;
}

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className={cx("relative", className)}>
      <select className={cx(CONTROL, "h-9 appearance-none pl-3 pr-8")} {...rest}>
        {children}
      </select>
      <CaretDown size={14} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-3" />
    </div>
  );
}
