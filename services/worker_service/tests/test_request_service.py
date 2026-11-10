"""
Тесты для RequestService — HTTP-клиента к n8n webhook'ам.
Проверяем успешные запросы, обработку ошибок и корректность payload.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx

from app.schemas.schemas import OCRRequest
from app.services.request_service import RequestService


# ────────────────────────────────────────────────────────────
# Вспомогательные fixtures
# ────────────────────────────────────────────────────────────

@pytest.fixture
def ocr_request() -> OCRRequest:
    """Тестовый OCR-запрос с известными данными."""
    return OCRRequest(
        task_id=uuid4(),
        document_id="doc-test-001",
        base64_document=["cGFnZTE=", "cGFnZTI="],
    )


@pytest.fixture
def mock_httpx_response() -> MagicMock:
    """Мок успешного HTTP-ответа (200 OK)."""
    response = MagicMock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {"status": "ok", "result": "распознанный текст"}
    response.raise_for_status.return_value = None
    return response


@pytest.fixture
def mock_client(mock_httpx_response: MagicMock) -> AsyncMock:
    """Мок httpx.AsyncClient с настроенным post()."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post = AsyncMock(return_value=mock_httpx_response)
    client.is_closed = False
    return client


@pytest.fixture
def service() -> RequestService:
    """Экземпляр RequestService без реального клиента."""
    return RequestService()


# ────────────────────────────────────────────────────────────
# Тесты успешного запроса
# ────────────────────────────────────────────────────────────

class TestOcrRequestSuccess:
    """Тесты успешного OCR-запроса."""

    async def test_successful_request_returns_json(
        self, service: RequestService, mock_client: AsyncMock, ocr_request: OCRRequest
    ):
        """ocr_request возвращает JSON из ответа при статусе 200."""
        service._client = mock_client

        result = await service.ocr_request(ocr_request)

        assert result == {"status": "ok", "result": "распознанный текст"}

    async def test_successful_request_calls_post_once(
        self, service: RequestService, mock_client: AsyncMock, ocr_request: OCRRequest
    ):
        """При успешном запросе client.post вызывается ровно один раз."""
        service._client = mock_client

        await service.ocr_request(ocr_request)

        mock_client.post.assert_awaited_once()


# ────────────────────────────────────────────────────────────
# Тесты формирования payload
# ────────────────────────────────────────────────────────────

class TestPayloadFormation:
    """Проверяем, что payload содержит правильные поля и URL."""

    async def test_payload_contains_task_id(
        self, service: RequestService, mock_client: AsyncMock, ocr_request: OCRRequest
    ):
        """В JSON-payload передаётся task_id."""
        service._client = mock_client

        await service.ocr_request(ocr_request)

        call_kwargs = mock_client.post.call_args
        json_payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert json_payload["task_id"] == str(ocr_request.task_id)

    async def test_payload_contains_document_id(
        self, service: RequestService, mock_client: AsyncMock, ocr_request: OCRRequest
    ):
        """В JSON-payload передаётся document_id."""
        service._client = mock_client

        await service.ocr_request(ocr_request)

        call_kwargs = mock_client.post.call_args
        json_payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert json_payload["document_id"] == ocr_request.document_id

    async def test_payload_contains_base64_document(
        self, service: RequestService, mock_client: AsyncMock, ocr_request: OCRRequest
    ):
        """В JSON-payload передаётся base64_document (массив страниц)."""
        service._client = mock_client

        await service.ocr_request(ocr_request)

        call_kwargs = mock_client.post.call_args
        json_payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert json_payload["base64_document"] == ocr_request.base64_document

    async def test_request_uses_correct_url(
        self, service: RequestService, mock_client: AsyncMock, ocr_request: OCRRequest
    ):
        """Запрос отправляется на URL из settings.n8n_ocr_webhook_url."""
        service._client = mock_client

        await service.ocr_request(ocr_request)

        call_args = mock_client.post.call_args
        called_url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
        # URL должен совпадать с тем, что используется в сервисе
        from app.core.config import settings
        assert called_url == settings.n8n_ocr_webhook_url

    async def test_request_sets_content_type_header(
        self, service: RequestService, mock_client: AsyncMock, ocr_request: OCRRequest
    ):
        """Запрос отправляется с заголовком Content-Type: application/json."""
        service._client = mock_client

        await service.ocr_request(ocr_request)

        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers", {})
        assert headers.get("Content-Type") == "application/json"

    async def test_payload_with_multiple_pages(
        self, service: RequestService, mock_client: AsyncMock
    ):
        """Payload корректно передаёт несколько страниц base64."""
        multi_page_request = OCRRequest(
            task_id=uuid4(),
            document_id="doc-multi",
            base64_document=["cGFnZTE=", "cGFnZTI=", "cGFnZTM="],
        )
        service._client = mock_client

        await service.ocr_request(multi_page_request)

        call_kwargs = mock_client.post.call_args
        json_payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert len(json_payload["base64_document"]) == 3


