"""FastAPI application: chat API, admin API and the built web frontend."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib import resources
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from support_agent import __version__
from support_agent.api.admin import build_admin_router
from support_agent.api.ratelimit import RateLimiter
from support_agent.api.wiring import start_channels
from support_agent.config import Settings, get_settings
from support_agent.service import ConversationNotFoundError, SupportService
from support_agent.store import Product

logger = logging.getLogger(__name__)

DEFAULT_FRONTEND_DIR = Path(str(resources.files("support_agent").joinpath("web", "dist")))


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


class StoreOut(BaseModel):
    name: str
    products: list[Product]


def create_app(
    settings: Settings | None = None,
    service: SupportService | None = None,
    frontend_dir: Path = DEFAULT_FRONTEND_DIR,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if service is None:
            from support_agent.api.wiring import build_service

            app.state.service = build_service(settings)
        else:
            app.state.service = service

        stop_channels = start_channels(settings, app.state.service)
        try:
            yield
        finally:
            stop_channels()

    app = FastAPI(
        title="ai-support-agent",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
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

    @app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
    def chat(body: ChatRequest, request: Request) -> ChatResponse:
        client = request.client.host if request.client else "unknown"
        if not limiter.allow(client):
            raise HTTPException(429, "Too many messages. Please wait a moment and try again.")
        message = body.message.strip()
        if not message:
            raise HTTPException(422, "Message is empty.")
        if len(message) > settings.max_message_chars:
            limit = settings.max_message_chars
            raise HTTPException(413, f"Message is longer than {limit} characters.")
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

    @app.get("/api/store", tags=["store"])
    def store(request: Request) -> StoreOut:
        """Public store info and catalog, used by the demo storefront."""
        return StoreOut(name=settings.store_name, products=get_service(request).list_products())

    app.include_router(build_admin_router(settings, get_service))
    _mount_frontend(app, frontend_dir)
    return app


def _mount_frontend(app: FastAPI, frontend_dir: Path) -> None:
    """Serve the built React app, with client-side routing fallback."""
    index = frontend_dir / "index.html"
    if (frontend_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend_dir / "assets"), name="assets")

    @app.get("/widget.js", include_in_schema=False)
    def widget() -> Response:
        path = frontend_dir / "widget.js"
        if not path.is_file():
            return PlainTextResponse("Widget not built. Run: npm --prefix frontend run build", 404)
        return FileResponse(
            path, media_type="text/javascript", headers={"Cache-Control": "no-cache"}
        )

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> Response:
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = (frontend_dir / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(frontend_dir.resolve()):
            return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index, headers={"Cache-Control": "no-cache"})
        return PlainTextResponse(
            "Frontend not built. Run: npm --prefix frontend ci && npm --prefix frontend run build",
            404,
        )
