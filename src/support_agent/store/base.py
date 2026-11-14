"""The interface every store adapter implements."""

from __future__ import annotations

from typing import Protocol

from support_agent.store.models import Order, OrderView, Product


class OrderLookupError(Exception):
    """Raised when an order can't be shown to the person asking.

    The message is safe to show the customer: it never reveals whether
    the order number exists when the email doesn't match.
    """


class StoreClient(Protocol):
    """Read-only access to a store's orders and products."""

    def get_order(self, number: str) -> Order | None: ...

    def list_products(self) -> list[Product]: ...


def normalize_order_number(number: str) -> str:
    return number.strip().lstrip("#").upper()


def lookup_order_for_customer(store: StoreClient, number: str, email: str) -> OrderView:
    """Return an order only if the email matches the one on the order.

    Unknown order numbers and wrong emails produce the same error, so the
    lookup can't be used to discover which order numbers exist.
    """
    not_found = OrderLookupError(
        "I couldn't find an order with that number and email. Please check both and try again."
    )
    if not number.strip() or not email.strip():
        raise not_found

    order = store.get_order(normalize_order_number(number))
    if order is None or order.customer_email.casefold() != email.strip().casefold():
        raise not_found
    return order.to_customer_view()
