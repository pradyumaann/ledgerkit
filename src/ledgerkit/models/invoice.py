import datetime as dt
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ledgerkit.models.account import Account
from ledgerkit.models.base import Base, ScaledDecimal, utcnow
from ledgerkit.models.item import Item, TaxRate
from ledgerkit.models.journal import JournalEntry
from ledgerkit.models.party import Party


class InvoiceKind(StrEnum):
    SALES = "sales"  # invoice we issue to a customer
    PURCHASE = "purchase"  # bill we receive from a vendor


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"
    VOID = "void"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), index=True)
    number: Mapped[str] = mapped_column(String(30), unique=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), index=True)
    invoice_date: Mapped[dt.date] = mapped_column(index=True)
    due_date: Mapped[dt.date] = mapped_column()
    status: Mapped[str] = mapped_column(String(10), default=InvoiceStatus.DRAFT)
    subtotal: Mapped[int] = mapped_column(BigInteger, default=0)
    tax_total: Mapped[int] = mapped_column(BigInteger, default=0)
    total: Mapped[int] = mapped_column(BigInteger, default=0)
    amount_paid: Mapped[int] = mapped_column(BigInteger, default=0)
    # The vendor's own bill number, or a customer PO reference.
    reference: Mapped[str | None] = mapped_column(String(100), default=None)
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)
    sales_order_id: Mapped[int | None] = mapped_column(ForeignKey("sales_docs.id"), default=None)
    journal_entry_id: Mapped[int | None] = mapped_column(ForeignKey("journal_entries.id"), default=None)
    created_by: Mapped[str | None] = mapped_column(String(100), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)

    party: Mapped[Party] = relationship()
    journal_entry: Mapped[JournalEntry | None] = relationship()
    lines: Mapped[list["InvoiceLine"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceLine.id"
    )

    @property
    def outstanding(self) -> int:
        return self.total - self.amount_paid if self.status == InvoiceStatus.POSTED else 0

    @property
    def payment_status(self) -> str:
        if self.status != InvoiceStatus.POSTED:
            return "n/a"
        if self.amount_paid >= self.total:
            return "paid"
        return "partial" if self.amount_paid else "unpaid"


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), index=True, default=None)
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal] = mapped_column(ScaledDecimal(4))
    unit_price: Mapped[int] = mapped_column(BigInteger)
    # Income account on a sales invoice; expense or asset account on a vendor bill.
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    tax_rate_id: Mapped[int | None] = mapped_column(ForeignKey("tax_rates.id"), default=None)
    line_subtotal: Mapped[int] = mapped_column(BigInteger)
    tax_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    # Sales invoices only: the item's standard cost at the time the line was created.
    unit_cost: Mapped[int] = mapped_column(BigInteger, default=0)
    cost_total: Mapped[int] = mapped_column(BigInteger, default=0)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")
    item: Mapped[Item | None] = relationship()
    account: Mapped[Account] = relationship()
    tax_rate: Mapped[TaxRate | None] = relationship()
