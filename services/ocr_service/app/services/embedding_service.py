"""
Сервис получения эмбеддингов через Ollama Embedding API.
Отправляет батч чанков и получает векторные представления.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 20


class EmbeddingService:
    """Получает эмбеддинги через Ollama /api/embed."""

    def __init__(self, timeout: float = 120.0) -> None:
        """
        Инициализация сервиса эмбеддингов.

        Args:
            timeout: Таймаут HTTP-запроса к Ollama в секундах.
        """
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def _base_url(self) -> str:
        """Базовый URL Ollama API."""
        return f"http://{settings.ollama_host}:{settings.ollama_port}"

    async def _get_client(self) -> httpx.AsyncClient:
        """Получает или создаёт HTTP-клиент."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def close(self) -> None:
        """Закрывает HTTP-клиент."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("HTTP-клиент EmbeddingService закрыт")

    async def _embed_single_batch(
        self,
        client: httpx.AsyncClient,
        batch: list[str],
        batch_index: int,
        total_batches: int,
    ) -> list[list[float]]:
        """
        Получает эмбеддинги для одного батча чанков.

        Args:
            client: HTTP-клиент для запроса.
            batch: Список текстовых чанков для векторизации.
            batch_index: Номер текущего батча (1-based).
            total_batches: Общее количество батчей.

        Returns:
            list[list[float]]: Список векторов для батча.

        Raises:
            httpx.TimeoutException: При таймауте запроса.
            httpx.HTTPStatusError: При HTTP-ошибке.
            RuntimeError: При неожиданном формате ответа.
        """
        url = f"{self._base_url}/api/embed"
        payload = {
            "model": settings.ollama_embedding_model,
            "input": batch,
        }

        try:
            logger.info(
                "Батч %d/%d: %d чанков",
                batch_index,
                total_batches,
                len(batch),
            )
            logger.debug("Ollama API URL: %s", url)
            logger.debug("Ollama base_url: %s", self._base_url)

            logger.info("Отправка запроса к Ollama: %d чанков", len(batch))
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info("Получен ответ от Ollama: status=%d, content-length=%s", response.status_code, response.headers.get('content-length', 'unknown'))

            data = response.json()
            # НЕ используем str(data) — это создаёт огромную строку для больших эмбеддингов
            embeddings = data.get("embeddings")
            if embeddings:
                logger.info(
                    "Размер ответа: эмбеддингов=%d, размерность=%d",
                    len(embeddings),
                    len(embeddings[0]) if embeddings else 0,
                )

            if embeddings is None:
                raise RuntimeError("Ollama вернул ответ без ключа 'embeddings'")

            if len(embeddings) != len(batch):
                raise RuntimeError(
                    "Количество эмбеддингов (%d) не совпадает с количеством чанков (%d)"
                    % (len(embeddings), len(batch))
                )

            logger.info(
                "Получено %d эмбеддингов, размерность=%d",
                len(embeddings),
                len(embeddings[0]) if embeddings else 0,
            )
            return embeddings

        except httpx.TimeoutException:
            logger.error("Таймаут запроса эмбеддингов к Ollama (url=%s)", url)
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP ошибка при запросе эмбеддингов: status=%d",
                e.response.status_code,
            )
            raise
        except Exception:
            logger.error("Ошибка при получении эмбеддингов")
            raise

    async def embed_batch(self, chunks: list[str]) -> list[list[float]]:
        """
        Получает эмбеддинги для одного готового батча чанков.

        Батч уже сформирован вызывающей стороной (DocumentVectorService),
        поэтому повторная нарезка на под-батчи здесь не выполняется.

        Args:
            chunks: Список текстовых чанков для векторизации (размер <= EMBED_BATCH_SIZE).

        Returns:
            list[list[float]]: Список векторов (каждый размерности 768).

        Raises:
            httpx.TimeoutException: При таймауте запроса.
            httpx.HTTPStatusError: При HTTP-ошибке.
            RuntimeError: При неожиданном формате ответа.
        """
        if not chunks:
            return []

        client = await self._get_client()
        total_chunks = len(chunks)

        logger.info(
            "Запрос эмбеддингов: %d чанков, модель=%s",
            total_chunks,
            settings.ollama_embedding_model,
        )

        embeddings = await self._embed_single_batch(client, chunks, batch_index=1, total_batches=1)

        logger.info(
            "Всего получено %d эмбеддингов для %d чанков",
            len(embeddings),
            total_chunks,
        )
        return embeddings
