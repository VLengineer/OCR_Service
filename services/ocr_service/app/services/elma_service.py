"""
Сервис для работы с ELMA365 API.
"""
import base64
import httpx
import logging
from typing import List, Optional

from app.core.config import settings
from app.schemas.schemas import ElmaDocument

logger = logging.getLogger(__name__)


class ElmaService:
    """Сервис для взаимодействия с ELMA365 API."""

    def __init__(self) -> None:
        self._base_url = settings.elma_base_url.rstrip("/")
        self._api_token = settings.elma_token
        self._list_path = settings.elma_list_path
        self._timeout = float(settings.elma_request_timeout_sec)

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_token}",
            "Content-Type": "application/json",
        }

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    async def get_documents_list(self) -> List[ElmaDocument]:
        """
        Получить список документов из ELMA365.

        ELMA365 возвращает массив объектов с полями __id, __name и т.д.
        Pydantic-модель ElmaDocument использует aliases для маппинга.
        """
        url = f"{self._base_url}{self._list_path}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=self._auth_headers())
                response.raise_for_status()

                data = response.json()

                # ELMA365 может возвращать список напрямую или вложенный
                items: list = data if isinstance(data, list) else data.get("items", data.get("documents", []))

                documents: List[ElmaDocument] = []
                for item in items:
                    documents.append(ElmaDocument.model_validate(item))

                logger.info("Получено %d документов из ELMA365", len(documents))
                return documents

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error при запросе к ELMA365 API: %s", e.response.status_code)
            raise
        except httpx.HTTPError as e:
            logger.error("Ошибка при запросе к ELMA365 API: %s", e)
            raise

    async def download_document(self, document_url: str) -> Optional[bytes]:
        """
        Скачать документ из ELMA365.

        Returns:
            Содержимое документа или None при ошибке.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(document_url, headers=self._auth_headers())
                response.raise_for_status()
                return response.content

        except httpx.HTTPError as e:
            logger.error("Ошибка при скачивании документа %s: %s", document_url, e)
            return None

    async def get_document_base64(self, document_url: str) -> Optional[str]:
        """Получить документ в формате base64."""
        content = await self.download_document(document_url)
        if content:
            return base64.b64encode(content).decode("utf-8")
        return None
