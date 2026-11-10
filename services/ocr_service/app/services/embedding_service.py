"""
Сервис получения эмбеддингов через Ollama Embedding API.
Отправляет батч чанков и получает векторные представления.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


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

    async def embed_batch(self, chunks: list[str]) -> list[list[float]]:
        """
        Получает эмбеддинги для батча чанков.

        Args:
            chunks: Список текстовых чанков для векторизации.

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
        url = f"{self._base_url}/api/embed"
        payload = {
            "model": settings.ollama_embedding_model,
            "input": chunks,
        }

        try:
            logger.info("Запрос эмбеддингов: %d чанков, модель=%s", len(chunks), settings.ollama_embedding_model)

            response = await client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            embeddings = data.get("embeddings")

            if embeddings is None:
                raise RuntimeError("Ollama вернул ответ без ключа 'embeddings'")

            if len(embeddings) != len(chunks):
                raise RuntimeError(
                    "Количество эмбеддингов (%d) не совпадает с количеством чанков (%d)"
                    % (len(embeddings), len(chunks))
                )

            logger.info("Получено %d эмбеддингов, размерность=%d", len(embeddings), len(embeddings[0]) if embeddings else 0)
            return embeddings

        except httpx.TimeoutException:
            logger.error("Таймаут запроса эмбеддингов к Ollama (url=%s)", url)
            raise
        except httpx.HTTPStatusError as e:
            logger.error("HTTP ошибка при запросе эмбеддингов: status=%d", e.response.status_code)
            raise
        except Exception:
            logger.error("Ошибка при получении эмбеддингов")
            raise
