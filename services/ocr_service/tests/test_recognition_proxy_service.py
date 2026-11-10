"""
Unit-тесты для RecognitionProxyService.

Тестируются:
- Успешное распознавание документа
- Ошибка парсинга ответа (ValueError)
- Ошибка HTTP-запроса (пробрасывание исключения)
- Логирование начала и конца распознавания
"""

import logging
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.schemas import Document, DocumentRequest
from app.services.recognition_proxy_service import RecognitionProxyService


class TestRecognitionProxyServiceRecognize:
    """Тесты для метода recognize."""

    @pytest.fixture
    def mock_request_service(self):
        """Мок для RequestService."""
        service = MagicMock()
        service.recognize_document = AsyncMock()
        return service

    @pytest.fixture
    def recognition_service(self, mock_request_service):
        """Создание экземпляра RecognitionProxyService."""
        return RecognitionProxyService(request_service=mock_request_service)

    @pytest.fixture
    def sample_document(self):
        """Тестовый документ."""
        return Document(
            document_id="doc-123",
            document_base64="base64data",
            document_type="incoming_contract",
        )

    @pytest.mark.asyncio
    async def test_recognize_success(
        self, recognition_service, mock_request_service, sample_document
    ):
        """Тест успешного распознавания документа.

        Mock RequestService.recognize_document возвращает валидный dict,
        проверяем что вернулся DocumentRequest с правильными полями.
        """
        # Arrange
        task_id = uuid4()
        mock_request_service.recognize_document.return_value = {
            "task_id": str(task_id),
            "document_id": "doc-123",
            "raw_text": "Распознанный текст документа",
            "document_type": "incoming_contract",
        }

        # Act
        result = await recognition_service.recognize(sample_document)

        # Assert
        assert isinstance(result, DocumentRequest)
        assert result.document_id == "doc-123"
        assert result.raw_text == "Распознанный текст документа"
        assert result.document_type == "incoming_contract"
        assert result.task_id == task_id

        mock_request_service.recognize_document.assert_called_once_with(
            sample_document
        )

    @pytest.mark.asyncio
    async def test_recognize_success_without_optional_fields(
        self, recognition_service, mock_request_service, sample_document
    ):
        """Тест успешного распознавания без опциональных полей."""
        # Arrange
        mock_request_service.recognize_document.return_value = {
            "document_id": "doc-123",
            "raw_text": "Текст без типа",
        }

        # Act
        result = await recognition_service.recognize(sample_document)

        # Assert
        assert isinstance(result, DocumentRequest)
        assert result.document_id == "doc-123"
        assert result.raw_text == "Текст без типа"
        assert result.task_id is None
        assert result.document_type is None

    @pytest.mark.asyncio
    async def test_recognize_invalid_response_raises_value_error(
        self, recognition_service, mock_request_service, sample_document
    ):
        """Тест ошибки парсинга ответа.

        Mock RequestService.recognize_document возвращает невалидный dict
        (отсутствует обязательное поле raw_text), проверяем ValueError.
        """
        # Arrange — raw_text отсутствует, DocumentRequest не сможет распарсить
        mock_request_service.recognize_document.return_value = {
            "document_id": "doc-123",
            # raw_text отсутствует — обязательное поле
        }

        # Act & Assert
        with pytest.raises(ValueError):
            await recognition_service.recognize(sample_document)

    @pytest.mark.asyncio
    async def test_recognize_http_error_propagates(
        self, recognition_service, mock_request_service, sample_document
    ):
        """Тест ошибки HTTP-запроса.

        Mock RequestService.recognize_document поднимает Exception,
        проверяем что исключение пробрасывается наружу.
        """
        # Arrange
        mock_request_service.recognize_document.side_effect = Exception(
            "HTTP connection timeout"
        )

        # Act & Assert
        with pytest.raises(Exception, match="HTTP connection timeout"):
            await recognition_service.recognize(sample_document)

    @pytest.mark.asyncio
    async def test_recognize_http_error_propagates_connection_error(
        self, recognition_service, mock_request_service, sample_document
    ):
        """Тест пробрасывания ConnectionError."""
        # Arrange
        mock_request_service.recognize_document.side_effect = ConnectionError(
            "Connection refused"
        )

        # Act & Assert
        with pytest.raises(ConnectionError, match="Connection refused"):
            await recognition_service.recognize(sample_document)


