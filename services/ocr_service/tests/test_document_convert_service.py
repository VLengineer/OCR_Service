"""
Unit-тесты для DocumentConvertService.

Тестируются методы:
- convert_document: конвертация документов различных типов
  в унифицированный формат изображений.
"""

import base64
from unittest.mock import MagicMock

import pytest

from app.schemas.schemas import DocumentConvertResponse
from app.services.document_convert_service import DocumentConvertService
from app.services.document_converter import DocumentType


class TestDocumentConvertService:
    """Тесты для DocumentConvertService."""

    @pytest.fixture
    def mock_document_converter(self):
        """Мок для DocumentConverter."""
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        converter.convert_word_to_pdf = MagicMock()
        converter.convert_pdf_to_images = MagicMock()
        converter.convert_image_to_base64 = MagicMock()
        converter._clean_base64 = MagicMock()
        return converter

    @pytest.fixture
    def document_convert_service(self, mock_document_converter):
        """Создание экземпляра DocumentConvertService."""
        return DocumentConvertService(document_converter=mock_document_converter)

    @pytest.mark.asyncio
    async def test_convert_word_document(
        self, document_convert_service, mock_document_converter
    ):
        """Тест конвертации Word документа в изображения (unified pipeline)."""
        # Arrange
        document_base64 = "word_base64_data"
        pdf_base64 = "converted_pdf_base64"
        page_images = ["page1_base64", "page2_base64"]

        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.convert_word_to_pdf.return_value = pdf_base64
        mock_document_converter.convert_pdf_to_images.return_value = page_images

        # Act
        result = await document_convert_service.convert_document(document_base64)

        # Assert
        assert isinstance(result, DocumentConvertResponse)
        assert result.document_type == DocumentType.WORD
        assert result.document_sheets == page_images

        mock_document_converter.detect_document_type.assert_called_once_with(document_base64)
        mock_document_converter.convert_word_to_pdf.assert_called_once_with(document_base64)
        mock_document_converter.convert_pdf_to_images.assert_called_once_with(pdf_base64)

    @pytest.mark.asyncio
    async def test_convert_pdf_document(
        self, document_convert_service, mock_document_converter
    ):
        """Тест конвертации PDF документа в изображения (unified pipeline)."""
        # Arrange
        document_base64 = "pdf_base64_data"
        page_images = ["page1_base64", "page2_base64", "page3_base64"]

        mock_document_converter.detect_document_type.return_value = DocumentType.PDF
        mock_document_converter.convert_pdf_to_images.return_value = page_images

        # Act
        result = await document_convert_service.convert_document(document_base64)

        # Assert
        assert isinstance(result, DocumentConvertResponse)
        assert result.document_type == DocumentType.PDF
        assert result.document_sheets == page_images

        mock_document_converter.detect_document_type.assert_called_once_with(document_base64)
        mock_document_converter.convert_pdf_to_images.assert_called_once_with(document_base64)

    @pytest.mark.asyncio
    async def test_convert_image(
        self, document_convert_service, mock_document_converter
    ):
        """Тест конвертации изображения в base64 (unified pipeline)."""
        # Arrange
        original_image_bytes = b"fake_image_data"
        document_base64 = base64.b64encode(original_image_bytes).decode("utf-8")
        converted_image_base64 = "converted_image_base64_data"

        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_document_converter._clean_base64.return_value = document_base64
        mock_document_converter.convert_image_to_base64.return_value = converted_image_base64

        # Act
        result = await document_convert_service.convert_document(document_base64)

        # Assert
        assert isinstance(result, DocumentConvertResponse)
        assert result.document_type == DocumentType.IMAGE
        assert result.document_sheets == [converted_image_base64]

        mock_document_converter.detect_document_type.assert_called_once_with(document_base64)
        mock_document_converter.convert_image_to_base64.assert_called_once_with(original_image_bytes)

    @pytest.mark.asyncio
    async def test_convert_document_detection_error(
        self, document_convert_service, mock_document_converter
    ):
        """Тест обработки ошибки при определении типа документа."""
        # Arrange
        document_base64 = "invalid_base64_data"
        mock_document_converter.detect_document_type.side_effect = Exception("Detection failed")

        # Act & Assert
        with pytest.raises(Exception, match="Detection failed"):
            await document_convert_service.convert_document(document_base64)

    @pytest.mark.asyncio
    async def test_convert_word_to_pdf_error(
        self, document_convert_service, mock_document_converter
    ):
        """Тест обработки ошибки при конвертации Word в PDF."""
        # Arrange
        document_base64 = "word_base64_data"
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.convert_word_to_pdf.side_effect = Exception("Word conversion failed")

        # Act & Assert
        with pytest.raises(Exception, match="Word conversion failed"):
            await document_convert_service.convert_document(document_base64)

    @pytest.mark.asyncio
    async def test_convert_pdf_conversion_error(
        self, document_convert_service, mock_document_converter
    ):
        """Тест обработки ошибки при конвертации PDF в изображения."""
        # Arrange
        document_base64 = "pdf_base64_data"
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF
        mock_document_converter.convert_pdf_to_images.side_effect = Exception("PDF conversion failed")

        # Act & Assert
        with pytest.raises(Exception, match="PDF conversion failed"):
            await document_convert_service.convert_document(document_base64)

    @pytest.mark.asyncio
    async def test_convert_image_conversion_error(
        self, document_convert_service, mock_document_converter
    ):
        """Тест обработки ошибки при конвертации изображения."""
        # Arrange
        original_image_bytes = b"fake_image_data"
        document_base64 = base64.b64encode(original_image_bytes).decode("utf-8")
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_document_converter._clean_base64.return_value = document_base64
        mock_document_converter.convert_image_to_base64.side_effect = Exception("Image conversion failed")

        # Act & Assert
        with pytest.raises(Exception, match="Image conversion failed"):
            await document_convert_service.convert_document(document_base64)

    @pytest.mark.asyncio
    async def test_convert_pdf_empty_pages(
        self, document_convert_service, mock_document_converter
    ):
        """Тест конвертации PDF с пустым результатом."""
        # Arrange
        document_base64 = "pdf_base64_data"
        page_images = []

        mock_document_converter.detect_document_type.return_value = DocumentType.PDF
        mock_document_converter.convert_pdf_to_images.return_value = page_images

        # Act
        result = await document_convert_service.convert_document(document_base64)

        # Assert
        assert isinstance(result, DocumentConvertResponse)
        assert result.document_type == DocumentType.PDF
        assert result.document_sheets == []

    @pytest.mark.asyncio
    async def test_convert_word_empty_pages(
        self, document_convert_service, mock_document_converter
    ):
        """Тест конвертации Word документа с пустым результатом."""
        # Arrange
        document_base64 = "word_base64_data"
        pdf_base64 = "converted_pdf_base64"
        page_images = []

        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.convert_word_to_pdf.return_value = pdf_base64
        mock_document_converter.convert_pdf_to_images.return_value = page_images

        # Act
        result = await document_convert_service.convert_document(document_base64)

        # Assert
        assert isinstance(result, DocumentConvertResponse)
        assert result.document_type == DocumentType.WORD
        assert result.document_sheets == []
