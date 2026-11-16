"""Database models for conversations, handoffs and unanswered questions."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from sqlalchemy import JSON, ForeignKey, Index, String, Text, create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        dict[str, Any]: JSON,
        list[dict[str, str]]: JSON,
    }


class Channel:
    WEB = "web"
    TELEGRAM = "telegram"


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conversations_channel_ref", "channel", "external_ref"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    channel: Mapped[str] = mapped_column(String(16), default=Channel.WEB)
    external_ref: Mapped[str | None] = mapped_column(String(64), default=None)
    """The chat's id on the external channel, e.g. a Telegram chat id."""
    closed: Mapped[bool] = mapped_column(default=False)
    """Closed conversations stay in history; the next message on that chat starts a new one."""
    created_at: Mapped[datetime] = mapped_column(default=_now)
    updated_at: Mapped[datetime] = mapped_column(default=_now, onupdate=_now)
    failed_order_lookups: Mapped[int] = mapped_column(default=0)
    handed_off: Mapped[bool] = mapped_column(default=False)

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="conversation", order_by="ChatMessage.id", cascade="all, delete-orphan"
    )
    handoffs: Mapped[list[Handoff]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list[dict[str, str]]] = mapped_column(default=list)
    tool_calls: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Handoff(Base):
    __tablename__ = "handoffs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    category: Mapped[str] = mapped_column(String(32))
    summary: Mapped[str] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(default=_now)

    conversation: Mapped[Conversation] = relationship(back_populates="handoffs")


class UnansweredQuestion(Base):
    __tablename__ = "unanswered_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"), index=True)
    question: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=_now)


def make_engine(database_url: str) -> Engine:
    if database_url.startswith("sqlite"):
        if database_url == "sqlite://" or ":memory:" in database_url:
            return create_engine(
                database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            database_url, connect_args={"check_same_thread": False, "timeout": 15}
        )
        event.listen(engine, "connect", _configure_sqlite)
        return engine
    return create_engine(database_url, pool_pre_ping=True)


def _configure_sqlite(dbapi_connection: Any, _record: Any) -> None:
    # WAL lets readers and a writer work at the same time, which matters when
    # several customers chat at once.
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


# Columns added after the first release. create_all() creates new tables but
# never alters existing ones, so add these to databases created earlier.
_ADDED_COLUMNS = {
    "conversations": {
        "channel": "VARCHAR(16) NOT NULL DEFAULT 'web'",
        "external_ref": "VARCHAR(64)",
        "closed": "BOOLEAN NOT NULL DEFAULT FALSE",
    },
}


def _add_missing_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in _ADDED_COLUMNS.items():
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, ddl in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_conversations_channel_ref "
                "ON conversations (channel, external_ref)"
            )
        )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    Base.metadata.create_all(engine)
    _add_missing_columns(engine)
    return sessionmaker(engine, expire_on_commit=False)
