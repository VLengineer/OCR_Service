"""
Сервис HTTP-запросов к n8n webhook'ам для worker_service.
Отправляет запросы на OCR-обработку и fill_rag.
"""

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.schemas import OCRRequest, FillRagRequest

logger = logging.getLogger(__name__)


class RequestService:
    """Сервис для отправки HTTP-запросов к n8n webhook'ам."""

    def __init__(self) -> None:
        """Инициализация сервиса запросов."""
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Получает или создаёт HTTP клиент."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.n8n_request_timeout_sec)
            )
        return self._client

    async def close(self) -> None:
        """Закрывает HTTP клиент."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("HTTP клиент закрыт")

    async def ocr_request(self, request: OCRRequest) -> dict[str, Any]:
        """
        Отправляет запрос на OCR-обработку.

        Args:
            request: Данные для OCR-обработки

        Returns:
            dict[str, Any]: Ответ от webhook

        Raises:
            httpx.HTTPError: При ошибке HTTP-запроса
        """
        client = await self._get_client()
        url = settings.n8n_ocr_webhook_url

        try:
            logger.info(
                f"Отправка OCR запроса: task_id={request.task_id}, "
                f"document_id={request.document_id}, "
                f"pages={len(request.base64_document)}"
            )

            response = await client.post(
                url,
                json=request.model_dump(mode="json"),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"OCR запрос успешен: task_id={request.task_id}, "
                f"document_id={request.document_id}"
            )
            return result

        except httpx.TimeoutException as e:
            logger.error(
                f"Таймаут OCR запроса: task_id={request.task_id}, "
                f"document_id={request.document_id}, error={e}"
            )
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP ошибка OCR запроса: status={e.response.status_code}, "
                f"task_id={request.task_id}, error={e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Ошибка OCR запроса: task_id={request.task_id}, error={e}"
            )
            raise

    async def fill_rag_request(self, request: FillRagRequest) -> dict[str, Any]:
        """
        Отправляет запрос на fill_rag обработку.

        Args:
            request: Данные для fill_rag обработки

        Returns:
            dict[str, Any]: Ответ от webhook

        Raises:
            httpx.HTTPError: При ошибке HTTP-запроса
        """
        client = await self._get_client()
        url = settings.n8n_fill_rag_webhook_url

        try:
            logger.info(
                f"Отправка fill_rag запроса: task_id={request.task_id}, "
                f"__id={request.id}, __name={request.name}"
            )

            # by_alias=True — n8n ожидает ключи с алиасами (__id, __name, __createdAt и т.д.)
            response = await client.post(
                url,
                json=request.model_dump(mode="json", by_alias=True),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"fill_rag запрос успешен: task_id={request.task_id}, "
                f"__id={request.id}"
            )
            return result

        except httpx.TimeoutException as e:
            logger.error(
                f"Таймаут fill_rag запроса: task_id={request.task_id}, "
                f"__id={request.id}, error={e}"
            )
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP ошибка fill_rag запроса: status={e.response.status_code}, "
                f"task_id={request.task_id}, error={e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Ошибка fill_rag запроса: task_id={request.task_id}, error={e}"
            )
            raise
