import datetime as dt
from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ledgerkit.models.account import Account
from ledgerkit.models.base import Base, utcnow
from ledgerkit.models.invoice import Invoice
from ledgerkit.models.party import Party


class PaymentDirection(StrEnum):
    INBOUND = "inbound"  # money received from a customer
    OUTBOUND = "outbound"  # money paid to a vendor


class PaymentStatus(StrEnum):
    POSTED = "posted"
    VOID = "void"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    direction: Mapped[str] = mapped_column(String(10))
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), index=True)
    payment_date: Mapped[dt.date] = mapped_column(index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    method: Mapped[str | None] = mapped_column(String(50), default=None)
    reference: Mapped[str | None] = mapped_column(String(100), default=None)
    status: Mapped[str] = mapped_column(String(10), default=PaymentStatus.POSTED)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"), default=None)
    created_by: Mapped[str | None] = mapped_column(String(100), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)

    party: Mapped[Party] = relationship()
    bank_account: Mapped[Account] = relationship()
    allocations: Mapped[list["PaymentAllocation"]] = relationship(
        back_populates="payment", cascade="all, delete-orphan", order_by="PaymentAllocation.id"
    )

    @property
    def unallocated(self) -> int:
        return self.amount - sum(a.amount for a in self.allocations)


class PaymentAllocation(Base):
    __tablename__ = "payment_allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)

    payment: Mapped[Payment] = relationship(back_populates="allocations")
    invoice: Mapped[Invoice] = relationship()
