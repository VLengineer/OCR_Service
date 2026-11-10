"""
Unit-тесты для DocumentConverter.

Тестируются методы:
- detect_document_type: определение типа документа
- extract_text_from_word: извлечение текста из Word
- extract_text_from_pdf_with_text: извлечение текста из PDF с текстом
- convert_pdf_to_images: конвертация PDF в изображения
- convert_image_to_base64: конвертация изображения в base64
"""

import base64
import io
from unittest.mock import MagicMock, patch

import pytest

from app.services.document_converter import DocumentConverter, DocumentType


class TestDocumentConverterDetectDocumentType:
    """Тесты для метода detect_document_type."""

    @pytest.fixture
    def converter(self):
        """Создание экземпляра DocumentConverter."""
        return DocumentConverter()

    def test_detect_word_document(self, converter):
        """Тест определения Word документа (DOCX)."""
        # Arrange: байты с сигнатурой ZIP (PK), мокаем DocxDocument
        fake_zip_bytes = b"PK\x03\x04" + b"fake docx content"
        fake_zip_base64 = base64.b64encode(fake_zip_bytes).decode("utf-8")

        mock_paragraph = MagicMock()
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_paragraph]

        with patch(
            "app.services.document_converter.DocxDocument",
            return_value=mock_doc,
        ):
            # Act
            result = converter.detect_document_type(fake_zip_base64)

        # Assert
        assert result == DocumentType.WORD

    def test_detect_pdf_with_text(self, converter):
        """Тест определения PDF с текстовым слоем."""
        # Arrange: мокаем fitz.Document для возврата PDF с текстом
        with patch("app.services.document_converter.fitz.Document") as mock_fitz:
            mock_page = MagicMock()
            mock_page.get_text.return_value = "Текстовое содержимое"
            mock_doc = MagicMock()
            mock_doc.__len__ = MagicMock(return_value=1)
            mock_doc.__getitem__ = MagicMock(return_value=mock_page)
            mock_fitz.return_value = mock_doc

            # Создаём фейковые PDF-байты с сигнатурой %PDF
            pdf_bytes = b"%PDF-1.4 fake content"
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            # Act
            result = converter.detect_document_type(pdf_base64)

            # Assert
            assert result == DocumentType.PDF_TEXT
            mock_fitz.assert_called_once()

    def test_detect_pdf_scan(self, converter):
        """Тест определения PDF-скана (без текста)."""
        # Arrange: мокаем fitz.Document для возврата PDF без текста
        with patch("app.services.document_converter.fitz.Document") as mock_fitz:
            mock_page = MagicMock()
            mock_page.get_text.return_value = ""  # Нет текста
            mock_doc = MagicMock()
            mock_doc.__len__ = MagicMock(return_value=1)
            mock_doc.__getitem__ = MagicMock(return_value=mock_page)
            mock_fitz.return_value = mock_doc

            pdf_bytes = b"%PDF-1.4 scan content"
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            # Act
            result = converter.detect_document_type(pdf_base64)

            # Assert
            assert result == DocumentType.PDF_SCAN

    def test_detect_image(self, converter):
        """Тест определения изображения."""
        # Arrange: мокаем PIL.Image.open для успешной верификации
        fake_image_bytes = b"\x89PNG\r\n\x1a\n" + b"fake image data"
        fake_image_base64 = base64.b64encode(fake_image_bytes).decode("utf-8")

        mock_img = MagicMock()
        mock_img.verify = MagicMock()  # Не вызывает исключение

        with patch(
            "app.services.document_converter.Image.open",
            return_value=mock_img,
        ):
            # Act
            result = converter.detect_document_type(fake_image_base64)

        # Assert
        assert result == DocumentType.IMAGE

    def test_detect_unknown_returns_pdf_scan(self, converter):
        """Тест: неизвестный тип возвращается как PDF-скан."""
        # Arrange: данные, которые не соответствуют ни одному типу
        unknown_bytes = b"unknown data format"
        unknown_base64 = base64.b64encode(unknown_bytes).decode("utf-8")

        # Мокаем Image.open чтобы он падал (не изображение)
        with patch(
            "app.services.document_converter.Image.open",
            side_effect=Exception("not an image"),
        ):
            # Act
            result = converter.detect_document_type(unknown_base64)

        # Assert
        assert result == DocumentType.PDF_SCAN

    def test_detect_word_with_invalid_docx_falls_through(self, converter):
        """Тест: невалидный DOCX (с сигнатурой PK, но не DOCX) пропускается."""
        # Arrange: байты с сигнатурой ZIP, но DocxDocument падает
        fake_zip_bytes = b"PK\x03\x04" + b"not a real docx"
        fake_zip_base64 = base64.b64encode(fake_zip_bytes).decode("utf-8")

        with patch(
            "app.services.document_converter.DocxDocument",
            side_effect=Exception("not a docx"),
        ), patch(
            "app.services.document_converter.Image.open",
            side_effect=Exception("not an image"),
        ):
            # Act
            result = converter.detect_document_type(fake_zip_base64)

        # Assert: должен вернуться PDF_SCAN как fallback
        assert result == DocumentType.PDF_SCAN

    def test_detect_pdf_with_data_uri_prefix(self, converter):
        """Тест: base64 с префиксом data URI корректно очищается."""
        # Arrange
        with patch("app.services.document_converter.fitz.Document") as mock_fitz:
            mock_page = MagicMock()
            mock_page.get_text.return_value = "Текст"
            mock_doc = MagicMock()
            mock_doc.__len__ = MagicMock(return_value=1)
            mock_doc.__getitem__ = MagicMock(return_value=mock_page)
            mock_fitz.return_value = mock_doc

            pdf_bytes = b"%PDF-1.4 content"
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
            data_uri = f"data:application/pdf;base64,{pdf_base64}"

            # Act
            result = converter.detect_document_type(data_uri)

            # Assert
            assert result == DocumentType.PDF_TEXT


