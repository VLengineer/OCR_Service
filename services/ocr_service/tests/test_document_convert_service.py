"""
Unit-тесты для DocumentConvertService.

Тестируются методы:
- convert_document: конвертация документов различных типов
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
        converter.extract_text_from_word = MagicMock()
        converter.extract_text_from_pdf_with_text = MagicMock()
        converter.convert_pdf_to_images = MagicMock()
        converter.convert_image_to_base64 = MagicMock()
        return converter

    @pytest.fixture
    def document_convert_service(self, mock_document_converter):
        """Создание экземпляра DocumentConvertService."""
        return DocumentConvertService(document_converter=mock_document_converter)

    @pytest.mark.asyncio
    async def test_convert_word_document(
        self, document_convert_service, mock_document_converter
    ):
        """Тест конвертации Word документа."""
        # Arrange
        document_base64 = "word_base64_data"
        extracted_text = "Извлечённый текст из Word документа"
        
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.extract_text_from_word.return_value = extracted_text

        # Act
        result = await document_convert_service.convert_document(document_base64)

        # Assert
        assert isinstance(result, DocumentConvertResponse)
        assert result.document_type == DocumentType.WORD
        assert result.document_sheets == [extracted_text]
        
        mock_document_converter.detect_document_type.assert_called_once_with(document_base64)
        mock_document_converter.extract_text_from_word.assert_called_once_with(document_base64)

    @pytest.mark.asyncio
    async def test_convert_pdf_with_text(
        self, document_convert_service, mock_document_converter
    ):
        """Тест конвертации PDF с текстом."""
        # Arrange
        document_base64 = "pdf_text_base64_data"
        extracted_text = "Извлечённый текст из PDF документа"
        
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_TEXT
        mock_document_converter.extract_text_from_pdf_with_text.return_value = extracted_text

        # Act
        result = await document_convert_service.convert_document(document_base64)

        # Assert
        assert isinstance(result, DocumentConvertResponse)
        assert result.document_type == DocumentType.PDF_TEXT
        assert result.document_sheets == [extracted_text]
        
        mock_document_converter.detect_document_type.assert_called_once_with(document_base64)
        mock_document_converter.extract_text_from_pdf_with_text.assert_called_once_with(document_base64)

    @pytest.mark.asyncio
    async def test_convert_pdf_scan(
        self, document_convert_service, mock_document_converter
    ):
        """Тест конвертации PDF-скана."""
        # Arrange
        document_base64 = "pdf_scan_base64_data"
        page_images = ["page1_base64", "page2_base64", "page3_base64"]
        
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_SCAN
        mock_document_converter.convert_pdf_to_images.return_value = page_images

        # Act
        result = await document_convert_service.convert_document(document_base64)

        # Assert
        assert isinstance(result, DocumentConvertResponse)
        assert result.document_type == DocumentType.PDF_SCAN
        assert result.document_sheets == page_images
        
        mock_document_converter.detect_document_type.assert_called_once_with(document_base64)
        mock_document_converter.convert_pdf_to_images.assert_called_once_with(document_base64)

    @pytest.mark.asyncio
    async def test_convert_image(
        self, document_convert_service, mock_document_converter
    ):
        """Тест конвертации изображения."""
        # Arrange
        original_image_bytes = b"fake_image_data"
        document_base64 = base64.b64encode(original_image_bytes).decode("utf-8")
        converted_image_base64 = "converted_image_base64_data"
        
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
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
        with pytest.raises(ValueError, match="Не удалось определить тип документа"):
            await document_convert_service.convert_document(document_base64)

    @pytest.mark.asyncio
    async def test_convert_word_extraction_error(
        self, document_convert_service, mock_document_converter
    ):
        """Тест обработки ошибки при извлечении текста из Word."""
        # Arrange
        document_base64 = "word_base64_data"
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.extract_text_from_word.side_effect = Exception("Extraction failed")

        # Act & Assert
        with pytest.raises(Exception, match="Extraction failed"):
            await document_convert_service.convert_document(document_base64)

    @pytest.mark.asyncio
    async def test_convert_pdf_text_extraction_error(
        self, document_convert_service, mock_document_converter
    ):
        """Тест обработки ошибки при извлечении текста из PDF."""
        # Arrange
        document_base64 = "pdf_text_base64_data"
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_TEXT
        mock_document_converter.extract_text_from_pdf_with_text.side_effect = Exception("PDF extraction failed")

        # Act & Assert
        with pytest.raises(Exception, match="PDF extraction failed"):
            await document_convert_service.convert_document(document_base64)

    @pytest.mark.asyncio
    async def test_convert_pdf_scan_conversion_error(
        self, document_convert_service, mock_document_converter
    ):
        """Тест обработки ошибки при конвертации PDF-скана."""
        # Arrange
        document_base64 = "pdf_scan_base64_data"
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_SCAN
        mock_document_converter.convert_pdf_to_images.side_effect = Exception("Conversion failed")

        # Act & Assert
        with pytest.raises(Exception, match="Conversion failed"):
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
        mock_document_converter.convert_image_to_base64.side_effect = Exception("Image conversion failed")

        # Act & Assert
        with pytest.raises(Exception, match="Image conversion failed"):
            await document_convert_service.convert_document(document_base64)

    @pytest.mark.asyncio
    async def test_convert_pdf_scan_empty_pages(
        self, document_convert_service, mock_document_converter
    ):
        """Тест конвертации PDF-скана с пустым результатом."""
        # Arrange
        document_base64 = "pdf_scan_base64_data"
        page_images = []
        
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_SCAN
        mock_document_converter.convert_pdf_to_images.return_value = page_images

        # Act
        result = await document_convert_service.convert_document(document_base64)

        # Assert
        assert isinstance(result, DocumentConvertResponse)
        assert result.document_type == DocumentType.PDF_SCAN
        assert result.document_sheets == []

    @pytest.mark.asyncio
    async def test_convert_word_empty_text(
        self, document_convert_service, mock_document_converter
    ):
        """Тест конвертации Word документа с пустым текстом."""
        # Arrange
        document_base64 = "word_base64_data"
        extracted_text = ""
        
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.extract_text_from_word.return_value = extracted_text

        # Act
        result = await document_convert_service.convert_document(document_base64)

        # Assert
        assert isinstance(result, DocumentConvertResponse)
        assert result.document_type == DocumentType.WORD
        assert result.document_sheets == [""]
