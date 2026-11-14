"""Read-only Shopify adapter using the Admin GraphQL API.

Required access scopes: ``read_orders`` and ``read_products``.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

import httpx

from support_agent.store.models import (
    FulfillmentStatus,
    LineItem,
    Order,
    Product,
    Shipment,
)

DEFAULT_API_VERSION = "2025-10"

_ORDER_QUERY = """
query OrderByName($query: String!) {
  orders(first: 1, query: $query) {
    nodes {
      name
      email
      createdAt
      cancelledAt
      displayFulfillmentStatus
      currencyCode
      customer { firstName }
      lineItems(first: 50) {
        nodes {
          sku
          title
          quantity
          originalUnitPriceSet { shopMoney { amount } }
        }
      }
      fulfillments(first: 5) {
        createdAt
        deliveredAt
        estimatedDeliveryAt
        trackingInfo(first: 1) { company number url }
      }
      returns(first: 1) { nodes { status } }
    }
  }
}
"""

_PRODUCTS_QUERY = """
query Products($cursor: String) {
  products(first: 100, after: $cursor, query: "status:active") {
    pageInfo { hasNextPage endCursor }
    nodes {
      handle
      title
      description
      tags
      onlineStoreUrl
      totalInventory
      tracksInventory
      variants(first: 1) { nodes { sku price } }
    }
  }
}
"""

_STATUS_MAP = {
    "UNFULFILLED": FulfillmentStatus.UNFULFILLED,
    "ON_HOLD": FulfillmentStatus.UNFULFILLED,
    "SCHEDULED": FulfillmentStatus.UNFULFILLED,
    "IN_PROGRESS": FulfillmentStatus.PROCESSING,
    "PENDING_FULFILLMENT": FulfillmentStatus.PROCESSING,
    "OPEN": FulfillmentStatus.PROCESSING,
    "PARTIALLY_FULFILLED": FulfillmentStatus.SHIPPED,
    "FULFILLED": FulfillmentStatus.SHIPPED,
}

_SAFE_ORDER_NAME = re.compile(r"^[A-Za-z0-9-]{1,32}$")


class ShopifyError(RuntimeError):
    """Raised when the Shopify API returns an error."""


class ShopifyStore:
    def __init__(
        self,
        shop_domain: str,
        access_token: str,
        *,
        api_version: str = DEFAULT_API_VERSION,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._client = httpx.Client(
            base_url=f"https://{shop_domain}/admin/api/{api_version}",
            headers={"X-Shopify-Access-Token": access_token},
            timeout=timeout,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def get_order(self, number: str) -> Order | None:
        # The order number ends up inside Shopify's search syntax, so only
        # allow characters that order names actually use.
        if not _SAFE_ORDER_NAME.fullmatch(number):
            return None
        data = self._graphql(_ORDER_QUERY, {"query": f"name:#{number}"})
        nodes = data["orders"]["nodes"]
        if not nodes:
            return None
        node = nodes[0]
        if node["name"].lstrip("#").upper() != number.upper():
            return None
        return _parse_order(node)

    def list_products(self) -> list[Product]:
        products: list[Product] = []
        cursor: str | None = None
        while True:
            data = self._graphql(_PRODUCTS_QUERY, {"cursor": cursor})
            page = data["products"]
            products.extend(_parse_product(node) for node in page["nodes"])
            if not page["pageInfo"]["hasNextPage"]:
                return products
            cursor = page["pageInfo"]["endCursor"]

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        response = self._client.post("/graphql.json", json={"query": query, "variables": variables})
        if response.status_code >= 400:
            raise ShopifyError(f"Shopify API returned HTTP {response.status_code}")
        payload: dict[str, Any] = response.json()
        if payload.get("errors"):
            raise ShopifyError(f"Shopify API error: {payload['errors']}")
        data: dict[str, Any] = payload["data"]
        return data


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _parse_order(node: dict[str, Any]) -> Order:
    fulfillments = node.get("fulfillments") or []
    shipment: Shipment | None = None
    for fulfillment in fulfillments:
        tracking = (fulfillment.get("trackingInfo") or [None])[0]
        if tracking and tracking.get("number"):
            shipment = Shipment(
                carrier=tracking.get("company") or "Carrier",
                tracking_number=tracking["number"],
                tracking_url=tracking.get("url"),
                shipped_on=_to_date(fulfillment["createdAt"]) or date.today(),
                estimated_delivery=_to_date(fulfillment.get("estimatedDeliveryAt")),
                delivered_on=_to_date(fulfillment.get("deliveredAt")),
            )
            break

    if node.get("cancelledAt"):
        status = FulfillmentStatus.CANCELLED
    elif (node.get("returns") or {}).get("nodes"):
        status = FulfillmentStatus.RETURNED
    elif shipment and shipment.delivered_on:
        status = FulfillmentStatus.DELIVERED
    else:
        status = _STATUS_MAP.get(node["displayFulfillmentStatus"], FulfillmentStatus.PROCESSING)

    return Order(
        number=node["name"].lstrip("#"),
        customer_email=node.get("email") or "",
        customer_first_name=(node.get("customer") or {}).get("firstName") or "there",
        placed_on=_to_date(node["createdAt"]) or date.today(),
        status=status,
        currency=node.get("currencyCode") or "USD",
        items=[
            LineItem(
                sku=item.get("sku") or "",
                title=item["title"],
                quantity=item["quantity"],
                unit_price=float(item["originalUnitPriceSet"]["shopMoney"]["amount"]),
            )
            for item in node["lineItems"]["nodes"]
        ],
        shipment=shipment,
    )


def _parse_product(node: dict[str, Any]) -> Product:
    variant = (node["variants"]["nodes"] or [{}])[0]
    in_stock = (not node.get("tracksInventory")) or (node.get("totalInventory") or 0) > 0
    return Product(
        sku=variant.get("sku") or node["handle"],
        title=node["title"],
        description=node.get("description") or "",
        price=float(variant.get("price") or 0),
        in_stock=in_stock,
        tags=node.get("tags") or [],
        url=node.get("onlineStoreUrl"),
    )
