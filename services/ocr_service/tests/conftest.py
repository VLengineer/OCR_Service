"""
Common fixtures for ocr_service tests.
"""

import os
import sys
from unittest.mock import MagicMock

# Мокаем модули, которые могут отсутствовать в тестовом окружении
# Это должно быть выполнено ДО любого импорта app модулей
# fitz (PyMuPDF), docx (python-docx), PIL (Pillow) используются в document_converter,
# но не нужны для тестов маршрутов и репозиториев
# Мокаем только если модули не установлены
try:
    import fitz
except ImportError:
    sys.modules["fitz"] = MagicMock()

try:
    import docx
except ImportError:
    sys.modules["docx"] = MagicMock()

try:
    import PIL
except ImportError:
    sys.modules["PIL"] = MagicMock()

# Убираем переменные окружения, которые не входят в модель Settings
# (они могут быть установлены извне и вызывать ошибки валидации)
# Это должно быть выполнено ДО любого импорта app модулей
os.environ.pop("DATABASE_URL", None)
os.environ.pop("ocr_service_bind_ip", None)
os.environ.pop("ocr_service_port", None)
os.environ.pop("ocr_log_level", None)

from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone

# Патчим create_async_engine и async_sessionmaker ДО импорта database.py
# database.py создаёт engine на уровне модуля при импорте
_mock_engine = MagicMock()
_mock_engine.begin = MagicMock()
_mock_engine.dispose = AsyncMock()

_patcher_engine = patch(
    "sqlalchemy.ext.asyncio.create_async_engine",
    return_value=_mock_engine,
)
_patcher_session = patch(
    "sqlalchemy.ext.asyncio.async_sessionmaker",
    return_value=MagicMock(),
)
_patcher_engine.start()
_patcher_session.start()

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


def pytest_sessionfinish(session, exitstatus):
    """Останавливаем патчеры после завершения тестов."""
    _patcher_engine.stop()
    _patcher_session.stop()


@pytest.fixture
def mock_session():
    """Mock AsyncSession for repository tests."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def sample_uuid():
    """Sample UUID for tests."""
    return uuid4()


@pytest.fixture
def sample_now():
    """Sample datetime for tests."""
    return datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for request service tests."""
    client = AsyncMock()
    client.is_closed = False
    client.post = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def mock_httpx_response():
    """Factory fixture for mock httpx responses."""
    def _make_response(json_data=None, status_code=200):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = json_data or {"status": "ok"}
        response.raise_for_status = MagicMock()
        return response
    return _make_response
