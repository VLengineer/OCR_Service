"""
Модульные тесты для Worker.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.worker_service import Worker
from app.services.request_service import RequestService
from app.repositories.task_repository import TaskRepository
from app.schemas.schemas import Task, State, CallType


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_mock_session():
    """Создаёт мок async_session, поддерживающий async with.
    """
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    return mock_session


def _make_mock_repository(**overrides):
    """Создаёт мок TaskRepository с настраиваемыми返回值.
    """
    repo = AsyncMock(spec=TaskRepository)
    repo.count_tasks_by_state = AsyncMock(
        return_value=overrides.get("processing_count", 0)
    )
    # next_task возвращается один раз, затем None (чтобы worker не зацикливался)
    next_task = overrides.get("next_task", None)
    if next_task is not None:
        repo.get_next_waiting_task = AsyncMock(side_effect=[next_task] + [None] * 100)
    else:
        repo.get_next_waiting_task = AsyncMock(return_value=None)
    repo.update_task_state = AsyncMock()
    repo.increment_retry_and_reset_state = AsyncMock()
    return repo


async def _run_worker_one_iteration(worker: Worker, timeout: float = 1.0):
    """Запускает worker на короткое время и останавливает.
    """
    task = asyncio.create_task(worker.start())
    await asyncio.sleep(timeout)
    await worker.stop()
    await asyncio.wait_for(task, timeout=2.0)


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

class TestWorker:

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_successful_processing(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
        sample_task,
    ):
        """waiting → processing → completed при успешном OCR.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        repo = _make_mock_repository(next_task=sample_task)
        mock_task_repo_cls.return_value = repo

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert
        repo.update_task_state.assert_any_call(sample_task.id, State.PROCESSING)
        repo.update_task_state.assert_any_call(sample_task.id, State.COMPLETED)
        mock_request_service.ocr_request.assert_awaited_once()
        repo.increment_retry_and_reset_state.assert_not_awaited()

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_retry_on_error(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
        sample_task,
    ):
        """OCR падает, retry_count < max_retries → increment_retry_and_reset_state.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        # retry_count=0, значит 0 < 3 → retry
        sample_task.retry_count = 0
        repo = _make_mock_repository(next_task=sample_task)
        mock_task_repo_cls.return_value = repo

        mock_request_service.ocr_request.side_effect = Exception("OCR failed")

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert
        repo.update_task_state.assert_called_once_with(sample_task.id, State.PROCESSING)
        repo.increment_retry_and_reset_state.assert_awaited_once_with(sample_task.id)
        # НЕ должен переходить в ERROR
        calls = repo.update_task_state.call_args_list
        error_calls = [c for c in calls if c.args[1] == State.ERROR]
        assert len(error_calls) == 0

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_max_retries_exceeded(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
        sample_task,
    ):
        """retry_count >= max_retries → окончательный error.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        # retry_count=3, значит 3 >= 3 → error
        sample_task.retry_count = 3
        repo = _make_mock_repository(next_task=sample_task)
        mock_task_repo_cls.return_value = repo

        mock_request_service.ocr_request.side_effect = Exception("OCR permanently failed")

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert
        repo.update_task_state.assert_any_call(sample_task.id, State.PROCESSING)
        repo.update_task_state.assert_any_call(sample_task.id, State.ERROR)
        repo.increment_retry_and_reset_state.assert_not_awaited()

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_blocked_by_processing(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
    ):
        """Если есть processing задачи — воркер ждёт, не берёт waiting.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        repo = _make_mock_repository(processing_count=2)
        mock_task_repo_cls.return_value = repo

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert
        repo.count_tasks_by_state.assert_awaited_with(State.PROCESSING)
        repo.get_next_waiting_task.assert_not_awaited()
        mock_request_service.ocr_request.assert_not_awaited()
        repo.update_task_state.assert_not_awaited()

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_graceful_shutdown(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
    ):
        """stop() корректно останавливает worker.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        # Нет задач — worker будет спать между итерациями
        repo = _make_mock_repository(next_task=None)
        mock_task_repo_cls.return_value = repo

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.15)
        assert worker._is_running is True
        await worker.stop()
        await asyncio.wait_for(task, timeout=2.0)

        # Assert
        assert worker._is_running is False

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_no_tasks_in_queue(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
    ):
        """При пустой очереди worker не делает лишних вызовов.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        repo = _make_mock_repository(processing_count=0, next_task=None)
        mock_task_repo_cls.return_value = repo

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert
        repo.count_tasks_by_state.assert_awaited()
        repo.get_next_waiting_task.assert_awaited()
        mock_request_service.ocr_request.assert_not_awaited()
        repo.update_task_state.assert_not_awaited()
        repo.increment_retry_and_reset_state.assert_not_awaited()

    # ──────────────────────────────────────────────
    # Fill RAG Tests
    # ──────────────────────────────────────────────

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_fill_rag_successful_processing(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
        sample_fill_rag_task,
    ):
        """waiting → processing → completed при успешном fill_rag.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        repo = _make_mock_repository(next_task=sample_fill_rag_task)
        mock_task_repo_cls.return_value = repo

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert
        repo.update_task_state.assert_any_call(sample_fill_rag_task.id, State.PROCESSING)
        repo.update_task_state.assert_any_call(sample_fill_rag_task.id, State.COMPLETED)
        mock_request_service.fill_rag_request.assert_awaited_once()
        # OCR не должен вызываться
        mock_request_service.ocr_request.assert_not_awaited()
        repo.increment_retry_and_reset_state.assert_not_awaited()

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_fill_rag_retry_on_error(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
        sample_fill_rag_task,
    ):
        """fill_rag_request падает, retry_count < max_retries → retry.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        sample_fill_rag_task.retry_count = 0
        repo = _make_mock_repository(next_task=sample_fill_rag_task)
        mock_task_repo_cls.return_value = repo

        mock_request_service.fill_rag_request.side_effect = Exception("fill_rag failed")

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert
        repo.update_task_state.assert_called_once_with(
            sample_fill_rag_task.id, State.PROCESSING
        )
        repo.increment_retry_and_reset_state.assert_awaited_once_with(
            sample_fill_rag_task.id
        )
        # НЕ должен переходить в ERROR
        calls = repo.update_task_state.call_args_list
        error_calls = [c for c in calls if c.args[1] == State.ERROR]
        assert len(error_calls) == 0

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_fill_rag_max_retries_exceeded(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
        sample_fill_rag_task,
    ):
        """fill_rag retry_count >= max_retries → окончательный error.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        sample_fill_rag_task.retry_count = 3
        repo = _make_mock_repository(next_task=sample_fill_rag_task)
        mock_task_repo_cls.return_value = repo

        mock_request_service.fill_rag_request.side_effect = Exception(
            "fill_rag permanently failed"
        )

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert
        repo.update_task_state.assert_any_call(
            sample_fill_rag_task.id, State.PROCESSING
        )
        repo.update_task_state.assert_any_call(sample_fill_rag_task.id, State.ERROR)
        repo.increment_retry_and_reset_state.assert_not_awaited()

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_routes_ocr_to_ocr_request(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
        sample_task,
    ):
        """OCR задача вызывает ocr_request, а не fill_rag_request.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        # Убедимся что задача — OCR
        assert sample_task.call_type == CallType.OCR

        repo = _make_mock_repository(next_task=sample_task)
        mock_task_repo_cls.return_value = repo

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert
        mock_request_service.ocr_request.assert_awaited_once()
        mock_request_service.fill_rag_request.assert_not_awaited()

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_routes_fill_rag_to_fill_rag_request(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
        sample_fill_rag_task,
    ):
        """fill_rag задача вызывает fill_rag_request, а не ocr_request.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        # Убедимся что задача — FILL_RAG
        assert sample_fill_rag_task.call_type == CallType.FILL_RAG

        repo = _make_mock_repository(next_task=sample_fill_rag_task)
        mock_task_repo_cls.return_value = repo

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert
        mock_request_service.fill_rag_request.assert_awaited_once()
        mock_request_service.ocr_request.assert_not_awaited()
