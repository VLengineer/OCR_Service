"""
Сервис обработки и маршрутизации документов.
Определяет тип документа и направляет на соответствующую обработку.
"""

import logging

from app.schemas.schemas import Document
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
        2. Конвертирует документ в изображения (unified pipeline):
           - Word → PDF (LibreOffice) → изображения
           - PDF → изображения
           - Изображение → base64
        3. Создаёт задачу OCR с массивом страниц

        Args:
            document: Документ для обработки
        """
        try:
            document_id = document.document_id
            logger.info(f"Начало обработки документа: id={document_id}")

            # Определяем тип документа
            doc_type = self._document_converter.detect_document_type(document.document_base64)
            logger.info(f"Тип документа: {doc_type}")

            # Конвертируем документ в изображения по unified pipeline
            images_base64 = self._convert_to_images(
                doc_type, document.document_base64
            )
            logger.debug(
                f"Конвертация завершена: id={document_id}, "
                f"страниц={len(images_base64)}, "
                f"первый_размер={len(images_base64[0]) if images_base64 else 0}"
            )

            # Создаём задачу OCR
            await self._task_repository.add_task(
                document_id=document_id,
                base64_document=images_base64,
                document_type=document.document_type,
            )
            logger.info(
                f"Документ отправлен на OCR: id={document_id}, "
                f"страниц={len(images_base64)}"
            )

            logger.info(f"Документ успешно обработан: id={document_id}")

        except Exception as e:
            logger.error(
                f"Ошибка обработки документа {document.document_id}: {e}"
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
