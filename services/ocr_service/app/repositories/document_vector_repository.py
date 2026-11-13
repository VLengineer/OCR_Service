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

_DEFAULT_BATCH_SIZE = 100

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

    async def save_all(self, rows: list[dict], batch_size: int = _DEFAULT_BATCH_SIZE) -> int:
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
            batch_size: Размер одного пакета для executemany (по умолчанию 100).

        Returns:
            int: Количество вставленных записей.
        """
        if not rows:
            return 0

        if batch_size <= 0:
            batch_size = _DEFAULT_BATCH_SIZE

        total_inserted = 0
        document_id = rows[0].get("document_id", "N/A")

        for batch_start in range(0, len(rows), batch_size):
            batch = rows[batch_start : batch_start + batch_size]
            params_list = [
                {
                    "document_id": row["document_id"],
                    "response_id": row.get("response_id"),
                    "counterparty_id": row.get("counterparty_id"),
                    "content": row.get("content"),
                    "embedding": row["embedding"],
                    "metadata": json.dumps(row["metadata"]) if row.get("metadata") is not None else None,
                }
                for row in batch
            ]

            await self._session.execute(_INSERT_SQL, params_list)
            total_inserted += len(params_list)
            logger.info(
                "Сохранён пакет векторов: document_id=%s, batch_size=%d, total_inserted=%d",
                document_id,
                len(params_list),
                total_inserted,
            )

        await self._session.flush()
        await self._session.expire_all()
        logger.info(
            "Сохранено %d векторов для document_id=%s",
            total_inserted,
            document_id,
        )
        return total_inserted
