"""A demo store backed by a JSON file, so the project runs without a real shop."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from pydantic import BaseModel

from support_agent.store.base import normalize_order_number
from support_agent.store.models import Order, Product


class _MockData(BaseModel):
    orders: list[Order]
    products: list[Product]


class MockStore:
    """Read-only store loaded from JSON. Defaults to the bundled demo data."""

    def __init__(self, data_path: Path | None = None) -> None:
        if data_path is None:
            raw = resources.files("support_agent.demo").joinpath("store.json").read_text("utf-8")
        else:
            raw = data_path.read_text("utf-8")
        data = _MockData.model_validate(json.loads(raw))
        self._orders = {normalize_order_number(o.number): o for o in data.orders}
        self._products = data.products

    def get_order(self, number: str) -> Order | None:
        return self._orders.get(normalize_order_number(number))

    def list_products(self) -> list[Product]:
        return list(self._products)
