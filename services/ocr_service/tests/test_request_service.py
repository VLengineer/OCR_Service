"""
Tests for RequestService: HTTP requests to n8n webhooks,
error handling, and client lifecycle management.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.request_service import RequestService
from app.schemas.schemas import OCRRequest, DocumentRequest


# ──────────────────────────────────────────────
# Client lifecycle
# ──────────────────────────────────────────────

class TestClientLifecycle:
    """Tests for HTTP client initialization and cleanup."""

    @pytest.mark.asyncio
    async def test_client_created_on_first_use(self):
        """Client is None initially and created when needed."""
        svc = RequestService()
        assert svc._client is None

        with patch("app.services.request_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.is_closed = False
            mock_client_cls.return_value = mock_client

            client = await svc._get_client()

            assert client == mock_client
            mock_client_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_reused_on_subsequent_calls(self):
        """Same client instance is reused if not closed."""
        svc = RequestService()

        with patch("app.services.request_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.is_closed = False
            mock_client_cls.return_value = mock_client

            client1 = await svc._get_client()
            client2 = await svc._get_client()

            assert client1 == client2
            mock_client_cls.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_recreated_if_closed(self):
        """New client is created if previous one was closed."""
        svc = RequestService()

        with patch("app.services.request_service.httpx.AsyncClient") as mock_client_cls:
            old_client = MagicMock()
            old_client.is_closed = True
            new_client = MagicMock()
            new_client.is_closed = False

            mock_client_cls.side_effect = [old_client, new_client]

            client1 = await svc._get_client()
            client2 = await svc._get_client()

            assert client1 == old_client
            assert client2 == new_client
            assert mock_client_cls.call_count == 2

    @pytest.mark.asyncio
    async def test_close_closes_client(self):
        """close() method closes the HTTP client."""
        svc = RequestService()

        with patch("app.services.request_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.is_closed = False
            mock_client_cls.return_value = mock_client

            await svc._get_client()
            await svc.close()

            mock_client.aclose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_does_nothing_if_client_is_none(self):
        """close() is safe to call when client was never created."""
        svc = RequestService()
        await svc.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_close_does_nothing_if_already_closed(self):
        """close() skips aclose() if client is already closed."""
        svc = RequestService()

        with patch("app.services.request_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.is_closed = True
            mock_client_cls.return_value = mock_client

            await svc._get_client()
            await svc.close()

            mock_client.aclose.assert_not_called()


# ──────────────────────────────────────────────
# ocr_request
# ──────────────────────────────────────────────

class TestOcrRequest:
    """Tests for RequestService.ocr_request."""

    @pytest.mark.asyncio
    async def test_successful_ocr_request(self):
        """Successful OCR request returns response JSON."""
        svc = RequestService()
        request = OCRRequest(
            document_id="doc-123",
            base64_document=["page1", "page2"],
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "success", "document_id": "doc-123"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(return_value=mock_response)

        svc._client = mock_client

        with patch("app.services.request_service.settings") as mock_settings:
            mock_settings.n8n_ocr_webhook_url = "http://n8n/webhook/ocr"

            result = await svc.ocr_request(request)

        assert result == {"status": "success", "document_id": "doc-123"}
        mock_client.post.assert_awaited_once()

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://n8n/webhook/ocr"
        assert call_args[1]["headers"] == {"Content-Type": "application/json"}

        json_payload = call_args[1]["json"]
        assert json_payload["document_id"] == "doc-123"
        assert json_payload["base64_document"] == ["page1", "page2"]

    @pytest.mark.asyncio
    async def test_ocr_request_timeout_raises(self):
        """TimeoutException is re-raised."""
        svc = RequestService()
        request = OCRRequest(
            document_id="doc-timeout",
            base64_document=["page1"],
        )

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        svc._client = mock_client

        with patch("app.services.request_service.settings") as mock_settings:
            mock_settings.n8n_ocr_webhook_url = "http://n8n/webhook/ocr"

            with pytest.raises(httpx.TimeoutException, match="timeout"):
                await svc.ocr_request(request)

    @pytest.mark.asyncio
    async def test_ocr_request_http_error_raises(self):
        """HTTPStatusError is re-raised."""
        svc = RequestService()
        request = OCRRequest(
            document_id="doc-error",
            base64_document=["page1"],
        )

        mock_response = MagicMock()
        mock_response.status_code = 500
        http_error = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(side_effect=http_error)

        svc._client = mock_client

        with patch("app.services.request_service.settings") as mock_settings:
            mock_settings.n8n_ocr_webhook_url = "http://n8n/webhook/ocr"

            with pytest.raises(httpx.HTTPStatusError):
                await svc.ocr_request(request)

    @pytest.mark.asyncio
    async def test_ocr_request_general_exception_raises(self):
        """General exceptions are re-raised."""
        svc = RequestService()
        request = OCRRequest(
            document_id="doc-exception",
            base64_document=["page1"],
        )

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(side_effect=Exception("network error"))

        svc._client = mock_client

        with patch("app.services.request_service.settings") as mock_settings:
            mock_settings.n8n_ocr_webhook_url = "http://n8n/webhook/ocr"

            with pytest.raises(Exception, match="network error"):
                await svc.ocr_request(request)

    @pytest.mark.asyncio
    async def test_ocr_request_calls_raise_for_status(self):
        """raise_for_status() is called on response."""
        svc = RequestService()
        request = OCRRequest(
            document_id="doc-status",
            base64_document=["page1"],
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(return_value=mock_response)

        svc._client = mock_client

        with patch("app.services.request_service.settings") as mock_settings:
            mock_settings.n8n_ocr_webhook_url = "http://n8n/webhook/ocr"
            await svc.ocr_request(request)

        mock_response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_ocr_request_serializes_list_as_json(self):
        """base64_document list is serialized correctly in JSON."""
        svc = RequestService()
        request = OCRRequest(
            document_id="doc-serial",
            base64_document=["data1", "data2", "data3"],
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(return_value=mock_response)

        svc._client = mock_client

        with patch("app.services.request_service.settings") as mock_settings:
            mock_settings.n8n_ocr_webhook_url = "http://n8n/webhook/ocr"
            await svc.ocr_request(request)

        json_payload = mock_client.post.call_args[1]["json"]
        assert json_payload["document_id"] == "doc-serial"
        assert json_payload["base64_document"] == ["data1", "data2", "data3"]


# ──────────────────────────────────────────────
# create_document
# ──────────────────────────────────────────────

class TestCreateDocument:
    """Tests for RequestService.create_document."""

    @pytest.mark.asyncio
    async def test_successful_create_document(self):
        """Successful document creation returns response JSON."""
        svc = RequestService()
        request = DocumentRequest(
            document_id="doc-456",
            raw_text="Extracted text content",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "created", "document_id": "doc-456"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(return_value=mock_response)

        svc._client = mock_client

        with patch("app.services.request_service.settings") as mock_settings:
            mock_settings.n8n_create_doc_webhook_url = "http://n8n/webhook/create_document"

            result = await svc.create_document(request)

        assert result == {"status": "created", "document_id": "doc-456"}
        mock_client.post.assert_awaited_once()

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://n8n/webhook/create_document"
        assert call_args[1]["headers"] == {"Content-Type": "application/json"}

        json_payload = call_args[1]["json"]
        assert json_payload["document_id"] == "doc-456"
        assert json_payload["raw_text"] == "Extracted text content"

    @pytest.mark.asyncio
    async def test_create_document_timeout_raises(self):
        """TimeoutException is re-raised."""
        svc = RequestService()
        request = DocumentRequest(
            document_id="doc-timeout",
            raw_text="text",
        )

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        svc._client = mock_client

        with patch("app.services.request_service.settings") as mock_settings:
            mock_settings.n8n_create_doc_webhook_url = "http://n8n/webhook/create_document"

            with pytest.raises(httpx.TimeoutException, match="timeout"):
                await svc.create_document(request)

    @pytest.mark.asyncio
    async def test_create_document_http_error_raises(self):
        """HTTPStatusError is re-raised."""
        svc = RequestService()
        request = DocumentRequest(
            document_id="doc-error",
            raw_text="text",
        )

        mock_response = MagicMock()
        mock_response.status_code = 400
        http_error = httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(side_effect=http_error)

        svc._client = mock_client

        with patch("app.services.request_service.settings") as mock_settings:
            mock_settings.n8n_create_doc_webhook_url = "http://n8n/webhook/create_document"

            with pytest.raises(httpx.HTTPStatusError):
                await svc.create_document(request)

    @pytest.mark.asyncio
    async def test_create_document_general_exception_raises(self):
        """General exceptions are re-raised."""
        svc = RequestService()
        request = DocumentRequest(
            document_id="doc-exception",
            raw_text="text",
        )

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(side_effect=Exception("connection failed"))

        svc._client = mock_client

        with patch("app.services.request_service.settings") as mock_settings:
            mock_settings.n8n_create_doc_webhook_url = "http://n8n/webhook/create_document"

            with pytest.raises(Exception, match="connection failed"):
                await svc.create_document(request)

    @pytest.mark.asyncio
    async def test_create_document_calls_raise_for_status(self):
        """raise_for_status() is called on response."""
        svc = RequestService()
        request = DocumentRequest(
            document_id="doc-status",
            raw_text="text",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(return_value=mock_response)

        svc._client = mock_client

        with patch("app.services.request_service.settings") as mock_settings:
            mock_settings.n8n_create_doc_webhook_url = "http://n8n/webhook/create_document"
            await svc.create_document(request)

        mock_response.raise_for_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_document_serializes_fields_correctly(self):
        """Document fields are serialized correctly in JSON."""
        svc = RequestService()
        request = DocumentRequest(
            document_id="doc-serial",
            raw_text="some text content",
        )

        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.is_closed = False
        mock_client.post = AsyncMock(return_value=mock_response)

        svc._client = mock_client

        with patch("app.services.request_service.settings") as mock_settings:
            mock_settings.n8n_create_doc_webhook_url = "http://n8n/webhook/create_document"
            await svc.create_document(request)

        json_payload = mock_client.post.call_args[1]["json"]
        assert json_payload["document_id"] == "doc-serial"
        assert json_payload["raw_text"] == "some text content"
