"""Store-agnostic data models shared by every store adapter."""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class FulfillmentStatus(StrEnum):
    UNFULFILLED = "unfulfilled"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    RETURNED = "returned"


class LineItem(BaseModel):
    sku: str
    title: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0)


class Shipment(BaseModel):
    carrier: str
    tracking_number: str
    tracking_url: str | None = None
    shipped_on: date
    estimated_delivery: date | None = None
    delivered_on: date | None = None


class Order(BaseModel):
    """An order as the store holds it, including private customer fields."""

    number: str
    customer_email: str
    customer_first_name: str
    placed_on: date
    status: FulfillmentStatus
    currency: str = "USD"
    items: list[LineItem]
    shipment: Shipment | None = None

    @property
    def total(self) -> float:
        return round(sum(item.unit_price * item.quantity for item in self.items), 2)

    def to_customer_view(self) -> OrderView:
        """Return only what is safe to show the verified customer."""
        return OrderView(
            number=self.number,
            first_name=self.customer_first_name,
            placed_on=self.placed_on,
            status=self.status,
            currency=self.currency,
            total=self.total,
            items=[f"{item.quantity} x {item.title}" for item in self.items],
            shipment=self.shipment,
        )


class OrderView(BaseModel):
    """Customer-facing order summary. Never includes the email or address."""

    number: str
    first_name: str
    placed_on: date
    status: FulfillmentStatus
    currency: str
    total: float
    items: list[str]
    shipment: Shipment | None = None


class Product(BaseModel):
    sku: str
    title: str
    description: str
    price: float = Field(ge=0)
    currency: str = "USD"
    in_stock: bool
    tags: list[str] = Field(default_factory=list)
    url: str | None = None

    def search_text(self) -> str:
        return f"{self.title}. {self.description} Tags: {', '.join(self.tags)}"
