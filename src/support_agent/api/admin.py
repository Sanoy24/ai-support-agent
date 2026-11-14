"""Admin JSON API used by the dashboard.

Disabled (404) unless ``ADMIN_PASSWORD`` is set. Login exchanges the
password for an HttpOnly, SameSite=Strict session cookie.
"""

import secrets
from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select

from support_agent.api.auth import COOKIE_NAME, SESSION_SECONDS, SessionSigner, password_matches
from support_agent.api.ratelimit import RateLimiter
from support_agent.config import Settings
from support_agent.db import ChatMessage, Conversation, Handoff, UnansweredQuestion
from support_agent.service import SupportService


class LoginRequest(BaseModel):
    password: str


class SourceOut(BaseModel):
    title: str
    source: str


class HandoffOut(BaseModel):
    id: int
    conversation_id: str
    category: str
    summary: str
    resolved: bool
    created_at: datetime


class UnansweredOut(BaseModel):
    id: int
    conversation_id: str
    question: str
    created_at: datetime


class ConversationSummaryOut(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    handed_off: bool
    preview: str


class MessageOut(BaseModel):
    role: str
    content: str
    sources: list[SourceOut]
    tools: list[str]
    created_at: datetime


class ConversationOut(BaseModel):
    id: str
    created_at: datetime
    handed_off: bool
    handoffs: list[HandoffOut]
    messages: list[MessageOut]


class OverviewOut(BaseModel):
    store_name: str
    total_conversations: int
    open_handoffs: int
    unanswered_questions: int
    handed_off_rate: float


def _handoff_out(h: Handoff) -> HandoffOut:
    return HandoffOut.model_validate(h, from_attributes=True)


def _message_out(m: ChatMessage) -> MessageOut:
    return MessageOut(
        role=m.role,
        content=m.content,
        sources=[SourceOut(**s) for s in m.sources],
        tools=list(m.tool_calls.get("names", [])),
        created_at=m.created_at,
    )


def build_admin_router(
    settings: Settings, get_service: Callable[[Request], SupportService]
) -> APIRouter:
    secret = (
        settings.session_secret.get_secret_value().encode()
        if settings.session_secret
        else secrets.token_bytes(32)
    )
    signer = SessionSigner(secret)
    login_limiter = RateLimiter(5)

    def admin_enabled() -> str:
        if settings.admin_password is None:
            raise HTTPException(404)
        return settings.admin_password.get_secret_value()

    def require_session(
        _: Annotated[str, Depends(admin_enabled)],
        asa_admin: Annotated[str | None, Cookie()] = None,
    ) -> None:
        if not signer.verify(asa_admin):
            raise HTTPException(401, "Please sign in.")

    public = APIRouter(prefix="/api/admin", tags=["admin"])
    private = APIRouter(
        prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_session)]
    )

    @public.post("/login", status_code=204)
    def login(
        body: LoginRequest,
        request: Request,
        response: Response,
        expected: Annotated[str, Depends(admin_enabled)],
    ) -> None:
        client = request.client.host if request.client else "unknown"
        if not login_limiter.allow(client):
            raise HTTPException(429, "Too many attempts. Wait a minute and try again.")
        if not password_matches(body.password, expected):
            raise HTTPException(401, "Incorrect password.")
        response.set_cookie(
            COOKIE_NAME,
            signer.issue(),
            max_age=SESSION_SECONDS,
            httponly=True,
            samesite="strict",
            secure=request.url.scheme == "https",
            path="/api/admin",
        )

    @public.post("/logout", status_code=204)
    def logout(response: Response) -> None:
        response.delete_cookie(COOKIE_NAME, path="/api/admin")

    @private.get("/session", status_code=204)
    def session_check() -> None:
        """Returns 204 when signed in, 401 otherwise."""

    @private.get("/overview")
    def overview(request: Request) -> OverviewOut:
        with get_service(request).sessions() as db:
            total = db.scalar(select(func.count(Conversation.id))) or 0
            handed = (
                db.scalar(
                    select(func.count(Conversation.id)).where(Conversation.handed_off.is_(True))
                )
                or 0
            )
            return OverviewOut(
                store_name=settings.store_name,
                total_conversations=total,
                open_handoffs=db.scalar(
                    select(func.count(Handoff.id)).where(Handoff.resolved.is_(False))
                )
                or 0,
                unanswered_questions=db.scalar(select(func.count(UnansweredQuestion.id))) or 0,
                handed_off_rate=round(handed / total, 3) if total else 0.0,
            )

    @private.get("/handoffs")
    def handoffs(request: Request, resolved: bool = False) -> list[HandoffOut]:
        with get_service(request).sessions() as db:
            rows = db.scalars(
                select(Handoff).where(Handoff.resolved.is_(resolved)).order_by(Handoff.id.desc())
            ).all()
            return [_handoff_out(h) for h in rows]

    @private.post("/handoffs/{handoff_id}/resolve")
    def resolve(request: Request, handoff_id: int) -> HandoffOut:
        with get_service(request).sessions.begin() as db:
            handoff = db.get(Handoff, handoff_id)
            if handoff is None:
                raise HTTPException(404, "Handoff not found.")
            handoff.resolved = True
            return _handoff_out(handoff)

    @private.get("/unanswered")
    def unanswered(request: Request, limit: int = 50) -> list[UnansweredOut]:
        with get_service(request).sessions() as db:
            rows = db.scalars(
                select(UnansweredQuestion)
                .order_by(UnansweredQuestion.id.desc())
                .limit(min(limit, 200))
            ).all()
            return [UnansweredOut.model_validate(q, from_attributes=True) for q in rows]

    @private.get("/conversations")
    def conversations(request: Request, limit: int = 50) -> list[ConversationSummaryOut]:
        with get_service(request).sessions() as db:
            rows = db.scalars(
                select(Conversation).order_by(Conversation.updated_at.desc()).limit(min(limit, 200))
            ).all()
            return [
                ConversationSummaryOut(
                    id=c.id,
                    created_at=c.created_at,
                    updated_at=c.updated_at,
                    message_count=len(c.messages),
                    handed_off=c.handed_off,
                    preview=next((m.content for m in c.messages if m.role == "user"), "")[:140],
                )
                for c in rows
            ]

    @private.get("/conversations/{conversation_id}")
    def conversation(request: Request, conversation_id: str) -> ConversationOut:
        with get_service(request).sessions() as db:
            convo = db.get(Conversation, conversation_id)
            if convo is None:
                raise HTTPException(404, "Conversation not found.")
            return ConversationOut(
                id=convo.id,
                created_at=convo.created_at,
                handed_off=convo.handed_off,
                handoffs=[_handoff_out(h) for h in convo.handoffs],
                messages=[_message_out(m) for m in convo.messages],
            )

    router = APIRouter()
    router.include_router(public)
    router.include_router(private)
    return router
