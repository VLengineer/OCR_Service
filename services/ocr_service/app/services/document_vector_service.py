"""
Оркестратор векторизации документов.
Координирует чанкинг, получение эмбеддингов и сохранение в БД.
"""

import asyncio
import ctypes
import gc
import logging
import resource

from app.repositories.document_vector_repository import DocumentVectorRepository
from app.schemas.schemas import DocumentVectorizeRequest, DocumentVectorizeResponse
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService, EMBED_BATCH_SIZE

logger = logging.getLogger(__name__)

# Семафор для ограничения конкурентной векторизации:
# в памяти одновременно обрабатывается не более 2 документов.
_semaphore = asyncio.Semaphore(2)


def _malloc_trim() -> None:
    """Принудительно возвращает память glibc allocator обратно в ОС.
    
    Критично для контейнеров! Без этого память накапливается и не освобождается.
    """
    try:
        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim(0)
    except (OSError, AttributeError):
        pass  # Не критично, если не удалось


def _get_memory_usage_mb() -> float:
    """Возвращает текущее использование памяти процессом в МБ (RSS из /proc/self/status)."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    # Формат: "VmRSS:    123456 kB"
                    return int(line.split()[1]) / 1024
    except (FileNotFoundError, ValueError, IndexError):
        pass
    # Fallback для не-Linux систем
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _get_cgroup_memory_mb() -> float:
    """Возвращает реальное потребление памяти всем контейнером (cgroup) в МБ.
    
    Читает все возможные cgroup файлы для диагностики.
    """
    memory_values = {}
    
    # cgroup v2
    try:
        with open("/sys/fs/cgroup/memory.current") as f:
            value = int(f.read().strip()) / (1024 * 1024)
            memory_values["v2_memory.current"] = value
    except (FileNotFoundError, ValueError, PermissionError) as e:
        memory_values["v2_memory.current"] = f"error: {e}"
    
    # cgroup v1
    try:
        with open("/sys/fs/cgroup/memory/memory.usage_in_bytes") as f:
            value = int(f.read().strip()) / (1024 * 1024)
            memory_values["v1_memory.usage"] = value
    except (FileNotFoundError, ValueError, PermissionError) as e:
        memory_values["v1_memory.usage"] = f"error: {e}"
    
    # cgroup v2 max
    try:
        with open("/sys/fs/cgroup/memory.max") as f:
            value = f.read().strip()
            memory_values["v2_memory.max"] = value
    except (FileNotFoundError, ValueError, PermissionError) as e:
        memory_values["v2_memory.max"] = f"error: {e}"
    
    # Логируем все значения для диагностики (только при первом вызове)
    if not hasattr(_get_cgroup_memory_mb, "_logged"):
        logger.info("Cgroup memory diagnostics: %s", memory_values)
        _get_cgroup_memory_mb._logged = True
    
    # Возвращаем максимальное значение (наиболее точное)
    numeric_values = [v for v in memory_values.values() if isinstance(v, (int, float))]
    return max(numeric_values) if numeric_values else 0.0


def _get_peak_memory_mb() -> float:
    """Возвращает пиковое использование памяти процессом в МБ."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _log_memory(label: str) -> None:
    """Логирует текущее потребление памяти: process RSS и cgroup."""
    logger.info(
        "%s: process RSS=%.2f MB, cgroup=%.2f MB, peak=%.2f MB",
        label,
        _get_memory_usage_mb(),
        _get_cgroup_memory_mb(),
        _get_peak_memory_mb(),
    )


