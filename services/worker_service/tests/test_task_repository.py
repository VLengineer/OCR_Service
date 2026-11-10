"""
Модульные тесты для TaskRepository.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

from app.repositories.task_repository import TaskRepository
from app.schemas.schemas import State, Task


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_mock_task_model(
    id=None,
    document_id="doc-123",
    state="waiting",
    retry_count=0,
    base64_document=None,
    created_at=None,
    updated_at=None,
    call_type="ocr",
    document_type="passport",
    metadata_=None,
):
    """Создаёт мок ORM-модели TaskModel."""
    model = MagicMock()
    model.id = id or uuid4()
    model.document_id = document_id
    model.state = state
    model.retry_count = retry_count
    model.base64_document = base64_document or [{"base64": "page1"}]
    model.created_at = created_at or datetime.now(timezone.utc)
    model.updated_at = updated_at or datetime.now(timezone.utc)
    model.call_type = call_type
    model.document_type = document_type
    model.metadata_ = metadata_
    return model


def _make_mock_result(scalar_value=None, scalar_one_value=None):
    """Создаёт мок результата SQLAlchemy query."""
    result = AsyncMock()
    result.scalar_one_or_none = MagicMock(return_value=scalar_value)
    result.scalar_one = MagicMock(return_value=scalar_one_value)
    return result


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

class TestTaskRepository:

    async def test_get_next_waiting_task_returns_task(self, mock_session):
        """Возвращает задачу, когда в очереди есть waiting задача."""
        # Arrange
        task_model = _make_mock_task_model(
            id=uuid4(),
            document_id="doc-123",
            state="waiting",
            retry_count=0,
            base64_document=[{"base64": "page1"}, {"base64": "page2"}],
        )
        mock_result = _make_mock_result(scalar_value=task_model)
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = TaskRepository(mock_session)

        # Act
        task = await repo.get_next_waiting_task()

        # Assert
        assert task is not None
        assert isinstance(task, Task)
        assert task.id == task_model.id
        assert task.document_id == "doc-123"
        assert task.state == State.WAITING
        assert task.retry_count == 0
        assert task.base64_document == ["page1", "page2"]
        mock_session.execute.assert_awaited_once()

    async def test_get_next_waiting_task_returns_none(self, mock_session):
        """Возвращает None, когда очередь пуста."""
        # Arrange
        mock_result = _make_mock_result(scalar_value=None)
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = TaskRepository(mock_session)

        # Act
        task = await repo.get_next_waiting_task()

        # Assert
        assert task is None
        mock_session.execute.assert_awaited_once()

    async def test_count_tasks_by_state(self, mock_session):
        """Подсчитывает количество задач по состоянию."""
        # Arrange
        mock_result = _make_mock_result(scalar_one_value=5)
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = TaskRepository(mock_session)

        # Act
        count = await repo.count_tasks_by_state(State.WAITING)

        # Assert
        assert count == 5
        mock_session.execute.assert_awaited_once()

    @pytest.mark.parametrize(
        "state,expected_count",
        [
            (State.WAITING, 10),
            (State.PROCESSING, 2),
            (State.COMPLETED, 50),
            (State.ERROR, 3),
        ],
    )
    async def test_count_tasks_by_state_various_states(
        self, mock_session, state, expected_count
    ):
        """Подсчитывает задачи для различных состояний."""
        # Arrange
        mock_result = _make_mock_result(scalar_one_value=expected_count)
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = TaskRepository(mock_session)

        # Act
        count = await repo.count_tasks_by_state(state)

        # Assert
        assert count == expected_count

    async def test_update_task_state(self, mock_session):
        """Обновляет состояние задачи и вызывает commit."""
        # Arrange
        task_id = uuid4()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        repo = TaskRepository(mock_session)

        # Act
        await repo.update_task_state(task_id, State.COMPLETED)

        # Assert
        mock_session.execute.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.parametrize(
        "new_state",
        [State.PROCESSING, State.COMPLETED, State.ERROR, State.WAITING],
    )
    async def test_update_task_state_various_states(
        self, mock_session, new_state
    ):
        """Обновляет состояние на различные значения."""
        # Arrange
        task_id = uuid4()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        repo = TaskRepository(mock_session)

        # Act
        await repo.update_task_state(task_id, new_state)

        # Assert
        mock_session.execute.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    async def test_increment_retry_and_reset_state(self, mock_session):
        """Увеличивает retry_count и возвращает задачу в waiting."""
        # Arrange
        task_id = uuid4()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        repo = TaskRepository(mock_session)

        # Act
        await repo.increment_retry_and_reset_state(task_id)

        # Assert
        mock_session.execute.assert_awaited_once()
        mock_session.commit.assert_awaited_once()


class TestTaskRepositoryHelpers:
    """Тесты вспомогательных методов TaskRepository."""

    def test_jsonb_to_sheets_with_data(self):
        """Конвертирует JSONB с данными в список base64-строк."""
        # Arrange
        base64_document = [
            {"base64": "page1_data"},
            {"base64": "page2_data"},
            {"base64": "page3_data"},
        ]

        # Act
        result = TaskRepository._jsonb_to_sheets(base64_document)

        # Assert
        assert result == ["page1_data", "page2_data", "page3_data"]

    def test_jsonb_to_sheets_empty_list(self):
        """Возвращает пустой список для пустого ввода."""
        # Arrange & Act
        result = TaskRepository._jsonb_to_sheets([])

        # Assert
        assert result == []

    def test_jsonb_to_sheets_none(self):
        """Возвращает пустой список для None."""
        # Arrange & Act
        result = TaskRepository._jsonb_to_sheets(None)

        # Assert
        assert result == []

    def test_jsonb_to_sheets_missing_base64_key(self):
        """Обрабатывает словари без ключа 'base64'."""
        # Arrange
        base64_document = [
            {"other_key": "value"},
            {"base64": "page2_data"},
        ]

        # Act
        result = TaskRepository._jsonb_to_sheets(base64_document)

        # Assert
        assert result == ["", "page2_data"]

    def test_to_domain(self):
        """Конвертирует ORM-модель в доменный объект Task."""
        # Arrange
        task_id = uuid4()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)
        task_model = _make_mock_task_model(
            id=task_id,
            document_id="doc-789",
            state="processing",
            retry_count=2,
            base64_document=[{"base64": "data1"}, {"base64": "data2"}],
            created_at=created_at,
            updated_at=updated_at,
        )

        # Act
        task = TaskRepository._to_domain(task_model)

        # Assert
        assert isinstance(task, Task)
        assert task.id == task_id
        assert task.document_id == "doc-789"
        assert task.state == State.PROCESSING
        assert task.retry_count == 2
        assert task.base64_document == ["data1", "data2"]
        assert task.created_at == created_at
        assert task.updated_at == updated_at
