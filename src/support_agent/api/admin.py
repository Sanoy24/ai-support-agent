"""Admin pages: handoffs, unanswered questions and conversations.

Protected with HTTP Basic auth (username ``admin``, password from
``ADMIN_PASSWORD``). Disabled entirely when no password is set.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from support_agent.config import Settings
from support_agent.db import Conversation, Handoff, UnansweredQuestion
from support_agent.service import SupportService

_basic = HTTPBasic(realm="ai-support-agent admin", auto_error=False)


def build_admin_router(
    settings: Settings,
    get_service: Callable[[Request], SupportService],
    templates: Jinja2Templates,
) -> APIRouter:
    def require_admin(
        credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
    ) -> None:
        if settings.admin_password is None:
            raise HTTPException(404)
        expected = settings.admin_password.get_secret_value().encode()
        valid = credentials is not None and (
            secrets.compare_digest(credentials.username.encode(), b"admin")
            & secrets.compare_digest(credentials.password.encode(), expected)
        )
        if not valid:
            raise HTTPException(401, headers={"WWW-Authenticate": 'Basic realm="admin"'})

    def require_same_origin(request: Request) -> None:
        # Browsers resend Basic credentials automatically, so reject
        # cross-site form posts.
        origin = request.headers.get("origin") or request.headers.get("referer")
        if not origin or urlsplit(origin).netloc != request.url.netloc:
            raise HTTPException(403, "Cross-site request blocked.")

    router = APIRouter(
        prefix="/admin", include_in_schema=False, dependencies=[Depends(require_admin)]
    )

    @router.get("", response_class=HTMLResponse)
    def dashboard(request: Request) -> HTMLResponse:
        with get_service(request).sessions() as session:
            context = {
                "store_name": settings.store_name,
                "total_conversations": session.scalar(select(func.count(Conversation.id))),
                "open_handoffs": session.scalars(
                    select(Handoff).where(Handoff.resolved.is_(False)).order_by(Handoff.id.desc())
                ).all(),
                "unanswered": session.scalars(
                    select(UnansweredQuestion).order_by(UnansweredQuestion.id.desc()).limit(25)
                ).all(),
                "conversations": session.scalars(
                    select(Conversation).order_by(Conversation.updated_at.desc()).limit(25)
                ).all(),
            }
            return templates.TemplateResponse(request, "admin.html", context)

    @router.get("/conversations/{conversation_id}", response_class=HTMLResponse)
    def conversation(request: Request, conversation_id: str) -> HTMLResponse:
        with get_service(request).sessions() as session:
            convo = session.get(Conversation, conversation_id)
            if convo is None:
                raise HTTPException(404)
            return templates.TemplateResponse(
                request,
                "conversation.html",
                {"store_name": settings.store_name, "conversation": convo},
            )

    @router.post("/handoffs/{handoff_id}/resolve", dependencies=[Depends(require_same_origin)])
    def resolve(request: Request, handoff_id: int) -> RedirectResponse:
        with get_service(request).sessions.begin() as session:
            handoff = session.get(Handoff, handoff_id)
            if handoff is None:
                raise HTTPException(404)
            handoff.resolved = True
        return RedirectResponse("/admin", status_code=303)

    return router
