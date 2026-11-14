"""FastAPI application: chat API, embeddable widget, demo page and admin."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import resources
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from support_agent import __version__
from support_agent.api.admin import build_admin_router
from support_agent.api.ratelimit import RateLimiter
from support_agent.config import Settings, get_settings
from support_agent.service import ConversationNotFoundError, SupportService

logger = logging.getLogger(__name__)

WEB_DIR = Path(str(resources.files("support_agent").joinpath("web")))
templates = Jinja2Templates(directory=WEB_DIR / "templates")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = Field(default=None, max_length=32)


class SourceOut(BaseModel):
    title: str
    source: str


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    handed_off: bool
    sources: list[SourceOut]


def create_app(settings: Settings | None = None, service: SupportService | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if service is None:
            from support_agent.api.wiring import build_service

            app.state.service = build_service(settings)
        else:
            app.state.service = service
        yield

    app = FastAPI(
        title="ai-support-agent",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url=None,
    )
    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_methods=["POST"],
            allow_headers=["Content-Type"],
        )

    limiter = RateLimiter(settings.chat_rate_limit_per_minute)

    def get_service(request: Request) -> SupportService:
        svc: SupportService = request.app.state.service
        return svc

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(body: ChatRequest, request: Request) -> ChatResponse:
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            raise HTTPException(429, "Too many messages. Please wait a moment and try again.")
        message = body.message.strip()
        if not message:
            raise HTTPException(422, "Message is empty.")
        if len(message) > settings.max_message_chars:
            raise HTTPException(
                413, f"Message is longer than {settings.max_message_chars} characters."
            )
        try:
            result = get_service(request).handle_message(body.conversation_id, message)
        except ConversationNotFoundError:
            raise HTTPException(404, "Conversation not found. Start a new one.") from None
        return ChatResponse(
            conversation_id=result.conversation_id,
            reply=result.reply,
            handed_off=result.handed_off,
            sources=[SourceOut(title=s.title, source=s.source) for s in result.sources],
        )

    @app.get("/widget.js", include_in_schema=False)
    def widget() -> FileResponse:
        return FileResponse(
            WEB_DIR / "static" / "widget.js",
            media_type="application/javascript",
            headers={"Cache-Control": "public, max-age=300"},
        )

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def demo(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "demo.html", {"store_name": settings.store_name})

    app.include_router(build_admin_router(settings, get_service, templates))
    return app
