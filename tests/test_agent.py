import json
from importlib import resources
from pathlib import Path

import pytest

from support_agent.agent import ConversationState, HandoffCategory, SupportAgent
from support_agent.agent.agent import FALLBACK_REPLY
from support_agent.knowledge import HashingEmbedder, KnowledgeIndex, policy_chunks
from support_agent.llm import ModelResponse, ScriptedModel, ToolCall
from support_agent.store import MockStore

POLICIES = Path(str(resources.files("support_agent.demo").joinpath("policies")))


@pytest.fixture(scope="module")
def knowledge() -> KnowledgeIndex:
    index = KnowledgeIndex(HashingEmbedder())
    index.add(policy_chunks(POLICIES))
    return index


def call(name: str, **arguments: str) -> ModelResponse:
    return ModelResponse(
        "", tool_calls=(ToolCall(id=f"id-{name}", name=name, arguments=arguments),)
    )


def answer(text: str) -> ModelResponse:
    return ModelResponse(text)


def make_agent(model: ScriptedModel, knowledge: KnowledgeIndex) -> SupportAgent:
    return SupportAgent(model, MockStore(), knowledge, min_score=0.2)


def tool_output(model: ScriptedModel, request_index: int) -> dict[str, object]:
    """The JSON the agent sent back for the most recent tool call of a request."""
    messages, _ = model.requests[request_index]
    result: dict[str, object] = json.loads(messages[-1].content)
    return result


def test_order_lookup_returns_order_to_the_model(knowledge: KnowledgeIndex) -> None:
    model = ScriptedModel(
        [
            call("lookup_order", order_number="TS-1002", email="liam.okafor@example.com"),
            answer("Your order shipped with USPS."),
        ]
    )
    reply = make_agent(model, knowledge).reply([], "Where is TS-1002? liam.okafor@example.com")

    assert reply.text == "Your order shipped with USPS."
    assert reply.tool_calls == ["lookup_order"]
    order = tool_output(model, 1)["order"]
    assert isinstance(order, dict)
    assert order["status"] == "shipped"
    assert "liam.okafor@example.com" not in json.dumps(order)


def test_failed_lookups_are_capped_per_conversation(knowledge: KnowledgeIndex) -> None:
    attempts = [
        call("lookup_order", order_number="TS-1001", email=f"guess{i}@example.com")
        for i in range(4)
    ]
    model = ScriptedModel([*attempts, answer("Let me connect you with a person.")])
    state = ConversationState()

    make_agent(model, knowledge).reply([], "check TS-1001", state)

    assert state.failed_order_lookups == 3
    assert "Too many unsuccessful lookups" in str(tool_output(model, 4)["error"])


def test_capped_lookups_stay_blocked_even_with_correct_email(knowledge: KnowledgeIndex) -> None:
    state = ConversationState(failed_order_lookups=3)
    model = ScriptedModel(
        [
            call("lookup_order", order_number="TS-1001", email="maya.chen@example.com"),
            answer("I'll connect you with a person."),
        ]
    )
    make_agent(model, knowledge).reply([], "TS-1001 maya.chen@example.com", state)
    assert "order" not in tool_output(model, 1)


def test_search_results_become_sources(knowledge: KnowledgeIndex) -> None:
    model = ScriptedModel(
        [call("search_help_center", query="return window days"), answer("You have 30 days.")]
    )
    reply = make_agent(model, knowledge).reply([], "How long do I have to return something?")

    assert any(s.source == "returns.md" for s in reply.sources)
    assert reply.unanswered is False


def test_empty_search_marks_question_unanswered(knowledge: KnowledgeIndex) -> None:
    model = ScriptedModel(
        [call("search_help_center", query="quantum chromodynamics"), answer("I don't know.")]
    )
    reply = make_agent(model, knowledge).reply([], "Do you sell quantum chromodynamics kits?")

    assert reply.unanswered is True
    assert reply.sources == []
    assert tool_output(model, 1)["results"] == []


def test_knowledge_gap_is_logged_even_when_handed_off(knowledge: KnowledgeIndex) -> None:
    model = ScriptedModel(
        [
            call("search_help_center", query="quantum chromodynamics"),
            call("hand_off_to_human", category="refund", summary="Wants a refund for TS-1001."),
            answer("A person will follow up."),
        ]
    )
    reply = make_agent(model, knowledge).reply([], "I want my money back for TS-1001")

    assert reply.handoff is not None
    assert reply.handoff.category is HandoffCategory.REFUND
    assert reply.handoff.summary == "Wants a refund for TS-1001."
    assert reply.unanswered is True


def test_retrying_a_search_successfully_is_not_a_gap(knowledge: KnowledgeIndex) -> None:
    model = ScriptedModel(
        [
            call("search_help_center", query="quantum chromodynamics"),
            call("search_help_center", query="return window days"),
            answer("You have 30 days."),
        ]
    )
    reply = make_agent(model, knowledge).reply([], "How long do I have to send something back?")
    assert reply.unanswered is False


def test_invalid_handoff_category_falls_back_to_other(knowledge: KnowledgeIndex) -> None:
    model = ScriptedModel(
        [call("hand_off_to_human", category="vip", summary="x"), answer("A person will help.")]
    )
    reply = make_agent(model, knowledge).reply([], "help")
    assert reply.handoff is not None
    assert reply.handoff.category is HandoffCategory.OTHER


def test_unknown_tool_returns_error_to_model(knowledge: KnowledgeIndex) -> None:
    model = ScriptedModel(
        [call("issue_refund", order_number="TS-1001"), answer("I can't do that.")]
    )
    make_agent(model, knowledge).reply([], "refund me")
    assert "Unknown tool" in str(tool_output(model, 1)["error"])


def test_step_limit_falls_back_and_hands_off(knowledge: KnowledgeIndex) -> None:
    loop = [call("search_help_center", query="returns") for _ in range(6)]
    reply = make_agent(ScriptedModel(loop), knowledge).reply([], "returns?")

    assert reply.text == FALLBACK_REPLY
    assert reply.handoff is not None


def test_agent_only_offers_read_and_handoff_tools(knowledge: KnowledgeIndex) -> None:
    model = ScriptedModel([answer("Hi!")])
    make_agent(model, knowledge).reply([], "hi")
    _, tools = model.requests[0]
    assert {t.name for t in tools} == {"lookup_order", "search_help_center", "hand_off_to_human"}
