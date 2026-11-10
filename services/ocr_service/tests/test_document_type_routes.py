"""
Unit-тесты для document_type валидации в эндпоинтах.

Тестируется POST /api/v1/ocr/documents и POST /api/v1/ocr
на предмет корректной обработки поля document_type
(валидные, невалидные, None, пустая строка).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.document_routes import router as document_router
from app.api.routes.direct_ocr_routes import router as direct_ocr_router
from app.api.deps import (
    get_document_service,
    get_direct_ocr_service,
    get_current_user,
    get_document_type_registry,
)
from app.core.document_type_registry import DocumentTypeRegistry
from app.services.document_service import DocumentService
from app.services.direct_ocr_service import DirectOCRService


VALID_TYPES = [
    "incoming_correspondence",
    "outgoing_contract",
    "payment",
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
def mock_document_service():
    """Mock DocumentService."""
    service = MagicMock(spec=DocumentService)
    service.processing = AsyncMock()
    return service


@pytest.fixture
def mock_direct_ocr_service():
    """Mock DirectOCRService."""
    service = MagicMock(spec=DirectOCRService)
    service.process = AsyncMock(return_value={"result": "ok"})
    return service


@pytest.fixture
def fake_user():
    """Фейковый пользователь для авторизации."""
    return {"sub": "test-user", "role": "admin"}


@pytest.fixture
def document_app(mock_document_service, mock_registry, fake_user):
    """Test FastAPI app для document_routes."""
    test_app = FastAPI()
    test_app.include_router(document_router)
    test_app.dependency_overrides[get_document_service] = lambda: mock_document_service
    test_app.dependency_overrides[get_current_user] = lambda: fake_user
    test_app.dependency_overrides[get_document_type_registry] = lambda: mock_registry
    return test_app


@pytest.fixture
def direct_ocr_app(mock_direct_ocr_service, mock_registry, fake_user):
    """Test FastAPI app для direct_ocr_routes."""
    test_app = FastAPI()
    test_app.include_router(direct_ocr_router)
    test_app.dependency_overrides[get_direct_ocr_service] = lambda: mock_direct_ocr_service
    test_app.dependency_overrides[get_current_user] = lambda: fake_user
    test_app.dependency_overrides[get_document_type_registry] = lambda: mock_registry
    return test_app


@pytest.fixture
def document_client(document_app):
    """TestClient для document_routes."""
    return TestClient(document_app)


@pytest.fixture
def direct_ocr_client(direct_ocr_app):
    """TestClient для direct_ocr_routes."""
    return TestClient(direct_ocr_app)


class TestDocumentEndpointDocumentType:
    """Тесты document_type в POST /api/v1/ocr/documents."""

    def test_process_document_with_valid_document_type(
        self, document_client, mock_document_service
    ):
        """Документ успешно принимается с валидным document_type."""
        response = document_client.post(
            "/api/v1/ocr/documents",
            json={
                "document_id": "doc-123",
                "document_base64": "aGVsbG8=",
                "document_type": "invoice",
            },
        )
        assert response.status_code == 202
        mock_document_service.processing.assert_called_once()

    def test_process_document_with_none_document_type(
        self, document_client, mock_document_service
    ):
        """Документ успешно принимается без document_type (None)."""
        response = document_client.post(
            "/api/v1/ocr/documents",
            json={
                "document_id": "doc-124",
                "document_base64": "aGVsbG8=",
            },
        )
        assert response.status_code == 202
        mock_document_service.processing.assert_called_once()

    def test_process_document_with_empty_string_document_type(
        self, document_client, mock_document_service
    ):
        """Документ успешно принимается с document_type=''."""
        response = document_client.post(
            "/api/v1/ocr/documents",
            json={
                "document_id": "doc-125",
                "document_base64": "aGVsbG8=",
                "document_type": "",
            },
        )
        assert response.status_code == 202
        mock_document_service.processing.assert_called_once()

    def test_process_document_with_invalid_document_type_returns_400(
        self, document_client, mock_document_service
    ):
        """Невалидный document_type возвращает 400."""
        response = document_client.post(
            "/api/v1/ocr/documents",
            json={
                "document_id": "doc-126",
                "document_base64": "aGVsbG8=",
                "document_type": "invalid_type_xyz",
            },
        )
        assert response.status_code == 400
        assert "invalid_type_xyz" in response.json()["detail"]
        mock_document_service.processing.assert_not_called()

    @pytest.mark.parametrize("doc_type", VALID_TYPES)
    def test_process_document_with_various_valid_types(
        self, document_client, mock_document_service, doc_type
    ):
        """Различные валидные типы принимаются."""
        response = document_client.post(
            "/api/v1/ocr/documents",
            json={
                "document_id": f"doc-{doc_type}",
                "document_base64": "aGVsbG8=",
                "document_type": doc_type,
            },
        )
        assert response.status_code == 202


class TestDirectOCREndpointDocumentType:
    """Тесты document_type в POST /api/v1/ocr."""

    def test_direct_ocr_with_valid_document_type(
        self, direct_ocr_client, mock_direct_ocr_service
    ):
        """Direct OCR успешно выполняется с валидным document_type."""
        response = direct_ocr_client.post(
            "/api/v1/ocr",
            json={
                "document_id": "doc-200",
                "document_base64": "aGVsbG8=",
                "document_type": "invoice",
            },
        )
        assert response.status_code == 200
        mock_direct_ocr_service.process.assert_called_once()

    def test_direct_ocr_with_none_document_type(
        self, direct_ocr_client, mock_direct_ocr_service
    ):
        """Direct OCR успешно выполняется без document_type."""
        response = direct_ocr_client.post(
            "/api/v1/ocr",
            json={
                "document_id": "doc-201",
                "document_base64": "aGVsbG8=",
            },
        )
        assert response.status_code == 200
        mock_direct_ocr_service.process.assert_called_once()

    def test_direct_ocr_with_empty_string_document_type(
        self, direct_ocr_client, mock_direct_ocr_service
    ):
        """Direct OCR успешно выполняется с document_type=''."""
        response = direct_ocr_client.post(
            "/api/v1/ocr",
            json={
                "document_id": "doc-202",
                "document_base64": "aGVsbG8=",
                "document_type": "",
            },
        )
        assert response.status_code == 200
        mock_direct_ocr_service.process.assert_called_once()

    def test_direct_ocr_with_invalid_document_type_returns_400(
        self, direct_ocr_client, mock_direct_ocr_service
    ):
        """Невалидный document_type возвращает 400."""
        response = direct_ocr_client.post(
            "/api/v1/ocr",
            json={
                "document_id": "doc-203",
                "document_base64": "aGVsbG8=",
                "document_type": "invalid_type_xyz",
            },
        )
        assert response.status_code == 400
        assert "invalid_type_xyz" in response.json()["detail"]
        mock_direct_ocr_service.process.assert_not_called()

    @pytest.mark.parametrize("doc_type", VALID_TYPES)
    def test_direct_ocr_with_various_valid_types(
        self, direct_ocr_client, mock_direct_ocr_service, doc_type
    ):
        """Различные валидные типы принимаются в direct OCR."""
        response = direct_ocr_client.post(
            "/api/v1/ocr",
            json={
                "document_id": f"doc-{doc_type}",
                "document_base64": "aGVsbG8=",
                "document_type": doc_type,
            },
        )
        assert response.status_code == 200
