"""Split Markdown documents into heading-aware chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class Chunk:
    source: str
    """Where the text came from, e.g. ``returns.md`` or ``product:TS-TENT-2P``."""
    heading: str
    """Heading path, e.g. ``Returns and Refunds > Return window``."""
    text: str

    def embedding_text(self) -> str:
        return f"{self.heading}\n{self.text}"


def chunk_markdown(source: str, markdown: str, max_chars: int = 1200) -> list[Chunk]:
    """Create one chunk per section, splitting long sections on paragraphs.

    Each chunk keeps its heading path so the answer can cite exactly
    which part of a policy it used.
    """
    chunks: list[Chunk] = []
    path: list[str] = []
    lines: list[str] = []

    def flush() -> None:
        body = "\n".join(lines).strip()
        lines.clear()
        if not body:
            return
        heading = " > ".join(path) or source
        for piece in _split_long(body, max_chars):
            chunks.append(Chunk(source=source, heading=heading, text=piece))

    for line in markdown.splitlines():
        match = _HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            del path[level - 1 :]
            path.append(match.group(2))
        else:
            lines.append(line)
    flush()
    return chunks


def _split_long(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    current = ""
    for paragraph in re.split(r"\n\s*\n", text):
        candidate = f"{current}\n\n{paragraph}".strip()
        if current and len(candidate) > max_chars:
            pieces.append(current)
            current = paragraph.strip()
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces
