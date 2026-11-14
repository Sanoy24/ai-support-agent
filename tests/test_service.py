from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from support_agent.agent import SupportAgent
from support_agent.db import (
    ChatMessage,
    Conversation,
    Handoff,
    UnansweredQuestion,
    make_engine,
    make_session_factory,
)
from support_agent.knowledge import KnowledgeIndex
from support_agent.llm import LLMError, Message, ModelResponse, ToolSpec
from support_agent.service import ConversationNotFoundError, SupportService
from support_agent.store import MockStore
from tests.conftest import ServiceFactory, answer, call


def count(sessions: sessionmaker[Session], model: type[object]) -> int:
    with sessions() as session:
        return session.scalar(select(func.count()).select_from(model)) or 0


def test_new_conversation_is_created_and_messages_saved(
    make_service: ServiceFactory, sessions: sessionmaker[Session]
) -> None:
    service, _ = make_service([answer("Hello! How can I help?")])

    result = service.handle_message(None, "hi")

    assert result.reply == "Hello! How can I help?"
    assert result.handed_off is False
    with sessions() as session:
        conversation = session.get(Conversation, result.conversation_id)
        assert conversation is not None
        assert [(m.role, m.content) for m in conversation.messages] == [
            ("user", "hi"),
            ("assistant", "Hello! How can I help?"),
        ]


def test_history_is_sent_on_later_turns(make_service: ServiceFactory) -> None:
    service, model = make_service([answer("Hi!"), answer("Sure.")])

    first = service.handle_message(None, "hello")
    service.handle_message(first.conversation_id, "thanks")

    messages, _ = model.requests[1]
    assert [(m.role, m.content) for m in messages[1:]] == [
        ("user", "hello"),
        ("assistant", "Hi!"),
        ("user", "thanks"),
    ]


def test_unknown_conversation_id_is_rejected(make_service: ServiceFactory) -> None:
    service, _ = make_service([])
    with pytest.raises(ConversationNotFoundError):
        service.handle_message("does-not-exist", "hi")


def test_failed_lookups_persist_across_turns(
    make_service: ServiceFactory, sessions: sessionmaker[Session]
) -> None:
    guess = call("lookup_order", order_number="TS-1001", email="guess@example.com")
    service, _ = make_service([guess, answer("Not found."), guess, answer("Not found.")])

    first = service.handle_message(None, "TS-1001 guess@example.com")
    service.handle_message(first.conversation_id, "TS-1001 guess@example.com")

    with sessions() as session:
        conversation = session.get(Conversation, first.conversation_id)
        assert conversation is not None
        assert conversation.failed_order_lookups == 2


def test_handoff_is_saved(make_service: ServiceFactory, sessions: sessionmaker[Session]) -> None:
    service, _ = make_service(
        [
            call("hand_off_to_human", category="refund", summary="Refund for TS-1001."),
            answer("A person will follow up."),
        ]
    )
    result = service.handle_message(None, "refund TS-1001 please")

    assert result.handed_off is True
    with sessions() as session:
        handoff = session.scalars(select(Handoff)).one()
        assert (handoff.category, handoff.summary, handoff.resolved) == (
            "refund",
            "Refund for TS-1001.",
            False,
        )


def test_unanswered_question_is_saved(
    make_service: ServiceFactory, sessions: sessionmaker[Session]
) -> None:
    service, _ = make_service(
        [call("search_help_center", query="kayak rentals"), answer("I don't know.")]
    )
    service.handle_message(None, "Do you rent kayaks?")

    with sessions() as session:
        assert session.scalars(select(UnansweredQuestion.question)).all() == ["Do you rent kayaks?"]


class BrokenModel:
    def complete(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        raise LLMError("provider is down")


def test_model_failure_falls_back_to_a_person(
    knowledge: KnowledgeIndex, sessions: sessionmaker[Session]
) -> None:
    agent = SupportAgent(BrokenModel(), MockStore(), knowledge)
    service = SupportService(agent, sessions)

    result = service.handle_message(None, "where is my order")

    assert result.handed_off is True
    assert "passed your conversation" in result.reply
    assert count(sessions, Handoff) == 1
    assert count(sessions, ChatMessage) == 2


def test_no_database_lock_is_held_while_the_model_runs(
    knowledge: KnowledgeIndex, tmp_path: Path
) -> None:
    """A slow model call must not block other customers from chatting.

    Regression test: the service used to hold a write transaction for the
    whole model call, so a second conversation failed with
    "database is locked" on SQLite.
    """
    sessions = make_session_factory(make_engine(f"sqlite:///{tmp_path / 'chat.db'}"))

    class OtherCustomerWritesMeanwhile:
        def complete(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
            # Simulates another conversation being saved while this model call runs.
            with sessions.begin() as session:
                session.add(Conversation())
            return ModelResponse("Hello!")

    agent = SupportAgent(OtherCustomerWritesMeanwhile(), MockStore(), knowledge)
    result = SupportService(agent, sessions).handle_message(None, "hi")

    assert result.reply == "Hello!"
    assert count(sessions, Conversation) == 2
