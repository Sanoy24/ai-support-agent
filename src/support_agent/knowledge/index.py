"""In-memory vector index over policy and product chunks.

A store's knowledge base is usually a few hundred chunks, which a
NumPy matrix searches in well under a millisecond. Swap in a vector
database only when the corpus actually needs one.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from support_agent.knowledge.chunking import Chunk, chunk_markdown
from support_agent.knowledge.embeddings import Embedder, Vectors
from support_agent.store.models import Product


@dataclass(frozen=True, slots=True)
class SearchHit:
    chunk: Chunk
    score: float


class KnowledgeIndex:
    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder
        self._chunks: list[Chunk] = []
        self._vectors: Vectors = np.zeros((0, 0), dtype=np.float32)

    def __len__(self) -> int:
        return len(self._chunks)

    def add(self, chunks: Iterable[Chunk]) -> None:
        new = list(chunks)
        if not new:
            return
        vectors = self._embedder.embed([c.embedding_text() for c in new])
        self._vectors = vectors if not self._chunks else np.vstack([self._vectors, vectors])
        self._chunks.extend(new)

    def search(self, query: str, *, limit: int = 4, min_score: float = 0.2) -> list[SearchHit]:
        if not self._chunks or not query.strip():
            return []
        query_vector = self._embedder.embed([query])[0]
        scores = self._vectors @ query_vector
        best = np.argsort(-scores)[:limit]
        return [
            SearchHit(self._chunks[i], float(scores[i])) for i in best if scores[i] >= min_score
        ]


def policy_chunks(directory: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(directory.glob("*.md")):
        chunks.extend(chunk_markdown(path.name, path.read_text("utf-8")))
    return chunks


def product_chunks(products: Iterable[Product]) -> list[Chunk]:
    return [
        Chunk(
            source=f"product:{p.sku}",
            heading=p.title,
            text=(
                f"{p.description}\nPrice: {p.price:.2f} {p.currency}. "
                f"{'In stock' if p.in_stock else 'Out of stock'}."
            ),
        )
        for p in products
    ]
