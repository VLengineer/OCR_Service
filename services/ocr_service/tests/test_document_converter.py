"""
Unit-тесты для DocumentConverter.

Тестируются методы:
- detect_document_type: определение типа документа
- convert_word_to_pdf: конвертация Word в PDF через LibreOffice
- convert_pdf_to_images: конвертация PDF в изображения
- convert_image_to_base64: конвертация изображения в base64
- _clean_base64: очистка base64 от data URI префиксов
"""

import base64
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

    def test_detect_pdf_document(self, converter):
        """Тест определения PDF документа."""
        # Arrange: любые байты с сигнатурой %PDF распознаются как PDF
        pdf_bytes = b"%PDF-1.4 fake content"
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        # Act
        result = converter.detect_document_type(pdf_base64)

        # Assert
        assert result == DocumentType.PDF

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

    def test_detect_unknown_returns_pdf(self, converter):
        """Тест: неизвестный тип возвращается как PDF (fallback)."""
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
        assert result == DocumentType.PDF

    def test_detect_word_with_invalid_docx_returns_word(self, converter):
        """Тест: ZIP-файл с сигнатурой PK, но невалидный для python-docx определяется как WORD."""
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

        # Assert: должен вернуться WORD по сигнатуре ZIP
        assert result == DocumentType.WORD

    def test_detect_ole2_doc_document(self, converter):
        """Тест: определение старого Word документа (.doc) по OLE2 сигнатуре."""
        # Arrange: OLE2 сигнатура D0 CF 11 E0 A1 B1 1A E1
        ole2_signature = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        ole2_bytes = ole2_signature + b"fake doc content"
        ole2_base64 = base64.b64encode(ole2_bytes).decode("utf-8")

        # Act
        result = converter.detect_document_type(ole2_base64)

        # Assert
        assert result == DocumentType.WORD

    def test_detect_pdf_with_data_uri_prefix(self, converter):
        """Тест: base64 с префиксом data URI корректно очищается."""
        # Arrange
        pdf_bytes = b"%PDF-1.4 content"
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
        data_uri = f"data:application/pdf;base64,{pdf_base64}"

        # Act
        result = converter.detect_document_type(data_uri)

        # Assert
        assert result == DocumentType.PDF


class TestDocumentConverterConvertWordToPdf:
    """Тесты для метода convert_word_to_pdf."""

    @pytest.fixture
    def converter(self):
        """Создание экземпляра DocumentConverter."""
        return DocumentConverter()

    def test_convert_word_to_pdf_success(self, converter):
        """Тест успешной конвертации Word в PDF через LibreOffice."""
        # Arrange
        fake_docx_bytes = b"PK\x03\x04" + b"fake docx"
        fake_docx_base64 = base64.b64encode(fake_docx_bytes).decode("utf-8")
        fake_pdf_bytes = b"%PDF-1.4 converted"

        with patch("app.services.document_converter.subprocess.run") as mock_run, \
             patch("app.services.document_converter.os.path.exists", return_value=True), \
             patch("app.services.document_converter.tempfile.mkdtemp", return_value="/tmp/fake_dir"), \
             patch("builtins.open", MagicMock()) as mock_open:

            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="success",
                stderr="",
            )

            # Мокаем чтение созданного PDF
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            mock_file.read.return_value = fake_pdf_bytes
            mock_open.return_value = mock_file

            # Act
            result = converter.convert_word_to_pdf(fake_docx_base64)

        # Assert
        assert isinstance(result, str)
        decoded = base64.b64decode(result)
        assert decoded == fake_pdf_bytes
        mock_run.assert_called_once()
        
        # Проверяем, что переданы env и UserInstallation
        call_args = mock_run.call_args
        assert "env" in call_args.kwargs
        assert "HOME" in call_args.kwargs["env"]
        assert "-env:UserInstallation=file:///tmp/fake_dir" in call_args.args[0]

    def test_convert_word_to_pdf_libreoffice_error(self, converter):
        """Тест: ошибка LibreOffice при конвертации Word в PDF."""
        # Arrange
        fake_docx_bytes = b"PK\x03\x04" + b"fake docx"
        fake_docx_base64 = base64.b64encode(fake_docx_bytes).decode("utf-8")

        with patch("app.services.document_converter.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="LibreOffice failed",
            )

            # Act & Assert
            with pytest.raises(RuntimeError, match="LibreOffice завершился"):
                converter.convert_word_to_pdf(fake_docx_base64)

    def test_convert_word_to_pdf_output_not_created(self, converter):
        """Тест: PDF файл не создан после работы LibreOffice."""
        # Arrange
        fake_docx_bytes = b"PK\x03\x04" + b"fake docx"
        fake_docx_base64 = base64.b64encode(fake_docx_bytes).decode("utf-8")

        with patch("app.services.document_converter.subprocess.run") as mock_run, \
             patch("app.services.document_converter.os.path.exists", return_value=False):

            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="",
                stderr="",
            )

            # Act & Assert
            with pytest.raises(RuntimeError, match="PDF файл не создан"):
                converter.convert_word_to_pdf(fake_docx_base64)


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
