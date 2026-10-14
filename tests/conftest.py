import pytest

from ledgerkit.db import make_engine, make_session_factory
from ledgerkit.models import Base
from ledgerkit.services.company import init_company
from ledgerkit.tools import Actor, registry

USER = Actor("user", "test")
AGENT = Actor("agent", "test")


def new_database(path):
    """An initialised company database at the given file path."""
    engine = make_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as session:
        init_company(session, name="Test Co", base_currency="USD")
        session.commit()
    return engine, factory


@pytest.fixture
def session_factory(tmp_path):
    engine, factory = new_database(tmp_path / "test.db")
    yield factory
    engine.dispose()


@pytest.fixture
def session(session_factory):
    with session_factory() as s:
        yield s


@pytest.fixture
def call(session_factory):
    """Call a tool as a human user and return its data, failing the test on an error."""

    def _call(tool: str, _actor: Actor = USER, **payload):
        result = registry.call(session_factory, tool, payload, _actor)
        assert result["status"] == "ok", result
        return result["data"]

    return _call


@pytest.fixture
def raw_call(session_factory):
    """Call a tool and return the whole result envelope, whatever its status."""

    def _call(tool: str, _actor: Actor = USER, **payload):
        return registry.call(session_factory, tool, payload, _actor)

    return _call


@pytest.fixture
def catalogue(call):
    """A tax rate, two items, a customer and a vendor."""
    call("create_tax_rate", name="Tax 10%", rate_pct=10)
    call(
        "create_item",
        sku="WIDGET",
        name="Widget",
        kind="product",
        sale_price="100.00",
        standard_cost="60.00",
        tax_rate="Tax 10%",
    )
    call(
        "create_item",
        sku="HOUR",
        name="Consulting hour",
        kind="service",
        sale_price="150.00",
        income_account_code="4100",
    )
    return {
        "customer": call("create_customer", name="Acme")["id"],
        "vendor": call("create_vendor", name="Supplier")["id"],
    }
