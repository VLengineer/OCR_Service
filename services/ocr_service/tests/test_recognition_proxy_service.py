"""
Unit-тесты для RecognitionProxyService.

Тестируются:
- Успешное распознавание: base64 → конвертация в PDF → отправка в OCR → текст
- Ошибка декодирования base64 → ValueError
- Ошибка конвертации документа → ValueError
- Ошибка запроса к OCR-сервису → проброс исключения
- Возврат распознанного текста (str)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.recognition_proxy_service import RecognitionProxyService
from app.schemas.schemas import RecognitionRequest
from app.services.direct_ocr_service import DirectOCRService


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def mock_request_service():
    """Mock RequestService."""
    service = MagicMock()
    service.recognize_document = AsyncMock()
    return service


@pytest.fixture
def mock_direct_ocr_service():
    """Mock DirectOCRService."""
    service = MagicMock(spec=DirectOCRService)
    return service


@pytest.fixture
def mock_document_converter():
    """Mock DocumentConverter."""
    converter = MagicMock()
    converter.detect_document_type = MagicMock()
    converter.convert_to_pdf = MagicMock(return_value=b"converted-pdf-bytes")
    return converter


@pytest.fixture
def recognition_service(
    mock_request_service, mock_direct_ocr_service, mock_document_converter
):
    """RecognitionProxyService с моками зависимостей."""
    return RecognitionProxyService(
        request_service=mock_request_service,
        document_converter=mock_document_converter,
    )


# ──────────────────────────────────────────────
# Тесты успешного распознавания
# ──────────────────────────────────────────────

class TestRecognitionSuccess:
    """Тесты успешного распознавания документа."""

    @pytest.mark.asyncio
    async def test_recognize_returns_extracted_text(
        self, recognition_service, mock_request_service, mock_document_converter
    ):
        """Успешное распознавание возвращает строку с распознанным текстом."""
        # Arrange
        request = RecognitionRequest(document_base64="aGVsbG8=")
        mock_document_converter.detect_document_type.return_value = "image"
        mock_request_service.recognize_document.return_value = {"raw_text": "Распознанный текст"}

        # Act
        result = await recognition_service.recognize(request)

        # Assert
        assert isinstance(result, str)
        assert result == "Распознанный текст"

    @pytest.mark.asyncio
    async def test_recognize_detects_document_type(
        self, recognition_service, mock_document_converter, mock_request_service
    ):
        """Перед отправкой в OCR определяется тип документа."""
        # Arrange
        from app.services.document_converter import DocumentType
        request = RecognitionRequest(document_base64="aGVsbG8=")
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_request_service.recognize_document.return_value = {"raw_text": "Текст"}

        # Act
        await recognition_service.recognize(request)

        # Assert — detect_document_type был вызван с base64
        mock_document_converter.detect_document_type.assert_called_once_with("aGVsbG8=")

    @pytest.mark.asyncio
    async def test_recognize_sends_document_to_request_service(
        self, recognition_service, mock_request_service, mock_document_converter
    ):
        """После определения типа документ отправляется в RequestService."""
        # Arrange
        from app.services.document_converter import DocumentType
        request = RecognitionRequest(document_base64="aGVsbG8=")
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_request_service.recognize_document.return_value = {"raw_text": "Текст"}

        # Act
        await recognition_service.recognize(request)

        # Assert — RequestService.recognize_document был вызван
        mock_request_service.recognize_document.assert_called_once()
        # Проверяем что переданный документ содержит base64
        call_args = mock_request_service.recognize_document.call_args[0][0]
        assert call_args.document_base64 == "aGVsbG8="

    @pytest.mark.asyncio
    async def test_recognize_returns_only_text_string(
        self, recognition_service, mock_request_service, mock_document_converter
    ):
        """Метод recognize возвращает только строку с текстом."""
        # Arrange
        from app.services.document_converter import DocumentType
        request = RecognitionRequest(document_base64="aGVsbG8=")
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_request_service.recognize_document.return_value = {"raw_text": "Только текст"}

        # Act
        result = await recognition_service.recognize(request)

        # Assert — возвращается строка, а не объект
        assert isinstance(result, str)
        assert result == "Только текст"


# ──────────────────────────────────────────────
# Тесты обработки ошибок
# ──────────────────────────────────────────────

class TestRecognitionErrorHandling:
    """Тесты обработки ошибок при распознавании."""

    @pytest.mark.asyncio
    async def test_invalid_base64_raises_value_error(
        self, recognition_service, mock_document_converter
    ):
        """Невалидный base64 → ValueError."""
        # Arrange
        request = RecognitionRequest(document_base64="not-valid-base64!!!")
        mock_document_converter.detect_document_type.side_effect = ValueError("Invalid base64")

        # Act & Assert
        with pytest.raises(ValueError, match="base64"):
            await recognition_service.recognize(request)

    @pytest.mark.asyncio
    async def test_empty_response_raises_value_error(
        self, recognition_service, mock_request_service, mock_document_converter
    ):
        """Пустой ответ от OCR → ValueError."""
        # Arrange
        from app.services.document_converter import DocumentType
        request = RecognitionRequest(document_base64="aGVsbG8=")
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_request_service.recognize_document.return_value = {"raw_text": ""}

        # Act & Assert
        with pytest.raises(ValueError, match="raw_text"):
            await recognition_service.recognize(request)

    @pytest.mark.asyncio
    async def test_request_service_error_propagates(
        self, recognition_service, mock_request_service, mock_document_converter
    ):
        """Ошибка от RequestService пробрасывается дальше."""
        # Arrange
        from app.services.document_converter import DocumentType
        request = RecognitionRequest(document_base64="aGVsbG8=")
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_request_service.recognize_document.side_effect = Exception("OCR service unavailable")

        # Act & Assert
        with pytest.raises(Exception, match="OCR service unavailable"):
            await recognition_service.recognize(request)

    @pytest.mark.asyncio
    async def test_request_service_connection_error_propagates(
        self, recognition_service, mock_request_service, mock_document_converter
    ):
        """ConnectionError от RequestService пробрасывается."""
        # Arrange
        from app.services.document_converter import DocumentType
        request = RecognitionRequest(document_base64="aGVsbG8=")
        mock_document_converter.detect_document_type.return_value = DocumentType.IMAGE
        mock_request_service.recognize_document.side_effect = ConnectionError("Connection refused")

        # Act & Assert
        with pytest.raises(ConnectionError, match="Connection refused"):
            await recognition_service.recognize(request)
