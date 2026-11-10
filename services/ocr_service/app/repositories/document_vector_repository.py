"""
Репозиторий для записи векторов документов в таблицу document_vector_store.
Использует raw SQL через sqlalchemy.text(), потому что тип VECTOR(768)
не поддерживается SQLAlchemy без расширения pgvector.
"""

import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_INSERT_SQL = text("""
    INSERT INTO document_vector_store
        (document_id, response_id, counterparty_id, content, embedding, metadata)
    VALUES
        (:document_id, :response_id, :counterparty_id, :content, CAST(:embedding AS vector), :metadata)
""")


class DocumentVectorRepository:
    """Репозиторий для сохранения векторных представлений документов."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_all(self, rows: list[dict]) -> int:
        """
        Сохраняет батч векторов в таблицу document_vector_store.

        Args:
            rows: Список словарей с ключами:
                - document_id (str, required)
                - response_id (str | None)
                - counterparty_id (str | None)
                - content (str | None)
                - embedding (str — строковое представление вектора, например "[0.1, 0.2, ...]")
                - metadata (dict | None)

        Returns:
            int: Количество вставленных записей.
        """
        if not rows:
            return 0

        inserted = 0
        for row in rows:
            params = {
                "document_id": row["document_id"],
                "response_id": row.get("response_id"),
                "counterparty_id": row.get("counterparty_id"),
                "content": row.get("content"),
                "embedding": row["embedding"],
                "metadata": json.dumps(row["metadata"]) if row.get("metadata") is not None else None,
            }
            await self._session.execute(_INSERT_SQL, params)
            inserted += 1

        await self._session.flush()
        logger.info("Сохранено %d векторов для document_id=%s", inserted, rows[0]["document_id"] if rows else "N/A")
        return inserted
