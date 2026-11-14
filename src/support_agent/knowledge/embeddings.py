"""Text embedding backends."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from typing import Any, Protocol

import httpx
import numpy as np
import numpy.typing as npt

Vectors = npt.NDArray[np.float32]

_TOKEN = re.compile(r"[a-z0-9]+")

# Common words that carry no meaning for matching questions to policies.
_STOPWORD_TEXT = (
    "a about all am an and any are as at be been but by can could did do does doing for "
    "from get got had has have how i if in into is it its just me my of on or our so than "
    "that the their them then there these they this to too us was we were what when where "
    "which who why will with would you your item items much many"
)
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> Vectors:
        """Return one L2-normalized row per input text."""
        ...


class HashingEmbedder:
    """Dependency-free lexical embedder using the hashing trick.

    It matches shared words rather than meaning, so it is mainly for tests
    and offline demos. Use :class:`FastEmbedEmbedder` for real deployments.
    """

    def __init__(self, dimensions: int = 512) -> None:
        self.dimensions = dimensions

    def embed(self, texts: Sequence[str]) -> Vectors:
        vectors = np.zeros((len(texts), self.dimensions), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in _TOKEN.findall(text.lower()):
                if token in _STOPWORDS:
                    continue
                stem = _light_stem(token)
                digest = hashlib.blake2b(stem.encode(), digest_size=8).digest()
                vectors[row, int.from_bytes(digest, "little") % self.dimensions] += 1.0
        return _normalize(vectors)


class OllamaEmbedder:
    """Semantic embeddings from a local Ollama server (free, runs offline).

    Pull a model first, e.g. ``ollama pull nomic-embed-text``.
    """

    def __init__(
        self,
        model: str = "nomic-embed-text",
        base_url: str = "http://localhost:11434",
        *,
        batch_size: int = 64,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._batch_size = batch_size
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)

    def embed(self, texts: Sequence[str]) -> Vectors:
        rows: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            batch = list(texts[start : start + self._batch_size])
            response = self._client.post("/api/embed", json={"model": self.model, "input": batch})
            response.raise_for_status()
            rows.extend(response.json()["embeddings"])
        return _normalize(np.array(rows, dtype=np.float32))


class FastEmbedEmbedder:
    """Local semantic embeddings via ``fastembed`` (ONNX, no API key needed).

    Install with ``pip install ai-support-agent[local-embeddings]``.
    """

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        try:
            from fastembed import TextEmbedding
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "fastembed is not installed. Install the 'local-embeddings' extra "
                "or set EMBEDDINGS_BACKEND=hashing."
            ) from exc
        self._model: Any = TextEmbedding(model_name=model_name)

    def embed(self, texts: Sequence[str]) -> Vectors:  # pragma: no cover - needs model download
        vectors = np.array(list(self._model.embed(list(texts))), dtype=np.float32)
        return _normalize(vectors)


def _light_stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def _normalize(vectors: Vectors) -> Vectors:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (vectors / norms).astype(np.float32)
