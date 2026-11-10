"""
Общие fixtures для тестов worker_service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from app.schemas.schemas import Task, State, CallType, OCRRequest
from app.services.request_service import RequestService


@pytest.fixture
def sample_task() -> Task:
    """Возвращает тестовую OCR-задачу в состоянии waiting.
    """
    return Task(
        id=uuid4(),
        document_id="doc-123",
        state=State.WAITING,
        retry_count=0,
        base64_document=["base64-page-1"],
        call_type=CallType.OCR,
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_fill_rag_task() -> Task:
    """Возвращает тестовую fill_rag-задачу в состоянии waiting с metadata.
    """
    return Task(
        id=uuid4(),
        document_id="doc-rag-1",
        state=State.WAITING,
        retry_count=0,
        base64_document=[],
        call_type=CallType.FILL_RAG,
        metadata={
            "url": "https://example.com/doc/123",
            "__id": "rec-abc-123",
            "__name": "Test Document",
            "__createdAt": "2025-01-15T10:30:00Z",
            "subject": "Test Subject",
            "description": "Test description",
            "counterparty": "Test Counterparty",
            "decisionMaker": "Test Decision Maker",
            "__register_name": "Test Register",
            "registrationDate": "2025-01-10",
        },
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_task_with_retries() -> Task:
    """Возвращает тестовую задачу с retry_count = 3 (на грани max_retries).
    """
    return Task(
        id=uuid4(),
        document_id="doc-456",
        state=State.WAITING,
        retry_count=3,
        base64_document=["base64-page-1", "base64-page-2"],
        call_type=CallType.OCR,
        metadata={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_request_service() -> AsyncMock:
    """Возвращает мок RequestService.
    """
    service = AsyncMock(spec=RequestService)
    service.ocr_request = AsyncMock(return_value={"status": "ok"})
    service.fill_rag_request = AsyncMock(return_value={"status": "ok"})
    return service


@pytest.fixture
def mock_session() -> AsyncMock:
    """Возвращает мок AsyncSession для тестов репозитория.
    """
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def sample_ocr_request(sample_task: Task) -> OCRRequest:
    """Возвращает тестовый OCR-запрос.
    """
    return OCRRequest(
        task_id=sample_task.id,
        document_id=sample_task.document_id,
        base64_document=sample_task.base64_document,
    )
