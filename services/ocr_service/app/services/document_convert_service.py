"""
Сервис конвертации документов.

Определяет тип документа и конвертирует его в унифицированный формат изображений:
- Word → PDF (LibreOffice) → [base64_image_1, ...]
- PDF → [base64_image_1, ...]
- Изображение → [base64_image]
"""

import base64
import logging

from app.schemas.schemas import DocumentConvertResponse
from app.services.document_converter import DocumentConverter, DocumentType

logger = logging.getLogger(__name__)


class DocumentConvertService:
    """Сервис конвертации документов в унифицированный формат изображений.

    Attributes:
        document_converter: Конвертер документов для определения типа
            и преобразования.
    """

    def __init__(self, document_converter: DocumentConverter) -> None:
        """Инициализация сервиса.

        Args:
            document_converter: Конвертер документов.
        """
        self.document_converter = document_converter

    async def convert_document(self, document_base64: str) -> DocumentConvertResponse:
        """Конвертирует документ в унифицированный формат изображений.

        Определяет тип документа и выполняет соответствующую конвертацию:
        - Word → PDF (LibreOffice) → [base64_image_1, ...]
        - PDF → [base64_image_1, ...]
        - Изображение → [base64_image]

        Args:
            document_base64: Base64 закодированный документ.

        Returns:
            DocumentConvertResponse: Результат конвертации с типом документа
            и массивом страниц/листов в формате base64.

        Raises:
            ValueError: Если тип документа не поддерживается.
            Exception: Если произошла ошибка при конвертации.
        """
        try:
            document_type = self.document_converter.detect_document_type(document_base64)
            logger.info(f"Определён тип документа: {document_type.value}")

            if document_type == DocumentType.WORD:
                # Word → PDF (через LibreOffice) → изображения
                pdf_base64 = self.document_converter.convert_word_to_pdf(document_base64)
                page_images = self.document_converter.convert_pdf_to_images(pdf_base64)
                logger.info(
                    f"Word документ конвертирован в {len(page_images)} изображений"
                )
                return DocumentConvertResponse(
                    document_type=document_type.value,
                    document_sheets=page_images,
                )

            elif document_type == DocumentType.PDF:
                # PDF → изображения
                page_images = self.document_converter.convert_pdf_to_images(document_base64)
                logger.info(
                    f"PDF документ конвертирован в {len(page_images)} изображений"
                )
                return DocumentConvertResponse(
                    document_type=document_type.value,
                    document_sheets=page_images,
                )

            elif document_type == DocumentType.IMAGE:
                # Image → base64
                raw_bytes = base64.b64decode(
                    self.document_converter._clean_base64(document_base64)
                )
                image_base64 = self.document_converter.convert_image_to_base64(raw_bytes)
                logger.info("Изображение подготовлено для OCR")
                return DocumentConvertResponse(
                    document_type=document_type.value,
                    document_sheets=[image_base64],
                )

            else:
                raise ValueError(f"Неподдерживаемый тип документа: {document_type}")

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Ошибка конвертации документа: {e}")
            raise
