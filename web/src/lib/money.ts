/**
 * Amounts arrive from the API as exact decimal strings ("1250.00").
 * They are formatted as strings and, where the UI must do arithmetic (a draft's
 * running subtotal), converted to integer minor units. They are never parsed to float.
 */

export type Currency = { code: string; decimals: number };

const formatters = new Map<string, Intl.NumberFormat>();

function formatter(currency: Currency, compact: boolean): Intl.NumberFormat {
  const key = `${currency.code}:${currency.decimals}:${compact}`;
  let found = formatters.get(key);
  if (!found) {
    found = new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: currency.code,
      minimumFractionDigits: compact ? 0 : currency.decimals,
      maximumFractionDigits: compact ? 1 : currency.decimals,
      notation: compact ? "compact" : "standard",
    });
    formatters.set(key, found);
  }
  return found;
}

/** "1250.00" -> "$1,250.00". Intl formats decimal strings exactly. */
export function formatMoney(amount: string | null | undefined, currency: Currency, compact = false): string {
  if (amount == null || amount === "") return "";
  // The string overload of format() is exact; the cast is only for older TypeScript lib typings.
  return formatter(currency, compact).format(amount as unknown as number);
}

/** "1250.00" -> { main: "$1,250", minor: ".00" }, so large figures can de-emphasise the cents. */
export function moneyParts(amount: string, currency: Currency): { main: string; minor: string } {
  const parts = formatter(currency, false).formatToParts(amount as unknown as number);
  const split = parts.findIndex((part) => part.type === "decimal");
  if (split === -1) return { main: parts.map((part) => part.value).join(""), minor: "" };
  const join = (slice: Intl.NumberFormatPart[]) => slice.map((part) => part.value).join("");
  return { main: join(parts.slice(0, split)), minor: join(parts.slice(split)) };
}

export function formatPercent(value: string | null | undefined): string {
  return value == null ? "n/a" : `${value}%`;
}

export function isNegative(amount: string): boolean {
  return amount.trim().startsWith("-") && !isZero(amount);
}

export function isZero(amount: string): boolean {
  return /^-?0*(\.0*)?$/.test(amount.trim());
}

/** "12.5" with 2 decimals -> 1250n. Throws on anything that is not a plain decimal. */
export function toMinor(amount: string, decimals: number): bigint {
  const match = /^(-?)(\d*)(?:\.(\d*))?$/.exec(amount.trim());
  if (!match || (match[2] === "" && !match[3])) throw new Error(`Not a number: ${amount}`);
  const [, sign, whole, fraction = ""] = match;
  if (fraction.length > decimals && /[1-9]/.test(fraction.slice(decimals))) {
    throw new Error(`${amount} has more than ${decimals} decimal places`);
  }
  const digits = (whole || "0") + fraction.slice(0, decimals).padEnd(decimals, "0");
  return BigInt(digits) * (sign ? -1n : 1n);
}

export function fromMinor(minor: bigint, decimals: number): string {
  const negative = minor < 0n;
  const digits = (negative ? -minor : minor).toString().padStart(decimals + 1, "0");
  const whole = digits.slice(0, digits.length - decimals);
  const fraction = decimals ? `.${digits.slice(-decimals)}` : "";
  return `${negative ? "-" : ""}${whole}${fraction}`;
}

/** Sum decimal strings exactly. */
export function sumMoney(amounts: string[], decimals: number): string {
  return fromMinor(
    amounts.reduce((total, amount) => total + toMinor(amount, decimals), 0n),
    decimals,
  );
}

const QUANTITY_SCALE = 4;

/** quantity x unit price, rounded half up to the currency's minor unit, as the server does. */
export function lineTotal(quantity: string, unitPrice: string, decimals: number): string | null {
  try {
    const product = toMinor(quantity, QUANTITY_SCALE) * toMinor(unitPrice, decimals);
    const divisor = 10n ** BigInt(QUANTITY_SCALE);
    const rounded = (product * 2n + divisor) / (divisor * 2n);
    return fromMinor(rounded, decimals);
  } catch {
    return null;
  }
}
