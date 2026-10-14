import { describe, expect, it } from "vitest";
import { formatMoney, fromMinor, isNegative, isZero, lineTotal, moneyParts, sumMoney, toMinor } from "./money";

const USD = { code: "USD", decimals: 2 };
const JPY = { code: "JPY", decimals: 0 };

describe("toMinor and fromMinor", () => {
  it("converts exactly in both directions", () => {
    expect(toMinor("1250.00", 2)).toBe(125000n);
    expect(toMinor("12.5", 2)).toBe(1250n);
    expect(toMinor(".5", 2)).toBe(50n);
    expect(toMinor("-0.07", 2)).toBe(-7n);
    expect(toMinor("300", 0)).toBe(300n);
    expect(fromMinor(125000n, 2)).toBe("1250.00");
    expect(fromMinor(-7n, 2)).toBe("-0.07");
    expect(fromMinor(300n, 0)).toBe("300");
  });

  it("keeps amounts a float would get wrong", () => {
    // 0.1 + 0.2 is 0.30000000000000004 in floating point.
    expect(sumMoney(["0.10", "0.20"], 2)).toBe("0.30");
    expect(sumMoney(["9007199254740993.01", "0.01"], 2)).toBe("9007199254740993.02");
  });

  it("rejects input that is not a plain decimal or has too many places", () => {
    expect(() => toMinor("abc", 2)).toThrow();
    expect(() => toMinor("", 2)).toThrow();
    expect(() => toMinor("1,000", 2)).toThrow();
    expect(() => toMinor("10.005", 2)).toThrow();
    expect(toMinor("10.500", 2)).toBe(1050n); // trailing zeros are harmless
  });
});

describe("lineTotal", () => {
  it("multiplies quantity by price and rounds half up, as the server does", () => {
    expect(lineTotal("3", "100.00", 2)).toBe("300.00");
    expect(lineTotal("2.5", "150", 2)).toBe("375.00");
    expect(lineTotal("0.3333", "10.00", 2)).toBe("3.33");
    expect(lineTotal("1.5", "0.01", 2)).toBe("0.02"); // 0.015 rounds up
    expect(lineTotal("7", "33", 0)).toBe("231");
  });

  it("returns null while the user is still typing something invalid", () => {
    expect(lineTotal("", "10", 2)).toBeNull();
    expect(lineTotal("two", "10", 2)).toBeNull();
  });
});

describe("formatting", () => {
  it("formats decimal strings without passing through a float", () => {
    expect(formatMoney("1250.00", USD)).toBe("$1,250.00");
    expect(formatMoney("-42.50", USD)).toBe("-$42.50");
    // Beyond what a float can hold. Digit grouping depends on the locale, so compare the digits.
    expect(formatMoney("9007199254740993.01", USD).replaceAll(",", "")).toBe("$9007199254740993.01");
    expect(formatMoney(null, USD)).toBe("");
  });

  it("splits the minor units off for large figures", () => {
    expect(moneyParts("19520.00", USD)).toEqual({ main: "$19,520", minor: ".00" });
    expect(moneyParts("1500", JPY).minor).toBe("");
  });

  it("recognises zero and negative amounts", () => {
    expect(isZero("0.00")).toBe(true);
    expect(isZero("-0.00")).toBe(true);
    expect(isZero("0.01")).toBe(false);
    expect(isNegative("-0.01")).toBe(true);
    expect(isNegative("-0.00")).toBe(false);
  });
});
