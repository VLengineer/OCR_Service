"""
Unit-тесты для DirectOCRService.

Тестируется метод:
- process: универсальная прямая OCR-обработка документа через конвертацию в изображения

Новая унифицированная логика:
- WORD -> convert_word_to_pdf -> convert_pdf_to_images -> ocr_request
- PDF  -> convert_pdf_to_images -> ocr_request
- IMAGE -> [document_base64] -> ocr_request
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.schemas import Document, OCRRequest
from app.services.direct_ocr_service import DirectOCRService
from app.services.document_converter import DocumentType


@pytest.fixture
def base_document():
    """Базовый документ с заполненным document_type."""
    return Document(
        document_id="doc_id",
        document_base64="base64_data",
        document_type="incoming_doc",
    )


def _make_service(request_service=None, document_converter=None):
    return DirectOCRService(
        request_service=request_service or MagicMock(),
        document_converter=document_converter or MagicMock(),
    )


class TestDirectOCRServiceInit:
    """Тесты инициализации DirectOCRService."""

    def test_init_stores_dependencies(self):
        """Тест: конструктор сохраняет зависимости."""
        mock_request_service = MagicMock()
        mock_document_converter = MagicMock()

        service = _make_service(
            request_service=mock_request_service,
            document_converter=mock_document_converter,
        )

        assert service._request_service is mock_request_service
        assert service._document_converter is mock_document_converter


class TestDirectOCRServiceProcessWord:
    """Тесты process для Word документа."""

    @pytest.fixture
    def mock_request_service(self):
        service = MagicMock()
        service.ocr_request = AsyncMock()
        return service

    @pytest.fixture
    def mock_document_converter(self):
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        converter.convert_word_to_pdf = MagicMock()
        converter.convert_pdf_to_images = MagicMock()
        return converter

    @pytest.fixture
    def service(self, mock_request_service, mock_document_converter):
        return _make_service(
            request_service=mock_request_service,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_process_word_converts_to_images_and_calls_ocr(
        self, service, mock_request_service, mock_document_converter
    ):
        """Тест: Word -> PDF -> изображения -> OCR."""
        document = Document(
            document_id="doc_word",
            document_base64="word_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.WORD
        mock_document_converter.convert_word_to_pdf.return_value = "pdf_base64"
        mock_document_converter.convert_pdf_to_images.return_value = ["page1", "page2"]
        mock_request_service.ocr_request.return_value = {"status": "done"}

        result = await service.process(document)

        assert result == {"status": "done"}
        mock_document_converter.detect_document_type.assert_called_once_with("word_base64")
        mock_document_converter.convert_word_to_pdf.assert_called_once_with("word_base64")
        mock_document_converter.convert_pdf_to_images.assert_called_once_with("pdf_base64")
        mock_request_service.ocr_request.assert_awaited_once()

        ocr_request = mock_request_service.ocr_request.call_args[0][0]
        assert isinstance(ocr_request, OCRRequest)
        assert ocr_request.document_id == "doc_word"
        assert ocr_request.base64_document == ["page1", "page2"]
        assert ocr_request.document_type == "incoming_doc"


class TestDirectOCRServiceProcessPdf:
    """Тесты process для PDF."""

    @pytest.fixture
    def mock_request_service(self):
        service = MagicMock()
        service.ocr_request = AsyncMock()
        return service

    @pytest.fixture
    def mock_document_converter(self):
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        converter.convert_pdf_to_images = MagicMock()
        return converter

    @pytest.fixture
    def service(self, mock_request_service, mock_document_converter):
        return _make_service(
            request_service=mock_request_service,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_process_pdf_converts_to_images_and_calls_ocr(
        self, service, mock_request_service, mock_document_converter
    ):
        """Тест: PDF -> изображения -> OCR."""
        document = Document(
            document_id="doc_pdf",
            document_base64="pdf_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.PDF
        mock_document_converter.convert_pdf_to_images.return_value = [
            "page1_base64", "page2_base64"
        ]
        mock_request_service.ocr_request.return_value = {"result": "ocr_done"}

        result = await service.process(document)

        assert result == {"result": "ocr_done"}
        mock_document_converter.detect_document_type.assert_called_once_with("pdf_base64")
        mock_document_converter.convert_pdf_to_images.assert_called_once_with("pdf_base64")
        mock_request_service.ocr_request.assert_awaited_once()

        ocr_request = mock_request_service.ocr_request.call_args[0][0]
        assert isinstance(ocr_request, OCRRequest)
        assert ocr_request.document_id == "doc_pdf"
        assert ocr_request.base64_document == ["page1_base64", "page2_base64"]
        assert ocr_request.document_type == "incoming_doc"


class TestDirectOCRServiceProcessImage:
    """Тесты process для изображения."""

    @pytest.fixture
    def mock_request_service(self):
        service = MagicMock()
        service.ocr_request = AsyncMock()
        return service

    @pytest.fixture
    def mock_document_converter(self):
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        return converter

    @pytest.fixture
    def service(self, mock_request_service, mock_document_converter):
        return _make_service(
            request_service=mock_request_service,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_process_image_calls_ocr_request_with_single_page(
        self, service, mock_request_service, mock_document_converter
    ):
        """Тест: изображение передаётся в OCR как одностраничный документ."""
        document = Document(
            document_id="doc_img",
            document_base64="img_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_request_service.ocr_request.return_value = {"status": "ok"}

        result = await service.process(document)

        assert result == {"status": "ok"}
        mock_document_converter.detect_document_type.assert_called_once_with("img_base64")
        mock_request_service.ocr_request.assert_awaited_once()

        ocr_request = mock_request_service.ocr_request.call_args[0][0]
        assert isinstance(ocr_request, OCRRequest)
        assert ocr_request.document_id == "doc_img"
        assert ocr_request.base64_document == ["img_base64"]
        assert ocr_request.document_type == "incoming_doc"


class TestDirectOCRServiceProcessErrors:
    """Тесты обработки ошибок в process."""

    @pytest.fixture
    def mock_request_service(self):
        service = MagicMock()
        service.ocr_request = AsyncMock()
        return service

    @pytest.fixture
    def mock_document_converter(self):
        converter = MagicMock()
        converter.detect_document_type = MagicMock()
        converter.convert_word_to_pdf = MagicMock()
        converter.convert_pdf_to_images = MagicMock()
        return converter

    @pytest.fixture
    def service(self, mock_request_service, mock_document_converter):
        return _make_service(
            request_service=mock_request_service,
            document_converter=mock_document_converter,
        )

    @pytest.mark.asyncio
    async def test_process_raises_when_detect_fails(
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
            await service.process(document)

    @pytest.mark.asyncio
    async def test_process_raises_when_word_conversion_fails(
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
            await service.process(document)

    @pytest.mark.asyncio
    async def test_process_raises_when_pdf_conversion_fails(
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
            await service.process(document)

    @pytest.mark.asyncio
    async def test_process_raises_when_ocr_request_fails(
        self, service, mock_request_service, mock_document_converter
    ):
        """Тест: исключение при OCR-запросе пробрасывается."""
        document = Document(
            document_id="doc_err",
            document_base64="img_base64",
            document_type="incoming_doc",
        )
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_request_service.ocr_request.side_effect = RuntimeError("ocr error")

        with pytest.raises(RuntimeError, match="ocr error"):
            await service.process(document)
