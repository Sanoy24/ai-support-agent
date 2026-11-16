"""Build the support service from settings."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from importlib import resources
from pathlib import Path

from support_agent.agent import SupportAgent
from support_agent.config import Settings
from support_agent.db import make_engine, make_session_factory
from support_agent.knowledge import (
    Embedder,
    FastEmbedEmbedder,
    HashingEmbedder,
    KnowledgeIndex,
    OllamaEmbedder,
    policy_chunks,
    product_chunks,
)
from support_agent.llm import OpenAICompatibleModel
from support_agent.service import SupportService
from support_agent.store import MockStore, StoreClient
from support_agent.store.shopify import ShopifyStore

logger = logging.getLogger(__name__)


def build_store(settings: Settings) -> StoreClient:
    if settings.store_backend == "shopify":
        if not (settings.shopify_shop_domain and settings.shopify_access_token):
            raise ValueError("Shopify backend needs a shop domain and access token")
        return ShopifyStore(
            settings.shopify_shop_domain, settings.shopify_access_token.get_secret_value()
        )
    return MockStore()


def build_embedder(settings: Settings) -> Embedder:
    if settings.embeddings_backend == "ollama":
        return OllamaEmbedder(settings.embeddings_model, settings.ollama_base_url)
    if settings.embeddings_backend == "fastembed":
        return FastEmbedEmbedder(settings.embeddings_model)
    return HashingEmbedder()


def build_knowledge(settings: Settings, store: StoreClient, embedder: Embedder) -> KnowledgeIndex:
    policies = settings.policies_dir or Path(
        str(resources.files("support_agent.demo").joinpath("policies"))
    )
    index = KnowledgeIndex(embedder)
    index.add(policy_chunks(policies))
    index.add(product_chunks(store.list_products()))
    logger.info("Indexed %d knowledge chunks from %s and the product catalog", len(index), policies)
    return index


def build_service(settings: Settings) -> SupportService:
    store = build_store(settings)
    knowledge = build_knowledge(settings, store, build_embedder(settings))
    model = OpenAICompatibleModel(
        settings.llm_model,
        settings.llm_base_url,
        settings.llm_api_key.get_secret_value() if settings.llm_api_key else None,
        reasoning_effort=settings.llm_reasoning_effort or None,
        fallback_models=settings.fallback_models,
        timeout=settings.llm_timeout_seconds,
    )
    agent = SupportAgent(
        model, store, knowledge, store_name=settings.store_name, min_score=settings.min_score
    )
    sessions = make_session_factory(make_engine(settings.database_url))
    return SupportService(agent, sessions)


def start_channels(settings: Settings, service: SupportService) -> Callable[[], None]:
    """Start messaging channels in the background. Returns a function that stops them."""
    if settings.telegram_bot_token is None:
        return lambda: None

    from support_agent.channels.telegram import TelegramBot, TelegramClient

    client = TelegramClient(settings.telegram_bot_token.get_secret_value())
    greeting = (
        f"Hi! I'm the {settings.store_name} assistant. I can check on an order or answer "
        "questions about shipping, returns and our products.\n\n"
        "Send /new at any time to start a new conversation."
    )
    bot = TelegramBot(
        client,
        service,
        greeting=greeting,
        rate_limit_per_minute=settings.chat_rate_limit_per_minute,
    )
    stop = threading.Event()
    thread = threading.Thread(target=bot.run_polling, args=(stop,), name="telegram", daemon=True)
    thread.start()

    def stop_bot() -> None:
        stop.set()
        thread.join(timeout=30)
        client.close()

    return stop_bot
