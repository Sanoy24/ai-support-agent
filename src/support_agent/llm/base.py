"""Provider-neutral chat types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None
    """For ``role="tool"``: the id of the call this message answers."""


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    """JSON Schema for the tool's arguments."""


@dataclass(frozen=True, slots=True)
class ModelResponse:
    content: str
    tool_calls: tuple[ToolCall, ...] = ()


class LLMError(RuntimeError):
    """Raised when the model provider fails or returns something unusable."""


class ChatModel(Protocol):
    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse: ...
