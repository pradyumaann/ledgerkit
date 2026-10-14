import {
  ArrowClockwise,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle,
  CircleDashed,
  Clock,
  type Icon,
  MinusCircle,
  WarningCircle,
} from "@phosphor-icons/react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Link } from "react-router";
import { type Currency, moneyParts } from "../lib/money";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/* ----------------------------------------------------------------------------------
   Button. One solid primary per view; everything else is a translucent pill.
---------------------------------------------------------------------------------- */

type ButtonVariant = "primary" | "tint" | "quiet";

const BUTTON_BASE =
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-full font-medium " +
  "transition-[background-color,transform,opacity] duration-300 ease-out-soft active:scale-[0.98] " +
  "disabled:pointer-events-none disabled:opacity-50";

const BUTTON_VARIANT: Record<ButtonVariant, string> = {
  primary: "bg-primary text-on-primary hover:bg-[color-mix(in_oklab,var(--primary),black_10%)]",
  tint: "bg-primary-wash text-ink hover:bg-[color-mix(in_oklab,var(--primary)_18%,transparent)]",
  quiet: "bg-wash text-ink hover:bg-[color-mix(in_oklab,var(--ink)_9%,transparent)]",
};

const BUTTON_SIZE = { md: "h-9 px-4", sm: "h-8 px-3 text-[13px]" };

type ButtonProps = {
  variant?: ButtonVariant;
  size?: keyof typeof BUTTON_SIZE;
  icon?: Icon;
  /** An icon set in its own disc at the trailing edge, for the main action on a screen. */
  trailing?: Icon;
  /** Renders a link styled as a button. */
  to?: string;
  loading?: boolean;
  children: ReactNode;
} & ButtonHTMLAttributes<HTMLButtonElement>;

export function Button({
  variant = "quiet",
  size = "md",
  icon: IconGlyph,
  trailing: Trailing,
  to,
  loading,
  children,
  className,
  ...rest
}: ButtonProps) {
  const classes = cx("group", BUTTON_BASE, BUTTON_VARIANT[variant], BUTTON_SIZE[size], Trailing && "pr-1.5", className);
  const content = (
    <>
      {IconGlyph && <IconGlyph size={16} className={loading ? "animate-spin" : undefined} />}
      {children}
      {Trailing && (
        <span className="flex size-6 items-center justify-center rounded-full bg-white/20 transition-transform duration-500 ease-out-soft group-hover:translate-x-0.5">
          <Trailing size={14} weight="bold" />
        </span>
      )}
    </>
  );
  if (to) {
    return (
      <Link to={to} className={classes}>
        {content}
      </Link>
    );
  }
  return (
    <button type="button" className={classes} disabled={loading || rest.disabled} {...rest}>
      {content}
    </button>
  );
}

/* ----------------------------------------------------------------------------------
   Card. A surface set inside a slightly recessed tray, so panels read as objects
   resting on the canvas without borders or heavy shadows.
---------------------------------------------------------------------------------- */

export function Card({
  children,
  className,
  tone = "surface",
}: {
  children: ReactNode;
  className?: string;
  tone?: "surface" | "lavender" | "night";
}) {
  const inner = { surface: "bg-surface shadow-card", lavender: "bg-lavender", night: "night shadow-card" }[tone];
  return (
    <section className={cx("rounded-[22px] bg-wash p-1.5 ring-1 ring-line", className)}>
      <div className={cx("h-full overflow-hidden rounded-[16px]", inner)}>{children}</div>
    </section>
  );
}

export function CardHeader({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 px-5 pt-5">
      <div>
        <h2 className="text-[15px] text-ink">{title}</h2>
        {hint && <p className="mt-0.5 text-[13px] text-ink-3">{hint}</p>}
      </div>
      {action}
    </div>
  );
}

/* ----------------------------------------------------------------------------------
   Status badge. The label stays in ink; a small icon carries the state colour,
   so state is never signalled by colour alone.
---------------------------------------------------------------------------------- */

type Tone = "good" | "warning" | "critical" | "neutral" | "muted";

