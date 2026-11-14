"""Application settings, loaded from environment variables or a ``.env`` file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Store
    store_name: str = "Trailhead Supply Co."
    store_backend: Literal["mock", "shopify"] = "mock"
    shopify_shop_domain: str | None = None
    shopify_access_token: SecretStr | None = None
    policies_dir: Path | None = Field(
        default=None, description="Folder of Markdown policies. Defaults to the demo policies."
    )

    # Language model (any OpenAI-compatible API; defaults to a local Ollama server)
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "granite4.2:8b"
    llm_api_key: SecretStr | None = None
    llm_reasoning_effort: str | None = "none"
    llm_timeout_seconds: float = 300.0

    # Embeddings and retrieval
    embeddings_backend: Literal["ollama", "fastembed", "hashing"] = "ollama"
    embeddings_model: str = "nomic-embed-text"
    ollama_base_url: str = "http://localhost:11434"
    retrieval_min_score: float | None = Field(
        default=None,
        description="Minimum similarity for a passage to count as relevant. "
        "Defaults to a value tuned for the chosen embeddings backend.",
    )

    # App
    database_url: str = "sqlite:///data/local/support.db"
    admin_password: SecretStr | None = Field(
        default=None, description="Enables the admin page at /admin when set."
    )
    allowed_origins: list[str] = Field(
        default_factory=list, description="Websites allowed to embed the chat widget."
    )
    chat_rate_limit_per_minute: int = 20
    max_message_chars: int = 2000

    @model_validator(mode="after")
    def _check_shopify(self) -> Settings:
        if self.store_backend == "shopify" and not (
            self.shopify_shop_domain and self.shopify_access_token
        ):
            raise ValueError(
                "STORE_BACKEND=shopify needs SHOPIFY_SHOP_DOMAIN and SHOPIFY_ACCESS_TOKEN"
            )
        return self

    @property
    def min_score(self) -> float:
        if self.retrieval_min_score is not None:
            return self.retrieval_min_score
        # Measured on the demo knowledge base: unrelated questions score up to
        # about 0.46 with nomic-embed-text, relevant ones 0.6 and above.
        return {"ollama": 0.55, "fastembed": 0.55, "hashing": 0.2}[self.embeddings_backend]


@lru_cache
def get_settings() -> Settings:
    return Settings()