class TestRecognitionProxyServiceLogging:
    """Тесты логирования в RecognitionProxyService."""

    @pytest.fixture
    def mock_request_service(self):
        """Мок для RequestService."""
        service = MagicMock()
        service.recognize_document = AsyncMock()
        return service

    @pytest.fixture
    def recognition_service(self, mock_request_service):
        """Создание экземпляра RecognitionProxyService."""
        return RecognitionProxyService(request_service=mock_request_service)

    @pytest.fixture
    def sample_document(self):
        """Тестовый документ."""
        return Document(
            document_id="doc-log-test",
            document_base64="base64data",
            document_type="generic_document",
        )

    @pytest.mark.asyncio
    async def test_recognize_logs_start_and_end(
        self,
        recognition_service,
        mock_request_service,
        sample_document,
        caplog,
    ):
        """Тест логирования начала и конца распознавания.

        Проверяем что логируются info-сообщения с document_id
        в начале и в конце распознавания.
        """
        # Arrange
        mock_request_service.recognize_document.return_value = {
            "document_id": "doc-log-test",
            "raw_text": "Текст для логирования",
        }

        # Act
        with caplog.at_level(logging.INFO, logger="app.services.recognition_proxy_service"):
            await recognition_service.recognize(sample_document)

        # Assert — проверяем наличие логов начала и конца
        log_messages = [record.message for record in caplog.records]

        # Лог начала распознавания
        start_logs = [
            msg for msg in log_messages
            if "Запрос распознавания документа" in msg
        ]
        assert len(start_logs) >= 1, "Должен быть лог начала распознавания"
        assert "doc-log-test" in start_logs[0]
        assert "generic_document" in start_logs[0]

        # Лог завершения распознавания
        end_logs = [
            msg for msg in log_messages
            if "Распознавание документа завершено" in msg
        ]
        assert len(end_logs) >= 1, "Должен быть лог завершения распознавания"
        assert "doc-log-test" in end_logs[0]

    @pytest.mark.asyncio
    async def test_recognize_logs_error_on_invalid_response(
        self,
        recognition_service,
        mock_request_service,
        sample_document,
        caplog,
    ):
        """Тест логирования ошибки при невалидном ответе."""
        # Arrange
        mock_request_service.recognize_document.return_value = {
            # Нет обязательного raw_text
            "document_id": "doc-log-test",
        }

        # Act
        with caplog.at_level(logging.ERROR, logger="app.services.recognition_proxy_service"):
            with pytest.raises(ValueError):
                await recognition_service.recognize(sample_document)

        # Assert — проверяем наличие error-лога
        log_messages = [record.message for record in caplog.records]
        error_logs = [
            msg for msg in log_messages
            if "Некорректный формат ответа" in msg
        ]
        assert len(error_logs) >= 1, "Должен быть error-лог при невалидном ответе"
        assert "doc-log-test" in error_logs[0]

    @pytest.mark.asyncio
    async def test_recognize_logs_error_on_exception(
        self,
        recognition_service,
        mock_request_service,
        sample_document,
        caplog,
    ):
        """Тест логирования ошибки при исключении HTTP-запроса."""
        # Arrange
        mock_request_service.recognize_document.side_effect = Exception(
            "Network failure"
        )

        # Act
        with caplog.at_level(logging.ERROR, logger="app.services.recognition_proxy_service"):
            with pytest.raises(Exception):
                await recognition_service.recognize(sample_document)

        # Assert — проверяем наличие error-лога
        log_messages = [record.message for record in caplog.records]
        error_logs = [
            msg for msg in log_messages
            if "Ошибка распознавания документа" in msg
        ]
        assert len(error_logs) >= 1, "Должен быть error-лог при исключении"
        assert "doc-log-test" in error_logs[0]
