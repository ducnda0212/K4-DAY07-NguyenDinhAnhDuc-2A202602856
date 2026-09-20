from __future__ import annotations

import math
import re


class FixedSizeChunker:
    """
    Split text into fixed-size chunks with optional overlap.

    Rules:
        - Each chunk is at most chunk_size characters long.
        - Consecutive chunks share overlap characters.
        - The last chunk contains whatever remains.
        - If text is shorter than chunk_size, return [text].
    """

    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]

        step = self.chunk_size - self.overlap
        chunks: list[str] = []
        for start in range(0, len(text), step):
            chunk = text[start : start + self.chunk_size]
            chunks.append(chunk)
            if start + self.chunk_size >= len(text):
                break
        return chunks


class SentenceChunker:
    """
    Split text into chunks of at most max_sentences_per_chunk sentences.

    Sentence detection: split on ". ", "! ", "? " or ".\n".
    Strip extra whitespace from each chunk.
    """

    def __init__(self, max_sentences_per_chunk: int = 3) -> None:
        self.max_sentences_per_chunk = max(1, max_sentences_per_chunk)

    def chunk(self, text: str) -> list[str]:
        stripped_text = text.strip()
        if not stripped_text:
            return []

        # Split after sentence-ending punctuation so the delimiter remains
        # attached to the sentence instead of being discarded by re.split().
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])(?:[ \t]+|\r?\n+)", stripped_text)
            if sentence.strip()
        ]

        return [
            " ".join(sentences[start : start + self.max_sentences_per_chunk])
            for start in range(0, len(sentences), self.max_sentences_per_chunk)
        ]


class RecursiveChunker:
    """
    Recursively split text using separators in priority order.

    Default separator priority:
        ["\n\n", "\n", ". ", " ", ""]
    """

    DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    def __init__(self, separators: list[str] | None = None, chunk_size: int = 500) -> None:
        self.separators = self.DEFAULT_SEPARATORS if separators is None else list(separators)
        self.chunk_size = max(1, chunk_size)

    def chunk(self, text: str) -> list[str]:
        stripped_text = text.strip()
        if not stripped_text:
            return []
        return self._split(stripped_text, self.separators)

    def _split(self, current_text: str, remaining_separators: list[str]) -> list[str]:
        current_text = current_text.strip()
        if not current_text:
            return []
        if len(current_text) <= self.chunk_size:
            return [current_text]

        # No semantic boundary remains: fall back to a safe hard split.
        if not remaining_separators or remaining_separators[0] == "":
            return [
                current_text[start : start + self.chunk_size].strip()
                for start in range(0, len(current_text), self.chunk_size)
                if current_text[start : start + self.chunk_size].strip()
            ]

        separator = remaining_separators[0]
        smaller_separators = remaining_separators[1:]
        if separator not in current_text:
            return self._split(current_text, smaller_separators)

        raw_parts = current_text.split(separator)
        parts: list[str] = []
        for index, raw_part in enumerate(raw_parts):
            # Keep non-whitespace delimiters, notably the period in ". ".
            suffix = separator if index < len(raw_parts) - 1 and not separator.isspace() else ""
            part = f"{raw_part}{suffix}".strip()
            if part:
                parts.append(part)

        split_parts: list[str] = []
        for part in parts:
            if len(part) > self.chunk_size:
                split_parts.extend(self._split(part, smaller_separators))
            else:
                split_parts.append(part)

        # Merge adjacent small pieces back up to avoid tiny, low-context chunks.
        joiner = separator if separator.isspace() else (" " if separator.endswith(" ") else "")
        chunks: list[str] = []
        buffer = ""
        for part in split_parts:
            candidate = part if not buffer else f"{buffer}{joiner}{part}"
            if len(candidate) <= self.chunk_size:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(buffer)
                buffer = part

        if buffer:
            chunks.append(buffer)
        return chunks


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def compute_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    cosine_similarity = dot(a, b) / (||a|| * ||b||)

    Returns 0.0 if either vector has zero magnitude.
    """
    magnitude_a = math.sqrt(_dot(vec_a, vec_a))
    magnitude_b = math.sqrt(_dot(vec_b, vec_b))
    if magnitude_a == 0.0 or magnitude_b == 0.0:
        return 0.0
    return _dot(vec_a, vec_b) / (magnitude_a * magnitude_b)


class ChunkingStrategyComparator:
    """Run all built-in chunking strategies and compare their results."""

    def compare(self, text: str, chunk_size: int = 200) -> dict:
        safe_chunk_size = max(1, chunk_size)
        fixed_overlap = min(50, safe_chunk_size - 1)
        strategy_chunks = {
            "fixed_size": FixedSizeChunker(
                chunk_size=safe_chunk_size,
                overlap=fixed_overlap,
            ).chunk(text),
            "by_sentences": SentenceChunker().chunk(text),
            "recursive": RecursiveChunker(chunk_size=safe_chunk_size).chunk(text),
        }

        result: dict[str, dict] = {}
        for strategy_name, chunks in strategy_chunks.items():
            count = len(chunks)
            result[strategy_name] = {
                "count": count,
                "avg_length": sum(len(chunk) for chunk in chunks) / count if count else 0.0,
                "chunks": chunks,
            }
        return result
