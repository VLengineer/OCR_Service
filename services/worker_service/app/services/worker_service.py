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
    1. Берёт следующую waiting задачу (FIFO) — наличие PROCESSING задач
       НЕ блокирует очередь, так как callback от n8n может быть долгим
       или потерянным.
    2. Обновляет состояние на processing.
    3. Маршрутизирует по call_type:
       - OCR: отправляет на OCR через n8n webhook
       - FILL_RAG: отправляет на fill_rag через n8n webhook
    4. При успехе отправки — задача остаётся в PROCESSING и ждёт
       callback от n8n (callback переводит задачу в COMPLETED или ERROR).
    5. При ошибке отправки: если retry_count < max_retries — возвращает
       в waiting с инкрементом retry_count, иначе — устанавливает error.
    6. Reaper: периодически проверяет зависшие PROCESSING задачи
       (обновлённые дольше worker_processing_timeout_sec секунд назад)
       и возвращает их в waiting для повторной обработки.
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

    async def start(self) -> None:
        """
        Бесконечный цикл polling задач из БД.
        Запускается как asyncio task.
        """
        self._is_running = True
        logger.info(
            f"Worker started: poll_interval={self._poll_interval}s, "
            f"max_retries={settings.worker_max_retries}, "
            f"n8n_base_url={settings.n8n_base_url}, "
            f"n8n_timeout={settings.n8n_request_timeout_sec}s, "
            f"processing_timeout={settings.worker_processing_timeout_sec}s"
        )

        while self._is_running:
            try:
                # Создаём новую сессию для каждой итерации
                async with async_session() as session:
                    repository = TaskRepository(session)

                    # 1. Reaper: возвращаем зависшие PROCESSING задачи в waiting
                    await self._reap_stuck_processing(repository)

                    # 2. Получаем следующую waiting задачу
                    task = await repository.get_next_waiting_task()
                    if not task:
                        logger.debug("No waiting tasks in queue")
                        await asyncio.sleep(self._poll_interval)
                        continue

                    logger.info(
                        f"Processing task: id={task.id}, document_id={task.document_id}, "
                        f"call_type={task.call_type}, retry_count={task.retry_count}"
                    )

                    # 3. Обновляем состояние на processing
                    await repository.update_task_state(task.id, State.PROCESSING)
                    logger.debug(f"Task state updated to PROCESSING: id={task.id}")

                    # 4. Маршрутизация по call_type
                    try:
                        if task.call_type == CallType.OCR:
                            # OCR обработка
                            ocr_request = OCRRequest(
                                task_id=task.id,
                                document_id=task.document_id,
                                base64_document=task.base64_document,
                                document_type=task.document_type,
                            )
                            await self._request_service.ocr_request(ocr_request)

                        elif task.call_type == CallType.FILL_RAG:
                            # Fill RAG обработка
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
                            # Неизвестный тип задачи
                            raise ValueError(f"Unknown call_type: {task.call_type}")

                        # 5. Успех -> задача остается в processing и ждет callback от n8n
                        logger.info(
                            f"Task sent to n8n successfully, waiting for callback: "
                            f"id={task.id}, call_type={task.call_type}"
                        )

                    except Exception as e:
                        # 6. Ошибка -> retry или error
                        logger.exception(
                            f"Task processing error: id={task.id}, call_type={task.call_type}, "
                            f"retry_count={task.retry_count}, error_type={type(e).__name__}, error={e}"
                        )
                        
                        if task.retry_count < settings.worker_max_retries:
                            # Ещё есть попытки — возвращаем в waiting с инкрементом retry_count
                            await repository.increment_retry_and_reset_state(task.id)
                            logger.warning(
                                f"Task {task.id} (call_type={task.call_type}) failed, retrying "
                                f"(attempt {task.retry_count + 1}/{settings.worker_max_retries}): {e}"
                            )
                        else:
                            # Лимит попыток исчерпан — окончательная ошибка
                            await repository.update_task_state(task.id, State.ERROR)
                            logger.error(
                                f"Task {task.id} (call_type={task.call_type}) failed, max retries "
                                f"({settings.worker_max_retries}) exceeded: {e}"
                            )

            except Exception as e:
                logger.exception(f"Worker loop error: {e}")
                await asyncio.sleep(self._poll_interval)

        logger.info("Worker stopped")

    async def _reap_stuck_processing(
        self,
        repository: TaskRepository,
    ) -> None:
        """
        Находит зависшие PROCESSING задачи (обновлённые дольше
        worker_processing_timeout_sec секунд назад) и возвращает их
        в waiting для повторной обработки.

        Это решает проблему блокировки очереди, когда callback от n8n
        потерян или задерживается неопределённо долго.
        """
        try:
            stuck_tasks = await repository.get_stuck_processing_tasks(
                timeout_sec=settings.worker_processing_timeout_sec,
            )
            for task in stuck_tasks:
                if task.retry_count < settings.worker_max_retries:
                    await repository.increment_retry_and_reset_state(task.id)
                    logger.warning(
                        f"Reaped stuck PROCESSING task: id={task.id}, "
                        f"call_type={task.call_type}, "
                        f"retry_count={task.retry_count + 1}/{settings.worker_max_retries}, "
                        f"reset to waiting"
                    )
                else:
                    await repository.update_task_state(task.id, State.ERROR)
                    logger.error(
                        f"Reaped stuck PROCESSING task (max retries exceeded): "
                        f"id={task.id}, call_type={task.call_type}, "
                        f"retry_count={task.retry_count}/{settings.worker_max_retries}, "
                        f"set to error"
                    )
        except Exception as e:
            logger.exception(f"Error reaping stuck PROCESSING tasks: {e}")

    async def stop(self) -> None:
        """Graceful shutdown воркера."""
        logger.info("Stopping worker...")
        self._is_running = False
