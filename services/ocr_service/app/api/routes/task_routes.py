"""
Эндпоинты для управления задачами OCR.
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user, get_request_service, get_task_repository
from app.repositories.task_repository import TaskRepository
from app.schemas.schemas import CallbackResponse, OCRRequest, State, Task
from app.services.request_service import RequestService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


@router.get(
    "",
    response_model=List[Task],
    status_code=status.HTTP_200_OK,
    summary="Получить список задач",
    description="Возвращает список задач с опциональным фильтром по состоянию. Требует JWT-авторизацию.",
)
async def get_tasks(
    state: Optional[State] = Query(None, description="Фильтр по состоянию задачи"),
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество задач"),
    task_repository: TaskRepository = Depends(get_task_repository),
    current_user: dict = Depends(get_current_user),
):
    if state is not None:
        tasks = await task_repository.get_tasks_by_state(state, limit=limit)
    else:
        # Если state не указан, возвращаем все задачи (в production нужен отдельный метод)
        # Для простоты: получаем задачи во всех состояниях
        all_tasks = []
        for s in State:
            tasks_batch = await task_repository.get_tasks_by_state(s, limit=limit)
            all_tasks.extend(tasks_batch)
        tasks = all_tasks[:limit]

    return tasks


@router.get(
    "/queue",
    response_model=Task,
    status_code=status.HTTP_200_OK,
    summary="Получить следующую задачу из очереди",
    description="Возвращает следующую задачу в состоянии waiting (FIFO). Требует JWT-авторизацию.",
)
async def get_next_waiting_task(
    task_repository: TaskRepository = Depends(get_task_repository),
    current_user: dict = Depends(get_current_user),
):
    task = await task_repository.get_next_waiting_task()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No waiting tasks in queue",
        )
    return task


@router.get(
    "/{task_id}",
    response_model=Task,
    status_code=status.HTTP_200_OK,
    summary="Получить задачу по ID",
    description="Возвращает задачу по её уникальному идентификатору. Требует JWT-авторизацию.",
)
async def get_task_by_id(
    task_id: UUID,
    task_repository: TaskRepository = Depends(get_task_repository),
    current_user: dict = Depends(get_current_user),
):
    task = await task_repository.get_task_by_id(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return task


@router.post(
    "/{task_id}/process",
    response_model=CallbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Запустить обработку задачи",
    description=(
        "Запускает OCR обработку задачи: обновляет state на processing, "
        "отправляет OCR запрос в n8n, обновляет state на completed или error. "
        "Требует JWT-авторизацию."
    ),
)
async def process_task(
    task_id: UUID,
    task_repository: TaskRepository = Depends(get_task_repository),
    request_service: RequestService = Depends(get_request_service),
    current_user: dict = Depends(get_current_user),
):
    # Получаем задачу
    task = await task_repository.get_task_by_id(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    try:
        # Обновляем состояние на processing
        await task_repository.update_task_state(task_id, State.PROCESSING)

        # Формируем OCR запрос
        ocr_request = OCRRequest(
            task_id=task.id,
            document_id=task.document_id,
            base64_document=task.base64_document,
        )

        # Отправляем в n8n
        await request_service.ocr_request(ocr_request)

        # Обновляем состояние на completed
        updated_task = await task_repository.update_task_state(task_id, State.COMPLETED)

        logger.info(f"Task {task_id} processed successfully")

        return CallbackResponse(
            task_id=updated_task.id,
            state=updated_task.state,
            updated_at=updated_task.updated_at,
        )

    except Exception as e:
        logger.error(f"Ошибка обработки задачи {task_id}: {e}")
        # Обновляем состояние на error
        await task_repository.update_task_state(task_id, State.ERROR)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task processing failed: {str(e)}",
        )


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Удалить задачу",
    description="Удаляет задачу по её уникальному идентификатору. Требует JWT-авторизацию.",
)
async def delete_task(
    task_id: UUID,
    task_repository: TaskRepository = Depends(get_task_repository),
    current_user: dict = Depends(get_current_user),
):
    deleted = await task_repository.remove_task(task_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )
    return {"status": "deleted", "task_id": str(task_id)}
