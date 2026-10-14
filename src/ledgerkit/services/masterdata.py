"""Accounts, parties, items and tax rates."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ledgerkit.errors import DomainError
from ledgerkit.models import Account, AccountSubtype, AccountType, Item, ItemKind, Party, TaxRate
from ledgerkit.services.company import system_account

# A subtype is only meaningful on one account type.
SUBTYPE_TYPE = {
    AccountSubtype.BANK: AccountType.ASSET,
    AccountSubtype.RECEIVABLE: AccountType.ASSET,
    AccountSubtype.INVENTORY: AccountType.ASSET,
    AccountSubtype.TAX_RECEIVABLE: AccountType.ASSET,
    AccountSubtype.PAYABLE: AccountType.LIABILITY,
    AccountSubtype.TAX_PAYABLE: AccountType.LIABILITY,
    AccountSubtype.RETAINED_EARNINGS: AccountType.EQUITY,
    AccountSubtype.COGS: AccountType.EXPENSE,
}


def create_account(session: Session, *, code: str, name: str, type: str, subtype: str | None = None) -> Account:
    if session.scalars(select(Account).where(Account.code == code)).first() is not None:
        raise DomainError("duplicate", f"An account with code '{code}' already exists.")
    required_type = SUBTYPE_TYPE[AccountSubtype(subtype)] if subtype is not None else None
    if required_type is not None and required_type != type:
        raise DomainError(
            "invalid_input", f"Subtype '{subtype}' is only valid on a {required_type.value} account, not {type}."
        )
    account = Account(code=code, name=name, type=type, subtype=subtype)
    session.add(account)
    session.flush()
    return account


def list_accounts(session: Session, *, type: str | None = None, include_inactive: bool = False) -> list[Account]:
    stmt = select(Account).order_by(Account.code)
    if type:
        stmt = stmt.where(Account.type == type)
    if not include_inactive:
        stmt = stmt.where(Account.is_active)
    return list(session.scalars(stmt))


def create_party(session: Session, *, name: str, is_customer: bool, is_vendor: bool, **fields) -> Party:
    """Create a customer or vendor. If a party with the same name exists, add the role to it."""
    existing = session.scalars(select(Party).where(Party.name == name)).first()
    if existing is not None:
        if (is_customer and existing.is_customer) or (is_vendor and existing.is_vendor):
            raise DomainError(
                "duplicate",
                f"'{name}' already exists as party id {existing.id}. Use that id instead of creating it again.",
            )
        existing.is_customer = existing.is_customer or is_customer
        existing.is_vendor = existing.is_vendor or is_vendor
        session.flush()
        return existing
    party = Party(name=name, is_customer=is_customer, is_vendor=is_vendor, **fields)
    session.add(party)
    session.flush()
    return party


def search_parties(
    session: Session, *, query: str | None = None, role: str | None = None, limit: int = 25
) -> list[Party]:
    stmt = select(Party).order_by(Party.name).limit(limit)
    if query:
        like = f"%{query}%"
        stmt = stmt.where(or_(Party.name.ilike(like), Party.email.ilike(like)))
    if role == "customer":
        stmt = stmt.where(Party.is_customer)
    elif role == "vendor":
        stmt = stmt.where(Party.is_vendor)
    return list(session.scalars(stmt))


def create_tax_rate(
    session: Session,
    *,
    name: str,
    rate_bp: int,
    sales_account: Account | None = None,
    purchase_account: Account | None = None,
) -> TaxRate:
    if session.scalars(select(TaxRate).where(TaxRate.name == name)).first() is not None:
        raise DomainError("duplicate", f"A tax rate named '{name}' already exists.")
    sales_account = sales_account or system_account(session, AccountSubtype.TAX_PAYABLE)
    purchase_account = purchase_account or system_account(session, AccountSubtype.TAX_RECEIVABLE)
    tax = TaxRate(
        name=name, rate_bp=rate_bp, sales_account_id=sales_account.id, purchase_account_id=purchase_account.id
    )
    session.add(tax)
    session.flush()
    return tax


def create_item(
    session: Session,
    *,
    sku: str,
    name: str,
    kind: str,
    sale_price: int,
    standard_cost: int,
    income_account: Account,
    tax_rate: TaxRate | None = None,
) -> Item:
    if session.scalars(select(Item).where(Item.sku == sku)).first() is not None:
        raise DomainError("duplicate", f"An item with SKU '{sku}' already exists.")
    if income_account.type != AccountType.INCOME:
        raise DomainError(
            "invalid_account", f"Account {income_account.code} {income_account.name} is not an income account."
        )
    if kind == ItemKind.SERVICE and standard_cost:
        raise DomainError(
            "invalid_input",
            "standard_cost only applies to products. A service's costs (such as salaries) are recorded "
            "as operating expenses.",
        )
    item = Item(
        sku=sku,
        name=name,
        kind=kind,
        sale_price=sale_price,
        standard_cost=standard_cost,
        income_account_id=income_account.id,
        tax_rate_id=tax_rate.id if tax_rate else None,
    )
    session.add(item)
    session.flush()
    return item