class DocumentVectorService:
    """Сервис векторизации документов: чанкинг -> эмбеддинги -> сохранение."""

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
        # Проверка памяти перед началом обработки
        current_memory = _get_memory_usage_mb()
        cgroup_memory = _get_cgroup_memory_mb()
        peak_memory = _get_peak_memory_mb()
        logger.info("Начало векторизации: document_id=%s", request.document_id)
        logger.info("Размер текста: %d символов, document_id=%s", len(request.content), request.document_id)
        logger.info(
            "Память: process RSS=%.2f MB, cgroup=%.2f MB, peak=%.2f MB",
            current_memory, cgroup_memory, peak_memory,
        )

        # Защита от OOM: если cgroup память > 3.5GB, отказываемся от обработки
        # (лимит контейнера 4G, оставляем запас 0.5GB)
        MEMORY_THRESHOLD_MB = 3500
        if cgroup_memory > MEMORY_THRESHOLD_MB:
            logger.error(
                "Отказ от векторизации: высокое потребление памяти контейнером "
                "(cgroup: %.2f MB, process RSS: %.2f MB, порог: %d MB). document_id=%s",
                cgroup_memory, current_memory, MEMORY_THRESHOLD_MB, request.document_id,
            )
            raise MemoryError(
                f"Слишком высокое потребление памяти контейнером: {cgroup_memory:.2f} MB "
                f"(порог: {MEMORY_THRESHOLD_MB} MB). Подождите и повторите попытку."
            )

        # Ограничение на размер текста (защита от слишком больших документов)
        MAX_TEXT_SIZE = 1_000_000  # 1 миллион символов ~ 1 MB текста
        if len(request.content) > MAX_TEXT_SIZE:
            logger.error(
                "Текст слишком большой: %d символов (максимум %d), document_id=%s",
                len(request.content), MAX_TEXT_SIZE, request.document_id,
            )
            raise ValueError(
                f"Текст слишком большой: {len(request.content)} символов. "
                f"Максимум: {MAX_TEXT_SIZE} символов."
            )

        # 1. Освобождаем оригинальный текст запроса — он больше не нужен,
        #    чанки будут получаться потоково.
        original_content = request.content
        request.content = None  # type: ignore[assignment]

        # 2. Подготавливаем потоковый генератор чанков
        _log_memory("Перед чанкингом")
        chunk_iterator = self._chunking_service.split_iter(original_content)

        # Общая статистика по документу
        total_chunks = 0
        total_batches = 0
        total_saved = 0

        # 3. Обрабатываем чанки потоково батчами по EMBED_BATCH_SIZE
        chunk_batch: list[str] = []
        batch_index = 0
        for chunk in chunk_iterator:
            total_chunks += 1
            chunk_batch.append(chunk)

            if len(chunk_batch) < EMBED_BATCH_SIZE:
                continue

            batch_index += 1
            total_batches += 1
            total_saved += await self._process_chunk_batch(
                request=request,
                chunk_batch=chunk_batch,
                batch_index=batch_index,
                total_batches_label="?",
            )
            chunk_batch = []

        # Обрабатываем остаток чанков, не набравших полный батч
        if chunk_batch:
            batch_index += 1
            total_batches += 1
            total_saved += await self._process_chunk_batch(
                request=request,
                chunk_batch=chunk_batch,
                batch_index=batch_index,
                total_batches_label=str(total_batches),
            )

        if total_chunks == 0:
            logger.warning("Текст документа %s пуст после чанкинга", request.document_id)
            _log_memory("Векторизация завершена (пустой документ)")
            return DocumentVectorizeResponse(
                document_id=request.document_id,
                chunks_count=0,
            )

        logger.info(
            "Документ %s разбит на %d чанков (%d батчей по %d)",
            request.document_id, total_chunks, total_batches, EMBED_BATCH_SIZE,
        )

        # Освобождаем ссылку на итератор и оригинальный текст
        del chunk_iterator
        del original_content
        gc.collect()
        _malloc_trim()  # Принудительно возвращаем память в ОС

        _log_memory("Векторизация завершена")
        logger.info("Векторизация завершена: document_id=%s, chunks=%d", request.document_id, total_saved)
        return DocumentVectorizeResponse(
            document_id=request.document_id,
            chunks_count=total_saved,
        )

    async def _process_chunk_batch(
        self,
        request: DocumentVectorizeRequest,
        chunk_batch: list[str],
        batch_index: int,
        total_batches_label: str,
    ) -> int:
        """
        Обрабатывает один батч чанков: эмбеддинги -> формирование строк -> сохранение в БД.

        После обработки явно освобождает все промежуточные объекты и возвращает
        память glibc allocator обратно в ОС.

        Args:
            request: Исходный запрос на векторизацию (content уже обнулён).
            chunk_batch: Батч чанков для обработки.
            batch_index: Порядковый номер батча (1-based).
            total_batches_label: Строка с общим количеством батчей для логов
                ("?", пока общее число неизвестно).

        Returns:
            int: Количество сохранённых записей.
        """
        _log_memory(
            f"Батч {batch_index}/{total_batches_label} ПЕРЕД Ollama (чанков={len(chunk_batch)})"
        )

        # 3.1. Получаем эмбеддинги для готового батча чанков
        embeddings = await self._embedding_service.embed_batch(chunk_batch)
        _log_memory(
            f"Батч {batch_index}/{total_batches_label} ПОСЛЕ Ollama (embeddings={len(embeddings)})"
        )

        # 3.2. Формируем строки для вставки только для текущего батча
        rows: list[dict] = []
        for chunk_text, embedding in zip(chunk_batch, embeddings):
            rows.append({
                "document_id": request.document_id,
                "response_id": request.response_id,
                "counterparty_id": request.counterparty_id,
                "content": chunk_text,
                "embedding": str(embedding),
                "metadata": request.metadata,
            })

        # 3.3. Сохраняем батч в БД
        saved = await self._repository.save_all(rows)

        # 3.4. Освобождаем все промежуточные объекты текущего батча
        del chunk_batch
        del embeddings
        del rows
        gc.collect()
        _malloc_trim()  # Принудительно возвращаем память в ОС

        _log_memory(
            f"Батч {batch_index}/{total_batches_label} после сохранения (saved={saved})"
        )

        logger.info(
            "Батч %d/%s сохранён: %d записей, document_id=%s",
            batch_index, total_batches_label, saved, request.document_id,
        )
        return saved
