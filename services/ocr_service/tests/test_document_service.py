"""
Unit-тесты для DocumentService.

Тестируется метод:
- processing: обработка документа с маршрутизацией по типу

Новая унифицированная логика:
- WORD -> convert_word_to_pdf -> convert_pdf_to_images -> add_task
- PDF  -> convert_pdf_to_images -> add_task
- IMAGE -> [document_base64] -> add_task
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.schemas import Document
from app.services.document_service import DocumentService
from app.services.document_converter import DocumentType


@pytest.fixture
def base_document():
    """Базовый документ с заполненным document_type."""
    return Document(
        document_id="doc_id",
        document_base64="base64_data",
        document_type="incoming_doc",
    )


def _make_service(request_service=None, task_repository=None, document_converter=None):
    return DocumentService(
        request_service=request_service or MagicMock(),
        task_repository=task_repository or MagicMock(),
        document_converter=document_converter or MagicMock(),
    )


class TestDocumentServiceInit:
    """Тесты инициализации DocumentService."""

    def test_init_stores_dependencies(self):
        """Тест: конструктор сохраняет все зависимости."""
        mock_request_service = MagicMock()
        mock_task_repository = MagicMock()
        mock_document_converter = MagicMock()

        service = _make_service(
            request_service=mock_request_service,
            task_repository=mock_task_repository,
            document_converter=mock_document_converter,
        )

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
        converter.convert_word_to_pdf = MagicMock()
        converter.convert_pdf_to_images = MagicMock()
        return converter

    @pytest.fixture
    def service(self, mock_request_service, mock_task_repository, mock_document_converter):
        return _make_service(
            request_service=mock_request_service,
            task_repository=mock_task_repository,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_processing_word_converts_to_images_and_adds_task(
        self, service, mock_task_repository, mock_document_converter
    ):
        """Тест: Word -> PDF -> изображения -> add_task."""
        document = Document(
            document_id="doc_word",
            document_base64="word_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.convert_word_to_pdf.return_value = "pdf_base64"
        mock_document_converter.convert_pdf_to_images.return_value = ["page1_b64", "page2_b64"]

        await service.processing(document)

        mock_document_converter.detect_document_type.assert_called_once_with("word_base64")
        mock_document_converter.convert_word_to_pdf.assert_called_once_with("word_base64")
        mock_document_converter.convert_pdf_to_images.assert_called_once_with("pdf_base64")
        mock_task_repository.add_task.assert_awaited_once_with(
            document_id="doc_word",
            base64_document=["page1_b64", "page2_b64"],
            document_type="incoming_doc",
        )

    @pytest.mark.asyncio
    async def test_processing_word_does_not_call_create_document(
        self, service, mock_request_service, mock_document_converter
    ):
        """Тест: для Word документа не вызывается create_document."""
        document = Document(
            document_id="doc_word",
            document_base64="word_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.convert_word_to_pdf.return_value = "pdf_base64"
        mock_document_converter.convert_pdf_to_images.return_value = ["page1_b64"]

        await service.processing(document)

        mock_request_service.create_document.assert_not_called()


class TestDocumentServiceProcessingPdf:
    """Тесты processing для PDF."""

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
        return _make_service(
            request_service=mock_request_service,
            task_repository=mock_task_repository,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_processing_pdf_converts_to_images_and_adds_task(
        self, service, mock_task_repository, mock_document_converter
    ):
        """Тест: PDF -> изображения -> add_task."""
        document = Document(
            document_id="doc_pdf",
            document_base64="pdf_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF
        mock_document_converter.convert_pdf_to_images.return_value = [
            "page1_b64", "page2_b64", "page3_b64"
        ]

        await service.processing(document)

        mock_document_converter.convert_pdf_to_images.assert_called_once_with("pdf_base64")
        mock_task_repository.add_task.assert_awaited_once_with(
            document_id="doc_pdf",
            base64_document=["page1_b64", "page2_b64", "page3_b64"],
            document_type="incoming_doc",
        )

    @pytest.mark.asyncio
    async def test_processing_pdf_does_not_call_create_document(
        self, service, mock_request_service, mock_document_converter
    ):
        """Тест: для PDF не вызывается create_document."""
        document = Document(
            document_id="doc_pdf",
            document_base64="pdf_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF
        mock_document_converter.convert_pdf_to_images.return_value = ["page1_b64"]

        await service.processing(document)

        mock_request_service.create_document.assert_not_called()


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
        return converter

    @pytest.fixture
    def service(self, mock_request_service, mock_task_repository, mock_document_converter):
        return _make_service(
            request_service=mock_request_service,
            task_repository=mock_task_repository,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_processing_image_adds_task_with_single_page(
        self, service, mock_task_repository, mock_document_converter
    ):
        """Тест: изображение передаётся в add_task как одностраничный документ."""
        document = Document(
            document_id="doc_img",
            document_base64="img_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE

        await service.processing(document)

        mock_task_repository.add_task.assert_awaited_once_with(
            document_id="doc_img",
            base64_document=["img_base64"],
            document_type="incoming_doc",
        )

    @pytest.mark.asyncio
    async def test_processing_image_does_not_call_create_document(
        self, service, mock_request_service, mock_document_converter
    ):
        """Тест: для изображения не вызывается create_document."""
        document = Document(
            document_id="doc_img",
            document_base64="img_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE

        await service.processing(document)

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
        return _make_service(
            request_service=mock_request_service,
            task_repository=mock_task_repository,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_processing_raises_when_detect_fails(
        self, service, mock_document_converter
    ):
        """Тест: исключение при определении типа пробрасывается."""
        document = Document(
            document_id="doc_err",
            document_base64="bad_data",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.side_effect = RuntimeError("parse error")

        with pytest.raises(RuntimeError, match="parse error"):
            await service.processing(document)

    @pytest.mark.asyncio
    async def test_processing_raises_when_word_conversion_fails(
        self, service, mock_document_converter
    ):
        """Тест: исключение при конвертации Word пробрасывается."""
        document = Document(
            document_id="doc_err",
            document_base64="word_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.convert_word_to_pdf.side_effect = RuntimeError("convert error")

        with pytest.raises(RuntimeError, match="convert error"):
            await service.processing(document)

    @pytest.mark.asyncio
    async def test_processing_raises_when_pdf_conversion_fails(
        self, service, mock_document_converter
    ):
        """Тест: исключение при конвертации PDF в изображения пробрасывается."""
        document = Document(
            document_id="doc_err",
            document_base64="pdf_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF
        mock_document_converter.convert_pdf_to_images.side_effect = RuntimeError("convert error")

        with pytest.raises(RuntimeError, match="convert error"):
            await service.processing(document)

    @pytest.mark.asyncio
    async def test_processing_raises_when_add_task_fails(
        self, service, mock_task_repository, mock_document_converter
    ):
        """Тест: исключение при добавлении задачи пробрасывается."""
        document = Document(
            document_id="doc_err",
            document_base64="img_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_task_repository.add_task.side_effect = RuntimeError("db error")

        with pytest.raises(RuntimeError, match="db error"):
            await service.processing(document)
