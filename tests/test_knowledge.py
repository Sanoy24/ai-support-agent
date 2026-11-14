import json
from importlib import resources
from pathlib import Path

import httpx
import numpy as np
import pytest

from support_agent.knowledge import (
    HashingEmbedder,
    KnowledgeIndex,
    OllamaEmbedder,
    chunk_markdown,
    policy_chunks,
    product_chunks,
)
from support_agent.store import MockStore

DEMO_POLICIES = Path(str(resources.files("support_agent.demo").joinpath("policies")))


def test_chunks_keep_heading_path() -> None:
    markdown = "# Returns\n\nIntro.\n\n## Window\n\n30 days.\n\n## Refunds\n\n5 to 7 days.\n"
    chunks = chunk_markdown("returns.md", markdown)
    assert [(c.heading, c.text) for c in chunks] == [
        ("Returns", "Intro."),
        ("Returns > Window", "30 days."),
        ("Returns > Refunds", "5 to 7 days."),
    ]


def test_heading_path_resets_at_same_level() -> None:
    markdown = "# A\n## B\n### C\ntext c\n## D\ntext d\n"
    headings = [c.heading for c in chunk_markdown("x.md", markdown)]
    assert headings == ["A > B > C", "A > D"]


def test_long_sections_split_on_paragraphs() -> None:
    paragraph = "word " * 50
    markdown = "# Big\n\n" + "\n\n".join([paragraph] * 6)
    chunks = chunk_markdown("big.md", markdown, max_chars=600)
    assert len(chunks) > 1
    assert all(len(c.text) <= 600 for c in chunks)
    assert all(c.heading == "Big" for c in chunks)


@pytest.fixture(scope="module")
def index() -> KnowledgeIndex:
    idx = KnowledgeIndex(HashingEmbedder())
    idx.add(policy_chunks(DEMO_POLICIES))
    idx.add(product_chunks(MockStore().list_products()))
    return idx


@pytest.mark.parametrize(
    ("question", "expected_source", "expected_heading"),
    [
        ("How many days do I have to return an item?", "returns.md", "Return window"),
        ("How much does expedited shipping cost?", "shipping.md", "Shipping options"),
        ("Which payment methods do you accept?", "faq.md", "payment methods"),
        ("Is the headlamp rechargeable with USB-C?", "product:TS-HEADLAMP", "Headlamp"),
    ],
)
def test_search_finds_the_right_section(
    index: KnowledgeIndex, question: str, expected_source: str, expected_heading: str
) -> None:
    # The agent reads the top few hits, so measure recall@3 rather than rank 1.
    hits = index.search(question, limit=3)
    assert any(
        h.chunk.source == expected_source and expected_heading in h.chunk.heading for h in hits
    ), [(h.chunk.source, h.chunk.heading, round(h.score, 2)) for h in hits]


def test_unrelated_query_returns_nothing(index: KnowledgeIndex) -> None:
    assert index.search("quantum chromodynamics lattice gauge", min_score=0.3) == []


def test_empty_index_and_blank_query() -> None:
    idx = KnowledgeIndex(HashingEmbedder())
    assert idx.search("anything") == []
    idx.add(chunk_markdown("a.md", "# A\ntext"))
    assert idx.search("   ") == []


def test_ollama_embedder_batches_and_normalizes() -> None:
    calls: list[list[str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/api/embed"
        assert body["model"] == "nomic-embed-text"
        calls.append(body["input"])
        return httpx.Response(200, json={"embeddings": [[3.0, 4.0] for _ in body["input"]]})

    embedder = OllamaEmbedder(batch_size=2, transport=httpx.MockTransport(handler))
    vectors = embedder.embed(["a", "b", "c"])

    assert calls == [["a", "b"], ["c"]]
    assert vectors.shape == (3, 2)
    assert np.allclose(vectors[0], [0.6, 0.8])
