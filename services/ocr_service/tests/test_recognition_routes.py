"""
Unit-тесты для recognition_routes (POST /api/v1/recognition/recognize).

Тестируются:
- Успешный запрос с валидным Document → 200 + DocumentRequest
- Невалидный document_type → 400
- Ошибка парсинга (ValueError) → 400
- Ошибка распознавания (Exception) → 500
- Запрос без JWT-авторизации → 401
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.recognition_routes import router as recognition_router
from app.api.deps import (
    get_current_user,
    get_document_type_registry,
    get_recognition_proxy_service,
)
from app.core.document_type_registry import DocumentTypeRegistry
from app.schemas.schemas import DocumentRequest
from app.services.recognition_proxy_service import RecognitionProxyService


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

VALID_TYPES = [
    "incoming_correspondence",
    "outgoing_contract",
    "invoice",
]


@pytest.fixture
def mock_registry():
    """Mock DocumentTypeRegistry с валидными типами."""
    registry = MagicMock(spec=DocumentTypeRegistry)
    registry.is_valid = MagicMock(side_effect=lambda dt: (
        dt is None or dt == "" or dt in VALID_TYPES
    ))
    return registry


@pytest.fixture
def mock_recognition_service():
    """Mock RecognitionProxyService."""
    service = MagicMock(spec=RecognitionProxyService)
    service.recognize = AsyncMock()
    return service


@pytest.fixture
def fake_user():
    """Фейковый пользователь для авторизации."""
    return {"sub": "test-user", "role": "admin"}


@pytest.fixture
def recognition_app(mock_recognition_service, mock_registry, fake_user):
    """Test FastAPI app для recognition_routes с моками зависимостей."""
    test_app = FastAPI()
    test_app.include_router(recognition_router)
    test_app.dependency_overrides[get_recognition_proxy_service] = (
        lambda: mock_recognition_service
    )
    test_app.dependency_overrides[get_current_user] = lambda: fake_user
    test_app.dependency_overrides[get_document_type_registry] = (
        lambda: mock_registry
    )
    return test_app


@pytest.fixture
def recognition_client(recognition_app):
    """TestClient для recognition_routes."""
    return TestClient(recognition_app)


@pytest.fixture
def unauthenticated_app(mock_recognition_service, mock_registry):
    """Test FastAPI app без override для get_current_user (для теста 401)."""
    test_app = FastAPI()
    test_app.include_router(recognition_router)
    test_app.dependency_overrides[get_recognition_proxy_service] = (
        lambda: mock_recognition_service
    )
    test_app.dependency_overrides[get_document_type_registry] = (
        lambda: mock_registry
    )
    # get_current_user НЕ переопределяем — будет реальная проверка JWT
    return test_app


@pytest.fixture
def unauthenticated_client(unauthenticated_app):
    """TestClient без авторизации."""
    return TestClient(unauthenticated_app)


# ──────────────────────────────────────────────
# Тесты успешного распознавания
# ──────────────────────────────────────────────

class TestRecognizeSuccess:
    """Тесты успешного запроса POST /api/v1/recognition/recognize."""

    def test_recognize_returns_200_with_valid_document(
        self, recognition_client, mock_recognition_service
    ):
        """Успешный запрос: POST с валидным Document → 200 и DocumentRequest."""
        # Arrange
        task_id = uuid4()
        mock_recognition_service.recognize.return_value = DocumentRequest(
            task_id=task_id,
            document_id="doc-123",
            raw_text="Распознанный текст",
            document_type="invoice",
        )

        # Act
        response = recognition_client.post(
            "/api/v1/recognition/recognize",
            json={
                "document_id": "doc-123",
                "document_base64": "aGVsbG8=",
                "document_type": "invoice",
            },
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc-123"
        assert data["raw_text"] == "Распознанный текст"
        assert data["document_type"] == "invoice"
        assert data["task_id"] == str(task_id)

        mock_recognition_service.recognize.assert_called_once()

    def test_recognize_without_document_type(
        self, recognition_client, mock_recognition_service
    ):
        """Успешный запрос без document_type (None)."""
        # Arrange
        mock_recognition_service.recognize.return_value = DocumentRequest(
            document_id="doc-456",
            raw_text="Текст",
        )

        # Act
        response = recognition_client.post(
            "/api/v1/recognition/recognize",
            json={
                "document_id": "doc-456",
                "document_base64": "aGVsbG8=",
            },
        )

        # Assert
        assert response.status_code == 200
        assert response.json()["document_id"] == "doc-456"

    def test_recognize_passes_document_to_service(
        self, recognition_client, mock_recognition_service
    ):
        """Проверяем, что документ передаётся в сервис распознавания."""
        # Arrange
        mock_recognition_service.recognize.return_value = DocumentRequest(
            document_id="doc-789",
            raw_text="Текст",
        )

        # Act
        recognition_client.post(
            "/api/v1/recognition/recognize",
            json={
                "document_id": "doc-789",
                "document_base64": "cGRmZGF0YQ==",
                "document_type": "incoming_correspondence",
            },
        )

        # Assert — проверяем что сервис был вызван с Document
        mock_recognition_service.recognize.assert_called_once()
        call_args = mock_recognition_service.recognize.call_args
        document = call_args[0][0]
        assert document.document_id == "doc-789"
        assert document.document_base64 == "cGRmZGF0YQ=="
        assert document.document_type == "incoming_correspondence"


# ──────────────────────────────────────────────
# Тесты валидации document_type
# ──────────────────────────────────────────────

class TestRecognizeDocumentTypeValidation:
    """Тесты валидации document_type."""

    def test_invalid_document_type_returns_400(
        self, recognition_client, mock_recognition_service
    ):
        """Невалидный document_type → 400."""
        # Act
        response = recognition_client.post(
            "/api/v1/recognition/recognize",
            json={
                "document_id": "doc-invalid",
                "document_base64": "aGVsbG8=",
                "document_type": "invalid",
            },
        )

        # Assert
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"]
        mock_recognition_service.recognize.assert_not_called()


# ──────────────────────────────────────────────
# Тесты обработки ошибок
# ──────────────────────────────────────────────

class TestRecognizeErrorHandling:
    """Тесты обработки ошибок распознавания."""

    def test_value_error_returns_400(
        self, recognition_client, mock_recognition_service
    ):
        """Ошибка парсинга (ValueError) → 400."""
        # Arrange
        mock_recognition_service.recognize.side_effect = ValueError(
            "Некорректный формат ответа"
        )

        # Act
        response = recognition_client.post(
            "/api/v1/recognition/recognize",
            json={
                "document_id": "doc-err",
                "document_base64": "aGVsbG8=",
                "document_type": "invoice",
            },
        )

        # Assert
        assert response.status_code == 400
        assert "Некорректный формат ответа" in response.json()["detail"]

    def test_general_exception_returns_500(
        self, recognition_client, mock_recognition_service
    ):
        """Ошибка распознавания (Exception) → 500."""
        # Arrange
        mock_recognition_service.recognize.side_effect = Exception(
            "Connection timeout"
        )

        # Act
        response = recognition_client.post(
            "/api/v1/recognition/recognize",
            json={
                "document_id": "doc-err",
                "document_base64": "aGVsbG8=",
                "document_type": "invoice",
            },
        )

        # Assert
        assert response.status_code == 500
        assert "Connection timeout" in response.json()["detail"]

    def test_connection_error_returns_500(
        self, recognition_client, mock_recognition_service
    ):
        """ConnectionError → 500."""
        # Arrange
        mock_recognition_service.recognize.side_effect = ConnectionError(
            "Network unreachable"
        )

        # Act
        response = recognition_client.post(
            "/api/v1/recognition/recognize",
            json={
                "document_id": "doc-err",
                "document_base64": "aGVsbG8=",
                "document_type": "invoice",
            },
        )

        # Assert
        assert response.status_code == 500
        assert "Network unreachable" in response.json()["detail"]


# ──────────────────────────────────────────────
# Тесты авторизации
# ──────────────────────────────────────────────

class TestRecognizeAuthorization:
    """Тесты JWT-авторизации."""

    def test_request_without_jwt_returns_401(
        self, unauthenticated_client
    ):
        """Запрос без JWT-токена → 401."""
        # Act
        response = unauthenticated_client.post(
            "/api/v1/recognition/recognize",
            json={
                "document_id": "doc-noauth",
                "document_base64": "aGVsbG8=",
                "document_type": "invoice",
            },
        )

        # Assert
        assert response.status_code == 401
