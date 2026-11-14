import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from support_agent.store.models import FulfillmentStatus
from support_agent.store.shopify import ShopifyError, ShopifyStore

Handler = Callable[[dict[str, Any]], httpx.Response]

ORDER_NODE: dict[str, Any] = {
    "name": "#1042",
    "email": "jo@example.com",
    "createdAt": "2026-11-01T10:00:00Z",
    "cancelledAt": None,
    "displayFulfillmentStatus": "FULFILLED",
    "currencyCode": "EUR",
    "customer": {"firstName": "Jo"},
    "lineItems": {
        "nodes": [
            {
                "sku": "MUG-1",
                "title": "Coffee Mug",
                "quantity": 2,
                "originalUnitPriceSet": {"shopMoney": {"amount": "12.50"}},
            }
        ]
    },
    "fulfillments": [
        {
            "createdAt": "2026-11-02T08:00:00Z",
            "deliveredAt": None,
            "estimatedDeliveryAt": "2026-11-06T00:00:00Z",
            "trackingInfo": [
                {"company": "DHL", "number": "JD0001", "url": "https://example.com/t"}
            ],
        }
    ],
    "returns": {"nodes": []},
}


def orders_response(*nodes: dict[str, Any]) -> Handler:
    return lambda _: httpx.Response(200, json={"data": {"orders": {"nodes": list(nodes)}}})


def make_store(handler: Handler) -> tuple[ShopifyStore, list[dict[str, Any]]]:
    seen: list[dict[str, Any]] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        body: dict[str, Any] = json.loads(request.content)
        seen.append(body)
        assert request.headers["X-Shopify-Access-Token"] == "test-token"
        return handler(body)

    store = ShopifyStore("demo.myshopify.com", "test-token", transport=httpx.MockTransport(wrapped))
    return store, seen


def test_get_order_maps_shopify_fields() -> None:
    store, seen = make_store(orders_response(ORDER_NODE))

    order = store.get_order("1042")

    assert order is not None
    assert seen[0]["variables"] == {"query": "name:#1042"}
    assert order.number == "1042"
    assert order.status is FulfillmentStatus.SHIPPED
    assert order.currency == "EUR"
    assert order.total == 25.0
    assert order.shipment is not None
    assert order.shipment.carrier == "DHL"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        (
            {
                "fulfillments": [
                    {**ORDER_NODE["fulfillments"][0], "deliveredAt": "2026-11-05T00:00Z"}
                ]
            },
            FulfillmentStatus.DELIVERED,
        ),
        ({"cancelledAt": "2026-11-01T12:00:00Z"}, FulfillmentStatus.CANCELLED),
        ({"returns": {"nodes": [{"status": "OPEN"}]}}, FulfillmentStatus.RETURNED),
        (
            {"displayFulfillmentStatus": "UNFULFILLED", "fulfillments": []},
            FulfillmentStatus.UNFULFILLED,
        ),
    ],
)
def test_order_status_mapping(overrides: dict[str, Any], expected: FulfillmentStatus) -> None:
    store, _ = make_store(orders_response({**ORDER_NODE, **overrides}))
    order = store.get_order("1042")
    assert order is not None
    assert order.status is expected


@pytest.mark.parametrize("number", ['1042" OR email:*', "1042 status:any", "x" * 40])
def test_get_order_refuses_search_syntax_injection(number: str) -> None:
    store, seen = make_store(orders_response(ORDER_NODE))
    assert store.get_order(number) is None
    assert seen == []


def test_get_order_ignores_partial_name_match() -> None:
    store, _ = make_store(orders_response({**ORDER_NODE, "name": "#10420"}))
    assert store.get_order("1042") is None


def test_get_order_returns_none_when_not_found() -> None:
    store, _ = make_store(orders_response())
    assert store.get_order("1042") is None


def test_list_products_follows_pagination() -> None:
    def product(handle: str, inventory: int) -> dict[str, Any]:
        return {
            "handle": handle,
            "title": handle.title(),
            "description": "desc",
            "tags": ["t"],
            "onlineStoreUrl": None,
            "totalInventory": inventory,
            "tracksInventory": True,
            "variants": {"nodes": [{"sku": handle.upper(), "price": "9.00"}]},
        }

    pages = iter(
        [
            {"pageInfo": {"hasNextPage": True, "endCursor": "c1"}, "nodes": [product("mug", 3)]},
            {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [product("cap", 0)]},
        ]
    )
    store, seen = make_store(
        lambda _: httpx.Response(200, json={"data": {"products": next(pages)}})
    )

    products = store.list_products()

    assert [p.sku for p in products] == ["MUG", "CAP"]
    assert [p.in_stock for p in products] == [True, False]
    assert seen[1]["variables"] == {"cursor": "c1"}


def test_graphql_errors_raise() -> None:
    store, _ = make_store(lambda _: httpx.Response(200, json={"errors": [{"message": "denied"}]}))
    with pytest.raises(ShopifyError):
        store.get_order("1042")


def test_http_errors_raise() -> None:
    store, _ = make_store(lambda _: httpx.Response(401, json={}))
    with pytest.raises(ShopifyError, match="401"):
        store.get_order("1042")
