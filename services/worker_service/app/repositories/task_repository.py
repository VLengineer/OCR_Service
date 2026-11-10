"""
Репозиторий задач для worker_service.
Работает с собственной сессией (не через FastAPI dependency).
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.repositories.task_model import TaskModel
from app.schemas.schemas import State, Task, CallType
from uuid import UUID
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class TaskRepository:
    """
    Репозиторий для работы с задачами в БД.
    Реализует операции чтения и обновления состояния для воркера.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # ──────────────────────────────────────────────
    # Вспомогательные методы конвертации
    # ──────────────────────────────────────────────

    @staticmethod
    def _jsonb_to_sheets(base64_document: list[dict] | None) -> List[str]:
        """Конвертирует JSONB из БД обратно в список base64-строк."""
        if not base64_document:
            return []
        return [item.get("base64", "") for item in base64_document]

    @staticmethod
    def _to_domain(task_model: TaskModel) -> Task:
        """Конвертирует ORM-модель в доменный объект."""
        return Task(
            id=task_model.id,
            document_id=task_model.document_id,
            document_type=task_model.document_type,
            state=State(task_model.state),
            retry_count=task_model.retry_count,
            base64_document=TaskRepository._jsonb_to_sheets(task_model.base64_document),
            call_type=CallType(task_model.call_type),
            metadata=task_model.metadata_,
            created_at=task_model.created_at,
            updated_at=task_model.updated_at,
        )

    # ──────────────────────────────────────────────
    # Read
    # ──────────────────────────────────────────────

    async def get_next_waiting_task(
        self,
        call_type: CallType | None = None,
    ) -> Optional[Task]:
        """
        Получает следующую задачу в состоянии waiting (FIFO).

        Args:
            call_type: Опциональная фильтрация по типу задачи.
                       Если None — возвращает любую waiting задачу.

        Returns:
            Task | None: Следующая задача или None если очередь пуста
        """
        query = (
            select(TaskModel)
            .where(TaskModel.state == State.WAITING.value)
        )
        if call_type is not None:
            query = query.where(TaskModel.call_type == call_type.value)

        query = query.order_by(TaskModel.created_at.asc()).limit(1)

        result = await self._session.execute(query)
        task_model = result.scalar_one_or_none()
        return self._to_domain(task_model) if task_model else None

    async def count_tasks_by_state(self, state: State) -> int:
        """
        Подсчитывает количество задач в указанном состоянии.

        Returns:
            int: Количество задач
        """
        result = await self._session.execute(
            select(func.count(TaskModel.id)).where(TaskModel.state == state.value)
        )
        return result.scalar_one()

    # ──────────────────────────────────────────────
    # Update
    # ──────────────────────────────────────────────

    async def update_task_state(
        self,
        task_id: UUID,
        new_state: State,
    ) -> None:
        """
        Обновляет состояние задачи.
        """
        await self._session.execute(
            update(TaskModel)
            .where(TaskModel.id == task_id)
            .values(state=new_state.value, updated_at=func.now())
        )
        await self._session.commit()
        logger.info(f"Task state updated: id={task_id}, new_state={new_state}")

    async def increment_retry_and_reset_state(self, task_id: UUID) -> None:
        """
        Увеличивает retry_count на 1 и возвращает задачу в состояние waiting.
        Используется для повторной обработки задач после ошибки.
        """
        await self._session.execute(
            update(TaskModel)
            .where(TaskModel.id == task_id)
            .values(
                retry_count=TaskModel.retry_count + 1,
                state=State.WAITING.value,
                updated_at=func.now(),
            )
        )
        await self._session.commit()
        logger.info(f"Task retry incremented and reset to waiting: id={task_id}")