# ────────────────────────────────────────────────────────────
# Тесты обработки HTTP-ошибок
# ────────────────────────────────────────────────────────────

class TestHttpErrorHandling:
    """Проверяем обработку HTTP-ошибок (status != 200)."""

    async def test_http_status_error_is_raised(
        self, service: RequestService, ocr_request: OCRRequest
    ):
        """При статусе 4xx/5xx пробрасывается httpx.HTTPStatusError."""
        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=error_response,
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=error_response)
        mock_client.is_closed = False
        service._client = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await service.ocr_request(ocr_request)

    async def test_http_404_error_is_raised(
        self, service: RequestService, ocr_request: OCRRequest
    ):
        """При статусе 404 пробрасывается httpx.HTTPStatusError."""
        error_response = MagicMock(spec=httpx.Response)
        error_response.status_code = 404
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=error_response,
        )

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=error_response)
        mock_client.is_closed = False
        service._client = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await service.ocr_request(ocr_request)


# ────────────────────────────────────────────────────────────
# Тесты обработки таймаутов и ошибок соединения
# ────────────────────────────────────────────────────────────

class TestTimeoutAndConnectionErrors:
    """Проверяем обработку таймаутов и сетевых ошибок."""

    async def test_timeout_exception_is_raised(
        self, service: RequestService, ocr_request: OCRRequest
    ):
        """При таймауте пробрасывается httpx.TimeoutException."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Таймаут"))
        mock_client.is_closed = False
        service._client = mock_client

        with pytest.raises(httpx.TimeoutException):
            await service.ocr_request(ocr_request)

    async def test_connect_error_is_raised(
        self, service: RequestService, ocr_request: OCRRequest
    ):
        """При ошибке соединения пробрасывается httpx.ConnectError."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        mock_client.is_closed = False
        service._client = mock_client

        with pytest.raises(httpx.ConnectError):
            await service.ocr_request(ocr_request)

    async def test_generic_exception_propagates(
        self, service: RequestService, ocr_request: OCRRequest
    ):
        """Неожиданные исключения пробрасываются дальше."""
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(side_effect=RuntimeError("Неожиданная ошибка"))
        mock_client.is_closed = False
        service._client = mock_client

        with pytest.raises(RuntimeError, match="Неожиданная ошибка"):
            await service.ocr_request(ocr_request)


# ────────────────────────────────────────────────────────────
# Тесты управления клиентом (_get_client, close)
# ────────────────────────────────────────────────────────────

class TestClientLifecycle:
    """Проверяем создание и закрытие HTTP-клиента."""

    @patch("app.services.request_service.httpx.AsyncClient")
    async def test_get_client_creates_client_when_none(
        self, mock_async_client_cls: MagicMock, service: RequestService
    ):
        """_get_client создаёт новый клиент, если _client is None."""
        mock_instance = AsyncMock(spec=httpx.AsyncClient)
        mock_instance.is_closed = False
        mock_async_client_cls.return_value = mock_instance

        client = await service._get_client()

        mock_async_client_cls.assert_called_once()
        assert client is mock_instance

    @patch("app.services.request_service.httpx.AsyncClient")
    async def test_get_client_reuses_existing_client(
        self, mock_async_client_cls: MagicMock, service: RequestService
    ):
        """_get_client переиспользует существующий клиент."""
        mock_instance = AsyncMock(spec=httpx.AsyncClient)
        mock_instance.is_closed = False
        mock_async_client_cls.return_value = mock_instance
        service._client = mock_instance

        client = await service._get_client()

        mock_async_client_cls.assert_not_called()
        assert client is mock_instance

    @patch("app.services.request_service.httpx.AsyncClient")
    async def test_get_client_recreates_when_closed(
        self, mock_async_client_cls: MagicMock, service: RequestService
    ):
        """_get_client создаёт новый клиент, если старый закрыт."""
        old_client = AsyncMock(spec=httpx.AsyncClient)
        old_client.is_closed = True

        new_client = AsyncMock(spec=httpx.AsyncClient)
        new_client.is_closed = False
        mock_async_client_cls.return_value = new_client
        service._client = old_client

        client = await service._get_client()

        mock_async_client_cls.assert_called_once()
        assert client is new_client

    async def test_close_closes_client(self):
        """close() закрывает HTTP-клиент."""
        service = RequestService()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = False
        mock_client.aclose = AsyncMock()
        service._client = mock_client

        await service.close()

        mock_client.aclose.assert_awaited_once()

    async def test_close_does_nothing_when_client_is_none(self):
        """close() ничего не делает, если клиент не создан."""
        service = RequestService()
        # Не должно выбрасывать исключений
        await service.close()
        assert service._client is None

    async def test_close_does_nothing_when_already_closed(self):
        """close() не вызывает aclose, если клиент уже закрыт."""
        service = RequestService()
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.is_closed = True
        mock_client.aclose = AsyncMock()
        service._client = mock_client

        await service.close()

        mock_client.aclose.assert_not_awaited()