class TestDocumentConverterExtractTextFromWord:
    """Тесты для метода extract_text_from_word."""

    @pytest.fixture
    def converter(self):
        """Создание экземпляра DocumentConverter."""
        return DocumentConverter()

    def test_extract_text_from_word_success(self, converter):
        """Тест успешного извлечения текста из Word."""
        # Arrange: мокаем DocxDocument с несколькими параграфами
        mock_para1 = MagicMock()
        mock_para1.text = "Первый параграф"
        mock_para2 = MagicMock()
        mock_para2.text = "Второй параграф"
        mock_para3 = MagicMock()
        mock_para3.text = ""  # Пустой параграф должен быть пропущен
        mock_para4 = MagicMock()
        mock_para4.text = "Третий параграф"

        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3, mock_para4]

        fake_bytes = b"PK\x03\x04" + b"fake docx"
        fake_base64 = base64.b64encode(fake_bytes).decode("utf-8")

        with patch(
            "app.services.document_converter.DocxDocument",
            return_value=mock_doc,
        ):
            # Act
            result = converter.extract_text_from_word(fake_base64)

        # Assert
        assert "Первый параграф" in result
        assert "Второй параграф" in result
        assert "Третий параграф" in result
        # Пустые параграфы не должны быть включены
        assert result.count("\n") == 2  # Только 2 перехода между непустыми параграфами

    def test_extract_text_from_word_empty_document(self, converter):
        """Тест извлечения текста из пустого Word документа."""
        # Arrange: мокаем DocxDocument без параграфов
        mock_doc = MagicMock()
        mock_doc.paragraphs = []

        fake_bytes = b"PK\x03\x04" + b"empty docx"
        fake_base64 = base64.b64encode(fake_bytes).decode("utf-8")

        with patch(
            "app.services.document_converter.DocxDocument",
            return_value=mock_doc,
        ):
            # Act
            result = converter.extract_text_from_word(fake_base64)

        # Assert
        assert result == ""

    def test_extract_text_from_word_invalid_data_raises(self, converter):
        """Тест: невалидные данные вызывают исключение."""
        # Arrange: мокаем DocxDocument чтобы он падал
        invalid_base64 = base64.b64encode(b"not a word document").decode("utf-8")

        with patch(
            "app.services.document_converter.DocxDocument",
            side_effect=Exception("not a docx"),
        ):
            # Act & Assert
            with pytest.raises(Exception):
                converter.extract_text_from_word(invalid_base64)

    def test_extract_text_from_word_with_data_uri_prefix(self, converter):
        """Тест: base64 с префиксом data URI корректно обрабатывается."""
        # Arrange
        mock_para = MagicMock()
        mock_para.text = "Текст параграфа"
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]

        fake_bytes = b"PK\x03\x04" + b"fake docx"
        fake_base64 = base64.b64encode(fake_bytes).decode("utf-8")
        data_uri = f"data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{fake_base64}"

        with patch(
            "app.services.document_converter.DocxDocument",
            return_value=mock_doc,
        ):
            # Act
            result = converter.extract_text_from_word(data_uri)

        # Assert
        assert result == "Текст параграфа"


