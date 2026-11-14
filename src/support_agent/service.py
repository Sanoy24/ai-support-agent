"""Connects the agent to storage: one call per customer message."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.orm import Session, sessionmaker

from support_agent.agent import ConversationState, HandoffCategory, Source, SupportAgent
from support_agent.agent.agent import FALLBACK_REPLY
from support_agent.db import ChatMessage, Conversation, Handoff, UnansweredQuestion
from support_agent.llm import LLMError, Message

logger = logging.getLogger(__name__)

HISTORY_TURNS = 20


@dataclass(frozen=True, slots=True)
class ChatResult:
    conversation_id: str
    reply: str
    handed_off: bool
    sources: list[Source] = field(default_factory=list)


class ConversationNotFoundError(LookupError):
    pass


class SupportService:
    def __init__(self, agent: SupportAgent, sessions: sessionmaker[Session]) -> None:
        self._agent = agent
        self._sessions = sessions

    def handle_message(self, conversation_id: str | None, text: str) -> ChatResult:
        with self._sessions.begin() as session:
            conversation = self._get_or_create(session, conversation_id)
            history = [
                Message("user" if m.role == "user" else "assistant", m.content)
                for m in conversation.messages[-HISTORY_TURNS:]
            ]
            state = ConversationState(failed_order_lookups=conversation.failed_order_lookups)

            try:
                reply = self._agent.reply(history, text, state)
                reply_text, sources, handoff = reply.text, reply.sources, reply.handoff
                tool_calls = reply.tool_calls
                unanswered = reply.unanswered
            except LLMError:
                logger.exception("Model provider failed; handing off to a person")
                reply_text, sources, tool_calls, unanswered = FALLBACK_REPLY, [], [], False
                handoff = None
                session.add(
                    Handoff(
                        conversation=conversation,
                        category=HandoffCategory.OTHER.value,
                        summary=f"The assistant was unavailable. Customer wrote: {text[:500]}",
                    )
                )
                conversation.handed_off = True

            conversation.failed_order_lookups = state.failed_order_lookups
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
                session.add(
                    Handoff(
                        conversation=conversation,
                        category=handoff.category.value,
                        summary=handoff.summary,
                    )
                )
                conversation.handed_off = True
            if unanswered:
                session.add(UnansweredQuestion(conversation_id=conversation.id, question=text))

            return ChatResult(
                conversation_id=conversation.id,
                reply=reply_text,
                handed_off=conversation.handed_off,
                sources=sources,
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
