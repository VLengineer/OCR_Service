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
from datetime import datetime, timedelta, timezone
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
            next_retry_at=task_model.next_retry_at,
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

    async def has_active_tasks(self, max_total_retries: int) -> bool:
        """
        Проверяет наличие активных задач, блокирующих обработку новых задач.

        Активными считаются:
        - задачи в состоянии processing;
        - задачи в состоянии error с retry_count < max_total_retries, у которых
          нет запланированного retry (next_retry_at IS NULL) или время retry
          ещё не наступило (next_retry_at > NOW()).

        Задачи в error с наступившим next_retry_at считаются готовыми
        к повторной обработке и не блокируют очередь.
        Задачи в error с retry_count >= max_total_retries — окончательно
        проваленные (permanently failed) — также не блокируют очередь.

        Args:
            max_total_retries: Общее максимальное количество попыток обработки.

        Returns:
            bool: True если есть блокирующие активные задачи.
        """
        result = await self._session.execute(
            select(func.count(TaskModel.id))
            .where(TaskModel.state.in_([State.PROCESSING.value, State.ERROR.value]))
            .where(
                (TaskModel.state == State.PROCESSING.value)
                | (
                    (TaskModel.state == State.ERROR.value)
                    & (TaskModel.retry_count < max_total_retries)
                    & (
                        (TaskModel.next_retry_at.is_(None))
                        | (TaskModel.next_retry_at > func.now())
                    )
                )
            )
        )
        return result.scalar_one() > 0

    async def get_active_task_counts(self) -> dict[str, int]:
        """
        Возвращает количество processing и error задач для логирования.

        Returns:
            dict: {"processing": int, "error": int}
        """
        result = await self._session.execute(
            select(TaskModel.state, func.count(TaskModel.id))
            .where(TaskModel.state.in_([State.PROCESSING.value, State.ERROR.value]))
            .group_by(TaskModel.state)
        )
        counts = {row[0]: row[1] for row in result.all()}
        return {
            "processing": counts.get(State.PROCESSING.value, 0),
            "error": counts.get(State.ERROR.value, 0),
        }

    async def get_next_retryable_error_task(self) -> Optional[Task]:
        """
        Получает следующую задачу в error, готовую к повторной обработке.

        Условия: status='error', next_retry_at IS NOT NULL
        AND next_retry_at <= NOW().

        Returns:
            Task | None: Следующая retryable задача или None.
        """
        result = await self._session.execute(
            select(TaskModel)
            .where(TaskModel.state == State.ERROR.value)
            .where(TaskModel.next_retry_at.isnot(None))
            .where(TaskModel.next_retry_at <= func.now())
            .order_by(TaskModel.next_retry_at.asc())
            .limit(1)
        )
        task_model = result.scalar_one_or_none()
        return self._to_domain(task_model) if task_model else None

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
        try:
            await self._session.commit()
            logger.info(f"Task state updated: id={task_id}, new_state={new_state}")
        except Exception as e:
            await self._session.rollback()
            logger.error(f"Failed to commit task state update: id={task_id}, error={e}")
            raise

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
                next_retry_at=None,
                updated_at=func.now(),
            )
        )
        try:
            await self._session.commit()
            logger.info(f"Task retry incremented and reset to waiting: id={task_id}")
        except Exception as e:
            await self._session.rollback()
            logger.error(
                f"Failed to commit task retry increment and reset: id={task_id}, error={e}"
            )
            raise

    async def schedule_secondary_retry(
        self,
        task_id: UUID,
        retry_delay_sec: int,
    ) -> None:
        """
        Увеличивает retry_count и планирует вторичную повторную попытку.

        Задача остаётся в состоянии error, next_retry_at устанавливается
        на NOW() + retry_delay_sec.

        Args:
            task_id: ID задачи.
            retry_delay_sec: Задержка до следующей попытки в секундах.
        """
        next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=retry_delay_sec)
        await self._session.execute(
            update(TaskModel)
            .where(TaskModel.id == task_id)
            .values(
                retry_count=TaskModel.retry_count + 1,
                state=State.ERROR.value,
                next_retry_at=next_retry_at,
                updated_at=func.now(),
            )
        )
        try:
            await self._session.commit()
            logger.info(
                f"Task secondary retry scheduled: id={task_id}, "
                f"next_retry_at={next_retry_at.isoformat()}"
            )
        except Exception as e:
            await self._session.rollback()
            logger.error(
                f"Failed to commit task secondary retry scheduling: id={task_id}, error={e}"
            )
            raise

    async def mark_task_permanently_failed(self, task_id: UUID) -> None:
        """
        Помечает задачу как окончательно проваленную.

        Устанавливает state='error' и next_retry_at=NULL.
        """
        await self._session.execute(
            update(TaskModel)
            .where(TaskModel.id == task_id)
            .values(
                state=State.ERROR.value,
                next_retry_at=None,
                updated_at=func.now(),
            )
        )
        try:
            await self._session.commit()
            logger.info(f"Task marked as permanently failed: id={task_id}")
        except Exception as e:
            await self._session.rollback()
            logger.error(
                f"Failed to commit task permanently failed mark: id={task_id}, error={e}"
            )
            raise

    async def move_error_to_waiting(self, task_id: UUID) -> bool:
        """
        Переводит задачу из error в waiting для повторной обработки.

        Используется для задач, у которых наступило next_retry_at.
        Атомарно проверяет состояние: обновляет только если задача всё ещё в error.

        Args:
            task_id: ID задачи.

        Returns:
            bool: True если задача успешно переведена, False если состояние изменилось.
        """
        result = await self._session.execute(
            update(TaskModel)
            .where(TaskModel.id == task_id)
            .where(TaskModel.state == State.ERROR.value)
            .values(
                state=State.WAITING.value,
                updated_at=func.now(),
            )
        )
        try:
            await self._session.commit()
            if result.rowcount == 0:
                logger.warning(
                    f"Task not moved from error to waiting (state changed): id={task_id}"
                )
                return False
            logger.info(f"Task moved from error to waiting: id={task_id}")
            return True
        except Exception as e:
            await self._session.rollback()
            logger.error(
                f"Failed to commit moving task from error to waiting: id={task_id}, error={e}"
            )
            raise
