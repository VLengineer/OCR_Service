"""
Сервис конвертации документов.

Определяет тип документа и конвертирует его в унифицированный формат:
- Word/PDF с текстом → извлечение текста → [text]
- PDF-скан → конвертация страниц в изображения → [base64_image_1, ...]
- Изображение → [base64_image]
"""

import base64
import logging

from app.schemas.schemas import DocumentConvertResponse
from app.services.document_converter import DocumentConverter, DocumentType

logger = logging.getLogger(__name__)


class DocumentConvertService:
    """Сервис конвертации документов в унифицированный формат.

    Attributes:
        _converter: Конвертер документов для определения типа и преобразования.
    """

    def __init__(self, document_converter: DocumentConverter) -> None:
        """Инициализация сервиса.

        Args:
            document_converter: Конвертер документов.
        """
        self._converter = document_converter

    async def convert_document(self, document_base64: str) -> DocumentConvertResponse:
        """Конвертирует документ в унифицированный формат.

        Определяет тип документа и выполняет соответствующую конвертацию:
        - Word → извлечение текста, возврат [text]
        - PDF с текстом → извлечение текста, возврат [text]
        - PDF-скан → конвертация страниц в изображения, возврат [base64, ...]
        - Изображение → возврат [base64_image]

        Args:
            document_base64: Base64 закодированный документ.

        Returns:
            DocumentConvertResponse: Результат конвертации с типом документа
            и массивом страниц/листов.

        Raises:
            ValueError: Если тип документа не поддерживается.
            Exception: Если произошла ошибка при конвертации.
        """
        logger.info("Начало конвертации документа")

        try:
            doc_type = self._converter.detect_document_type(document_base64)
            logger.info(f"Определён тип документа: {doc_type}")
        except Exception as e:
            logger.error(f"Ошибка определения типа документа: {e}")
            raise ValueError(f"Не удалось определить тип документа: {e}") from e

        if doc_type == DocumentType.WORD:
            return await self._convert_word(document_base64)
        elif doc_type == DocumentType.PDF_TEXT:
            return await self._convert_pdf_text(document_base64)
        elif doc_type == DocumentType.PDF_SCAN:
            return await self._convert_pdf_scan(document_base64)
        elif doc_type == DocumentType.IMAGE:
            return await self._convert_image(document_base64)
        else:
            raise ValueError(f"Неподдерживаемый тип документа: {doc_type}")

    async def _convert_word(self, document_base64: str) -> DocumentConvertResponse:
        """Конвертирует Word документ.

        Args:
            document_base64: Base64 закодированный Word документ.

        Returns:
            DocumentConvertResponse: Результат с извлечённым текстом.
        """
        logger.info("Конвертация Word документа")
        text = self._converter.extract_text_from_word(document_base64)
        logger.info(f"Извлечён текст из Word: {len(text)} символов")
        return DocumentConvertResponse(
            document_type=DocumentType.WORD,
            document_sheets=[text],
        )

    async def _convert_pdf_text(self, document_base64: str) -> DocumentConvertResponse:
        """Конвертирует PDF с текстовым слоем.

        Args:
            document_base64: Base64 закодированный PDF документ.

        Returns:
            DocumentConvertResponse: Результат с извлечённым текстом.
        """
        logger.info("Конвертация PDF с текстом")
        text = self._converter.extract_text_from_pdf_with_text(document_base64)
        logger.info(f"Извлечён текст из PDF: {len(text)} символов")
        return DocumentConvertResponse(
            document_type=DocumentType.PDF_TEXT,
            document_sheets=[text],
        )

    async def _convert_pdf_scan(self, document_base64: str) -> DocumentConvertResponse:
        """Конвертирует PDF-скан в массив изображений.

        Args:
            document_base64: Base64 закодированный PDF-скан.

        Returns:
            DocumentConvertResponse: Результат с массивом base64 изображений страниц.
        """
        logger.info("Конвертация PDF-скана в изображения")
        images = self._converter.convert_pdf_to_images(document_base64)
        logger.info(f"PDF-скан конвертирован в {len(images)} изображений")
        return DocumentConvertResponse(
            document_type=DocumentType.PDF_SCAN,
            document_sheets=images,
        )

    async def _convert_image(self, document_base64: str) -> DocumentConvertResponse:
        """Конвертирует изображение.

        Args:
            document_base64: Base64 закодированное изображение.

        Returns:
            DocumentConvertResponse: Результат с base64 изображением.
        """
        logger.info("Конвертация изображения")
        image_bytes = base64.b64decode(document_base64)
        image_b64 = self._converter.convert_image_to_base64(image_bytes)
        logger.info("Изображение конвертировано в base64")
        return DocumentConvertResponse(
            document_type=DocumentType.IMAGE,
            document_sheets=[image_b64],
        )
