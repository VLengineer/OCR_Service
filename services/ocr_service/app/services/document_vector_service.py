"""
Оркестратор векторизации документов.
Координирует чанкинг, получение эмбеддингов и сохранение в БД.
"""

import gc
import logging

from app.repositories.document_vector_repository import DocumentVectorRepository
from app.schemas.schemas import DocumentVectorizeRequest, DocumentVectorizeResponse
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService, EMBED_BATCH_SIZE

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

        Обработка выполняется потоково батчами по EMBED_BATCH_SIZE чанков:
        в любой момент времени в памяти находится только один батч чанков,
        один батч эмбеддингов и один батч строк для вставки.

        Args:
            request: Запрос на векторизацию документа.

        Returns:
            DocumentVectorizeResponse: Результат векторизации.
        """
        logger.info("Начало векторизации: document_id=%s", request.document_id)
        logger.info("Размер текста: %d символов, document_id=%s", len(request.content), request.document_id)

        # 1. Разбиваем текст на чанки
        chunks = self._chunking_service.split(request.content)
        if not chunks:
            logger.warning("Текст документа %s пуст после чанкинга", request.document_id)
            return DocumentVectorizeResponse(
                document_id=request.document_id,
                chunks_count=0,
            )

        total_chunks = len(chunks)
        total_batches = (total_chunks + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
        logger.info(
            "Документ %s разбит на %d чанков (%d батчей по %d)",
            request.document_id,
            total_chunks,
            total_batches,
            EMBED_BATCH_SIZE,
        )
        logger.info("Общий размер чанков: %d символов", sum(len(c) for c in chunks))

        # 2. Обрабатываем чанки потоково батчами
        total_saved = 0
        for batch_index in range(total_batches):
            start = batch_index * EMBED_BATCH_SIZE
            end = start + EMBED_BATCH_SIZE
            chunk_batch = chunks[start:end]

            logger.info(
                "Обработка батча %d/%d: %d чанков, document_id=%s",
                batch_index + 1,
                total_batches,
                len(chunk_batch),
                request.document_id,
            )

            # 2.1. Получаем эмбеддинги для текущего батча
            embeddings = await self._embedding_service.embed_batch(chunk_batch)

            # 2.2. Формируем строки для вставки только для текущего батча
            rows = []
            for chunk_text, embedding in zip(chunk_batch, embeddings):
                rows.append({
                    "document_id": request.document_id,
                    "response_id": request.response_id,
                    "counterparty_id": request.counterparty_id,
                    "content": chunk_text,
                    "embedding": str(embedding),
                    "metadata": request.metadata,
                })

            # 2.3. Освобождаем промежуточные объекты текущего батча
            del chunk_batch
            del embeddings
            gc.collect()

            # 2.4. Сохраняем батч в БД
            saved = await self._repository.save_all(rows)
            total_saved += saved

            # 2.5. Освобождаем строки текущего батча
            del rows
            gc.collect()

            logger.info(
                "Батч %d/%d сохранён: %d записей, всего сохранено %d, document_id=%s",
                batch_index + 1,
                total_batches,
                saved,
                total_saved,
                request.document_id,
            )

        # Освобождаем список всех чанков после потоковой обработки
        del chunks
        gc.collect()

        logger.info("Векторизация завершена: document_id=%s, chunks=%d", request.document_id, total_saved)
        return DocumentVectorizeResponse(
            document_id=request.document_id,
            chunks_count=total_saved,
        )
