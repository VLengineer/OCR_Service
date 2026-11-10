"""
Тесты для recognition_routes.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock

from main import app
from app.api.deps import get_current_user, get_recognition_proxy_service


@pytest.fixture
def mock_recognition_service():
    """Фикстура для мокирования RecognitionProxyService через dependency_overrides."""
    service_instance = AsyncMock()
    app.dependency_overrides[get_recognition_proxy_service] = lambda: service_instance
    yield service_instance
    app.dependency_overrides.pop(get_recognition_proxy_service, None)


@pytest.fixture
def mock_current_user():
    """Фикстура для мокирования текущего пользователя через dependency_overrides."""
    app.dependency_overrides[get_current_user] = lambda: {"sub": "test_user", "role": "user"}
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_recognize_document_success(mock_recognition_service, mock_current_user):
    """Тест успешного распознавания документа."""
    mock_recognition_service.recognize = AsyncMock(return_value="Распознанный текст документа")

    request_data = {
        "document_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/ocr/recognize", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["extracted_text"] == "Распознанный текст документа"
    mock_recognition_service.recognize.assert_called_once()


@pytest.mark.asyncio
async def test_recognize_document_missing_base64(mock_recognition_service, mock_current_user):
    """Тест ошибки при отсутствии document_base64."""
    request_data = {}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/ocr/recognize", json=request_data)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_recognize_document_empty_base64(mock_recognition_service, mock_current_user):
    """Тест ошибки при пустом document_base64."""
    request_data = {"document_base64": ""}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/ocr/recognize", json=request_data)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_recognize_document_service_error(mock_recognition_service, mock_current_user):
    """Тест обработки ошибки сервиса."""
    mock_recognition_service.recognize = AsyncMock(
        side_effect=Exception("Ошибка распознавания")
    )

    request_data = {
        "document_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/ocr/recognize", json=request_data)

    assert response.status_code == 500
    data = response.json()
    assert "Recognition failed" in data["detail"]


@pytest.mark.asyncio
async def test_recognize_document_requires_auth():
    """Тест что эндпоинт требует авторизации."""
    async def mock_no_auth():
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    app.dependency_overrides[get_current_user] = mock_no_auth

    try:
        request_data = {
            "document_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.post("/api/v1/ocr/recognize", json=request_data)

        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
