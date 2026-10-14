import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from sqlalchemy.orm import Session

from ledgerkit.errors import DomainError
from ledgerkit.models import Company
from ledgerkit.money import to_minor
from ledgerkit.services.company import fiscal_year_start

if TYPE_CHECKING:
    from ledgerkit.tools.registry import ToolRegistry


@dataclass(frozen=True)
class Actor:
    """Who is calling a tool. Adapters decide this; callers cannot choose it themselves."""

    type: Literal["user", "agent", "system"]
    id: str = "local"

    @property
    def label(self) -> str:
        return f"{self.type}:{self.id}"


@dataclass
class ToolContext:
    session: Session
    actor: Actor
    company: Company
    registry: "ToolRegistry"

    @property
    def today(self) -> dt.date:
        return dt.date.today()

    def minor(self, amount: Decimal) -> int:
        """Convert an amount in the company currency to integer minor units."""
        return to_minor(amount, self.company.currency_decimals)

    def period(self, date_from: dt.date | None, date_to: dt.date | None) -> tuple[dt.date, dt.date]:
        """Resolve an optional date range to the fiscal year to date."""
        date_to = date_to or self.today
        date_from = date_from or fiscal_year_start(self.company, date_to)
        if date_from > date_to:
            raise DomainError("invalid_input", f"date_from {date_from} is after date_to {date_to}.")
        return date_from, date_to
