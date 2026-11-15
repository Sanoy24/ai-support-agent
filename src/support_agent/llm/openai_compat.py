"""Client for any OpenAI-compatible chat completions API.

This covers a local Ollama server (``http://localhost:11434/v1``), OpenAI,
OpenRouter, Groq and most other hosted providers.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable, Sequence
from typing import Any

import httpx

from support_agent.llm.base import LLMError, Message, ModelResponse, ToolCall, ToolSpec

logger = logging.getLogger(__name__)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)
_RETRYABLE_STATUS = {429, 502, 503, 504}
_MAX_RETRY_DELAY = 10.0


class OpenAICompatibleModel:
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434/v1",
        api_key: str | None = None,
        *,
        temperature: float = 0.2,
        reasoning_effort: str | None = None,
        fallback_models: Sequence[str] = (),
        max_retries: int = 2,
        timeout: float = 300.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """
        Args:
            reasoning_effort: Passed through for models that reason before answering.
                ``"none"`` turns reasoning off on Ollama, which makes local models several
                times faster for tool-calling tasks like this one. Leave unset for providers
                that don't support it.
            fallback_models: Models to try if the main one is rate limited or unavailable.
                Sent as OpenRouter's ``models`` routing list, so only set this for
                providers that support it.
            max_retries: Retries for rate limits and temporary provider errors.
        """
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.model = model
        self._temperature = temperature
        self._reasoning_effort = reasoning_effort
        self._fallback_models = list(fallback_models)
        self._max_retries = max_retries
        self._sleep = sleep
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
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        if self._fallback_models:
            payload["models"] = [self.model, *self._fallback_models]

        response = self._post_with_retries(payload)

        try:
            message = response.json()["choices"][0]["message"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError("Model provider returned an unexpected response") from exc

        content = _THINK_BLOCK.sub("", message.get("content") or "").strip()
        calls = tuple(
            _decode_tool_call(i, c) for i, c in enumerate(message.get("tool_calls") or [])
        )
        return ModelResponse(content=content, tool_calls=calls)

    def _post_with_retries(self, payload: dict[str, Any]) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.post("/chat/completions", json=payload)
            except httpx.HTTPError as exc:
                raise LLMError(f"Could not reach the model provider: {exc}") from exc
            if response.status_code < 400:
                return response
            if response.status_code not in _RETRYABLE_STATUS or attempt == self._max_retries:
                raise LLMError(f"Model provider returned HTTP {response.status_code}")
            delay = _retry_delay(response, attempt)
            logger.warning(
                "Model provider returned HTTP %s; retrying in %.1fs",
                response.status_code,
                delay,
            )
            self._sleep(delay)
        raise AssertionError("unreachable")  # pragma: no cover


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("retry-after", "")
    try:
        return min(float(retry_after), _MAX_RETRY_DELAY)
    except ValueError:
        return min(2.0**attempt, _MAX_RETRY_DELAY)


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
