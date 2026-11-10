"""
Сервис обработки и маршрутизации документов.
Определяет тип документа и направляет на соответствующую обработку.
"""

import base64
import logging

from app.schemas.schemas import Document, DocumentRequest, OCRRequest
from app.services.document_converter import DocumentConverter, DocumentType
from app.services.request_service import RequestService
from app.repositories.task_repository import TaskRepository


logger = logging.getLogger(__name__)


class DocumentService:
    """Сервис для обработки и маршрутизации документов."""

    def __init__(
        self,
        request_service: RequestService,
        task_repository: TaskRepository,
        document_converter: DocumentConverter,
    ) -> None:
        """
        Инициализация сервиса документов.

        Args:
            request_service: Сервис HTTP-запросов к n8n
            task_repository: Репозиторий управления задачами
            document_converter: Конвертер документов
        """
        self._request_service = request_service
        self._task_repository = task_repository
        self._document_converter = document_converter

    async def processing(self, document: Document) -> None:
        """
        Обрабатывает документ с маршрутизацией по типу.

        Логика:
        1. Определяет тип документа
        2. Маршрутизирует:
           - Word/PDF с текстом → извлечение текста → n8n create_document
           - Изображение → base64 → задача OCR (1 страница)
           - PDF-скан → страницы в картинки → задача OCR (массив)

        Args:
            document: Документ для обработки
        """
        try:
            document_id = document.document_id
            logger.info(f"Начало обработки документа: id={document_id}")

            # Определяем тип документа
            doc_type = self._document_converter.detect_document_type(document.document_base64)
            logger.info(f"Тип документа: {doc_type}")

            if doc_type == DocumentType.WORD:
                # Word документ - извлекаем текст и отправляем
                text = self._document_converter.extract_text_from_word(document.document_base64)

                document_request = DocumentRequest(
                    document_id=document_id,
                    raw_text=text,
                    document_type=document.document_type,
                )

                await self._request_service.create_document(document_request)
                logger.info(f"Word документ обработан: id={document_id}")

            elif doc_type == DocumentType.PDF_TEXT:
                # PDF с текстом - извлекаем текст и отправляем
                text = self._document_converter.extract_text_from_pdf_with_text(
                    document.document_base64
                )

                document_request = DocumentRequest(
                    document_id=document_id,
                    raw_text=text,
                    document_type=document.document_type,
                )

                await self._request_service.create_document(document_request)
                logger.info(f"PDF с текстом обработан: id={document_id}")

            elif doc_type == DocumentType.IMAGE:
                # Изображение - конвертируем в base64 и создаём задачу OCR
                image_bytes = base64.b64decode(document.document_base64)
                image_base64 = self._document_converter.convert_image_to_base64(image_bytes)

                ocr_request = OCRRequest(
                    document_id=document_id,
                    base64_document=[image_base64],
                    document_type=document.document_type,
                )

                await self._task_repository.add_task(
                    document_id=document_id,
                    base64_document=[image_base64],
                    document_type=document.document_type,
                )
                logger.info(f"Изображение отправлено на OCR: id={document_id}")

            elif doc_type == DocumentType.PDF_SCAN:
                # PDF-скан - конвертируем в изображения и создаём задачу OCR
                images_base64 = self._document_converter.convert_pdf_to_images(
                    document.document_base64
                )

                await self._task_repository.add_task(
                    document_id=document_id,
                    base64_document=images_base64,
                    document_type=document.document_type,
                )
                logger.info(
                    f"PDF-скан отправлен на OCR: id={document_id}, "
                    f"страниц={len(images_base64)}"
                )

            logger.info(f"Документ успешно обработан: id={document_id}")

        except Exception as e:
            logger.error(
                f"Ошибка обработки документа {document.document_id}: {e}"
            )
            raise


