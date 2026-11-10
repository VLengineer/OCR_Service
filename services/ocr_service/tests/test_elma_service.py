"""Тесты для ElmaService."""
import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.services.elma_service import ElmaService


@pytest.fixture
def mock_settings():
    """Фикстура для мокирования настроек."""
    with patch("app.services.elma_service.settings") as mock:
        mock.elma_base_url = "http://test-elma.local"
        mock.elma_token = "test_token"
        mock.elma_list_path = "/api/documents"
        mock.elma_request_timeout_sec = 30
        yield mock


@pytest.fixture
def elma_service(mock_settings):
    """Создание экземпляра ElmaService для тестов."""
    return ElmaService()


class TestAuthHeaders:
    """Тесты для метода _auth_headers."""

    def test_auth_headers_contains_bearer_token(self, elma_service):
        """Заголовки авторизации содержат Bearer токен."""
        headers = elma_service._auth_headers()
        assert headers["Authorization"] == "Bearer test_token"
        assert headers["Content-Type"] == "application/json"


class TestGetDocumentsList:
    """Тесты для метода get_documents_list."""

    @pytest.mark.asyncio
    async def test_get_documents_list_success_with_list_response(self, elma_service):
        """Успешное получение списка документов (ответ - массив)."""
        mock_response_data = [
            {"__id": "1", "__name": "doc1.pdf", "__createdAt": "2024-01-15T10:30:00"},
            {"__id": "2", "__name": "doc2.pdf", "__createdAt": "2024-01-16T11:00:00"},
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await elma_service.get_documents_list()

        assert len(result) == 2
        assert result[0].id_ == "1"
        assert result[0].name_ == "doc1.pdf"
        assert result[1].id_ == "2"
        assert result[1].name_ == "doc2.pdf"

    @pytest.mark.asyncio
    async def test_get_documents_list_success_with_items_key(self, elma_service):
        """Успешное получение списка документов (ответ с ключом 'items')."""
        mock_response_data = {
            "items": [
                {"__id": "10", "__name": "report.pdf"},
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await elma_service.get_documents_list()

        assert len(result) == 1
        assert result[0].id_ == "10"

    @pytest.mark.asyncio
    async def test_get_documents_list_success_with_documents_key(self, elma_service):
        """Успешное получение списка документов (ответ с ключом 'documents')."""
        mock_response_data = {
            "documents": [
                {"__id": "20", "__name": "contract.pdf"},
            ]
        }

        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await elma_service.get_documents_list()

        assert len(result) == 1
        assert result[0].id_ == "20"

    @pytest.mark.asyncio
    async def test_get_documents_list_empty_response(self, elma_service):
        """Получение пустого списка документов."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await elma_service.get_documents_list()

        assert result == []

    @pytest.mark.asyncio
    async def test_get_documents_list_http_error(self, elma_service):
        """Обработка HTTP ошибки при получении списка документов."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500)
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await elma_service.get_documents_list()


class TestDownloadDocument:
    """Тесты для метода download_document."""

    @pytest.mark.asyncio
    async def test_download_document_success(self, elma_service):
        """Успешное скачивание документа."""
        file_content = b"PDF file content here"

        mock_response = MagicMock()
        mock_response.content = file_content
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await elma_service.download_document(
                document_url="http://elma.local/docs/123"
            )

        assert result == file_content

    @pytest.mark.asyncio
    async def test_download_document_http_error_returns_none(self, elma_service):
        """Обработка HTTP ошибки при скачивании документа (возвращает None)."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=MagicMock(status_code=404)
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await elma_service.download_document(
                document_url="http://elma.local/docs/999"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_download_document_connection_error_returns_none(self, elma_service):
        """Обработка ошибки соединения при скачивании (возвращает None)."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await elma_service.download_document(
                document_url="http://elma.local/docs/1"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_download_document_empty_content(self, elma_service):
        """Скачивание документа с пустым содержимым."""
        mock_response = MagicMock()
        mock_response.content = b""
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await elma_service.download_document(
                document_url="http://elma.local/docs/1"
            )

        assert result == b""


class TestGetDocumentBase64:
    """Тесты для метода get_document_base64."""

    @pytest.mark.asyncio
    async def test_get_document_base64_success(self, elma_service):
        """Успешное получение документа в base64."""
        file_content = b"Test file content for base64 encoding"
        expected_base64 = base64.b64encode(file_content).decode("utf-8")

        mock_response = MagicMock()
        mock_response.content = file_content
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await elma_service.get_document_base64(
                document_url="http://elma.local/docs/456"
            )

        assert result == expected_base64

    @pytest.mark.asyncio
    async def test_get_document_base64_binary_content(self, elma_service):
        """Получение base64 для бинарного содержимого."""
        file_content = bytes(range(256))  # все возможные байты
        expected_base64 = base64.b64encode(file_content).decode("utf-8")

        mock_response = MagicMock()
        mock_response.content = file_content
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await elma_service.get_document_base64(
                document_url="http://elma.local/docs/789"
            )

        assert result == expected_base64

    @pytest.mark.asyncio
    async def test_get_document_base64_http_error_returns_none(self, elma_service):
        """Обработка HTTP ошибки при получении base64 (возвращает None)."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized",
            request=MagicMock(),
            response=MagicMock(status_code=401)
        )

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await elma_service.get_document_base64(
                document_url="http://elma.local/docs/111"
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_document_base64_empty_content_returns_none(self, elma_service):
        """Получение base64 для пустого содержимого (возвращает None)."""
        mock_response = MagicMock()
        mock_response.content = b""
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            result = await elma_service.get_document_base64(
                document_url="http://elma.local/docs/empty"
            )

        assert result is None
