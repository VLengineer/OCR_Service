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
    1. Проверяет наличие задач в состоянии processing
    2. Если таких нет — берёт следующую waiting задачу (FIFO)
    3. Обновляет состояние на processing
    4. Маршрутизирует по call_type:
       - OCR: отправляет на OCR через n8n webhook
       - FILL_RAG: отправляет на fill_rag через n8n webhook
    5. При успехе обновляет состояние на completed
    6. При ошибке: если retry_count < max_retries — возвращает в waiting с инкрементом retry_count,
       иначе — устанавливает состояние error
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
        logger.info(f"Worker started with poll interval {self._poll_interval}s")

        while self._is_running:
            try:
                # Создаём новую сессию для каждой итерации
                async with async_session() as session:
                    repository = TaskRepository(session)

                    # 1. Проверяем есть ли processing задачи
                    processing_count = await repository.count_tasks_by_state(State.PROCESSING)

                    if processing_count > 0:
                        logger.debug(
                            f"Skipping: processing={processing_count}"
                        )
                        await asyncio.sleep(self._poll_interval)
                        continue

                    # 2. Получаем следующую waiting задачу
                    task = await repository.get_next_waiting_task()
                    if not task:
                        logger.debug("No waiting tasks in queue")
                        await asyncio.sleep(self._poll_interval)
                        continue

                    logger.info(
                        f"Processing task: id={task.id}, document_id={task.document_id}"
                    )

                    # 3. Обновляем состояние на processing
                    await repository.update_task_state(task.id, State.PROCESSING)

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

                        # 5. Успех -> completed
                        await repository.update_task_state(task.id, State.COMPLETED)
                        logger.info(f"Task completed: id={task.id}, call_type={task.call_type}")

                    except Exception as e:
                        # 6. Ошибка -> retry или error
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
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(self._poll_interval)

        logger.info("Worker stopped")

    async def stop(self) -> None:
        """Graceful shutdown воркера."""
        logger.info("Stopping worker...")
        self._is_running = False
