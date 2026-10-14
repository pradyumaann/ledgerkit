from enum import StrEnum

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ledgerkit.models.base import Base


class AccountType(StrEnum):
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"


class AccountSubtype(StrEnum):
    """Roles the system needs to find specific accounts when it posts documents."""

    BANK = "bank"
    RECEIVABLE = "receivable"
    INVENTORY = "inventory"
    TAX_RECEIVABLE = "tax_receivable"
    PAYABLE = "payable"
    TAX_PAYABLE = "tax_payable"
    RETAINED_EARNINGS = "retained_earnings"
    COGS = "cogs"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(20))
    subtype: Mapped[str | None] = mapped_column(String(30), default=None)
    is_active: Mapped[bool] = mapped_column(default=True)


# (code, name, type, subtype)
DEFAULT_CHART = [
    ("1000", "Bank", AccountType.ASSET, AccountSubtype.BANK),
    ("1010", "Cash on Hand", AccountType.ASSET, AccountSubtype.BANK),
    ("1100", "Accounts Receivable", AccountType.ASSET, AccountSubtype.RECEIVABLE),
    ("1200", "Inventory", AccountType.ASSET, AccountSubtype.INVENTORY),
    ("1300", "Input Tax Recoverable", AccountType.ASSET, AccountSubtype.TAX_RECEIVABLE),
    ("1500", "Equipment", AccountType.ASSET, None),
    ("2000", "Accounts Payable", AccountType.LIABILITY, AccountSubtype.PAYABLE),
    ("2100", "Sales Tax Payable", AccountType.LIABILITY, AccountSubtype.TAX_PAYABLE),
    ("2500", "Loans Payable", AccountType.LIABILITY, None),
    ("3000", "Owner's Equity", AccountType.EQUITY, None),
    ("3100", "Retained Earnings", AccountType.EQUITY, AccountSubtype.RETAINED_EARNINGS),
    ("4000", "Sales Revenue", AccountType.INCOME, None),
    ("4100", "Service Revenue", AccountType.INCOME, None),
    ("4900", "Other Income", AccountType.INCOME, None),
    ("5000", "Cost of Goods Sold", AccountType.EXPENSE, AccountSubtype.COGS),
    ("6000", "Salaries and Wages", AccountType.EXPENSE, None),
    ("6100", "Rent", AccountType.EXPENSE, None),
    ("6200", "Utilities", AccountType.EXPENSE, None),
    ("6300", "Marketing", AccountType.EXPENSE, None),
    ("6400", "Software and Subscriptions", AccountType.EXPENSE, None),
    ("6500", "Professional Fees", AccountType.EXPENSE, None),
    ("6600", "Office Supplies", AccountType.EXPENSE, None),
    ("6700", "Travel", AccountType.EXPENSE, None),
    ("6800", "Bank Charges", AccountType.EXPENSE, None),
    ("6900", "Other Expenses", AccountType.EXPENSE, None),
]
