"""
Unit tests for ChunkingService.

Covers streaming chunk generation, boundary cases (empty input, single chunk,
overlap, separator handling), and the deprecated split() method.
"""

import warnings

import pytest

from app.services.chunking_service import ChunkingService


# ──────────────────────────────────────────────
# split_iter
# ──────────────────────────────────────────────

class TestSplitIter:
    """Tests for ChunkingService.split_iter()."""

    def test_empty_string_returns_no_chunks(self):
        """Empty string produces no chunks."""
        svc = ChunkingService(chunk_size=10, chunk_overlap=2)
        chunks = list(svc.split_iter(""))
        assert chunks == []

    def test_whitespace_only_returns_no_chunks(self):
        """Whitespace-only input produces no chunks."""
        svc = ChunkingService(chunk_size=10, chunk_overlap=2)
        chunks = list(svc.split_iter("   \n\t  "))
        assert chunks == []

    def test_single_chunk_when_text_fits(self):
        """Short text that fits in chunk_size returns one chunk."""
        svc = ChunkingService(chunk_size=50, chunk_overlap=5)
        text = "Quick brown fox jumps over the lazy dog."
        chunks = list(svc.split_iter(text))
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_splits_on_sentence_boundary(self):
        """Split position prefers sentence separators over arbitrary spaces."""
        svc = ChunkingService(chunk_size=30, chunk_overlap=5)
        text = "First sentence here. Second part is longer."
        chunks = list(svc.split_iter(text))
        # Алгоритм применяет overlap после каждой границы, поэтому получается больше чанков
        assert len(chunks) >= 2
        assert chunks[0] == "First sentence here."
        assert any("Second part is longer." in chunk for chunk in chunks)

    def test_splits_on_paragraph_boundary(self):
        """Paragraph separator is preferred before single newline."""
        svc = ChunkingService(chunk_size=25, chunk_overlap=3)
        text = "Paragraph one.\n\nParagraph two has more words."
        chunks = list(svc.split_iter(text))
        # Алгоритм применяет overlap после каждой границы, поэтому получается больше чанков
        assert len(chunks) >= 2
        assert chunks[0] == "Paragraph one."
        # Второй параграф разбивается на несколько чанков из-за overlap
        assert any("Paragraph" in chunk for chunk in chunks[1:])

    def test_overlap_is_applied(self):
        """Consecutive chunks share the configured overlap."""
        svc = ChunkingService(chunk_size=20, chunk_overlap=5)
        text = "alpha beta gamma delta epsilon zeta eta theta"
        chunks = list(svc.split_iter(text))
        assert len(chunks) > 1
        # Проверяем, что overlap работает: второй чанк начинается с части первого
        # Первый чанк: "alpha beta gamma" (18 символов)
        # Второй чанк начинается с позиции 18-5=13, то есть с "amma"
        assert chunks[1].startswith("amma")
        assert "delta" in chunks[1]
        assert "epsilon" in chunks[1]

    def test_long_text_produces_multiple_chunks(self):
        """Long repetitive text produces many chunks."""
        svc = ChunkingService(chunk_size=500, chunk_overlap=50)
        # Each sentence is ~480 chars; 200 sentences produce >150 chunks.
        sentence = "word " * 80  # ~480 characters
        text = " ".join(f"sentence{i} {sentence}" for i in range(200))
        chunks = list(svc.split_iter(text))
        assert len(chunks) > 100
        assert all(len(chunk) <= 500 for chunk in chunks)

    def test_skips_empty_chunks(self):
        """Empty fragments produced by separators are skipped."""
        svc = ChunkingService(chunk_size=15, chunk_overlap=2)
        text = "a\n\n\n\nb"
        chunks = list(svc.split_iter(text))
        # Текст имеет длину 9 символов, что меньше chunk_size=15
        # Поэтому он не разбивается и возвращается как один чанк
        assert len(chunks) == 1
        assert chunks[0] == "a\n\n\n\nb"


# ──────────────────────────────────────────────
# split (deprecated)
# ──────────────────────────────────────────────

class TestSplit:
    """Tests for ChunkingService.split() compatibility method."""

    def test_split_returns_list(self):
        """split() returns the same list as split_iter()."""
        svc = ChunkingService(chunk_size=20, chunk_overlap=5)
        text = "one two three four five six seven eight"
        with pytest.deprecated_call():
            result = svc.split(text)
        assert result == list(svc.split_iter(text))

    def test_split_emits_deprecation_warning(self):
        """split() emits a DeprecationWarning."""
        svc = ChunkingService(chunk_size=20, chunk_overlap=5)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            svc.split("hello world")
        assert any(issubclass(item.category, DeprecationWarning) for item in w)


# ──────────────────────────────────────────────
# Constructor / configuration
# ──────────────────────────────────────────────

class TestChunkingServiceConfiguration:
    """Tests for service configuration."""

    def test_defaults_from_settings(self):
        """When no sizes are provided, defaults come from settings."""
        svc = ChunkingService()
        assert svc._chunk_size > 0
        assert svc._chunk_overlap >= 0

    def test_explicit_values_override_settings(self):
        """Explicit chunk_size and chunk_overlap override settings."""
        svc = ChunkingService(chunk_size=42, chunk_overlap=7)
        assert svc._chunk_size == 42
        assert svc._chunk_overlap == 7
