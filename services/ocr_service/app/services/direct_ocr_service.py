"""
Сервис прямой OCR-обработки документов (без очереди).

Определяет тип документа, конвертирует его в изображения через unified pipeline
и напрямую отправляет запросы на OCR в n8n webhook, минуя очередь задач.
"""

import logging
from typing import Any

from app.schemas.schemas import Document, OCRRequest
from app.services.document_converter import DocumentConverter, DocumentType
from app.services.request_service import RequestService

logger = logging.getLogger(__name__)


class DirectOCRService:
    """Сервис для прямой OCR-обработки документов без очереди."""

    def __init__(
        self,
        request_service: RequestService,
        document_converter: DocumentConverter,
    ) -> None:
        """
        Инициализация сервиса прямой OCR-обработки.

        Args:
            request_service: Сервис HTTP-запросов к n8n
            document_converter: Конвертер документов
        """
        self._request_service = request_service
        self._document_converter = document_converter

    async def process(
        self, document: Document
    ) -> dict[str, Any]:
        """
        Универсальная прямая OCR-обработка документа (без очереди).

        Логика:
        1. Определяет тип документа
        2. Конвертирует документ в изображения (unified pipeline):
           - Word → PDF (LibreOffice) → изображения
           - PDF → изображения
           - Изображение → base64
        3. Формирует OCRRequest со всеми страницами
        4. Напрямую отправляет запрос в n8n webhook

        Args:
            document: Документ для обработки

        Returns:
            dict[str, Any]: Результат OCR-обработки от n8n

        Raises:
            httpx.HTTPError: При ошибке HTTP-запроса к n8n
            ValueError: Если тип документа не поддерживается
        """
        try:
            document_id = document.document_id
            logger.info(
                f"Начало прямой OCR-обработки документа: id={document_id}"
            )

            # Определяем тип документа
            doc_type = self._document_converter.detect_document_type(
                document.document_base64
            )
            logger.info(f"Тип документа: {doc_type}")

            # Конвертируем документ в изображения по unified pipeline
            images_base64 = self._convert_to_images(
                doc_type, document.document_base64
            )

            # Формируем OCR-запрос
            ocr_request = OCRRequest(
                document_id=document_id,
                base64_document=images_base64,
                document_type=document.document_type,
            )

            # Прямая отправка на OCR
            result = await self._request_service.ocr_request(ocr_request)

            logger.info(
                f"Документ успешно обработан через прямой OCR: "
                f"id={document_id}, страниц={len(images_base64)}"
            )
            return result

        except Exception as e:
            logger.error(
                f"Ошибка прямой OCR-обработки документа "
                f"{document.document_id}: {e}"
            )
            raise

    def _convert_to_images(
        self, doc_type: DocumentType, document_base64: str
    ) -> list[str]:
        """
        Конвертирует документ в список изображений base64.

        Args:
            doc_type: Тип документа
            document_base64: Документ в формате base64

        Returns:
            list[str]: Список base64 изображений страниц

        Raises:
            ValueError: Если тип документа не поддерживается
        """
        if doc_type == DocumentType.WORD:
            logger.info("Конвертация Word документа в изображения")
            pdf_base64 = self._document_converter.convert_word_to_pdf(
                document_base64
            )
            return self._document_converter.convert_pdf_to_images(pdf_base64)

        if doc_type == DocumentType.PDF:
            logger.info("Конвертация PDF документа в изображения")
            return self._document_converter.convert_pdf_to_images(
                document_base64
            )

        if doc_type == DocumentType.IMAGE:
            logger.info("Подготовка изображения для OCR")
            return [document_base64]

        raise ValueError(f"Неподдерживаемый тип документа: {doc_type}")
