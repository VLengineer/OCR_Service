"""
Сервис HTTP-запросов к n8n webhook'ам.
Отправляет запросы на OCR-обработку и создание документов.
"""

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.schemas.schemas import Document, DocumentRequest, OCRRequest

logger = logging.getLogger(__name__)


class RequestService:
    """Сервис для отправки HTTP-запросов к n8n webhook'ам."""

    def __init__(self) -> None:
        """Инициализация сервиса запросов."""
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Получает или создаёт HTTP клиент.

        Returns:
            httpx.AsyncClient: HTTP клиент
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=settings.n8n_request_timeout_sec
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

    async def create_document(
        self,
        request: DocumentRequest,
    ) -> dict[str, Any]:
        """
        Отправляет запрос на создание документа.

        Args:
            request: Данные документа

        Returns:
            dict[str, Any]: Ответ от webhook

        Raises:
            httpx.HTTPError: При ошибке HTTP-запроса
        """
        client = await self._get_client()
        url = settings.n8n_create_doc_webhook_url

        try:
            logger.info(
                f"Отправка запроса создания документа: "
                f"task_id={request.task_id}, "
                f"document_id={request.document_id}"
            )

            response = await client.post(
                url,
                json=request.model_dump(mode="json"),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Создание документа успешно: task_id={request.task_id}, "
                f"document_id={request.document_id}"
            )
            return result

        except httpx.TimeoutException as e:
            logger.error(
                f"Таймаут запроса создания документа: "
                f"task_id={request.task_id}, error={e}"
            )
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP ошибка создания документа: "
                f"status={e.response.status_code}, "
                f"task_id={request.task_id}, error={e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Ошибка создания документа: "
                f"task_id={request.task_id}, error={e}"
            )
            raise

    async def recognize_document(
        self,
        document: Document,
    ) -> dict[str, Any]:
        """
        Отправляет запрос на распознавание документа.

        Args:
            document: Документ для распознавания

        Returns:
            dict[str, Any]: Ответ от webhook

        Raises:
            httpx.HTTPError: При ошибке HTTP-запроса
        """
        client = await self._get_client()
        url = settings.n8n_recognize_webhook_url

        try:
            logger.info(
                f"Отправка запроса распознавания документа: "
                f"document_id={document.document_id}, "
                f"document_type={document.document_type}"
            )

            response = await client.post(
                url,
                json=document.model_dump(mode="json"),
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            result = response.json()
            logger.info(
                f"Распознавание документа успешно: "
                f"document_id={document.document_id}"
            )
            return result

        except httpx.TimeoutException as e:
            logger.error(
                f"Таймаут запроса распознавания документа: "
                f"document_id={document.document_id}, error={e}"
            )
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP ошибка распознавания документа: "
                f"status={e.response.status_code}, "
                f"document_id={document.document_id}, error={e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Ошибка распознавания документа: "
                f"document_id={document.document_id}, error={e}"
            )
            raise
