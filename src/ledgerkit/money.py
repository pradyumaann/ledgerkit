"""Money is stored and computed as integer minor units (e.g. cents). Never float."""

from decimal import ROUND_HALF_UP, Decimal

from ledgerkit.errors import DomainError


class Minor(int):
    """Marks an integer as an amount in minor units, so the tool layer renders it
    as a decimal string in the company currency."""


def to_minor(amount: Decimal, decimals: int) -> int:
    scaled = Decimal(amount).scaleb(decimals)
    if scaled != scaled.to_integral_value():
        raise DomainError(
            "invalid_amount",
            f"Amount {amount} has more than {decimals} decimal places, which the company currency does not allow.",
        )
    return int(scaled)


def from_minor(value: int, decimals: int) -> Decimal:
    return Decimal(int(value)).scaleb(-decimals)


def round_half_up(value: Decimal) -> int:
    return int(Decimal(value).to_integral_value(ROUND_HALF_UP))


def trim(value: Decimal) -> Decimal:
    """Drop trailing zeros without switching to exponent notation: 10.0000 -> 10, 2.5000 -> 2.5."""
    value = Decimal(value)
    return value.quantize(Decimal(1)) if value == value.to_integral_value() else value.normalize()


def fmt(value: int, company) -> str:
    return f"{from_minor(value, company.currency_decimals)} {company.base_currency}"


def pct(numerator: int, denominator: int) -> Decimal | None:
    """Percentage rounded to 2 places, or None when the denominator is zero."""
    if not denominator:
        return None
    return (Decimal(numerator) * 100 / Decimal(denominator)).quantize(Decimal("0.01"), ROUND_HALF_UP)