class TestDocumentConverterExtractTextFromPdfWithText:
    """Тесты для метода extract_text_from_pdf_with_text."""

    @pytest.fixture
    def converter(self):
        """Создание экземпляра DocumentConverter."""
        return DocumentConverter()

    def test_extract_text_from_pdf_success(self, converter):
        """Тест успешного извлечения текста из PDF."""
        # Arrange: мокаем fitz.Document
        with patch("app.services.document_converter.fitz.Document") as mock_fitz:
            mock_page1 = MagicMock()
            mock_page1.get_text.return_value = "Текст страницы 1"
            mock_page2 = MagicMock()
            mock_page2.get_text.return_value = "Текст страницы 2"

            mock_doc = MagicMock()
            mock_doc.__len__ = MagicMock(return_value=2)
            mock_doc.__getitem__ = MagicMock(side_effect=[mock_page1, mock_page2])
            mock_fitz.return_value = mock_doc

            pdf_bytes = b"%PDF-1.4 content"
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            # Act
            result = converter.extract_text_from_pdf_with_text(pdf_base64)

            # Assert
            assert "Текст страницы 1" in result
            assert "Текст страницы 2" in result
            assert "\n" in result

    def test_extract_text_from_pdf_empty_pages(self, converter):
        """Тест извлечения текста из PDF с пустыми страницами."""
        # Arrange
        with patch("app.services.document_converter.fitz.Document") as mock_fitz:
            mock_page = MagicMock()
            mock_page.get_text.return_value = ""

            mock_doc = MagicMock()
            mock_doc.__len__ = MagicMock(return_value=1)
            mock_doc.__getitem__ = MagicMock(return_value=mock_page)
            mock_fitz.return_value = mock_doc

            pdf_bytes = b"%PDF-1.4 empty"
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            # Act
            result = converter.extract_text_from_pdf_with_text(pdf_base64)

            # Assert
            assert result == ""

    def test_extract_text_from_pdf_invalid_data_raises(self, converter):
        """Тест: невалидные данные вызывают исключение."""
        # Arrange
        with patch("app.services.document_converter.fitz.Document") as mock_fitz:
            mock_fitz.side_effect = Exception("invalid pdf")

            invalid_base64 = base64.b64encode(b"not a pdf").decode("utf-8")

            # Act & Assert
            with pytest.raises(Exception):
                converter.extract_text_from_pdf_with_text(invalid_base64)


