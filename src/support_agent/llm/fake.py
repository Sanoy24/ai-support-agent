"""A scripted model for tests and offline demos."""

from __future__ import annotations

from collections.abc import Iterable

from support_agent.llm.base import LLMError, Message, ModelResponse, ToolSpec


class ScriptedModel:
    """Returns pre-written responses in order and records every request."""

    def __init__(self, responses: Iterable[ModelResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[list[Message], list[ToolSpec]]] = []

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        self.requests.append((list(messages), list(tools)))
        if not self._responses:
            raise LLMError("ScriptedModel ran out of responses")
        return self._responses.pop(0)
