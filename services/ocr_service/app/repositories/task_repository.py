from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from app.models.task_model import TaskModel
from app.schemas.schemas import State, Task, CallType
from uuid import UUID
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class TaskRepository:
    """
    Репозиторий для работы с задачами в БД.
    Реализует CRUD-операции для таблицы task.
    Скрывает ORM-модель и возвращает доменные объекты Task.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # ──────────────────────────────────────────────
    # Вспомогательные методы конвертации
    # ──────────────────────────────────────────────

    @staticmethod
    def _sheets_to_jsonb(sheets: List[str] | None) -> list[dict] | None:
        """Конвертирует список base64-строк в формат JSONB для хранения.
        Возвращает None, если входной список None (для задач без base64).
        """
        if sheets is None:
            return None
        return [{"base64": sheet} for sheet in sheets]

    @staticmethod
    def _jsonb_to_sheets(base64_document: list[dict] | None) -> List[str]:
        """Конвертирует JSONB из БД обратно в список base64-строк"""
        if not base64_document:
            return []
        return [item.get("base64", "") for item in base64_document]

    @staticmethod
    def _to_domain(task_model: TaskModel) -> Task:
        """
        Конвертирует ORM-модель в доменный объект.
        
        Args:
            task_model: SQLAlchemy модель задачи
            
        Returns:
            Task: Доменный объект Pydantic
        """
        return Task(
            id=task_model.id,
            document_id=task_model.document_id,
            document_type=task_model.document_type,
            state=State(task_model.state),
            retry_count=task_model.retry_count,
            base64_document=TaskRepository._jsonb_to_sheets(task_model.base64_document),
            call_type=CallType(task_model.call_type) if task_model.call_type else CallType.OCR,
            metadata=task_model.metadata_,
            created_at=task_model.created_at,
            updated_at=task_model.updated_at,
        )

    # ──────────────────────────────────────────────
    # Create
    # ──────────────────────────────────────────────

    async def add_task(
        self,
        document_id: str,
        base64_document: List[str] | None = None,
        document_type: str | None = None,
        state: State = State.WAITING,
        call_type: CallType = CallType.OCR,
        metadata: dict | None = None,
    ) -> Task:
        """
        Создает новую задачу в БД.

        Args:
            document_id: ID документа из ELMA365
            base64_document: Массив страниц в base64 (None для задач без base64, например fill_rag)
            document_type: Тип документа из ELMA365
            state: Начальное состояние задачи (по умолчанию waiting)
            call_type: Тип вызова (по умолчанию ocr)
            metadata: Дополнительные метаданные задачи

        Returns:
            Task: Созданная задача
        """
        task = TaskModel(
            document_id=document_id,
            document_type=document_type,
            state=state.value,
            base64_document=self._sheets_to_jsonb(base64_document),
            call_type=call_type.value,
            metadata_=metadata,
        )

        self._session.add(task)
        await self._session.flush()
        await self._session.refresh(task)

        logger.info(f"Task created: id={task.id}, document_id={document_id}, state={state}")
        return self._to_domain(task)

    # ──────────────────────────────────────────────
    # Read
    # ──────────────────────────────────────────────

    async def get_task_by_id(self, task_id: UUID) -> Optional[Task]:
        """
        Получает задачу по ID.

        Returns:
            Task | None: Задача или None если не найдена
        """
        result = await self._session.execute(
            select(TaskModel).where(TaskModel.id == task_id)
        )
        task_model = result.scalar_one_or_none()
        return self._to_domain(task_model) if task_model else None

    async def get_tasks_by_state(self, state: State, limit: int = 100) -> List[Task]:
        """
        Получает список задач по состоянию (FIFO).

        Returns:
            List[Task]: Список задач
        """
        result = await self._session.execute(
            select(TaskModel)
            .where(TaskModel.state == state.value)
            .order_by(TaskModel.created_at.asc())
            .limit(limit)
        )
        return [self._to_domain(m) for m in result.scalars().all()]

    async def get_next_waiting_task(self) -> Optional[Task]:
        """
        Получает следующую задачу в состоянии waiting (FIFO).

        Returns:
            Task | None: Следующая задача или None если очередь пуста
        """
        result = await self._session.execute(
            select(TaskModel)
            .where(TaskModel.state == State.WAITING.value)
            .order_by(TaskModel.created_at.asc())
            .limit(1)
        )
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
    ) -> Optional[Task]:
        """
        Обновляет состояние задачи.

        Returns:
            Task | None: Обновленная задача или None если не найдена
        """
        await self._session.execute(
            update(TaskModel)
            .where(TaskModel.id == task_id)
            .values(state=new_state.value)
        )
        await self._session.flush()

        return await self.get_task_by_id(task_id)

    async def update_task_base64(
        self,
        task_id: UUID,
        base64_document: List[str],
    ) -> Optional[Task]:
        """
        Обновляет массив страниц задачи.

        Returns:
            Task | None: Обновленная задача или None если не найдена
        """
        await self._session.execute(
            update(TaskModel)
            .where(TaskModel.id == task_id)
            .values(base64_document=self._sheets_to_jsonb(base64_document))
        )
        await self._session.flush()

        return await self.get_task_by_id(task_id)

    # ──────────────────────────────────────────────
    # Delete
    # ──────────────────────────────────────────────

    async def remove_task(self, task_id: UUID) -> bool:
        """
        Удаляет задачу по ID.

        Returns:
            bool: True если задача удалена, False если не найдена
        """
        result = await self._session.execute(
            delete(TaskModel).where(TaskModel.id == task_id)
        )
        await self._session.flush()

        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Task deleted: id={task_id}")
        else:
            logger.warning(f"Task not found for deletion: id={task_id}")

        return deleted
