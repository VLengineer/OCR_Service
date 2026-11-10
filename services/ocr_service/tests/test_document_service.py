"""
Unit-тесты для DocumentService.

Тестируется метод:
- processing: обработка документа с маршрутизацией по типу
"""

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.schemas import Document, DocumentRequest, OCRRequest
from app.services.document_service import DocumentService
from app.services.document_converter import DocumentType


class TestDocumentServiceInit:
    """Тесты инициализации DocumentService."""

    def test_init_stores_dependencies(self):
        """Тест: конструктор сохраняет все зависимости."""
        # Arrange
        mock_request_service = MagicMock()
        mock_task_repository = MagicMock()
        mock_document_converter = MagicMock()

        # Act
        service = DocumentService(
            request_service=mock_request_service,
            task_repository=mock_task_repository,
            document_converter=mock_document_converter,
        )

        # Assert
        assert service._request_service is mock_request_service
        assert service._task_repository is mock_task_repository
        assert service._document_converter is mock_document_converter


class TestDocumentServiceProcessingWord:
    """Тесты processing для Word документа."""

    @pytest.fixture
    def mock_request_service(self):
        service = MagicMock()
        service.create_document = AsyncMock()
        return service

    @pytest.fixture
    def mock_task_repository(self):
        repo = MagicMock()
        repo.add_task = AsyncMock()
        return repo

    @pytest.fixture
    def mock_document_converter(self):
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        converter.extract_text_from_word = MagicMock()
        return converter

    @pytest.fixture
    def service(self, mock_request_service, mock_task_repository, mock_document_converter):
        return DocumentService(
            request_service=mock_request_service,
            task_repository=mock_task_repository,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_processing_word_extracts_text_and_calls_create_document(
        self, service, mock_request_service, mock_document_converter
    ):
        """Тест: Word документ → извлечение текста → create_document."""
        # Arrange
        document = Document(document_id="doc_word", document_base64="word_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.extract_text_from_word.return_value = "Текст из Word"

        # Act
        await service.processing(document)

        # Assert
        mock_document_converter.detect_document_type.assert_called_once_with("word_base64")
        mock_document_converter.extract_text_from_word.assert_called_once_with("word_base64")
        mock_request_service.create_document.assert_called_once()

        call_args = mock_request_service.create_document.call_args
        doc_request = call_args[0][0]
        assert isinstance(doc_request, DocumentRequest)
        assert doc_request.document_id == "doc_word"
        assert doc_request.raw_text == "Текст из Word"

    @pytest.mark.asyncio
    async def test_processing_word_does_not_call_task_repository(
        self, service, mock_task_repository, mock_document_converter
    ):
        """Тест: для Word документа не вызывается task_repository."""
        # Arrange
        document = Document(document_id="doc_word", document_base64="word_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.extract_text_from_word.return_value = "Текст"

        # Act
        await service.processing(document)

        # Assert
        mock_task_repository.add_task.assert_not_called()


class TestDocumentServiceProcessingPdfText:
    """Тесты processing для PDF с текстом."""

    @pytest.fixture
    def mock_request_service(self):
        service = MagicMock()
        service.create_document = AsyncMock()
        return service

    @pytest.fixture
    def mock_task_repository(self):
        repo = MagicMock()
        repo.add_task = AsyncMock()
        return repo

    @pytest.fixture
    def mock_document_converter(self):
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        converter.extract_text_from_pdf_with_text = MagicMock()
        return converter

    @pytest.fixture
    def service(self, mock_request_service, mock_task_repository, mock_document_converter):
        return DocumentService(
            request_service=mock_request_service,
            task_repository=mock_task_repository,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_processing_pdf_text_extracts_text_and_calls_create_document(
        self, service, mock_request_service, mock_document_converter
    ):
        """Тест: PDF с текстом → извлечение текста → create_document."""
        # Arrange
        document = Document(document_id="doc_pdftext", document_base64="pdf_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_TEXT
        mock_document_converter.extract_text_from_pdf_with_text.return_value = "PDF текст"

        # Act
        await service.processing(document)

        # Assert
        mock_document_converter.extract_text_from_pdf_with_text.assert_called_once_with(
            "pdf_base64"
        )
        mock_request_service.create_document.assert_called_once()

        call_args = mock_request_service.create_document.call_args
        doc_request = call_args[0][0]
        assert isinstance(doc_request, DocumentRequest)
        assert doc_request.document_id == "doc_pdftext"
        assert doc_request.raw_text == "PDF текст"

    @pytest.mark.asyncio
    async def test_processing_pdf_text_does_not_call_task_repository(
        self, service, mock_task_repository, mock_document_converter
    ):
        """Тест: для PDF с текстом не вызывается task_repository."""
        # Arrange
        document = Document(document_id="doc_pdftext", document_base64="pdf_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_TEXT
        mock_document_converter.extract_text_from_pdf_with_text.return_value = "Текст"

        # Act
        await service.processing(document)

        # Assert
        mock_task_repository.add_task.assert_not_called()


class TestDocumentServiceProcessingImage:
    """Тесты processing для изображения."""

    @pytest.fixture
    def mock_request_service(self):
        service = MagicMock()
        service.create_document = AsyncMock()
        return service

    @pytest.fixture
    def mock_task_repository(self):
        repo = MagicMock()
        repo.add_task = AsyncMock()
        return repo

    @pytest.fixture
    def mock_document_converter(self):
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        converter.convert_image_to_base64 = MagicMock()
        return converter

    @pytest.fixture
    def service(self, mock_request_service, mock_task_repository, mock_document_converter):
        return DocumentService(
            request_service=mock_request_service,
            task_repository=mock_task_repository,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_processing_image_converts_and_adds_task(
        self, service, mock_task_repository, mock_document_converter
    ):
        """Тест: изображение → конвертация в base64 → добавление задачи."""
        # Arrange
        image_bytes = b"fake_image_bytes"
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        document = Document(document_id="doc_img", document_base64=image_base64)
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_document_converter.convert_image_to_base64.return_value = "converted_base64"

        # Act
        await service.processing(document)

        # Assert
        mock_document_converter.convert_image_to_base64.assert_called_once_with(image_bytes)
        mock_task_repository.add_task.assert_called_once_with(
            document_id="doc_img",
            base64_document=["converted_base64"],
            document_type=None,
        )

    @pytest.mark.asyncio
    async def test_processing_image_does_not_call_create_document(
        self, service, mock_request_service, mock_document_converter
    ):
        """Тест: для изображения не вызывается create_document."""
        # Arrange
        image_base64 = base64.b64encode(b"img").decode("utf-8")
        document = Document(document_id="doc_img", document_base64=image_base64)
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_document_converter.convert_image_to_base64.return_value = "converted"

        # Act
        await service.processing(document)

        # Assert
        mock_request_service.create_document.assert_not_called()


class TestDocumentServiceProcessingPdfScan:
    """Тесты processing для PDF-скана."""

    @pytest.fixture
    def mock_request_service(self):
        service = MagicMock()
        service.create_document = AsyncMock()
        return service

    @pytest.fixture
    def mock_task_repository(self):
        repo = MagicMock()
        repo.add_task = AsyncMock()
        return repo

    @pytest.fixture
    def mock_document_converter(self):
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        converter.convert_pdf_to_images = MagicMock()
        return converter

    @pytest.fixture
    def service(self, mock_request_service, mock_task_repository, mock_document_converter):
        return DocumentService(
            request_service=mock_request_service,
            task_repository=mock_task_repository,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_processing_pdf_scan_converts_and_adds_task(
        self, service, mock_task_repository, mock_document_converter
    ):
        """Тест: PDF-скан → конвертация в изображения → добавление задачи."""
        # Arrange
        document = Document(document_id="doc_scan", document_base64="pdf_scan_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_SCAN
        mock_document_converter.convert_pdf_to_images.return_value = [
            "page1_b64", "page2_b64", "page3_b64"
        ]

        # Act
        await service.processing(document)

        # Assert
        mock_document_converter.convert_pdf_to_images.assert_called_once_with("pdf_scan_base64")
        mock_task_repository.add_task.assert_called_once_with(
            document_id="doc_scan",
            base64_document=["page1_b64", "page2_b64", "page3_b64"],
            document_type=None,
        )

    @pytest.mark.asyncio
    async def test_processing_pdf_scan_does_not_call_create_document(
        self, service, mock_request_service, mock_document_converter
    ):
        """Тест: для PDF-скана не вызывается create_document."""
        # Arrange
        document = Document(document_id="doc_scan", document_base64="pdf_scan_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF_SCAN
        mock_document_converter.convert_pdf_to_images.return_value = ["page1_b64"]

        # Act
        await service.processing(document)

        # Assert
        mock_request_service.create_document.assert_not_called()


class TestDocumentServiceProcessingErrors:
    """Тесты обработки ошибок в processing."""

    @pytest.fixture
    def mock_request_service(self):
        service = MagicMock()
        service.create_document = AsyncMock()
        return service

    @pytest.fixture
    def mock_task_repository(self):
        repo = MagicMock()
        repo.add_task = AsyncMock()
        return repo

    @pytest.fixture
    def mock_document_converter(self):
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        return converter

    @pytest.fixture
    def service(self, mock_request_service, mock_task_repository, mock_document_converter):
        return DocumentService(
            request_service=mock_request_service,
            task_repository=mock_task_repository,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_processing_raises_when_detect_fails(
        self, service, mock_document_converter
    ):
        """Тест: исключение при определении типа пробрасывается."""
        # Arrange
        document = Document(document_id="doc_err", document_base64="bad_data")
        mock_document_converter.detect_document_type.side_effect = RuntimeError("parse error")

        # Act & Assert
        with pytest.raises(RuntimeError, match="parse error"):
            await service.processing(document)

    @pytest.mark.asyncio
    async def test_processing_raises_when_extract_text_fails(
        self, service, mock_document_converter
    ):
        """Тест: исключение при извлечении текста пробрасывается."""
        # Arrange
        document = Document(document_id="doc_err", document_base64="word_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.extract_text_from_word = MagicMock(
            side_effect=RuntimeError("extract error")
        )

        # Act & Assert
        with pytest.raises(RuntimeError, match="extract error"):
            await service.processing(document)

    @pytest.mark.asyncio
    async def test_processing_raises_when_create_document_fails(
        self, service, mock_request_service, mock_document_converter
    ):
        """Тест: исключение при HTTP-запросе пробрасывается."""
        # Arrange
        document = Document(document_id="doc_err", document_base64="word_base64")
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.extract_text_from_word.return_value = "Текст"
        mock_request_service.create_document.side_effect = ConnectionError("network error")

        # Act & Assert
        with pytest.raises(ConnectionError, match="network error"):
            await service.processing(document)

    @pytest.mark.asyncio
    async def test_processing_raises_when_add_task_fails(
        self, service, mock_task_repository, mock_document_converter
    ):
        """Тест: исключение при добавлении задачи пробрасывается."""
        # Arrange
        image_base64 = base64.b64encode(b"img").decode("utf-8")
        document = Document(document_id="doc_err", document_base64=image_base64)
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_document_converter.convert_image_to_base64 = MagicMock(return_value="converted")
        mock_task_repository.add_task.side_effect = RuntimeError("db error")

        # Act & Assert
        with pytest.raises(RuntimeError, match="db error"):
            await service.processing(document)