class TestDocumentConverterConvertPdfToImages:
    """Тесты для метода convert_pdf_to_images."""

    @pytest.fixture
    def converter(self):
        """Создание экземпляра DocumentConverter."""
        return DocumentConverter()

    def test_convert_pdf_to_images_success(self, converter):
        """Тест успешной конвертации PDF в изображения."""
        # Arrange: мокаем fitz.Document и рендеринг
        with patch("app.services.document_converter.fitz.Document") as mock_fitz, \
             patch("app.services.document_converter.fitz.Matrix"):

            mock_pixmap = MagicMock()
            mock_pixmap.tobytes.return_value = b"fake_png_data"

            mock_page = MagicMock()
            mock_page.get_pixmap.return_value = mock_pixmap

            mock_doc = MagicMock()
            mock_doc.__len__ = MagicMock(return_value=2)
            mock_doc.__getitem__ = MagicMock(side_effect=[mock_page, mock_page])
            mock_fitz.return_value = mock_doc

            pdf_bytes = b"%PDF-1.4 scan"
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            # Act
            result = converter.convert_pdf_to_images(pdf_base64)

            # Assert
            assert len(result) == 2
            assert all(isinstance(img, str) for img in result)
            # Проверяем, что результат - валидный base64
            for img_b64 in result:
                decoded = base64.b64decode(img_b64)
                assert decoded == b"fake_png_data"

    def test_convert_pdf_to_images_single_page(self, converter):
        """Тест конвертации одностраничного PDF."""
        # Arrange
        with patch("app.services.document_converter.fitz.Document") as mock_fitz, \
             patch("app.services.document_converter.fitz.Matrix"):

            mock_pixmap = MagicMock()
            mock_pixmap.tobytes.return_value = b"single_page_png"

            mock_page = MagicMock()
            mock_page.get_pixmap.return_value = mock_pixmap

            mock_doc = MagicMock()
            mock_doc.__len__ = MagicMock(return_value=1)
            mock_doc.__getitem__ = MagicMock(return_value=mock_page)
            mock_fitz.return_value = mock_doc

            pdf_bytes = b"%PDF-1.4 single"
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            # Act
            result = converter.convert_pdf_to_images(pdf_base64)

            # Assert
            assert len(result) == 1

    def test_convert_pdf_to_images_invalid_data_raises(self, converter):
        """Тест: невалидные данные вызывают исключение."""
        # Arrange
        with patch("app.services.document_converter.fitz.Document") as mock_fitz:
            mock_fitz.side_effect = Exception("invalid pdf")

            invalid_base64 = base64.b64encode(b"not a pdf").decode("utf-8")

            # Act & Assert
            with pytest.raises(Exception):
                converter.convert_pdf_to_images(invalid_base64)


class TestDocumentConverterConvertImageToBase64:
    """Тесты для метода convert_image_to_base64."""

    @pytest.fixture
    def converter(self):
        """Создание экземпляра DocumentConverter."""
        return DocumentConverter()

    def test_convert_image_to_base64_success(self, converter):
        """Тест успешной конвертации изображения в base64."""
        # Arrange: произвольные байты (метод не использует PIL)
        image_bytes = b"\x89PNG\r\n\x1a\n" + b"fake image data"

        # Act
        result = converter.convert_image_to_base64(image_bytes)

        # Assert
        assert isinstance(result, str)
        # Проверяем, что можно декодировать обратно
        decoded = base64.b64decode(result)
        assert decoded == image_bytes

    def test_convert_image_to_base64_empty_bytes(self, converter):
        """Тест конвертации пустых байтов."""
        # Arrange
        empty_bytes = b""

        # Act
        result = converter.convert_image_to_base64(empty_bytes)

        # Assert
        assert result == ""

    def test_convert_image_to_base64_raw_bytes(self, converter):
        """Тест конвертации произвольных байтов."""
        # Arrange
        raw_bytes = b"\x89PNG\r\n\x1a\n" + b"fake image data"

        # Act
        result = converter.convert_image_to_base64(raw_bytes)

        # Assert
        decoded = base64.b64decode(result)
        assert decoded == raw_bytes


class TestDocumentConverterCleanBase64:
    """Тесты для метода _clean_base64."""

    @pytest.fixture
    def converter(self):
        """Создание экземпляра DocumentConverter."""
        return DocumentConverter()

    def test_clean_base64_without_prefix(self, converter):
        """Тест: base64 без префикса возвращается как есть."""
        # Arrange
        raw_bytes = b"test data"
        base64_str = base64.b64encode(raw_bytes).decode("utf-8")

        # Act
        result = converter._clean_base64(base64_str)

        # Assert
        assert result == base64_str

    def test_clean_base64_with_data_uri_prefix(self, converter):
        """Тест: префикс data URI удаляется."""
        # Arrange
        raw_bytes = b"test data"
        base64_str = base64.b64encode(raw_bytes).decode("utf-8")
        data_uri = f"data:application/pdf;base64,{base64_str}"

        # Act
        result = converter._clean_base64(data_uri)

        # Assert
        assert result == base64_str

    def test_clean_base64_with_complex_prefix(self, converter):
        """Тест: сложный префикс data URI удаляется."""
        # Arrange
        raw_bytes = b"test data"
        base64_str = base64.b64encode(raw_bytes).decode("utf-8")
        data_uri = f"data:image/png;base64,{base64_str}"

        # Act
        result = converter._clean_base64(data_uri)

        # Assert
        assert result == base64_str
