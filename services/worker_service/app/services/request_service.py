"""
Сервис HTTP-запросов к n8n webhook'ам для worker_service.
Отправляет запросы на OCR-обработку и fill_rag.
"""

import logging
import time
from typing import Any

import httpx

from app.core.config import settings
from app.core.utils import sanitize_url
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
            logger.info(
                f"Создание HTTP клиента: timeout={settings.n8n_request_timeout_sec}s"
            )
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.n8n_request_timeout_sec)
            )
        return self._client

    async def close(self) -> None:
        """Закрывает HTTP клиент."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            logger.debug("HTTP клиент закрыт")

    @staticmethod
    def _safe_read_response_body(response: httpx.Response) -> Any:
        """
        Безопасно читает тело HTTP-ответа для логирования.

        Args:
            response: HTTP-ответ.

        Returns:
            Any: Распарсенное JSON-тело или сырые текст/байты при ошибке парсинга.
        """
        try:
            return response.json()
        except Exception:
            try:
                return response.text
            except Exception:
                return "<unable to read response body>"

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
        sanitized_url = sanitize_url(url)
        payload = request.model_dump(mode="json")

        logger.info(
            f"Отправка OCR запроса: task_id={request.task_id}, "
            f"document_id={request.document_id}, "
            f"pages={len(request.base64_document)}, "
            f"url={sanitized_url}"
        )
        logger.debug(
            f"OCR payload: task_id={request.task_id}, "
            f"payload={payload}, url={sanitized_url}"
        )

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.n8n_token}",
        }

        start_time = time.monotonic()
        try:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            elapsed_ms = (time.monotonic() - start_time) * 1000
            result = response.json()
            logger.info(
                f"OCR запрос успешен: task_id={request.task_id}, "
                f"document_id={request.document_id}, "
                f"status_code={response.status_code}, elapsed_ms={elapsed_ms:.2f}"
            )
            logger.debug(
                f"OCR response body: task_id={request.task_id}, "
                f"body={result}"
            )
            return result

        except httpx.ConnectError as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                f"Ошибка подключения OCR запроса: task_id={request.task_id}, "
                f"document_id={request.document_id}, url={sanitized_url}, "
                f"elapsed_ms={elapsed_ms:.2f}, error={e}"
            )
            raise
        except httpx.TimeoutException as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                f"Таймаут OCR запроса: task_id={request.task_id}, "
                f"document_id={request.document_id}, url={sanitized_url}, "
                f"timeout={settings.n8n_request_timeout_sec}s, "
                f"elapsed_ms={elapsed_ms:.2f}, error={e}"
            )
            raise
        except httpx.HTTPStatusError as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            body = self._safe_read_response_body(e.response)
            logger.error(
                f"HTTP ошибка OCR запроса: task_id={request.task_id}, "
                f"document_id={request.document_id}, url={sanitized_url}, "
                f"status_code={e.response.status_code}, elapsed_ms={elapsed_ms:.2f}, "
                f"body={body}, error={e}"
            )
            raise
        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                f"Ошибка OCR запроса: task_id={request.task_id}, "
                f"document_id={request.document_id}, url={sanitized_url}, "
                f"elapsed_ms={elapsed_ms:.2f}, error={e}"
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
        sanitized_url = sanitize_url(url)
        payload = request.model_dump(mode="json", by_alias=True)

        logger.info(
            f"Отправка fill_rag запроса: task_id={request.task_id}, "
            f"__id={request.id}, __name={request.name}, "
            f"url={sanitized_url}"
        )
        logger.debug(
            f"fill_rag payload: task_id={request.task_id}, "
            f"payload={payload}, url={sanitized_url}"
        )

        # by_alias=True — n8n ожидает ключи с алиасами (__id, __name, __createdAt и т.д.)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.n8n_token}",
        }

        start_time = time.monotonic()
        try:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()

            elapsed_ms = (time.monotonic() - start_time) * 1000
            result = response.json()
            logger.info(
                f"fill_rag запрос успешен: task_id={request.task_id}, "
                f"__id={request.id}, status_code={response.status_code}, "
                f"elapsed_ms={elapsed_ms:.2f}"
            )
            logger.debug(
                f"fill_rag response body: task_id={request.task_id}, "
                f"__id={request.id}, body={result}"
            )
            return result

        except httpx.ConnectError as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                f"Ошибка подключения fill_rag запроса: task_id={request.task_id}, "
                f"__id={request.id}, url={sanitized_url}, "
                f"elapsed_ms={elapsed_ms:.2f}, error={e}"
            )
            raise
        except httpx.TimeoutException as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                f"Таймаут fill_rag запроса: task_id={request.task_id}, "
                f"__id={request.id}, url={sanitized_url}, "
                f"timeout={settings.n8n_request_timeout_sec}s, "
                f"elapsed_ms={elapsed_ms:.2f}, error={e}"
            )
            raise
        except httpx.HTTPStatusError as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            body = self._safe_read_response_body(e.response)
            logger.error(
                f"HTTP ошибка fill_rag запроса: task_id={request.task_id}, "
                f"__id={request.id}, url={sanitized_url}, "
                f"status_code={e.response.status_code}, elapsed_ms={elapsed_ms:.2f}, "
                f"body={body}, error={e}"
            )
            raise
        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                f"Ошибка fill_rag запроса: task_id={request.task_id}, "
                f"__id={request.id}, url={sanitized_url}, "
                f"elapsed_ms={elapsed_ms:.2f}, error={e}"
            )
            raise
