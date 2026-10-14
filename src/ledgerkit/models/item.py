from enum import StrEnum

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ledgerkit.models.account import Account
from ledgerkit.models.base import Base


class TaxRate(Base):
    __tablename__ = "tax_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    # Basis points: 1800 means 18.00%.
    rate_bp: Mapped[int] = mapped_column()
    # Liability credited on sales; asset debited on purchases.
    sales_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    purchase_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    is_active: Mapped[bool] = mapped_column(default=True)


class ItemKind(StrEnum):
    PRODUCT = "product"
    SERVICE = "service"


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(10), default=ItemKind.PRODUCT)
    sale_price: Mapped[int] = mapped_column(BigInteger, default=0)
    # Products only. Snapshotted onto each sales invoice line to compute cost of goods sold.
    standard_cost: Mapped[int] = mapped_column(BigInteger, default=0)
    income_account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    tax_rate_id: Mapped[int | None] = mapped_column(ForeignKey("tax_rates.id"), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)

    income_account: Mapped[Account] = relationship()
    tax_rate: Mapped[TaxRate | None] = relationship()
