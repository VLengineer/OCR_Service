"""
API endpoints для интеграции с ELMA365.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.api.deps import get_current_user, get_elma_service, get_task_repository
from app.repositories.task_repository import TaskRepository
from app.schemas.schemas import ElmaDocument, State, Task, CallType
from app.services.elma_service import ElmaService

router = APIRouter(prefix="/api/v1/elma", tags=["ELMA365"])


@router.get("/documents", response_model=List[ElmaDocument])
async def get_documents_list(
    elma_service: ElmaService = Depends(get_elma_service),
    current_user: dict = Depends(get_current_user),
) -> List[ElmaDocument]:
    """
    Получить список документов из ELMA365.

    Требует JWT-авторизацию.
    """
    try:
        documents = await elma_service.get_documents_list()
        return documents
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении списка документов: {str(e)}",
        )


@router.post("/documents/{document_id}/process", response_model=Task)
async def process_elma_document(
    document_id: str,
    elma_service: ElmaService = Depends(get_elma_service),
    task_repository: TaskRepository = Depends(get_task_repository),
    current_user: dict = Depends(get_current_user),
) -> Task:
    """
    Создать задачу на обработку документа из ELMA365.

    Скачивает документ из ELMA365 и создает задачу с типом FILL_RAG.

    Требует JWT-авторизацию.
    """
    # Получаем список документов и ищем нужный
    documents = await elma_service.get_documents_list()
    document = next((d for d in documents if d.id_ == document_id), None)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Документ {document_id} не найден в ELMA365",
        )

    # Проверяем наличие URL для документа
    if not document.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Документ {document_id} не имеет URL для скачивания",
        )

    # Создаем задачу с типом FILL_RAG (base64 не нужен, воркер скачает сам по url)
    task = await task_repository.add_task(
        document_id=document_id,
        base64_document=None,
        document_type=document.register_name_,
        state=State.WAITING,
        call_type=CallType.FILL_RAG,
        metadata={
            "url": document.url,
            "__id": document.id_,
            "__name": document.name_,
            "subject": document.subject,
            "description": document.description,
            "__createdAt": document.created_at,
            "counterparty": document.counterparty,
            "decisionMaker": document.decision_maker,
            "__register_name": document.register_name_,
            "registrationDate": document.registration_date,
        },
    )

    return task


@router.post("/load-documents", response_model=List[Task])
async def load_documents_from_elma(
    elma_service: ElmaService = Depends(get_elma_service),
    task_repository: TaskRepository = Depends(get_task_repository),
    current_user: dict = Depends(get_current_user),
) -> List[Task]:
    """
    Загрузить все документы из ELMA365 и создать задачи на обработку.

    Для каждого документа создается задача с типом FILL_RAG.

    Требует JWT-авторизацию.
    """
    documents = await elma_service.get_documents_list()
    created_tasks: List[Task] = []

    for document in documents:
        if not document.url:
            continue

        # Создаем задачу (base64 не нужен, воркер скачает сам по url)
        task = await task_repository.add_task(
            document_id=document.id_ or "unknown",
            base64_document=None,
            document_type=document.register_name_,
            state=State.WAITING,
            call_type=CallType.FILL_RAG,
            metadata={
                "url": document.url,
                "__id": document.id_,
                "__name": document.name_,
                "subject": document.subject,
                "description": document.description,
                "__createdAt": document.created_at,
                "counterparty": document.counterparty,
                "decisionMaker": document.decision_maker,
                "__register_name": document.register_name_,
                "registrationDate": document.registration_date,
            },
        )
        created_tasks.append(task)

    return created_tasks
