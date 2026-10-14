import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from ledgerkit.errors import DomainError
from ledgerkit.models import DEFAULT_CHART, Account, Company, Sequence


def get_company(session: Session) -> Company:
    company = session.scalars(select(Company).limit(1)).first()
    if company is None:
        raise DomainError("not_initialised", "No company is set up yet. Run `ledgerkit init` first.")
    return company


def init_company(
    session: Session,
    *,
    name: str,
    base_currency: str = "USD",
    currency_decimals: int = 2,
    fiscal_year_start_month: int = 1,
) -> Company:
    """Create the company and its default chart of accounts. Idempotent."""
    existing = session.scalars(select(Company).limit(1)).first()
    if existing is not None:
        return existing
    if not 1 <= fiscal_year_start_month <= 12:
        raise DomainError("invalid_input", "fiscal_year_start_month must be between 1 and 12.")
    if not 0 <= currency_decimals <= 4:
        raise DomainError("invalid_input", "currency_decimals must be between 0 and 4.")
    company = Company(
        name=name,
        base_currency=base_currency.upper(),
        currency_decimals=currency_decimals,
        fiscal_year_start_month=fiscal_year_start_month,
    )
    session.add(company)
    for code, account_name, type_, subtype in DEFAULT_CHART:
        session.add(Account(code=code, name=account_name, type=type_, subtype=subtype))
    session.flush()
    return company


def system_account(session: Session, subtype: str) -> Account:
    """The account the system posts to for a given role (lowest code wins)."""
    account = session.scalars(
        select(Account).where(Account.subtype == subtype, Account.is_active).order_by(Account.code).limit(1)
    ).first()
    if account is None:
        raise DomainError(
            "missing_system_account",
            f"No active account has the subtype '{subtype}'. Create one with create_account.",
        )
    return account


def check_period_open(company: Company, on: dt.date) -> None:
    if company.lock_date and on <= company.lock_date:
        raise DomainError(
            "period_locked",
            f"The books are locked up to {company.lock_date.isoformat()}, so nothing can be posted "
            f"on {on.isoformat()}. Use a later date.",
        )


def fiscal_year_start(company: Company, on: dt.date) -> dt.date:
    month = company.fiscal_year_start_month
    year = on.year if on.month >= month else on.year - 1
    return dt.date(year, month, 1)


def next_number(session: Session, key: str, prefix: str) -> str:
    seq = session.get(Sequence, key, with_for_update=True)
    if seq is None:
        seq = Sequence(name=key, next_value=1)
        session.add(seq)
    value = seq.next_value
    seq.next_value = value + 1
    return f"{prefix}-{value:05d}"
