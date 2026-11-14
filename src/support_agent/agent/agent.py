"""The support agent's reasoning loop."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from support_agent.agent.prompts import build_system_prompt
from support_agent.agent.tools import ALL_TOOLS, HandoffCategory
from support_agent.knowledge import KnowledgeIndex
from support_agent.llm import ChatModel, Message, ToolCall
from support_agent.store import OrderLookupError, StoreClient, lookup_order_for_customer

logger = logging.getLogger(__name__)

FALLBACK_REPLY = (
    "Sorry, I'm having trouble with that one. I've passed your conversation to our support "
    "team and a person will follow up with you."
)


@dataclass(frozen=True, slots=True)
class Source:
    title: str
    source: str


@dataclass(frozen=True, slots=True)
class Handoff:
    category: HandoffCategory
    summary: str


@dataclass(slots=True)
class ConversationState:
    """Per-conversation state that must survive between turns."""

    failed_order_lookups: int = 0


@dataclass(slots=True)
class AgentReply:
    text: str
    sources: list[Source] = field(default_factory=list)
    handoff: Handoff | None = None
    unanswered: bool = False
    """True when the knowledge base had nothing relevant and no person was asked to help."""
    tool_calls: list[str] = field(default_factory=list)


class SupportAgent:
    def __init__(
        self,
        model: ChatModel,
        store: StoreClient,
        knowledge: KnowledgeIndex,
        *,
        store_name: str = "Trailhead Supply Co.",
        min_score: float = 0.55,
        max_steps: int = 6,
        max_failed_lookups: int = 3,
        today: date | None = None,
    ) -> None:
        self._model = model
        self._store = store
        self._knowledge = knowledge
        self._store_name = store_name
        self._min_score = min_score
        self._max_steps = max_steps
        self._max_failed_lookups = max_failed_lookups
        self._today = today

    def reply(
        self,
        history: list[Message],
        user_message: str,
        state: ConversationState | None = None,
    ) -> AgentReply:
        """Answer one customer message. ``history`` holds earlier user and assistant turns."""
        state = state or ConversationState()
        messages = [
            Message("system", build_system_prompt(self._store_name, self._today)),
            *history,
            Message("user", user_message),
        ]
        result = AgentReply(text="")
        empty_searches = 0

        for _ in range(self._max_steps):
            response = self._model.complete(messages, ALL_TOOLS)
            if not response.tool_calls:
                result.text = response.content or FALLBACK_REPLY
                break

            messages.append(Message("assistant", response.content, tool_calls=response.tool_calls))
            for call in response.tool_calls:
                result.tool_calls.append(call.name)
                output = self._run_tool(call, state, result)
                if call.name == "search_help_center" and not output.get("results"):
                    empty_searches += 1
                messages.append(Message("tool", json.dumps(output), tool_call_id=call.id))
        else:
            logger.warning("Agent hit the step limit without a final answer")
            result.text = FALLBACK_REPLY
            if result.handoff is None:
                result.handoff = Handoff(
                    HandoffCategory.OTHER,
                    f"The assistant couldn't resolve this. Customer's last message: {user_message}",
                )

        result.unanswered = empty_searches > 0 and result.handoff is None
        return result

    def _run_tool(
        self, call: ToolCall, state: ConversationState, result: AgentReply
    ) -> dict[str, Any]:
        args = call.arguments
        if call.name == "lookup_order":
            return self._lookup_order(
                str(args.get("order_number", "")), str(args.get("email", "")), state
            )
        if call.name == "search_help_center":
            return self._search(str(args.get("query", "")), result)
        if call.name == "hand_off_to_human":
            return self._hand_off(args, result)
        return {"error": f"Unknown tool '{call.name}'."}

    def _lookup_order(self, number: str, email: str, state: ConversationState) -> dict[str, Any]:
        if state.failed_order_lookups >= self._max_failed_lookups:
            return {
                "error": "Too many unsuccessful lookups in this conversation. Don't try again; "
                "offer to connect the customer with a person instead."
            }
        try:
            order = lookup_order_for_customer(self._store, number, email)
        except OrderLookupError as exc:
            state.failed_order_lookups += 1
            return {"error": str(exc)}
        return {"order": order.model_dump(mode="json")}

    def _search(self, query: str, result: AgentReply) -> dict[str, Any]:
        hits = self._knowledge.search(query, limit=4, min_score=self._min_score)
        if not hits:
            return {
                "results": [],
                "note": "Nothing relevant found. Don't guess; offer to connect a person.",
            }
        for hit in hits:
            source = Source(title=hit.chunk.heading, source=hit.chunk.source)
            if source not in result.sources:
                result.sources.append(source)
        return {
            "results": [{"title": h.chunk.heading, "text": h.chunk.text} for h in hits],
        }

    def _hand_off(self, args: dict[str, Any], result: AgentReply) -> dict[str, Any]:
        try:
            category = HandoffCategory(str(args.get("category", "other")))
        except ValueError:
            category = HandoffCategory.OTHER
        summary = str(args.get("summary", "")).strip() or "Customer asked for help from a person."
        result.handoff = Handoff(category, summary[:1000])
        return {"status": "handed_off", "message": "A person from the support team will follow up."}
