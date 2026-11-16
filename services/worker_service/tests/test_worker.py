"""
Модульные тесты для Worker.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from uuid import uuid4

from app.services.worker_service import Worker
from app.services.request_service import RequestService
from app.repositories.task_repository import TaskRepository
from app.schemas.schemas import Task, State, CallType


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

class _MockSessionContextManager:
    """Асинхронный контекстный менеджер, возвращающий заданную сессию."""

    def __init__(self, session):
        self._session = session

    @property
    def session(self):
        """Внутренняя замоканная сессия (для проверок rollback/close)."""
        return self._session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        await self._session.close()
        return False


def _make_mock_session():
    """Создаёт мок async_session, поддерживающий async with.
    """
    mock_session = AsyncMock()
    return _MockSessionContextManager(mock_session)


def _make_mock_repository(**overrides):
    """Создаёт мок TaskRepository с настраиваемыми возвращаемыми значениями.
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
    # has_active_tasks — по умолчанию False (нет активных задач, очередь открыта)
    repo.has_active_tasks = AsyncMock(
        return_value=overrides.get("has_active_tasks", False)
    )
    # get_active_task_counts — возвращает counts для логирования
    repo.get_active_task_counts = AsyncMock(
        return_value=overrides.get("active_task_counts", {"processing": 0, "error": 0})
    )
    # get_next_retryable_error_task — по умолчанию None (нет retryable error задач)
    repo.get_next_retryable_error_task = AsyncMock(
        return_value=overrides.get("next_retryable_error_task", None)
    )
    # move_error_to_waiting — по умолчанию успешный
    repo.move_error_to_waiting = AsyncMock(
        return_value=overrides.get("move_error_to_waiting_result", True)
    )
    # schedule_secondary_retry — по умолчанию успешный
    repo.schedule_secondary_retry = AsyncMock()
    # mark_task_permanently_failed — по умолчанию успешный
    repo.mark_task_permanently_failed = AsyncMock()
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
        """waiting → processing при успешной отправке OCR.
        Задача остаётся в PROCESSING (ждёт callback от n8n).
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_max_secondary_retries = 3
        mock_settings.worker_secondary_retry_interval_sec = 300
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
        mock_request_service.ocr_request.assert_awaited_once()
        repo.increment_retry_and_reset_state.assert_not_awaited()
        # Задача НЕ должна переходить в COMPLETED — она ждёт callback
        calls = repo.update_task_state.call_args_list
        completed_calls = [c for c in calls if c.args[1] == State.COMPLETED]
        assert len(completed_calls) == 0

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
        mock_settings.worker_max_secondary_retries = 3
        mock_settings.worker_secondary_retry_interval_sec = 300
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
        """retry_count >= max_total_retries → окончательный провал (mark_task_permanently_failed).
        max_total_retries = worker_max_retries * (1 + worker_max_secondary_retries) = 3 * 4 = 12.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_max_secondary_retries = 3
        mock_settings.worker_secondary_retry_interval_sec = 300
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        # retry_count=12, значит 12 >= max_total_retries(12) → permanent failure
        sample_task.retry_count = 12
        repo = _make_mock_repository(next_task=sample_task)
        mock_task_repo_cls.return_value = repo

        mock_request_service.ocr_request.side_effect = Exception("OCR permanently failed")

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert
        repo.update_task_state.assert_any_call(sample_task.id, State.PROCESSING)
        repo.mark_task_permanently_failed.assert_awaited_once_with(sample_task.id)
        repo.increment_retry_and_reset_state.assert_not_awaited()
        repo.schedule_secondary_retry.assert_not_awaited()

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_not_blocked_by_processing(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
        sample_task,
    ):
        """Наличие PROCESSING задач НЕ блокирует очередь.
        Воркер берёт следующую waiting задачу независимо от processing_count.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_max_secondary_retries = 3
        mock_settings.worker_secondary_retry_interval_sec = 300
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        # Есть 2 зависшие PROCESSING задачи, но они не блокируют
        repo = _make_mock_repository(
            processing_count=2,
            stuck_tasks=[],  # не зависшие (по мнению reaper)
            next_task=sample_task,
        )
        mock_task_repo_cls.return_value = repo

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert — воркер взял waiting задачу, несмотря на processing_count
        repo.get_next_waiting_task.assert_awaited()
        mock_request_service.ocr_request.assert_awaited_once()
        repo.update_task_state.assert_any_call(sample_task.id, State.PROCESSING)

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
        mock_settings.worker_max_secondary_retries = 3
        mock_settings.worker_secondary_retry_interval_sec = 300
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
        mock_settings.worker_max_secondary_retries = 3
        mock_settings.worker_secondary_retry_interval_sec = 300
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        repo = _make_mock_repository(next_task=None)
        mock_task_repo_cls.return_value = repo

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        await _run_worker_one_iteration(worker)

        # Assert
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
        """waiting → processing при успешной отправке fill_rag.
        Задача остаётся в PROCESSING (ждёт callback от n8n).
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_max_secondary_retries = 3
        mock_settings.worker_secondary_retry_interval_sec = 300
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
        mock_request_service.fill_rag_request.assert_awaited_once()
        # OCR не должен вызываться
        mock_request_service.ocr_request.assert_not_awaited()
        repo.increment_retry_and_reset_state.assert_not_awaited()
        # Задача НЕ должна переходить в COMPLETED — она ждёт callback
        calls = repo.update_task_state.call_args_list
        completed_calls = [c for c in calls if c.args[1] == State.COMPLETED]
        assert len(completed_calls) == 0

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
        mock_settings.worker_max_secondary_retries = 3
        mock_settings.worker_secondary_retry_interval_sec = 300
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
        """fill_rag retry_count >= max_total_retries → окончательный провал.
        max_total_retries = worker_max_retries * (1 + worker_max_secondary_retries) = 3 * 4 = 12.
        """
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_max_secondary_retries = 3
        mock_settings.worker_secondary_retry_interval_sec = 300
        mock_settings.worker_poll_interval_sec = 5
        mock_session = _make_mock_session()
        mock_async_session.return_value = mock_session

        # retry_count=12, значит 12 >= max_total_retries(12) → permanent failure
        sample_fill_rag_task.retry_count = 12
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
        repo.mark_task_permanently_failed.assert_awaited_once_with(sample_fill_rag_task.id)
        repo.increment_retry_and_reset_state.assert_not_awaited()
        repo.schedule_secondary_retry.assert_not_awaited()

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
        mock_settings.worker_max_secondary_retries = 3
        mock_settings.worker_secondary_retry_interval_sec = 300
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
        mock_settings.worker_max_secondary_retries = 3
        mock_settings.worker_secondary_retry_interval_sec = 300
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

    @patch("app.services.worker_service.settings")
    @patch("app.services.worker_service.TaskRepository")
    @patch("app.services.worker_service.async_session")
    async def test_worker_rolls_back_polling_session_on_update_task_state_error(
        self,
        mock_async_session,
        mock_task_repo_cls,
        mock_settings,
        mock_request_service,
        sample_task,
    ):
        """Ошибка update_task_state в цикле → rollback polling_session, worker продолжает работу."""
        # Arrange
        mock_settings.worker_max_retries = 3
        mock_settings.worker_max_secondary_retries = 3
        mock_settings.worker_secondary_retry_interval_sec = 300
        mock_settings.worker_poll_interval_sec = 5

        polling_session_cm = _make_mock_session()
        polling_session = polling_session_cm.session
        mock_async_session.return_value = polling_session_cm

        repo = _make_mock_repository(next_task=sample_task)
        repo.update_task_state = AsyncMock(side_effect=Exception("DB error"))
        mock_task_repo_cls.return_value = repo

        worker = Worker(mock_request_service, poll_interval=0.05)

        # Act
        task = asyncio.create_task(worker.start())
        await asyncio.sleep(0.2)
        await worker.stop()
        await asyncio.wait_for(task, timeout=2.0)

        # Assert
        polling_session.rollback.assert_awaited_once()
        assert polling_session.close.await_count >= 1
        assert worker._is_running is False
