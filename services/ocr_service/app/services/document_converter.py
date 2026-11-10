"""
Конвертер документов: определение типа и конвертация форматов.
Отвечает за распознавание типа документа и преобразование
между форматами (Word, PDF, изображения, base64).
"""

import base64
import io
import logging
from typing import List

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from PIL import Image

logger = logging.getLogger(__name__)


class DocumentType:
    """Константы типов документов."""
    WORD = "word"
    PDF_TEXT = "pdf_text"
    PDF_SCAN = "pdf_scan"
    IMAGE = "image"


class DocumentConverter:
    """Конвертер документов: определение типа и конвертация форматов."""

    # DPI для рендеринга PDF в изображения
    PDF_RENDER_DPI = 2.0  # 2x zoom для лучшего качества

    def _clean_base64(self, base64_data: str) -> str:
        """
        Очищает base64 строку от префиксов data URI.

        Args:
            base64_data: Base64 строка, возможно с префиксом data URI

        Returns:
            str: Очищенная base64 строка
        """
        # Удаляем префикс data URI, если он есть
        # Пример: data:application/pdf;base64,
        if base64_data.startswith('data:'):
            # Ищем запятую, после которой идут данные
            comma_index = base64_data.find(',')
            if comma_index != -1:
                base64_data = base64_data[comma_index + 1:]
                logger.debug("Удален префикс data URI из base64")
        
        return base64_data

    def detect_document_type(self, base64_data: str) -> str:
        """
        Определяет тип документа по содержимому.

        Args:
            base64_data: Base64 закодированные данные документа

        Returns:
            str: Тип документа (word, pdf_text, pdf_scan, image)
        """
        try:
            # Очищаем base64 от возможных префиксов
            cleaned_base64 = self._clean_base64(base64_data)
            file_bytes = base64.b64decode(cleaned_base64)

            # Логируем первые байты для диагностики
            logger.debug(f"Первые байты документа: {file_bytes[:10].hex()}")

            # Проверка на Word документ (DOCX) - ZIP архив с сигнатурой PK
            if file_bytes[:4] == b"PK\x03\x04":
                try:
                    doc = DocxDocument(io.BytesIO(file_bytes))
                    if doc.paragraphs:
                        logger.debug("Определён тип: Word документ")
                        return DocumentType.WORD
                except Exception:
                    pass

            # Проверка на PDF
            if file_bytes[:4] == b"%PDF":
                pdf_doc = fitz.Document(stream=file_bytes, filetype="pdf")
                has_text = False

                for page_num in range(len(pdf_doc)):
                    page = pdf_doc[page_num]
                    text = page.get_text().strip()  # type: ignore[attr-defined]
                    if text:
                        has_text = True
                        break

                pdf_doc.close()

                if has_text:
                    logger.debug("Определён тип: PDF с текстом")
                    return DocumentType.PDF_TEXT
                else:
                    logger.debug("Определён тип: PDF-скан")
                    return DocumentType.PDF_SCAN

            # Проверка на изображение
            try:
                img = Image.open(io.BytesIO(file_bytes))
                img.verify()
                logger.debug("Определён тип: Изображение")
                return DocumentType.IMAGE
            except Exception:
                pass

            logger.warning(
                "Не удалось определить тип документа, "
                "по умолчанию PDF-скан"
            )
            return DocumentType.PDF_SCAN

        except Exception as e:
            logger.error(f"Ошибка определения типа документа: {e}")
            return DocumentType.PDF_SCAN

    def extract_text_from_word(self, base64_data: str) -> str:
        """
        Извлекает текст из Word документа.

        Args:
            base64_data: Base64 закодированный Word документ

        Returns:
            str: Извлечённый текст
        """
        try:
            # Очищаем base64 от возможных префиксов
            cleaned_base64 = self._clean_base64(base64_data)
            file_bytes = base64.b64decode(cleaned_base64)
            doc = DocxDocument(io.BytesIO(file_bytes))

            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)

            full_text = "\n".join(text_parts)
            logger.info(f"Извлечён текст из Word: {len(full_text)} символов")
            return full_text

        except Exception as e:
            logger.error(f"Ошибка извлечения текста из Word: {e}")
            raise

    def extract_text_from_pdf_with_text(self, base64_data: str) -> str:
        """
        Извлекает текст из PDF с текстовым слоем.

        Args:
            base64_data: Base64 закодированный PDF документ

        Returns:
            str: Извлечённый текст
        """
        try:
            # Очищаем base64 от возможных префиксов
            cleaned_base64 = self._clean_base64(base64_data)
            file_bytes = base64.b64decode(cleaned_base64)
            pdf_doc = fitz.Document(stream=file_bytes, filetype="pdf")

            text_parts = []
            for page_num in range(len(pdf_doc)):
                page = pdf_doc[page_num]
                text = page.get_text()  # type: ignore[attr-defined]
                if text.strip():
                    text_parts.append(text)

            pdf_doc.close()

            full_text = "\n".join(text_parts)
            logger.info(f"Извлечён текст из PDF: {len(full_text)} символов")
            return full_text

        except Exception as e:
            logger.error(f"Ошибка извлечения текста из PDF: {e}")
            raise

    def convert_pdf_to_images(self, base64_data: str) -> List[str]:
        """
        Конвертирует страницы PDF в изображения (base64).

        Args:
            base64_data: Base64 закодированный PDF документ

        Returns:
            List[str]: Список base64 закодированных изображений страниц
        """
        try:
            # Очищаем base64 от возможных префиксов
            cleaned_base64 = self._clean_base64(base64_data)
            file_bytes = base64.b64decode(cleaned_base64)
            
            # Логируем размер документа для диагностики
            logger.info(f"Размер PDF документа: {len(file_bytes)} байт")
            
            pdf_doc = fitz.Document(stream=file_bytes, filetype="pdf")

            images_base64 = []
            for page_num in range(len(pdf_doc)):
                page = pdf_doc[page_num]

                # Рендерим страницу в изображение с высоким DPI
                mat = fitz.Matrix(self.PDF_RENDER_DPI, self.PDF_RENDER_DPI)
                pix = page.get_pixmap(matrix=mat)  # type: ignore[attr-defined]

                # Конвертируем в PNG
                img_bytes = pix.tobytes("png")
                img_base64 = base64.b64encode(img_bytes).decode("utf-8")
                images_base64.append(img_base64)

                logger.debug(
                    f"Конвертирована страница {page_num + 1}/{len(pdf_doc)}"
                )

            pdf_doc.close()

            logger.info(
                f"PDF конвертирован в {len(images_base64)} изображений"
            )
            return images_base64

        except Exception as e:
            logger.error(f"Ошибка конвертации PDF в изображения: {e}")
            raise

    def convert_image_to_base64(self, image_bytes: bytes) -> str:
        """
        Конвертирует изображение в base64.

        Args:
            image_bytes: Байты изображения

        Returns:
            str: Base64 закодированное изображение
        """
        try:
            img_base64 = base64.b64encode(image_bytes).decode("utf-8")
            logger.debug("Изображение конвертировано в base64")
            return img_base64
        except Exception as e:
            logger.error(f"Ошибка конвертации изображения в base64: {e}")
            raise
