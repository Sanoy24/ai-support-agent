"""Client for any OpenAI-compatible chat completions API.

This covers a local Ollama server (``http://localhost:11434/v1``), OpenAI,
OpenRouter, Groq and most other hosted providers.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from support_agent.llm.base import LLMError, Message, ModelResponse, ToolCall, ToolSpec

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


class OpenAICompatibleModel:
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        api_key: str | None = None,
        *,
        temperature: float = 0.2,
        timeout: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.model = model
        self._temperature = temperature
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), headers=headers, timeout=timeout, transport=transport
        )

    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [_encode_message(m) for m in messages],
            "temperature": self._temperature,
            "stream": False,
        }
        if tools:
            payload["tools"] = [_encode_tool(t) for t in tools]

        try:
            response = self._client.post("/chat/completions", json=payload)
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not reach the model provider: {exc}") from exc
        if response.status_code >= 400:
            raise LLMError(f"Model provider returned HTTP {response.status_code}")

        try:
            message = response.json()["choices"][0]["message"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError("Model provider returned an unexpected response") from exc

        content = _THINK_BLOCK.sub("", message.get("content") or "").strip()
        calls = tuple(
            _decode_tool_call(i, c) for i, c in enumerate(message.get("tool_calls") or [])
        )
        return ModelResponse(content=content, tool_calls=calls)


def _encode_message(message: Message) -> dict[str, Any]:
    encoded: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        encoded["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in message.tool_calls
        ]
    if message.tool_call_id:
        encoded["tool_call_id"] = message.tool_call_id
    return encoded


def _encode_tool(tool: ToolSpec) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters or {"type": "object", "properties": {}},
        },
    }


def _decode_tool_call(index: int, raw: dict[str, Any]) -> ToolCall:
    function = raw.get("function") or {}
    arguments = function.get("arguments") or {}
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments) if arguments.strip() else {}
        except json.JSONDecodeError:
            arguments = {"_invalid_json": arguments}
    if not isinstance(arguments, dict):
        arguments = {}
    return ToolCall(
        id=raw.get("id") or f"call_{index}",
        name=function.get("name", ""),
        arguments=arguments,
    )
