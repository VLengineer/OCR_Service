"""
API endpoints для интеграции с ELMA365.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import re

from app.api.deps import get_current_user, get_elma_service, get_task_repository
from app.repositories.task_repository import TaskRepository
from app.schemas.schemas import ElmaDocument, State, Task, CallType
from app.services.elma_service import ElmaService

router = APIRouter(prefix="/api/v1/elma", tags=["ELMA365"])


def extract_document_type_from_url(url: str | None) -> str | None:
    """
    Извлечь тип документа из URL ELMA365.
    
    URL имеет формат: .../app/chancellery/<type>/...
    Возвращает часть пути после /app/chancellery/
    
    Examples:
        "https://elma.example.com/app/chancellery/incoming/123" -> "incoming"
        "https://elma.example.com/app/chancellery/dogovor/456" -> "dogovor"
    """
    if not url:
        return None
    
    # Ищем паттерн /app/chancellery/<type>
    match = re.search(r'/app/chancellery/([^/]+)', url)
    if match:
        return match.group(1)
    
    return None


@router.post(
    "/documents",
    response_model=List[ElmaDocument],
    status_code=status.HTTP_200_OK,
    summary="Получить список документов из ELMA365",
    description="Возвращает список документов из системы ELMA365. Требует JWT-авторизацию.",
)
async def get_documents_list(
    elma_service: ElmaService = Depends(get_elma_service),
    current_user: dict = Depends(get_current_user),
) -> List[ElmaDocument]:
    try:
        documents = await elma_service.get_documents_list()
        return documents
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при получении списка документов: {str(e)}",
        )


@router.post(
    "/documents/{document_id}/process",
    response_model=Task,
    status_code=status.HTTP_200_OK,
    summary="Создать задачу на обработку документа из ELMA365",
    description=(
        "Скачивает документ из ELMA365 и создает задачу с типом FILL_RAG на его обработку. "
        "Требует JWT-авторизацию."
    ),
)
async def process_elma_document(
    document_id: str,
    elma_service: ElmaService = Depends(get_elma_service),
    task_repository: TaskRepository = Depends(get_task_repository),
    current_user: dict = Depends(get_current_user),
) -> Task:
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
        document_type=extract_document_type_from_url(document.url),
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


@router.post(
    "/load-documents",
    response_model=List[Task],
    status_code=status.HTTP_200_OK,
    summary="Загрузить все документы из ELMA365",
    description=(
        "Загружает все документы из ELMA365 и создает задачи на их обработку. "
        "Для каждого документа создается задача с типом FILL_RAG. "
        "Требует JWT-авторизацию."
    ),
)
async def load_documents_from_elma(
    elma_service: ElmaService = Depends(get_elma_service),
    task_repository: TaskRepository = Depends(get_task_repository),
    current_user: dict = Depends(get_current_user),
) -> List[Task]:
    documents = await elma_service.get_documents_list()
    created_tasks: List[Task] = []

    for document in documents:
        if not document.url:
            continue

        # Создаем задачу (base64 не нужен, воркер скачает сам по url)
        task = await task_repository.add_task(
            document_id=document.id_ or "unknown",
            base64_document=None,
            document_type=extract_document_type_from_url(document.url),
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
