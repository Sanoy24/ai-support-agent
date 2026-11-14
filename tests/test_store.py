import pytest

from support_agent.store import (
    FulfillmentStatus,
    MockStore,
    OrderLookupError,
    lookup_order_for_customer,
)


@pytest.fixture
def store() -> MockStore:
    return MockStore()


def test_demo_store_loads_orders_and_products(store: MockStore) -> None:
    assert store.get_order("TS-1001") is not None
    assert len(store.list_products()) >= 5


@pytest.mark.parametrize("number", ["TS-1002", "ts-1002", "#TS-1002", "  TS-1002  "])
def test_lookup_accepts_common_order_number_formats(store: MockStore, number: str) -> None:
    view = lookup_order_for_customer(store, number, "liam.okafor@example.com")
    assert view.number == "TS-1002"
    assert view.status is FulfillmentStatus.SHIPPED


def test_lookup_email_is_case_insensitive(store: MockStore) -> None:
    view = lookup_order_for_customer(store, "TS-1001", "  Maya.Chen@Example.com ")
    assert view.first_name == "Maya"


def test_wrong_email_and_unknown_order_give_the_same_error(store: MockStore) -> None:
    with pytest.raises(OrderLookupError) as wrong_email:
        lookup_order_for_customer(store, "TS-1001", "someone.else@example.com")
    with pytest.raises(OrderLookupError) as unknown_order:
        lookup_order_for_customer(store, "TS-9999", "maya.chen@example.com")
    assert str(wrong_email.value) == str(unknown_order.value)


@pytest.mark.parametrize(("number", "email"), [("", "maya.chen@example.com"), ("TS-1001", " ")])
def test_lookup_rejects_blank_input(store: MockStore, number: str, email: str) -> None:
    with pytest.raises(OrderLookupError):
        lookup_order_for_customer(store, number, email)


def test_customer_view_never_contains_the_email(store: MockStore) -> None:
    view = lookup_order_for_customer(store, "TS-1002", "liam.okafor@example.com")
    assert "liam.okafor@example.com" not in view.model_dump_json()


def test_customer_view_total_sums_line_items(store: MockStore) -> None:
    view = lookup_order_for_customer(store, "TS-1002", "liam.okafor@example.com")
    assert view.total == 159.0 + 2 * 24.0
