"""
Оркестратор векторизации документов.
Координирует чанкинг, получение эмбеддингов и сохранение в БД.
"""

import logging

from app.repositories.document_vector_repository import DocumentVectorRepository
from app.schemas.schemas import DocumentVectorizeRequest, DocumentVectorizeResponse
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class DocumentVectorService:
    """Сервис векторизации документов: чанкинг → эмбеддинги → сохранение."""

    def __init__(
        self,
        chunking_service: ChunkingService,
        embedding_service: EmbeddingService,
        repository: DocumentVectorRepository,
    ) -> None:
        self._chunking_service = chunking_service
        self._embedding_service = embedding_service
        self._repository = repository

    async def vectorize(self, request: DocumentVectorizeRequest) -> DocumentVectorizeResponse:
        """
        Векторизует текст документа: разбивает на чанки, получает эмбеддинги,
        сохраняет в таблицу document_vector_store.

        Args:
            request: Запрос на векторизацию документа.

        Returns:
            DocumentVectorizeResponse: Результат векторизации.
        """
        logger.info("Начало векторизации: document_id=%s", request.document_id)

        # 1. Разбиваем текст на чанки
        chunks = self._chunking_service.split(request.content)
        if not chunks:
            logger.warning("Текст документа %s пуст после чанкинга", request.document_id)
            return DocumentVectorizeResponse(
                document_id=request.document_id,
                chunks_count=0,
            )

        logger.info("Документ %s разбит на %d чанков", request.document_id, len(chunks))

        # 2. Получаем эмбеддинги для всех чанков
        embeddings = await self._embedding_service.embed_batch(chunks)

        # 3. Формируем строки для вставки
        rows = []
        for chunk, embedding in zip(chunks, embeddings):
            rows.append({
                "document_id": request.document_id,
                "response_id": request.response_id,
                "counterparty_id": request.counterparty_id,
                "content": chunk,
                "embedding": str(embedding),
                "metadata": request.metadata,
            })

        # 4. Сохраняем в БД
        count = await self._repository.save_all(rows)

        logger.info("Векторизация завершена: document_id=%s, chunks=%d", request.document_id, count)
        return DocumentVectorizeResponse(
            document_id=request.document_id,
            chunks_count=count,
        )
