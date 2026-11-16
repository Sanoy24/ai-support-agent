"""Connects the agent to storage: one call per customer message."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from support_agent.agent import ConversationState, HandoffCategory, Source, SupportAgent
from support_agent.agent.agent import FALLBACK_REPLY
from support_agent.db import ChatMessage, Conversation, Handoff, UnansweredQuestion
from support_agent.llm import LLMError, Message
from support_agent.store import Product

logger = logging.getLogger(__name__)

HISTORY_TURNS = 20


@dataclass(frozen=True, slots=True)
class ChatResult:
    conversation_id: str
    reply: str
    handed_off: bool
    sources: list[Source] = field(default_factory=list)
    newly_handed_off: bool = False
    """True only on the message that caused the handoff."""


class ConversationNotFoundError(LookupError):
    pass


class SupportService:
    def __init__(self, agent: SupportAgent, sessions: sessionmaker[Session]) -> None:
        self._agent = agent
        self._sessions = sessions

    @property
    def sessions(self) -> sessionmaker[Session]:
        return self._sessions

    def list_products(self) -> list[Product]:
        return self._agent.store.list_products()

    def handle_message(self, conversation_id: str | None, text: str) -> ChatResult:
        """Handle a message from the website widget."""
        return self._handle(text, lambda session: self._get_or_create(session, conversation_id))

    def handle_channel_message(self, channel: str, external_ref: str, text: str) -> ChatResult:
        """Handle a message from an external channel such as Telegram.

        Messages from the same chat continue its open conversation, so the
        assistant remembers context the way the website widget does.
        """
        return self._handle(
            text, lambda session: self._get_or_create_for_chat(session, channel, external_ref)
        )

    def close_channel_conversation(self, channel: str, external_ref: str) -> bool:
        """Close the chat's open conversation, so its next message starts a new one."""
        with self._sessions.begin() as session:
            conversation = self._open_conversation_for_chat(session, channel, external_ref)
            if conversation is None:
                return False
            conversation.closed = True
            return True

    def _handle(self, text: str, resolve: Callable[[Session], Conversation]) -> ChatResult:
        # Phase 1: load (or create) the conversation in a short transaction.
        with self._sessions.begin() as session:
            conversation = resolve(session)
            conversation_id = conversation.id
            was_handed_off = conversation.handed_off
            history = [
                Message("user" if m.role == "user" else "assistant", m.content)
                for m in conversation.messages[-HISTORY_TURNS:]
            ]
            failed_before = conversation.failed_order_lookups

        # Phase 2: run the model with no transaction open. Model calls can take
        # many seconds, and holding a database lock that long would block every
        # other customer.
        state = ConversationState(failed_order_lookups=failed_before)
        handoff: Handoff | None
        try:
            reply = self._agent.reply(history, text, state)
            reply_text, sources, tool_calls = reply.text, reply.sources, reply.tool_calls
            unanswered = reply.unanswered
            handoff = (
                Handoff(category=reply.handoff.category.value, summary=reply.handoff.summary)
                if reply.handoff
                else None
            )
        except LLMError:
            logger.exception("Model provider failed; handing off to a person")
            reply_text, sources, tool_calls, unanswered = FALLBACK_REPLY, [], [], False
            handoff = Handoff(
                category=HandoffCategory.OTHER.value,
                summary=f"The assistant was unavailable. Customer wrote: {text[:500]}",
            )

        # Phase 3: save the outcome in a second short transaction.
        with self._sessions.begin() as session:
            conversation = session.get_one(Conversation, conversation_id)
            # Apply the change as a delta in case another message on this
            # conversation was saved while the model was running.
            conversation.failed_order_lookups += state.failed_order_lookups - failed_before
            conversation.messages.append(ChatMessage(role="user", content=text))
            conversation.messages.append(
                ChatMessage(
                    role="assistant",
                    content=reply_text,
                    sources=[{"title": s.title, "source": s.source} for s in sources],
                    tool_calls={"names": tool_calls},
                )
            )
            if handoff is not None:
                conversation.handoffs.append(handoff)
                conversation.handed_off = True
            if unanswered:
                session.add(UnansweredQuestion(conversation_id=conversation_id, question=text))

            return ChatResult(
                conversation_id=conversation_id,
                reply=reply_text,
                handed_off=conversation.handed_off,
                sources=sources,
                newly_handed_off=conversation.handed_off and not was_handed_off,
            )

    def _get_or_create(self, session: Session, conversation_id: str | None) -> Conversation:
        if conversation_id:
            conversation = session.get(Conversation, conversation_id)
            if conversation is None:
                raise ConversationNotFoundError(conversation_id)
            return conversation
        conversation = Conversation()
        session.add(conversation)
        session.flush()
        return conversation

    @staticmethod
    def _open_conversation_for_chat(
        session: Session, channel: str, external_ref: str
    ) -> Conversation | None:
        return session.scalars(
            select(Conversation)
            .where(
                Conversation.channel == channel,
                Conversation.external_ref == external_ref,
                Conversation.closed.is_(False),
            )
            .order_by(Conversation.created_at.desc())
            .limit(1)
        ).first()

    def _get_or_create_for_chat(
        self, session: Session, channel: str, external_ref: str
    ) -> Conversation:
        conversation = self._open_conversation_for_chat(session, channel, external_ref)
        if conversation is None:
            conversation = Conversation(channel=channel, external_ref=external_ref)
            session.add(conversation)
            session.flush()
        return conversation
