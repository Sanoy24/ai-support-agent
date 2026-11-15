# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Support agent with read-only order lookup, policy and catalog search, and human handoff.
- Verified order lookup: email must match, with a cap on failed attempts per conversation.
- Knowledge index over Markdown policies and the product catalog, with local Ollama embeddings.
- OpenAI-compatible LLM client that works with Ollama and hosted providers.
- Demo store with fictional orders, and a read-only Shopify adapter.
- Chat API with rate limiting, and conversation, handoff and unanswered-question storage.
- Embeddable chat widget rendered in a Shadow DOM.
- Demo storefront and admin dashboard with password sign-in.
- Docker image, Compose setup and CI for Python, the frontend and the image.
- Retries for rate limits and temporary provider errors, and OpenRouter fallback models.

### Fixed

- A slow model call no longer blocks other conversations from being saved.
- The assistant offers a person instead of handing off automatically when it can't answer,
  and declines discount and prompt-injection requests without creating a handoff.
- Questions the help content can't answer are logged even when a person takes over.
