"""
Tests for TaskRepository: CRUD operations with mocked AsyncSession,
and conversion helpers _sheets_to_jsonb / _jsonb_to_sheets.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.task_repository import TaskRepository
from app.schemas.schemas import State, Task, CallType
from app.models.task_model import TaskModel


# ──────────────────────────────────────────────
# Helper: build a fake TaskModel-like object
# ──────────────────────────────────────────────

def _make_task_model(
    task_id=None,
    document_id="doc-1",
    document_type="test_type",
    state="waiting",
    base64_document=None,
    retry_count=0,
    created_at=None,
    updated_at=None,
    call_type="ocr",
    metadata_=None,
):
    """Create a mock that looks like a TaskModel instance."""
    m = MagicMock()
    m.id = task_id or uuid4()
    m.document_id = document_id
    m.document_type = document_type
    m.state = state
    m.retry_count = retry_count
    m.base64_document = base64_document if base64_document is not None else []
    m.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
    m.updated_at = updated_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
    m.call_type = call_type
    m.metadata_ = metadata_
    return m


# ──────────────────────────────────────────────
# Conversion helpers (pure functions, no mocking needed)
# ──────────────────────────────────────────────

class TestSheetsToJsonb:
    """Tests for _sheets_to_jsonb static method."""

    def test_empty_list(self):
        assert TaskRepository._sheets_to_jsonb([]) == []

    def test_single_sheet(self):
        result = TaskRepository._sheets_to_jsonb(["abc123"])
        assert result == [{"base64": "abc123"}]

    def test_multiple_sheets(self):
        sheets = ["page1", "page2", "page3"]
        result = TaskRepository._sheets_to_jsonb(sheets)
        assert result == [
            {"base64": "page1"},
            {"base64": "page2"},
            {"base64": "page3"},
        ]

    def test_preserves_order(self):
        sheets = ["z", "a", "m"]
        result = TaskRepository._sheets_to_jsonb(sheets)
        assert [item["base64"] for item in result] == ["z", "a", "m"]

    def test_none_returns_none(self):
        """None input (for tasks without base64, e.g. fill_rag) returns None."""
        assert TaskRepository._sheets_to_jsonb(None) is None


class TestJsonbToSheets:
    """Tests for _jsonb_to_sheets static method."""

    def test_none_returns_empty_list(self):
        assert TaskRepository._jsonb_to_sheets(None) == []

    def test_empty_list_returns_empty_list(self):
        assert TaskRepository._jsonb_to_sheets([]) == []

    def test_single_item(self):
        result = TaskRepository._jsonb_to_sheets([{"base64": "abc"}])
        assert result == ["abc"]

    def test_multiple_items(self):
        data = [{"base64": "p1"}, {"base64": "p2"}, {"base64": "p3"}]
        result = TaskRepository._jsonb_to_sheets(data)
        assert result == ["p1", "p2", "p3"]

    def test_missing_base64_key_returns_empty_string(self):
        data = [{"other_key": "value"}]
        result = TaskRepository._jsonb_to_sheets(data)
        assert result == [""]

    def test_mixed_keys(self):
        data = [{"base64": "ok"}, {"no_key": "x"}, {"base64": "fine"}]
        result = TaskRepository._jsonb_to_sheets(data)
        assert result == ["ok", "", "fine"]


# ──────────────────────────────────────────────
# _to_domain conversion
# ──────────────────────────────────────────────

class TestToDomain:
    """Tests for _to_domain static method."""

    def test_converts_task_model_to_task(self):
        task_id = uuid4()
        now = datetime(2025, 6, 1, tzinfo=timezone.utc)
        model = _make_task_model(
            task_id=task_id,
            document_id="doc-42",
            state="processing",
            base64_document=[{"base64": "data1"}, {"base64": "data2"}],
            created_at=now,
            updated_at=now,
        )

        task = TaskRepository._to_domain(model)

        assert isinstance(task, Task)
        assert task.id == task_id
        assert task.document_id == "doc-42"
        assert task.state == State.PROCESSING
        assert task.base64_document == ["data1", "data2"]
        assert task.created_at == now
        assert task.updated_at == now

    def test_converts_empty_base64_document(self):
        model = _make_task_model(base64_document=[])
        task = TaskRepository._to_domain(model)
        assert task.base64_document == []

    def test_converts_null_base64_document(self):
        model = _make_task_model(base64_document=None)
        task = TaskRepository._to_domain(model)
        assert task.base64_document == []

    def test_converts_call_type_ocr(self):
        """call_type='ocr' maps to CallType.OCR."""
        model = _make_task_model(call_type="ocr")
        task = TaskRepository._to_domain(model)
        assert task.call_type == CallType.OCR

    def test_converts_call_type_fill_rag(self):
        """call_type='fill_rag' maps to CallType.FILL_RAG."""
        model = _make_task_model(call_type="fill_rag")
        task = TaskRepository._to_domain(model)
        assert task.call_type == CallType.FILL_RAG

    def test_converts_call_type_none_defaults_to_ocr(self):
        """None call_type defaults to CallType.OCR."""
        model = _make_task_model(call_type=None)
        task = TaskRepository._to_domain(model)
        assert task.call_type == CallType.OCR

    def test_converts_metadata_dict(self):
        """metadata_ dict is passed through to Task.metadata."""
        meta = {"url": "https://example.com/doc", "key": "value"}
        model = _make_task_model(metadata_=meta)
        task = TaskRepository._to_domain(model)
        assert task.metadata == meta

    def test_converts_metadata_none(self):
        """None metadata_ results in None metadata."""
        model = _make_task_model(metadata_=None)
        task = TaskRepository._to_domain(model)
        assert task.metadata is None

    def test_converts_fill_rag_with_metadata_and_no_base64(self):
        """Full fill_rag scenario: call_type=fill_rag, metadata set, no base64."""
        task_id = uuid4()
        now = datetime(2025, 7, 1, tzinfo=timezone.utc)
        meta = {"url": "https://elma.example.com/download/123", "__id": "123"}
        model = _make_task_model(
            task_id=task_id,
            document_id="doc-rag",
            state="waiting",
            base64_document=None,
            call_type="fill_rag",
            metadata_=meta,
            created_at=now,
            updated_at=now,
        )

        task = TaskRepository._to_domain(model)

        assert task.call_type == CallType.FILL_RAG
        assert task.metadata == meta
        assert task.base64_document == []
        assert task.document_id == "doc-rag"


# ──────────────────────────────────────────────
# CRUD: add_task
# ──────────────────────────────────────────────

class TestAddTask:
    """Tests for TaskRepository.add_task."""

    @pytest.mark.asyncio
    async def test_add_task_creates_and_returns_task(self, mock_session):
        repo = TaskRepository(mock_session)
        task_id = uuid4()
        now = datetime(2025, 3, 1, tzinfo=timezone.utc)

        def capture_add(obj):
            obj.id = task_id
            obj.created_at = now
            obj.updated_at = now
            obj.retry_count = 0

        mock_session.add.side_effect = capture_add

        result = await repo.add_task(
            document_id="doc-abc",
            base64_document=["page1"],
            state=State.WAITING,
        )

        assert isinstance(result, Task)
        assert result.id == task_id
        assert result.document_id == "doc-abc"
        assert result.state == State.WAITING
        assert result.base64_document == ["page1"]

        mock_session.add.assert_called_once()
        mock_session.flush.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_add_task_default_state_is_waiting(self, mock_session):
        repo = TaskRepository(mock_session)
        task_id = uuid4()
        now = datetime(2025, 3, 1, tzinfo=timezone.utc)

        def capture_add(obj):
            obj.id = task_id
            obj.created_at = now
            obj.updated_at = now
            obj.retry_count = 0

        mock_session.add.side_effect = capture_add

        result = await repo.add_task(
            document_id="doc-default",
            base64_document=[],
        )

        assert result.state == State.WAITING

    @pytest.mark.asyncio
    async def test_add_task_converts_base64_to_jsonb(self, mock_session):
        repo = TaskRepository(mock_session)
        task_id = uuid4()
        now = datetime(2025, 3, 1, tzinfo=timezone.utc)

        captured_model = None

        def capture_add(obj):
            nonlocal captured_model
            captured_model = obj
            obj.id = task_id
            obj.created_at = now
            obj.updated_at = now
            obj.retry_count = 0

        mock_session.add.side_effect = capture_add

        await repo.add_task(
            document_id="doc-jsonb",
            base64_document=["b64_1", "b64_2"],
        )

        # Verify the TaskModel was created with JSONB format
        assert captured_model.base64_document == [
            {"base64": "b64_1"},
            {"base64": "b64_2"},
        ]

    @pytest.mark.asyncio
    async def test_add_task_fill_rag_with_metadata_and_none_base64(self, mock_session):
        """add_task with call_type=FILL_RAG, metadata, and base64_document=None."""
        repo = TaskRepository(mock_session)
        task_id = uuid4()
        now = datetime(2025, 7, 15, tzinfo=timezone.utc)
        meta = {"url": "https://elma.example.com/dl/1", "__id": "doc-rag-1"}

        captured_model = None

        def capture_add(obj):
            nonlocal captured_model
            captured_model = obj
            obj.id = task_id
            obj.created_at = now
            obj.updated_at = now
            obj.retry_count = 0

        mock_session.add.side_effect = capture_add

        result = await repo.add_task(
            document_id="doc-rag-1",
            base64_document=None,
            document_type="contract",
            state=State.WAITING,
            call_type=CallType.FILL_RAG,
            metadata=meta,
        )

        assert isinstance(result, Task)
        assert result.call_type == CallType.FILL_RAG
        assert result.metadata == meta
        assert result.base64_document == []

        # Verify the TaskModel was created correctly
        assert captured_model.call_type == "fill_rag"
        assert captured_model.metadata_ == meta
        assert captured_model.base64_document is None  # _sheets_to_jsonb(None) → None

    @pytest.mark.asyncio
    async def test_add_task_default_call_type_is_ocr(self, mock_session):
        """Default call_type is OCR."""
        repo = TaskRepository(mock_session)
        task_id = uuid4()
        now = datetime(2025, 3, 1, tzinfo=timezone.utc)

        captured_model = None

        def capture_add(obj):
            nonlocal captured_model
            captured_model = obj
            obj.id = task_id
            obj.created_at = now
            obj.updated_at = now
            obj.retry_count = 0

        mock_session.add.side_effect = capture_add

        result = await repo.add_task(
            document_id="doc-ocr",
            base64_document=["page1"],
        )

        assert result.call_type == CallType.OCR
        assert captured_model.call_type == "ocr"

    @pytest.mark.asyncio
    async def test_add_task_none_base64_stores_none_in_model(self, mock_session):
        """base64_document=None stores None in the model (not empty list)."""
        repo = TaskRepository(mock_session)
        task_id = uuid4()
        now = datetime(2025, 3, 1, tzinfo=timezone.utc)

        captured_model = None

        def capture_add(obj):
            nonlocal captured_model
            captured_model = obj
            obj.id = task_id
            obj.created_at = now
            obj.updated_at = now
            obj.retry_count = 0

        mock_session.add.side_effect = capture_add

        await repo.add_task(
            document_id="doc-no-b64",
            base64_document=None,
        )

        assert captured_model.base64_document is None


# ──────────────────────────────────────────────
# CRUD: get_task_by_id
# ──────────────────────────────────────────────

class TestGetTaskById:
    """Tests for TaskRepository.get_task_by_id."""

    @pytest.mark.asyncio
    async def test_returns_task_when_found(self, mock_session):
        repo = TaskRepository(mock_session)
        task_id = uuid4()
        model = _make_task_model(
            task_id=task_id,
            document_id="doc-found",
            state="waiting",
            base64_document=[{"base64": "data"}],
        )

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repo.get_task_by_id(task_id)

        assert result is not None
        assert result.id == task_id
        assert result.document_id == "doc-found"
        assert result.base64_document == ["data"]

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_session):
        repo = TaskRepository(mock_session)
        task_id = uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_task_by_id(task_id)

        assert result is None


# ──────────────────────────────────────────────
# CRUD: get_tasks_by_state
# ──────────────────────────────────────────────

class TestGetTasksByState:
    """Tests for TaskRepository.get_tasks_by_state."""

    @pytest.mark.asyncio
    async def test_returns_list_of_tasks(self, mock_session):
        repo = TaskRepository(mock_session)
        models = [
            _make_task_model(task_id=uuid4(), document_id=f"doc-{i}")
            for i in range(3)
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = models
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repo.get_tasks_by_state(State.WAITING)

        assert len(result) == 3
        assert all(isinstance(t, Task) for t in result)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_tasks(self, mock_session):
        repo = TaskRepository(mock_session)

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await repo.get_tasks_by_state(State.PROCESSING)

        assert result == []


# ──────────────────────────────────────────────
# CRUD: get_next_waiting_task
# ──────────────────────────────────────────────

class TestGetNextWaitingTask:
    """Tests for TaskRepository.get_next_waiting_task."""

    @pytest.mark.asyncio
    async def test_returns_next_task(self, mock_session):
        repo = TaskRepository(mock_session)
        model = _make_task_model(document_id="doc-next")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repo.get_next_waiting_task()

        assert result is not None
        assert result.document_id == "doc-next"

    @pytest.mark.asyncio
    async def test_returns_none_when_queue_empty(self, mock_session):
        repo = TaskRepository(mock_session)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repo.get_next_waiting_task()

        assert result is None


# ──────────────────────────────────────────────
# CRUD: count_tasks_by_state
# ──────────────────────────────────────────────

class TestCountTasksByState:
    """Tests for TaskRepository.count_tasks_by_state."""

    @pytest.mark.asyncio
    async def test_returns_count(self, mock_session):
        repo = TaskRepository(mock_session)

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 42
        mock_session.execute.return_value = mock_result

        count = await repo.count_tasks_by_state(State.WAITING)

        assert count == 42

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_tasks(self, mock_session):
        repo = TaskRepository(mock_session)

        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_session.execute.return_value = mock_result

        count = await repo.count_tasks_by_state(State.COMPLETED)

        assert count == 0


# ──────────────────────────────────────────────
# CRUD: update_task_state
# ──────────────────────────────────────────────

class TestUpdateTaskState:
    """Tests for TaskRepository.update_task_state."""

    @pytest.mark.asyncio
    async def test_updates_state_and_returns_task(self, mock_session):
        repo = TaskRepository(mock_session)
        task_id = uuid4()
        model = _make_task_model(task_id=task_id, state="processing")

        # First execute: the update statement
        # Second execute: the select in get_task_by_id
        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = model
        mock_session.execute = AsyncMock(side_effect=[MagicMock(), mock_select_result])

        result = await repo.update_task_state(task_id, State.PROCESSING)

        assert result is not None
        assert result.state == State.PROCESSING
        assert mock_session.execute.await_count == 2
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_none_when_task_not_found(self, mock_session):
        repo = TaskRepository(mock_session)
        task_id = uuid4()

        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(side_effect=[MagicMock(), mock_select_result])

        result = await repo.update_task_state(task_id, State.ERROR)

        assert result is None


# ──────────────────────────────────────────────
# CRUD: update_task_base64
# ──────────────────────────────────────────────

class TestUpdateTaskBase64:
    """Tests for TaskRepository.update_task_base64."""

    @pytest.mark.asyncio
    async def test_updates_base64_and_returns_task(self, mock_session):
        repo = TaskRepository(mock_session)
        task_id = uuid4()
        model = _make_task_model(
            task_id=task_id,
            base64_document=[{"base64": "new1"}, {"base64": "new2"}],
        )

        mock_select_result = MagicMock()
        mock_select_result.scalar_one_or_none.return_value = model
        mock_session.execute = AsyncMock(side_effect=[MagicMock(), mock_select_result])

        result = await repo.update_task_base64(task_id, ["new1", "new2"])

        assert result is not None
        assert result.base64_document == ["new1", "new2"]
        mock_session.flush.assert_awaited_once()


# ──────────────────────────────────────────────
# CRUD: remove_task
# ──────────────────────────────────────────────

class TestRemoveTask:
    """Tests for TaskRepository.remove_task."""

    @pytest.mark.asyncio
    async def test_removes_existing_task_returns_true(self, mock_session):
        repo = TaskRepository(mock_session)
        task_id = uuid4()

        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        deleted = await repo.remove_task(task_id)

        assert deleted is True
        mock_session.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_false_when_task_not_found(self, mock_session):
        repo = TaskRepository(mock_session)
        task_id = uuid4()

        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        deleted = await repo.remove_task(task_id)

        assert deleted is False
