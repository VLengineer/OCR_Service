"""
Основной воркер для обработки задач.
Получает задачи из БД, маршрутизирует по call_type,
отправляет на обработку через n8n webhook,
обновляет состояние задач.
"""

import asyncio
import logging

from app.repositories.database import async_session
from app.repositories.task_repository import TaskRepository
from app.services.request_service import RequestService
from app.schemas.schemas import State, CallType, OCRRequest, FillRagRequest
from app.core.config import settings

logger = logging.getLogger(__name__)


class Worker:
    """
    Воркер для последовательной обработки задач.

    Логика:
    1. Проверяет наличие активных задач (processing или error без
       наступившего next_retry_at). Если есть — очередь заблокирована.
    2. Берёт следующую waiting задачу (FIFO) или retryable error задачу.
    3. Обновляет состояние на processing.
    4. Маршрутизирует по call_type:
       - OCR: отправляет на OCR через n8n webhook
       - FILL_RAG: отправляет на fill_rag через n8n webhook
    5. При успехе отправки — задача остаётся в PROCESSING и ждёт
       callback от n8n (callback переводит задачу в COMPLETED или ERROR).
    6. При ошибке отправки:
       - Первичный retry: если retry_count < worker_max_retries — возвращает
         в waiting, сбрасывает next_retry_at.
       - Вторичный retry: если retry_count < worker_max_retries +
         worker_max_secondary_retries * worker_max_retries — переводит в error
         с next_retry_at = NOW() + worker_secondary_retry_interval_sec.
       - Окончательный провал: иначе — error с next_retry_at=NULL.
    """

    def __init__(
        self,
        request_service: RequestService,
        poll_interval: int = None,
    ) -> None:
        """
        Инициализация воркера.

        Args:
            request_service: Сервис для HTTP-запросов к n8n
            poll_interval: Интервал опроса БД в секундах
        """
        self._request_service = request_service
        self._poll_interval = poll_interval or settings.worker_poll_interval_sec
        self._is_running = False

    @property
    def _max_total_retries(self) -> int:
        """Общее максимальное количество попыток обработки задачи."""
        return settings.worker_max_retries * (
            1 + settings.worker_max_secondary_retries
        )

    async def start(self) -> None:
        """
        Бесконечный цикл polling задач из БД.
        Запускается как asyncio task.
        """
        self._is_running = True
        logger.info(
            f"Worker started: poll_interval={self._poll_interval}s, "
            f"max_retries={settings.worker_max_retries}, "
            f"max_secondary_retries={settings.worker_max_secondary_retries}, "
            f"secondary_retry_interval={settings.worker_secondary_retry_interval_sec}s, "
            f"max_total_retries={self._max_total_retries}, "
            f"n8n_base_url={settings.n8n_base_url}, "
            f"n8n_timeout={settings.n8n_request_timeout_sec}s"
        )

        while self._is_running:
            try:
                async with async_session() as session:
                    try:
                        repository = TaskRepository(session)

                        # 2.1. Проверяем, не заблокирована ли очередь активными задачами
                        if await repository.has_active_tasks(self._max_total_retries):
                            counts = await repository.get_active_task_counts()
                            logger.warning(
                                f"Worker paused: {counts['processing']} processing, "
                                f"{counts['error']} error tasks exist"
                            )
                            await asyncio.sleep(self._poll_interval)
                            continue

                        # 2.2. Получаем следующую waiting задачу
                        task = await repository.get_next_waiting_task()

                        # 2.3. Если нет waiting — ищем retryable error задачу
                        if not task:
                            task = await repository.get_next_retryable_error_task()
                            if task:
                                logger.info(
                                    f"Retrying error task: id={task.id}, "
                                    f"call_type={task.call_type}, "
                                    f"retry_count={task.retry_count}, "
                                    f"next_retry_at={task.next_retry_at.isoformat()}"
                                )
                                try:
                                    await repository.move_error_to_waiting(task.id)
                                except Exception as e:
                                    # Состояние гонки: другой воркер уже взял задачу
                                    await session.rollback()
                                    logger.warning(
                                        f"Failed to move error task to waiting "
                                        f"(race condition): id={task.id}, error={e}"
                                    )
                                    task = None

                        if not task:
                            logger.debug("No waiting or retryable tasks in queue")
                            await asyncio.sleep(self._poll_interval)
                            continue

                        logger.info(
                            f"Processing task: id={task.id}, document_id={task.document_id}, "
                            f"call_type={task.call_type}, retry_count={task.retry_count}"
                        )

                        # 2.4. Обновляем состояние на processing
                        await repository.update_task_state(task.id, State.PROCESSING)
                        logger.debug(f"Task state updated to PROCESSING: id={task.id}")

                        # 2.5. Маршрутизация по call_type
                        try:
                            await self._dispatch_task(task)

                            # 2.6. Успех -> задача остается в processing и ждет callback от n8n
                            logger.info(
                                f"Task sent to n8n successfully, waiting for callback: "
                                f"id={task.id}, call_type={task.call_type}"
                            )

                        except Exception as e:
                            # 2.7. Ошибка -> retry или error
                            logger.exception(
                                f"Task processing error: id={task.id}, call_type={task.call_type}, "
                                f"retry_count={task.retry_count}, error_type={type(e).__name__}, error={e}"
                            )
                            await self._handle_task_failure(repository, task)

                    except Exception:
                        # Любая непредвиденная ошибка внутри сессии polling — откатываем транзакцию
                        # и передаём управление внешнему обработчику для засыпания.
                        await session.rollback()
                        raise

            except Exception as e:
                logger.exception(f"Worker loop error: {e}")
                await asyncio.sleep(self._poll_interval)

        logger.info("Worker stopped")

    async def _dispatch_task(self, task) -> None:
        """Маршрутизирует задачу по call_type и отправляет в n8n."""
        if task.call_type == CallType.OCR:
            ocr_request = OCRRequest(
                task_id=task.id,
                document_id=task.document_id,
                base64_document=task.base64_document,
                document_type=task.document_type,
            )
            await self._request_service.ocr_request(ocr_request)

        elif task.call_type == CallType.FILL_RAG:
            if not task.metadata:
                raise ValueError(
                    f"Task {task.id} has call_type=FILL_RAG but metadata is empty"
                )
            fill_rag_request = FillRagRequest(
                task_id=task.id,
                **task.metadata,
            )
            await self._request_service.fill_rag_request(fill_rag_request)

        else:
            raise ValueError(f"Unknown call_type: {task.call_type}")

    async def _handle_task_failure(
        self,
        repository: TaskRepository,
        task,
    ) -> None:
        """
        Обрабатывает ошибку отправки задачи в n8n.

        - Первичный retry: retry_count < worker_max_retries -> waiting.
        - Вторичный retry: worker_max_retries <= retry_count < max_total_retries -> error + next_retry_at.
        - Окончательный провал: retry_count >= max_total_retries -> error + next_retry_at=NULL.
        """
        if task.retry_count < settings.worker_max_retries:
            await repository.increment_retry_and_reset_state(task.id)
            logger.warning(
                f"Task {task.id} (call_type={task.call_type}) failed, primary retry "
                f"(attempt {task.retry_count + 1}/{settings.worker_max_retries})"
            )
        elif task.retry_count < self._max_total_retries:
            await repository.schedule_secondary_retry(
                task.id,
                settings.worker_secondary_retry_interval_sec,
            )
            secondary_attempt = (
                task.retry_count - settings.worker_max_retries
            ) // settings.worker_max_retries + 1
            logger.warning(
                f"Task {task.id} (call_type={task.call_type}) failed, secondary retry "
                f"(cycle {secondary_attempt}/{settings.worker_max_secondary_retries}) scheduled "
                f"in {settings.worker_secondary_retry_interval_sec}s"
            )
        else:
            await repository.mark_task_permanently_failed(task.id)
            logger.error(
                f"Task {task.id} (call_type={task.call_type}) failed, max total retries "
                f"({self._max_total_retries}) exceeded, permanently failed"
            )

    async def stop(self) -> None:
        """Graceful shutdown воркера."""
        logger.info("Stopping worker...")
        self._is_running = False
