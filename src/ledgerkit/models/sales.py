import datetime as dt
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ledgerkit.models.base import Base, ScaledDecimal, utcnow
from ledgerkit.models.item import Item, TaxRate
from ledgerkit.models.party import Party


class LeadStatus(StrEnum):
    NEW = "new"
    QUALIFIED = "qualified"
    DISQUALIFIED = "disqualified"
    CONVERTED = "converted"


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str | None] = mapped_column(String(200), default=None)
    email: Mapped[str | None] = mapped_column(String(200), default=None)
    phone: Mapped[str | None] = mapped_column(String(50), default=None)
    source: Mapped[str | None] = mapped_column(String(100), default=None)
    status: Mapped[str] = mapped_column(String(20), default=LeadStatus.NEW)
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)


class OpportunityStage(StrEnum):
    PROSPECTING = "prospecting"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    WON = "won"
    LOST = "lost"


OPEN_STAGES = (OpportunityStage.PROSPECTING, OpportunityStage.PROPOSAL, OpportunityStage.NEGOTIATION)


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    party_id: Mapped[int | None] = mapped_column(ForeignKey("parties.id"), default=None)
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), default=None)
    stage: Mapped[str] = mapped_column(String(20), default=OpportunityStage.PROSPECTING)
    expected_value: Mapped[int] = mapped_column(BigInteger, default=0)
    probability_pct: Mapped[int] = mapped_column(default=10)
    expected_close: Mapped[dt.date | None] = mapped_column(default=None)
    lost_reason: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)
    closed_at: Mapped[dt.datetime | None] = mapped_column(default=None)

    party: Mapped[Party | None] = relationship()
    lead: Mapped[Lead | None] = relationship()


class SalesDocKind(StrEnum):
    QUOTATION = "quotation"
    ORDER = "order"


class SalesDocStatus(StrEnum):
    # Quotations
    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    # Orders
    OPEN = "open"
    INVOICED = "invoiced"
    CANCELLED = "cancelled"


class SalesDoc(Base):
    """A quotation or a sales order. Neither touches the ledger."""

    __tablename__ = "sales_docs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10))
    number: Mapped[str] = mapped_column(String(30), unique=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("parties.id"), index=True)
    doc_date: Mapped[dt.date] = mapped_column()
    valid_until: Mapped[dt.date | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(String(10))
    opportunity_id: Mapped[int | None] = mapped_column(ForeignKey("opportunities.id"), default=None)
    # For an order: the quotation it came from.
    source_doc_id: Mapped[int | None] = mapped_column(ForeignKey("sales_docs.id"), default=None)
    subtotal: Mapped[int] = mapped_column(BigInteger, default=0)
    tax_total: Mapped[int] = mapped_column(BigInteger, default=0)
    total: Mapped[int] = mapped_column(BigInteger, default=0)
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)
    created_by: Mapped[str | None] = mapped_column(String(100), default=None)
    created_at: Mapped[dt.datetime] = mapped_column(default=utcnow)

    party: Mapped[Party] = relationship()
    lines: Mapped[list["SalesDocLine"]] = relationship(
        back_populates="doc", cascade="all, delete-orphan", order_by="SalesDocLine.id"
    )


class SalesDocLine(Base):
    __tablename__ = "sales_doc_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_id: Mapped[int] = mapped_column(ForeignKey("sales_docs.id"), index=True)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), default=None)
    description: Mapped[str] = mapped_column(String(500))
    quantity: Mapped[Decimal] = mapped_column(ScaledDecimal(4))
    unit_price: Mapped[int] = mapped_column(BigInteger)
    tax_rate_id: Mapped[int | None] = mapped_column(ForeignKey("tax_rates.id"), default=None)
    line_subtotal: Mapped[int] = mapped_column(BigInteger)
    tax_amount: Mapped[int] = mapped_column(BigInteger, default=0)

    doc: Mapped[SalesDoc] = relationship(back_populates="lines")
    item: Mapped[Item | None] = relationship()
    tax_rate: Mapped[TaxRate | None] = relationship()
