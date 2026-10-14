import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, MetaData
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from ledgerkit.money import round_half_up

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ScaledDecimal(TypeDecorator):
    """Exact decimal stored as a scaled integer, so it is exact on SQLite too
    and still sums correctly in SQL."""

    impl = BigInteger
    cache_ok = True

    def __init__(self, scale: int = 4):
        super().__init__()
        self.scale = scale

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return round_half_up(Decimal(value).scaleb(self.scale))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Decimal(int(value)).scaleb(-self.scale)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)
