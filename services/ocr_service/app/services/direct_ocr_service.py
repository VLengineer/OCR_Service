"""
Сервис прямой OCR-обработки документов (без очереди).

Определяет тип документа и напрямую отправляет запросы на OCR
в n8n webhook, минуя очередь задач (TaskRepository).
"""

import base64
import logging
from typing import Any

from app.schemas.schemas import Document, DocumentRequest, OCRRequest
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

    async def process_image(self, document: Document) -> dict[str, Any]:
        """
        Прямая OCR-обработка изображения (без очереди).

        Логика:
        1. Проверяет что документ является изображением
        2. Конвертирует изображение в base64
        3. Формирует OCRRequest
        4. Напрямую отправляет запрос в n8n webhook

        Args:
            document: Документ (изображение) для обработки

        Returns:
            dict[str, Any]: Результат OCR-обработки от n8n

        Raises:
            ValueError: Если документ не является изображением
            httpx.HTTPError: При ошибке HTTP-запроса к n8n
        """
        try:
            document_id = document.document_id
            logger.info(
                f"Начало прямой OCR-обработки изображения: id={document_id}"
            )

            # Проверяем тип документа
            doc_type = self._document_converter.detect_document_type(
                document.document_base64
            )
            if doc_type != DocumentType.IMAGE:
                raise ValueError(
                    f"Ожидалось изображение, получен тип: {doc_type}"
                )

            # Конвертируем в base64
            image_bytes = base64.b64decode(document.document_base64)
            image_base64 = self._document_converter.convert_image_to_base64(
                image_bytes
            )

            # Формируем OCR-запрос
            ocr_request = OCRRequest(
                document_id=document_id,
                base64_document=[image_base64],
                document_type=document.document_type,
            )

            # Прямая отправка на OCR
            result = await self._request_service.ocr_request(ocr_request)

            logger.info(
                f"Изображение успешно обработано через прямой OCR: "
                f"id={document_id}"
            )
            return result

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Ошибка прямой OCR-обработки изображения "
                f"{document.document_id}: {e}"
            )
            raise

    async def process_pdf_scan(self, document: Document) -> dict[str, Any]:
        """
        Прямая OCR-обработка PDF-скана (без очереди).

        Логика:
        1. Проверяет что документ является PDF-сканом
        2. Конвертирует страницы PDF в изображения
        3. Формирует OCRRequest со всеми страницами
        4. Напрямую отправляет запрос в n8n webhook

        Args:
            document: Документ (PDF-скан) для обработки

        Returns:
            dict[str, Any]: Результат OCR-обработки от n8n

        Raises:
            ValueError: Если документ не является PDF-сканом
            httpx.HTTPError: При ошибке HTTP-запроса к n8n
        """
        try:
            document_id = document.document_id
            logger.info(
                f"Начало прямой OCR-обработки PDF-скана: id={document_id}"
            )

            # Проверяем тип документа
            doc_type = self._document_converter.detect_document_type(
                document.document_base64
            )
            if doc_type != DocumentType.PDF_SCAN:
                raise ValueError(
                    f"Ожидался PDF-скан, получен тип: {doc_type}"
                )

            # Конвертируем PDF в изображения
            images_base64 = self._document_converter.convert_pdf_to_images(
                document.document_base64
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
                f"PDF-скан успешно обработан через прямой OCR: "
                f"id={document_id}, страниц={len(images_base64)}"
            )
            return result

        except ValueError:
            raise
        except Exception as e:
            logger.error(
                f"Ошибка прямой OCR-обработки PDF-скана "
                f"{document.document_id}: {e}"
            )
            raise

    async def process(
        self, document: Document
    ) -> dict[str, Any] | None:
        """
        Универсальная прямая обработка документа (без очереди).

        Автоматически определяет тип документа и маршрутизирует:
        - IMAGE → прямая OCR-обработка
        - PDF_SCAN → прямая OCR-обработка всех страниц
        - WORD → извлечение текста и отправка в create_document
        - PDF_TEXT → извлечение текста и отправка в create_document

        Args:
            document: Документ для обработки

        Returns:
            dict[str, Any] | None: Результат обработки или None для текстовых документов

        Raises:
            httpx.HTTPError: При ошибке HTTP-запроса к n8n
        """
        try:
            document_id = document.document_id
            logger.info(
                f"Начало прямой обработки документа: id={document_id}"
            )

            # Определяем тип документа
            doc_type = self._document_converter.detect_document_type(
                document.document_base64
            )
            logger.info(f"Тип документа: {doc_type}")

            if doc_type == DocumentType.IMAGE:
                # Изображение — прямая OCR-обработка
                return await self.process_image(document)

            elif doc_type == DocumentType.PDF_SCAN:
                # PDF-скан — прямая OCR-обработка
                return await self.process_pdf_scan(document)

            elif doc_type == DocumentType.WORD:
                # Word документ — извлекаем текст и отправляем
                text = self._document_converter.extract_text_from_word(
                    document.document_base64
                )

                document_request = DocumentRequest(
                    document_id=document_id,
                    raw_text=text,
                    document_type=document.document_type,
                )

                await self._request_service.create_document(document_request)
                logger.info(
                    f"Word документ обработан напрямую: id={document_id}"
                )
                return None

            elif doc_type == DocumentType.PDF_TEXT:
                # PDF с текстом — извлекаем текст и отправляем
                text = self._document_converter.extract_text_from_pdf_with_text(
                    document.document_base64
                )

                document_request = DocumentRequest(
                    document_id=document_id,
                    raw_text=text,
                    document_type=document.document_type,
                )

                await self._request_service.create_document(document_request)
                logger.info(
                    f"PDF с текстом обработан напрямую: id={document_id}"
                )
                return None

            logger.info(
                f"Документ успешно обработан напрямую: id={document_id}"
            )
            return None

        except Exception as e:
            logger.error(
                f"Ошибка прямой обработки документа "
                f"{document.document_id}: {e}"
            )
            raise
