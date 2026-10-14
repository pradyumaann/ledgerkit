import datetime as dt

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ledgerkit.models.base import Base, utcnow


class Party(Base):
    """A customer, a vendor, or both."""

    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    is_customer: Mapped[bool] = mapped_column(default=False)
    is_vendor: Mapped[bool] = mapped_column(default=False)
    email: Mapped[str | None] = mapped_column(String(200), default=None)
    phone: Mapped[str | None] = mapped_column(String(50), default=None)
    address: Mapped[str | None] = mapped_column(String(500), default=None)
    tax_id: Mapped[str | None] = mapped_column(String(50), default=None)
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)

    contacts: Mapped[list["Contact"]] = relationship(back_populates="party", cascade="all, delete-orphan")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200), default=None)
    phone: Mapped[str | None] = mapped_column(String(50), default=None)
    role: Mapped[str | None] = mapped_column(String(100), default=None)

    party: Mapped[Party] = relationship(back_populates="contacts")
