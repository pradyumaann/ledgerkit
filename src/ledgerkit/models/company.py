import datetime as dt

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ledgerkit.models.base import Base


class Company(Base):
    """Single row: one database holds one company's books."""

    __tablename__ = "company"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    base_currency: Mapped[str] = mapped_column(String(3), default="USD")
    currency_decimals: Mapped[int] = mapped_column(default=2)
    fiscal_year_start_month: Mapped[int] = mapped_column(default=1)
    # Entries dated on or before this date can no longer be posted.
    lock_date: Mapped[dt.date | None] = mapped_column(default=None)


class Sequence(Base):
    __tablename__ = "sequences"

    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    next_value: Mapped[int] = mapped_column(default=1)
