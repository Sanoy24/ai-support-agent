"""Tools the support agent can call. All of them are read-only or hand off to a person."""

from __future__ import annotations

from enum import StrEnum

from support_agent.llm import ToolSpec


class HandoffCategory(StrEnum):
    REFUND = "refund"
    CANCELLATION = "cancellation"
    ORDER_CHANGE = "order_change"
    DAMAGED_OR_WRONG_ITEM = "damaged_or_wrong_item"
    COMPLAINT = "complaint"
    CUSTOMER_REQUEST = "customer_request"
    OTHER = "other"


LOOKUP_ORDER = ToolSpec(
    name="lookup_order",
    description=(
        "Look up an order's status, items and tracking. Requires the order number and the "
        "email address the customer used when ordering."
    ),
    parameters={
        "type": "object",
        "properties": {
            "order_number": {"type": "string", "description": "Order number, e.g. TS-1002"},
            "email": {"type": "string", "description": "Email address used for the order"},
        },
        "required": ["order_number", "email"],
    },
)

SEARCH_HELP_CENTER = ToolSpec(
    name="search_help_center",
    description=(
        "Search the store's policies (shipping, returns, refunds, warranty, payments, FAQ) and "
        "product catalog. Returns the most relevant passages."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look up, in plain words"},
        },
        "required": ["query"],
    },
)

HAND_OFF_TO_HUMAN = ToolSpec(
    name="hand_off_to_human",
    description=(
        "Pass the conversation to a human support agent. Use for refunds, cancellations, "
        "order changes, damaged or wrong items, complaints, or when the customer asks for a "
        "person or you can't help."
    ),
    parameters={
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": [c.value for c in HandoffCategory]},
            "summary": {
                "type": "string",
                "description": (
                    "One to three sentences for the support agent: what the customer wants, "
                    "the order number if known, and anything already checked."
                ),
            },
        },
        "required": ["category", "summary"],
    },
)

ALL_TOOLS = [LOOKUP_ORDER, SEARCH_HELP_CENTER, HAND_OFF_TO_HUMAN]
