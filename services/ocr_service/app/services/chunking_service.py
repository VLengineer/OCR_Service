"""
Сервис разбивки текста на чанки.
Использует character-based splitting с overlap.
Граница чанка — по концу предложения/абзаца (не режет слова).
"""

import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChunkingService:
    """Разбивает текст на перекрывающиеся чанки фиксированного размера."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        """
        Инициализация сервиса чанкинга.

        Args:
            chunk_size: Размер чанка в символах (по умолчанию из settings).
            chunk_overlap: Overlap между чанками в символах (по умолчанию из settings).
        """
        self._chunk_size = chunk_size or settings.chunk_size
        self._chunk_overlap = chunk_overlap or settings.chunk_overlap

    def split(self, text: str) -> list[str]:
        """
        Разбивает текст на чанки размером chunk_size с overlap chunk_overlap.

        Не режет слова — ищет последний пробел в пределах chunk_size.
        Пустые чанки пропускаются.

        Args:
            text: Исходный текст для разбивки.

        Returns:
            list[str]: Список непустых чанков.
        """
        if not text or not text.strip():
            return []

        chunks: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + self._chunk_size

            if end >= text_len:
                # Последний фрагмент — берём всё до конца
                chunk = text[start:]
            else:
                # Ищем границу по пробелу, чтобы не резать слова
                split_pos = self._find_split_position(text, start, end)
                chunk = text[start:split_pos]
                end = split_pos

            stripped = chunk.strip()
            if stripped:
                chunks.append(stripped)

            # Сдвигаемся с учётом overlap
            start = end - self._chunk_overlap
            if start <= (end - self._chunk_size):
                # Защита от бесконечного цикла при overlap >= chunk_size
                start = end

        logger.info("Разбито на %d чанков (chunk_size=%d, overlap=%d)", len(chunks), self._chunk_size, self._chunk_overlap)
        return chunks

    @staticmethod
    def _find_split_position(text: str, start: int, end: int) -> int:
        """
        Находит позицию разбивки, не разрезающую слова.

        Ищет последний пробел/символ переноса в пределах [start, end).
        Если не находит — использует end как есть.

        Args:
            text: Исходный текст.
            start: Начало текущего фрагмента.
            end: Желаемый конец фрагмента.

        Returns:
            int: Позиция для разбивки.
        """
        # Сначала ищем конец предложения/абзаца
        for separator in ["\n\n", "\n", ". ", "! ", "? "]:
            pos = text.rfind(separator, start, end)
            if pos != -1:
                return pos + len(separator)

        # Если не нашли — ищем последний пробел
        space_pos = text.rfind(" ", start, end)
        if space_pos != -1:
            return space_pos + 1

        # Если и пробела нет — режем где есть (редкий случай)
        return end
