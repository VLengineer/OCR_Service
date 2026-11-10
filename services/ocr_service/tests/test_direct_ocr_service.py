"""
Unit-тесты для DirectOCRService.

Тестируются методы:
- process_image: прямая OCR-обработка изображения
- process_pdf_scan: прямая OCR-обработка PDF-скана
- process: универсальная прямая обработка документа
"""

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.schemas import Document, DocumentRequest, OCRRequest
from app.services.direct_ocr_service import DirectOCRService
from app.services.document_converter import DocumentType

# Valid base64 string for tests that go through base64.b64decode
VALID_IMAGE_B64 = base64.b64encode(b"fake_image_data").decode()


class TestDirectOCRServiceProcessImage:
    """Тесты для метода process_image."""

    @pytest.fixture
    def mock_request_service(self):
        """Мок для RequestService."""
        service = MagicMock()
        service.ocr_request = AsyncMock()
        return service

    @pytest.fixture
    def mock_document_converter(self):
        """Мок для DocumentConverter."""
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        converter.convert_image_to_base64 = MagicMock()
        return converter

    @pytest.fixture
    def direct_ocr_service(self, mock_request_service, mock_document_converter):
        """Создание экземпляра DirectOCRService."""
        return DirectOCRService(
            request_service=mock_request_service,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_process_image_success(
        self, direct_ocr_service, mock_request_service, mock_document_converter
    ):
        """Тест успешной прямой OCR-обработки изображения."""
        # Arrange
        document = Document(document_id="doc123", document_base64=VALID_IMAGE_B64)
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_document_converter.convert_image_to_base64.return_value = "converted_base64"
        mock_request_service.ocr_request.return_value = {"result": "success"}

        # Act
        result = await direct_ocr_service.process_image(document)

        # Assert
        assert result == {"result": "success"}
        mock_document_converter.detect_document_type.assert_called_once_with(VALID_IMAGE_B64)
        mock_document_converter.convert_image_to_base64.assert_called_once()
        mock_request_service.ocr_request.assert_called_once()
        
        # Проверяем, что создан правильный OCRRequest
        call_args = mock_request_service.ocr_request.call_args
        ocr_request = call_args[0][0]
        assert isinstance(ocr_request, OCRRequest)
        assert ocr_request.document_id == "doc123"
        assert ocr_request.base64_document == ["converted_base64"]

    @pytest.mark.asyncio
    async def test_process_image_raises_error_when_not_image(
        self, direct_ocr_service, mock_document_converter
    ):
        """Тест: вызывается ошибка, если документ не является изображением."""
        # Arrange
        document = Document(document_id="doc123", document_base64="base64data")
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_SCAN

        # Act & Assert
        with pytest.raises(ValueError, match="Ожидалось изображение"):
            await direct_ocr_service.process_image(document)


class TestDirectOCRServiceProcessPdfScan:
    """Тесты для метода process_pdf_scan."""

    @pytest.fixture
    def mock_request_service(self):
        """Мок для RequestService."""
        service = MagicMock()
        service.ocr_request = AsyncMock()
        return service

    @pytest.fixture
    def mock_document_converter(self):
        """Мок для DocumentConverter."""
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        converter.convert_pdf_to_images = MagicMock()
        return converter

    @pytest.fixture
    def direct_ocr_service(self, mock_request_service, mock_document_converter):
        """Создание экземпляра DirectOCRService."""
        return DirectOCRService(
            request_service=mock_request_service,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_process_pdf_scan_success(
        self, direct_ocr_service, mock_request_service, mock_document_converter
    ):
        """Тест успешной прямой OCR-обработки PDF-скана."""
        # Arrange
        document = Document(document_id="doc456", document_base64="pdf_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_SCAN
        mock_document_converter.convert_pdf_to_images.return_value = [
            "page1_base64",
            "page2_base64",
        ]
        mock_request_service.ocr_request.return_value = {"result": "ocr_done"}

        # Act
        result = await direct_ocr_service.process_pdf_scan(document)

        # Assert
        assert result == {"result": "ocr_done"}
        mock_document_converter.detect_document_type.assert_called_once_with("pdf_base64")
        mock_document_converter.convert_pdf_to_images.assert_called_once_with("pdf_base64")
        mock_request_service.ocr_request.assert_called_once()
        
        # Проверяем, что создан правильный OCRRequest
        call_args = mock_request_service.ocr_request.call_args
        ocr_request = call_args[0][0]
        assert isinstance(ocr_request, OCRRequest)
        assert ocr_request.document_id == "doc456"
        assert ocr_request.base64_document == ["page1_base64", "page2_base64"]

    @pytest.mark.asyncio
    async def test_process_pdf_scan_raises_error_when_not_pdf_scan(
        self, direct_ocr_service, mock_document_converter
    ):
        """Тест: вызывается ошибка, если документ не является PDF-сканом."""
        # Arrange
        document = Document(document_id="doc456", document_base64="pdf_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE

        # Act & Assert
        with pytest.raises(ValueError, match="Ожидался PDF-скан"):
            await direct_ocr_service.process_pdf_scan(document)


class TestDirectOCRServiceProcess:
    """Тесты для метода process."""

    @pytest.fixture
    def mock_request_service(self):
        """Мок для RequestService."""
        service = MagicMock()
        service.ocr_request = AsyncMock()
        service.create_document = AsyncMock()
        return service

    @pytest.fixture
    def mock_document_converter(self):
        """Мок для DocumentConverter."""
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        converter.convert_image_to_base64 = MagicMock()
        converter.convert_pdf_to_images = MagicMock()
        converter.extract_text_from_word = MagicMock()
        converter.extract_text_from_pdf_with_text = MagicMock()
        return converter

    @pytest.fixture
    def direct_ocr_service(self, mock_request_service, mock_document_converter):
        """Создание экземпляра DirectOCRService."""
        return DirectOCRService(
            request_service=mock_request_service,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_process_image_routes_to_process_image(
        self, direct_ocr_service, mock_document_converter, mock_request_service
    ):
        """Тест: изображение маршрутизируется в process_image."""
        # Arrange
        document = Document(document_id="doc_img", document_base64=VALID_IMAGE_B64)
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_document_converter.convert_image_to_base64.return_value = "converted_img"
        mock_request_service.ocr_request.return_value = {"status": "ok"}

        # Act
        result = await direct_ocr_service.process(document)

        # Assert
        assert result == {"status": "ok"}
        mock_request_service.ocr_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_pdf_scan_routes_to_process_pdf_scan(
        self, direct_ocr_service, mock_document_converter, mock_request_service
    ):
        """Тест: PDF-скан маршрутизируется в process_pdf_scan."""
        # Arrange
        document = Document(document_id="doc_pdf", document_base64="pdf_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_SCAN
        mock_document_converter.convert_pdf_to_images.return_value = ["page1", "page2"]
        mock_request_service.ocr_request.return_value = {"status": "done"}

        # Act
        result = await direct_ocr_service.process(document)

        # Assert
        assert result == {"status": "done"}
        mock_request_service.ocr_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_word_extracts_text_and_creates_document(
        self, direct_ocr_service, mock_document_converter, mock_request_service
    ):
        """Тест: Word документ извлекает текст и вызывает create_document."""
        # Arrange
        document = Document(document_id="doc_word", document_base64="word_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.extract_text_from_word.return_value = "Извлечённый текст"

        # Act
        result = await direct_ocr_service.process(document)

        # Assert
        assert result is None
        mock_document_converter.extract_text_from_word.assert_called_once_with("word_base64")
        mock_request_service.create_document.assert_called_once()
        
        # Проверяем, что создан правильный DocumentRequest
        call_args = mock_request_service.create_document.call_args
        doc_request = call_args[0][0]
        assert isinstance(doc_request, DocumentRequest)
        assert doc_request.document_id == "doc_word"
        assert doc_request.raw_text == "Извлечённый текст"

    @pytest.mark.asyncio
    async def test_process_pdf_text_extracts_text_and_creates_document(
        self, direct_ocr_service, mock_document_converter, mock_request_service
    ):
        """Тест: PDF с текстом извлекает текст и вызывает create_document."""
        # Arrange
        document = Document(document_id="doc_pdftext", document_base64="pdftext_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_TEXT
        mock_document_converter.extract_text_from_pdf_with_text.return_value = "PDF текст"

        # Act
        result = await direct_ocr_service.process(document)

        # Assert
        assert result is None
        mock_document_converter.extract_text_from_pdf_with_text.assert_called_once_with(
            "pdftext_base64"
        )
        mock_request_service.create_document.assert_called_once()
        
        # Проверяем, что создан правильный DocumentRequest
        call_args = mock_request_service.create_document.call_args
        doc_request = call_args[0][0]
        assert isinstance(doc_request, DocumentRequest)
        assert doc_request.document_id == "doc_pdftext"
        assert doc_request.raw_text == "PDF текст"

    @pytest.mark.asyncio
    async def test_process_handles_exception_and_raises(
        self, direct_ocr_service, mock_document_converter
    ):
        """Тест: исключение в процессе обработки логируется и пробрасывается."""
        # Arrange
        document = Document(document_id="doc_err", document_base64="err_base64")
        mock_document_converter.detect_document_type.side_effect = Exception("Test error")

        # Act & Assert
        with pytest.raises(Exception, match="Test error"):
            await direct_ocr_service.process(document)
