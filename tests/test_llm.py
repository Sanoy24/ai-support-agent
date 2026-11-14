import json
from typing import Any

import httpx
import pytest

from support_agent.llm import (
    LLMError,
    Message,
    OpenAICompatibleModel,
    ToolCall,
    ToolSpec,
)

LOOKUP = ToolSpec(
    name="lookup_order",
    description="Look up an order",
    parameters={"type": "object", "properties": {"order_number": {"type": "string"}}},
)


def make_model(
    reply: dict[str, Any], seen: list[dict[str, Any]], status: int = 200
) -> OpenAICompatibleModel:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        seen.append(json.loads(request.content))
        return httpx.Response(status, json={"choices": [{"message": reply}]})

    return OpenAICompatibleModel(
        "test-model",
        "http://llm.test/v1",
        api_key="sk-test",
        transport=httpx.MockTransport(handler),
    )


def test_encodes_messages_tools_and_tool_results() -> None:
    seen: list[dict[str, Any]] = []
    model = make_model({"content": "Done."}, seen)
    call = ToolCall(id="c1", name="lookup_order", arguments={"order_number": "TS-1"})

    model.complete(
        [
            Message("system", "Be helpful."),
            Message("user", "Where is TS-1?"),
            Message("assistant", "", tool_calls=(call,)),
            Message("tool", '{"status": "shipped"}', tool_call_id="c1"),
        ],
        [LOOKUP],
    )

    body = seen[0]
    assert body["model"] == "test-model"
    assert body["tools"][0]["function"]["name"] == "lookup_order"
    assistant = body["messages"][2]
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {
        "order_number": "TS-1"
    }
    assert body["messages"][3] == {
        "role": "tool",
        "content": '{"status": "shipped"}',
        "tool_call_id": "c1",
    }


def test_decodes_tool_calls_with_string_or_object_arguments() -> None:
    reply = {
        "content": "",
        "tool_calls": [
            {
                "id": "a",
                "function": {"name": "lookup_order", "arguments": '{"order_number": "TS-1"}'},
            },
            {"function": {"name": "lookup_order", "arguments": {"order_number": "TS-2"}}},
            {"function": {"name": "lookup_order", "arguments": "not json"}},
        ],
    }
    response = make_model(reply, []).complete([Message("user", "hi")], [LOOKUP])

    assert [c.arguments for c in response.tool_calls] == [
        {"order_number": "TS-1"},
        {"order_number": "TS-2"},
        {"_invalid_json": "not json"},
    ]
    assert response.tool_calls[1].id == "call_1"


def test_strips_inline_reasoning_blocks() -> None:
    response = make_model({"content": "<think>hmm</think>\nYour order shipped."}, []).complete(
        [Message("user", "hi")], []
    )
    assert response.content == "Your order shipped."


def test_omits_tools_when_none_given() -> None:
    seen: list[dict[str, Any]] = []
    make_model({"content": "hi"}, seen).complete([Message("user", "hi")], [])
    assert "tools" not in seen[0]


def test_http_errors_raise_llm_error() -> None:
    with pytest.raises(LLMError, match="500"):
        make_model({}, [], status=500).complete([Message("user", "hi")], [])


def test_reasoning_effort_is_sent_only_when_set() -> None:
    seen: list[dict[str, Any]] = []
    make_model({"content": "hi"}, seen).complete([Message("user", "hi")], [])

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})

    OpenAICompatibleModel(
        "m", "http://llm.test/v1", reasoning_effort="none", transport=httpx.MockTransport(handler)
    ).complete([Message("user", "hi")], [])

    assert "reasoning_effort" not in seen[0]
    assert seen[1]["reasoning_effort"] == "none"
