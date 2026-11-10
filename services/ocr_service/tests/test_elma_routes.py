"""
Unit-тесты для elma_routes.

Тестируются:
- GET /api/v1/elma/documents: получение списка документов
- POST /api/v1/elma/documents/{document_id}/process: создание задачи на обработку документа
- POST /api/v1/elma/load-documents: загрузка всех документов
- Обработка ошибок и авторизация (401)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.elma_routes import router as elma_router
from app.api.deps import get_current_user, get_elma_service, get_task_repository
from app.schemas.schemas import ElmaDocument, State, Task, CallType
from app.services.elma_service import ElmaService
from app.repositories.task_repository import TaskRepository


# ──────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────

@pytest.fixture
def mock_elma_service():
    """Mock ElmaService."""
    service = MagicMock(spec=ElmaService)
    service.get_documents_list = AsyncMock()
    service.download_document = AsyncMock()
    service.get_document_base64 = AsyncMock()
    return service


@pytest.fixture
def mock_task_repository():
    """Mock TaskRepository."""
    repository = MagicMock(spec=TaskRepository)
    repository.add_task = AsyncMock()
    return repository


@pytest.fixture
def fake_user():
    """Фейковый пользователь для авторизации."""
    return {"sub": "test-user", "role": "admin"}


@pytest.fixture
def sample_elma_documents():
    """Пример списка документов из ELMA365."""
    return [
        ElmaDocument(
            __id="doc-1",
            __name="Документ 1",
            url="https://elma365.example.com/download/1",
            subject="Тема 1",
            description="Описание 1",
            __createdAt="2025-01-01T10:00:00Z",
            counterparty="Контрагент 1",
            decisionMaker="Ответственный 1",
            __register_name="Договоры",
            registrationDate="2025-01-01",
        ),
        ElmaDocument(
            __id="doc-2",
            __name="Документ 2",
            url="https://elma365.example.com/download/2",
            subject="Тема 2",
            description="Описание 2",
            __createdAt="2025-01-02T10:00:00Z",
            counterparty="Контрагент 2",
            decisionMaker="Ответственный 2",
            __register_name="Счета",
            registrationDate="2025-01-02",
        ),
    ]


@pytest.fixture
def sample_task():
    """Пример созданной задачи."""
    now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    return Task(
        id=uuid4(),
        document_id="doc-1",
        document_type="Договоры",
        state=State.WAITING,
        retry_count=0,
        base64_document=[],
        call_type=CallType.FILL_RAG,
        metadata={
            "url": "https://elma365.example.com/download/1",
            "__id": "doc-1",
            "__name": "Документ 1",
        },
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def elma_app(mock_elma_service, mock_task_repository, fake_user):
    """Test FastAPI app для elma_routes с моками зависимостей."""
    test_app = FastAPI()
    test_app.include_router(elma_router)
    test_app.dependency_overrides[get_elma_service] = lambda: mock_elma_service
    test_app.dependency_overrides[get_task_repository] = lambda: mock_task_repository
    test_app.dependency_overrides[get_current_user] = lambda: fake_user
    return test_app


@pytest.fixture
def elma_client(elma_app):
    """TestClient для elma_routes."""
    return TestClient(elma_app)


@pytest.fixture
def unauthenticated_app(mock_elma_service, mock_task_repository):
    """Test FastAPI app без override для get_current_user (для теста 401)."""
    test_app = FastAPI()
    test_app.include_router(elma_router)
    test_app.dependency_overrides[get_elma_service] = lambda: mock_elma_service
    test_app.dependency_overrides[get_task_repository] = lambda: mock_task_repository
    # get_current_user НЕ переопределяем — будет реальная проверка JWT
    return test_app


@pytest.fixture
def unauthenticated_client(unauthenticated_app):
    """TestClient без авторизации."""
    return TestClient(unauthenticated_app)


# ──────────────────────────────────────────────
# Тесты GET /api/v1/elma/documents
# ──────────────────────────────────────────────

class TestGetDocumentsList:
    """Тесты получения списка документов из ELMA365."""

    def test_returns_list_of_documents(
        self, elma_client, mock_elma_service, sample_elma_documents
    ):
        """Успешный запрос: GET → 200 и список документов."""
        # Arrange
        mock_elma_service.get_documents_list.return_value = sample_elma_documents

        # Act
        response = elma_client.get("/api/v1/elma/documents")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["__id"] == "doc-1"
        assert data[0]["__name"] == "Документ 1"
        assert data[1]["__id"] == "doc-2"

        mock_elma_service.get_documents_list.assert_called_once()

    def test_returns_empty_list_when_no_documents(
        self, elma_client, mock_elma_service
    ):
        """Пустой список документов → 200 и пустой массив."""
        # Arrange
        mock_elma_service.get_documents_list.return_value = []

        # Act
        response = elma_client.get("/api/v1/elma/documents")

        # Assert
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_500_on_elma_service_error(
        self, elma_client, mock_elma_service
    ):
        """Ошибка в ElmaService → 500."""
        # Arrange
        mock_elma_service.get_documents_list.side_effect = Exception(
            "Connection to ELMA365 failed"
        )

        # Act
        response = elma_client.get("/api/v1/elma/documents")

        # Assert
        assert response.status_code == 500
        assert "Connection to ELMA365 failed" in response.json()["detail"]


# ──────────────────────────────────────────────
# Тесты POST /api/v1/elma/documents/{document_id}/process
# ──────────────────────────────────────────────

class TestProcessElmaDocument:
    """Тесты создания задачи на обработку документа из ELMA365."""

    def test_creates_task_for_existing_document(
        self, elma_client, mock_elma_service, mock_task_repository,
        sample_elma_documents, sample_task
    ):
        """Документ найден → создаётся задача с типом FILL_RAG."""
        # Arrange
        mock_elma_service.get_documents_list.return_value = sample_elma_documents
        mock_task_repository.add_task.return_value = sample_task

        # Act
        response = elma_client.post("/api/v1/elma/documents/doc-1/process")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc-1"
        assert data["call_type"] == "fill_rag"
        assert data["state"] == "waiting"

        # Проверяем что add_task был вызван с правильными параметрами
        mock_task_repository.add_task.assert_called_once()
        call_kwargs = mock_task_repository.add_task.call_args[1]
        assert call_kwargs["document_id"] == "doc-1"
        assert call_kwargs["base64_document"] is None
        assert call_kwargs["call_type"] == CallType.FILL_RAG
        assert call_kwargs["state"] == State.WAITING
        assert call_kwargs["metadata"]["url"] == "https://elma365.example.com/download/1"

    def test_returns_404_when_document_not_found(
        self, elma_client, mock_elma_service, sample_elma_documents
    ):
        """Документ не найден в ELMA365 → 404."""
        # Arrange
        mock_elma_service.get_documents_list.return_value = sample_elma_documents

        # Act
        response = elma_client.post("/api/v1/elma/documents/doc-999/process")

        # Assert
        assert response.status_code == 404
        assert "doc-999" in response.json()["detail"]
        assert "не найден" in response.json()["detail"]

    def test_returns_400_when_document_has_no_url(
        self, elma_client, mock_elma_service
    ):
        """Документ без URL → 400."""
        # Arrange
        document_without_url = ElmaDocument(
            __id="doc-no-url",
            __name="Документ без URL",
            url=None,  # Нет URL
            __register_name="Договоры",
        )
        mock_elma_service.get_documents_list.return_value = [document_without_url]

        # Act
        response = elma_client.post("/api/v1/elma/documents/doc-no-url/process")

        # Assert
        assert response.status_code == 400
        assert "не имеет URL" in response.json()["detail"]

    def test_metadata_contains_all_document_fields(
        self, elma_client, mock_elma_service, mock_task_repository,
        sample_elma_documents, sample_task
    ):
        """Метаданные задачи содержат все поля документа."""
        # Arrange
        mock_elma_service.get_documents_list.return_value = sample_elma_documents
        mock_task_repository.add_task.return_value = sample_task

        # Act
        elma_client.post("/api/v1/elma/documents/doc-1/process")

        # Assert
        call_kwargs = mock_task_repository.add_task.call_args[1]
        metadata = call_kwargs["metadata"]
        assert metadata["url"] == "https://elma365.example.com/download/1"
        assert metadata["__id"] == "doc-1"
        assert metadata["__name"] == "Документ 1"
        assert metadata["subject"] == "Тема 1"
        assert metadata["description"] == "Описание 1"
        assert metadata["__createdAt"] == "2025-01-01T10:00:00Z"
        assert metadata["counterparty"] == "Контрагент 1"
        assert metadata["decisionMaker"] == "Ответственный 1"
        assert metadata["__register_name"] == "Договоры"
        assert metadata["registrationDate"] == "2025-01-01"


# ──────────────────────────────────────────────
# Тесты POST /api/v1/elma/load-documents
# ──────────────────────────────────────────────

class TestLoadDocumentsFromElma:
    """Тесты загрузки всех документов из ELMA365."""

    def test_creates_tasks_for_all_documents_with_url(
        self, elma_client, mock_elma_service, mock_task_repository,
        sample_elma_documents
    ):
        """Документы с URL → создаются задачи для каждого."""
        # Arrange
        mock_elma_service.get_documents_list.return_value = sample_elma_documents
        task1 = MagicMock(spec=Task)
        task1.id = uuid4()
        task1.document_id = "doc-1"
        task1.call_type = CallType.FILL_RAG
        task1.state = State.WAITING
        task1.base64_document = []
        task1.created_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        task1.updated_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        task1.model_dump = MagicMock(return_value={
            "id": str(task1.id),
            "document_id": "doc-1",
            "call_type": "fill_rag",
            "state": "waiting",
        })

        task2 = MagicMock(spec=Task)
        task2.id = uuid4()
        task2.document_id = "doc-2"
        task2.call_type = CallType.FILL_RAG
        task2.state = State.WAITING
        task2.base64_document = []
        task2.created_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        task2.updated_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        task2.model_dump = MagicMock(return_value={
            "id": str(task2.id),
            "document_id": "doc-2",
            "call_type": "fill_rag",
            "state": "waiting",
        })

        mock_task_repository.add_task.side_effect = [task1, task2]

        # Act
        response = elma_client.post("/api/v1/elma/load-documents")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["document_id"] == "doc-1"
        assert data[1]["document_id"] == "doc-2"

        # Проверяем что add_task был вызван дважды
        assert mock_task_repository.add_task.call_count == 2

    def test_skips_documents_without_url(
        self, elma_client, mock_elma_service, mock_task_repository
    ):
        """Документы без URL пропускаются."""
        # Arrange
        documents = [
            ElmaDocument(
                __id="doc-1",
                __name="Документ 1",
                url="https://elma365.example.com/download/1",
                __register_name="Договоры",
            ),
            ElmaDocument(
                __id="doc-2",
                __name="Документ 2",
                url=None,  # Нет URL
                __register_name="Счета",
            ),
            ElmaDocument(
                __id="doc-3",
                __name="Документ 3",
                url="https://elma365.example.com/download/3",
                __register_name="Акты",
            ),
        ]
        mock_elma_service.get_documents_list.return_value = documents

        task1 = MagicMock(spec=Task)
        task1.id = uuid4()
        task1.document_id = "doc-1"
        task1.call_type = CallType.FILL_RAG
        task1.state = State.WAITING
        task1.base64_document = []
        task1.created_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        task1.updated_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        task1.model_dump = MagicMock(return_value={
            "id": str(task1.id),
            "document_id": "doc-1",
            "call_type": "fill_rag",
            "state": "waiting",
        })

        task3 = MagicMock(spec=Task)
        task3.id = uuid4()
        task3.document_id = "doc-3"
        task3.call_type = CallType.FILL_RAG
        task3.state = State.WAITING
        task3.base64_document = []
        task3.created_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        task3.updated_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        task3.model_dump = MagicMock(return_value={
            "id": str(task3.id),
            "document_id": "doc-3",
            "call_type": "fill_rag",
            "state": "waiting",
        })

        mock_task_repository.add_task.side_effect = [task1, task3]

        # Act
        response = elma_client.post("/api/v1/elma/load-documents")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # Только 2 задачи, doc-2 пропущен
        assert data[0]["document_id"] == "doc-1"
        assert data[1]["document_id"] == "doc-3"

        # Проверяем что add_task был вызван только 2 раза (не для doc-2)
        assert mock_task_repository.add_task.call_count == 2

    def test_returns_empty_list_when_no_documents(
        self, elma_client, mock_elma_service, mock_task_repository
    ):
        """Нет документов → пустой список задач."""
        # Arrange
        mock_elma_service.get_documents_list.return_value = []

        # Act
        response = elma_client.post("/api/v1/elma/load-documents")

        # Assert
        assert response.status_code == 200
        assert response.json() == []
        mock_task_repository.add_task.assert_not_called()

    def test_creates_tasks_with_correct_parameters(
        self, elma_client, mock_elma_service, mock_task_repository,
        sample_elma_documents
    ):
        """Задачи создаются с правильными параметрами (call_type=FILL_RAG, base64=None)."""
        # Arrange
        mock_elma_service.get_documents_list.return_value = sample_elma_documents

        task = MagicMock(spec=Task)
        task.id = uuid4()
        task.document_id = "doc-1"
        task.call_type = CallType.FILL_RAG
        task.state = State.WAITING
        task.base64_document = []
        task.created_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        task.updated_at = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        task.model_dump = MagicMock(return_value={
            "id": str(task.id),
            "document_id": "doc-1",
            "call_type": "fill_rag",
            "state": "waiting",
        })
        mock_task_repository.add_task.return_value = task

        # Act
        elma_client.post("/api/v1/elma/load-documents")

        # Assert
        assert mock_task_repository.add_task.call_count == 2

        # Проверяем параметры первого вызова
        first_call = mock_task_repository.add_task.call_args_list[0]
        assert first_call[1]["call_type"] == CallType.FILL_RAG
        assert first_call[1]["base64_document"] is None
        assert first_call[1]["state"] == State.WAITING
        assert first_call[1]["metadata"]["url"] == "https://elma365.example.com/download/1"


# ──────────────────────────────────────────────
# Тесты авторизации
# ──────────────────────────────────────────────

class TestElmaAuthorization:
    """Тесты JWT-авторизации для ELMA endpoints."""

    def test_get_documents_without_jwt_returns_401(
        self, unauthenticated_client
    ):
        """GET /documents без JWT → 401."""
        response = unauthenticated_client.get("/api/v1/elma/documents")
        assert response.status_code == 401

    def test_process_document_without_jwt_returns_401(
        self, unauthenticated_client
    ):
        """POST /documents/{id}/process без JWT → 401."""
        response = unauthenticated_client.post("/api/v1/elma/documents/doc-1/process")
        assert response.status_code == 401

    def test_load_documents_without_jwt_returns_401(
        self, unauthenticated_client
    ):
        """POST /load-documents без JWT → 401."""
        response = unauthenticated_client.post("/api/v1/elma/load-documents")
        assert response.status_code == 401
