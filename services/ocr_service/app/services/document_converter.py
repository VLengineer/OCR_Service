"""
Конвертер документов: определение типа и конвертация форматов.
Отвечает за распознавание типа документа и преобразование
между форматами (Word, PDF, изображения, base64).
"""

import base64
import io
import logging
import os
import shutil
import subprocess
import tempfile
from enum import Enum
from typing import List

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from PIL import Image

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Типы документов."""

    WORD = "word"
    PDF = "pdf"
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

    def detect_document_type(self, base64_data: str) -> DocumentType:
        """
        Определяет тип документа по содержимому.

        Args:
            base64_data: Base64 закодированные данные документа

        Returns:
            DocumentType: Тип документа (word, pdf, image)
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
                    if doc.paragraphs is not None:
                        logger.info(
                            "Определён тип: Word документ "
                            "(DOCX, распознан python-docx)"
                        )
                        return DocumentType.WORD
                except Exception as docx_error:
                    logger.warning(
                        f"DOCX не удалось распарсить python-docx: {docx_error}. "
                        f"Всё равно определяем как Word по сигнатуре ZIP"
                    )
                    return DocumentType.WORD

            # Проверка на старый Word документ (.doc) - OLE2 сигнатура
            ole2_signature = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
            if len(file_bytes) >= len(ole2_signature) and file_bytes[:len(ole2_signature)] == ole2_signature:
                logger.info(
                    "Определён тип: Word документ (OLE2, .doc)"
                )
                return DocumentType.WORD

            # Проверка на PDF
            if file_bytes[:4] == b"%PDF":
                logger.info("Определён тип: PDF документ")
                return DocumentType.PDF

            # Проверка на изображение
            # Image.open не читает данные сразу, verify() проверяет сигнатуру.
            # Без close() файловый дескриптор остаётся открытым.
            try:
                with Image.open(io.BytesIO(file_bytes)) as img:
                    img.verify()
                logger.info("Определён тип: Изображение")
                return DocumentType.IMAGE
            except Exception as image_error:
                logger.debug(f"Не удалось распознать изображение: {image_error}")

            logger.warning(
                "Не удалось определить тип документа, "
                "по умолчанию PDF"
            )
            return DocumentType.PDF

        except Exception as e:
            logger.error(f"Ошибка определения типа документа: {e}")
            return DocumentType.PDF

    def convert_word_to_pdf(self, base64_data: str) -> str:
        """
        Конвертирует Word документ в PDF через LibreOffice.

        Args:
            base64_data: Base64 закодированный Word документ

        Returns:
            str: Base64 закодированный PDF документ

        Raises:
            RuntimeError: Если конвертация не удалась.
        """
        cleaned_base64 = self._clean_base64(base64_data)
        file_bytes = base64.b64decode(cleaned_base64)

        temp_dir = tempfile.mkdtemp()
        lo_profile_dir = tempfile.mkdtemp(prefix="lo_profile_")
        temp_docx_path = os.path.join(temp_dir, "document.docx")

        try:
            with open(temp_docx_path, "wb") as temp_docx_file:
                temp_docx_file.write(file_bytes)

            logger.info("Конвертация Word документа в PDF через LibreOffice")

            # Задаём временную HOME и профиль LibreOffice,
            # чтобы избежать ошибок прав в контейнере
            env = {**os.environ, "HOME": lo_profile_dir}

            result = subprocess.run(
                [
                    "libreoffice",
                    "-env:UserInstallation=file:///" + lo_profile_dir.lstrip("/"),
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    temp_dir,
                    temp_docx_path,
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            if result.returncode != 0:
                error_message = (
                    f"LibreOffice завершился с кодом {result.returncode}. "
                    f"stdout: {result.stdout}, stderr: {result.stderr}"
                )
                logger.error(error_message)
                raise RuntimeError(error_message)

            pdf_path = os.path.join(temp_dir, "document.pdf")
            if not os.path.exists(pdf_path):
                error_message = (
                    f"PDF файл не создан. stdout: {result.stdout}, "
                    f"stderr: {result.stderr}"
                )
                logger.error(error_message)
                raise RuntimeError(error_message)

            with open(pdf_path, "rb") as pdf_file:
                pdf_bytes = pdf_file.read()

            logger.info(
                f"Word документ конвертирован в PDF: {len(pdf_bytes)} байт"
            )
            return base64.b64encode(pdf_bytes).decode("utf-8")

        finally:
            # Удаляем временные файлы
            try:
                for filename in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, filename)
                    os.remove(file_path)
                os.rmdir(temp_dir)
                logger.debug("Временные файлы LibreOffice удалены")
            except Exception as cleanup_error:
                logger.warning(
                    f"Не удалось удалить временные файлы: {cleanup_error}"
                )
            
            # Удаляем временный профиль LibreOffice
            try:
                shutil.rmtree(lo_profile_dir)
                logger.debug("Временный профиль LibreOffice удалён")
            except Exception as cleanup_error:
                logger.warning(
                    f"Не удалось удалить временный профиль LibreOffice: {cleanup_error}"
                )

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
            logger.debug(
                f"PDF открыт: страниц={len(pdf_doc)}, "
                f"размер={len(file_bytes)} байт"
            )

            images_base64 = []
            try:
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
                        f"Конвертирована страница {page_num + 1}/{len(pdf_doc)}, "
                        f"размер PNG={len(img_bytes)} байт"
                    )
            finally:
                # Гарантированно закрываем PDF даже при исключении,
                # иначе файловый дескриптор и буферы PyMuPDF не освобождаются
                pdf_doc.close()
                logger.debug("PDF документ закрыт")

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