const STATUS: Record<string, { label: string; tone: Tone; icon: Icon }> = {
  draft: { label: "Draft", tone: "muted", icon: CircleDashed },
  posted: { label: "Posted", tone: "neutral", icon: CheckCircle },
  void: { label: "Void", tone: "muted", icon: MinusCircle },
  unpaid: { label: "Unpaid", tone: "warning", icon: Clock },
  partial: { label: "Part paid", tone: "warning", icon: Clock },
  paid: { label: "Paid", tone: "good", icon: CheckCircle },
  overdue: { label: "Overdue", tone: "critical", icon: WarningCircle },
  pending: { label: "Pending", tone: "warning", icon: Clock },
  approved: { label: "Approved", tone: "good", icon: CheckCircle },
  rejected: { label: "Rejected", tone: "muted", icon: MinusCircle },
  accepted: { label: "Accepted", tone: "good", icon: CheckCircle },
  open: { label: "Open", tone: "warning", icon: Clock },
  invoiced: { label: "Invoiced", tone: "good", icon: CheckCircle },
  cancelled: { label: "Cancelled", tone: "muted", icon: MinusCircle },
  new: { label: "New", tone: "neutral", icon: CircleDashed },
  qualified: { label: "Qualified", tone: "warning", icon: Clock },
  converted: { label: "Converted", tone: "good", icon: CheckCircle },
  disqualified: { label: "Disqualified", tone: "muted", icon: MinusCircle },
  won: { label: "Won", tone: "good", icon: CheckCircle },
  lost: { label: "Lost", tone: "muted", icon: MinusCircle },
  ok: { label: "Succeeded", tone: "good", icon: CheckCircle },
  error: { label: "Refused", tone: "critical", icon: WarningCircle },
  pending_approval: { label: "Held for approval", tone: "warning", icon: Clock },
  balanced: { label: "Balanced", tone: "good", icon: CheckCircle },
  unbalanced: { label: "Out of balance", tone: "critical", icon: WarningCircle },
};

const TONE_ICON: Record<Tone, string> = {
  good: "text-good",
  warning: "text-warning",
  critical: "text-critical",
  neutral: "text-primary-ink",
  muted: "text-ink-3",
};

export function StatusBadge({ status }: { status: string }) {
  const known = STATUS[status] ?? { label: status, tone: "muted" as Tone, icon: CircleDashed };
  const Glyph = known.icon;
  return (
    <span className="inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-full bg-wash pl-1.5 pr-2.5 text-[13px] text-ink">
      <Glyph size={15} weight="fill" className={TONE_ICON[known.tone]} />
      {known.label}
    </span>
  );
}

/* ----------------------------------------------------------------------------------
   Figures and identity marks
---------------------------------------------------------------------------------- */

/** A large amount with its minor units set smaller and quieter. */
export function Amount({ value, currency, className }: { value: string; currency: Currency; className?: string }) {
  const { main, minor } = moneyParts(value, currency);
  return (
    <span className={cx("whitespace-nowrap", className)}>
      {main}
      {minor && <span className="text-[0.55em] text-ink-3">{minor}</span>}
    </span>
  );
}

/** Initials in a disc, so rows of names are easier to scan. */
export function Monogram({ name }: { name: string }) {
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? "")
    .join("");
  return (
    <span
      aria-hidden
      className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary-wash text-[11px] font-medium text-primary-ink"
    >
      {initials}
    </span>
  );
}

/**
 * Change against the previous period. The arrow shows direction and its colour shows
 * whether that direction is good; the figure itself stays in ink.
 */
export function Delta({ pct, upIsGood = true }: { pct: string | null | undefined; upIsGood?: boolean }) {
  if (pct == null) return null;
  const up = !pct.startsWith("-");
  const Glyph = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className="inline-flex items-center gap-1 whitespace-nowrap text-[13px]">
      <Glyph size={14} weight="bold" className={up === upIsGood ? "text-good" : "text-critical"} />
      <span className="figures text-ink">{pct.replace("-", "")}%</span>
      <span className="text-ink-3">{up ? "up" : "down"} on the previous period</span>
    </span>
  );
}

/* ----------------------------------------------------------------------------------
   Page furniture and states
---------------------------------------------------------------------------------- */

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        <h1 className="text-[30px] leading-tight text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-[65ch] text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex min-w-0 max-w-full flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Segmented<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { id: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="inline-flex max-w-full gap-1 overflow-x-auto rounded-full bg-wash p-1 [scrollbar-width:none]">
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={option.id === value}
          onClick={() => onChange(option.id)}
          className={cx(
            "h-7 whitespace-nowrap rounded-full px-3 text-[13px] transition-colors duration-300 ease-out-soft",
            option.id === value ? "bg-surface font-medium text-ink shadow-float" : "text-ink-2 hover:text-ink",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** Structured data shown as formatted JSON, for tool inputs and results. */
export function Json({ value, className }: { value: unknown; className?: string }) {
  return (
    <pre className={cx("overflow-x-auto rounded-xl bg-wash p-3 font-mono text-[12.5px] leading-relaxed text-ink-2", className)}>
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cx("animate-pulse rounded-md bg-wash", className)} />;
}

export function EmptyState({
  icon: Glyph,
  title,
  body,
  action,
}: {
  icon: Icon;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <span className="flex size-11 items-center justify-center rounded-full bg-primary-wash text-primary-ink">
        <Glyph size={22} />
      </span>
      <h3 className="mt-4 text-[15px] text-ink">{title}</h3>
      <p className="mt-1 max-w-[42ch] text-ink-2">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center" role="alert">
      <WarningCircle size={24} weight="fill" className="text-critical" />
      <h3 className="mt-3 text-[15px] text-ink">This could not be loaded</h3>
      <p className="mt-1 max-w-[52ch] text-ink-2">{message}</p>
      {onRetry && (
        <Button className="mt-5" icon={ArrowClockwise} onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
