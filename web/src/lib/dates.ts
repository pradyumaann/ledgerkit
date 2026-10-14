/** Dates travel as "YYYY-MM-DD" strings and are handled in local time, never UTC. */

export function isoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

export function today(): string {
  return isoDate(new Date());
}

function parse(iso: string): Date {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return new Date(year, month - 1, day);
}

const dateFormat = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });
const monthFormat = new Intl.DateTimeFormat(undefined, { month: "short" });
const monthYearFormat = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" });

export function formatDate(iso: string | null | undefined): string {
  return iso ? dateFormat.format(parse(iso)) : "";
}

/** "2026-09" -> "Sep" */
export function formatMonth(yearMonth: string): string {
  return monthFormat.format(parse(`${yearMonth}-01`));
}

export function formatMonthYear(yearMonth: string): string {
  return monthYearFormat.format(parse(`${yearMonth}-01`));
}

export type Period = { date_from: string; date_to: string };
export type PeriodPreset = "6m" | "fytd" | "month" | "30d";

export const PERIOD_PRESETS: { id: PeriodPreset; label: string }[] = [
  { id: "6m", label: "Last 6 months" },
  { id: "fytd", label: "Fiscal year" },
  { id: "month", label: "This month" },
  { id: "30d", label: "Last 30 days" },
];

export function resolvePeriod(preset: PeriodPreset, fiscalStartMonth: number, now = new Date()): Period {
  const end = isoDate(now);
  switch (preset) {
    case "6m":
      return { date_from: isoDate(new Date(now.getFullYear(), now.getMonth() - 5, 1)), date_to: end };
    case "fytd": {
      const startMonth = fiscalStartMonth - 1;
      const year = now.getMonth() >= startMonth ? now.getFullYear() : now.getFullYear() - 1;
      return { date_from: isoDate(new Date(year, startMonth, 1)), date_to: end };
    }
    case "month":
      return { date_from: isoDate(new Date(now.getFullYear(), now.getMonth(), 1)), date_to: end };
    case "30d":
      return { date_from: isoDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 29)), date_to: end };
  }
}
