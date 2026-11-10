"""
Зависимости FastAPI для инъекции сервисов и проверки авторизации.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_token
from app.core.document_type_registry import DocumentTypeRegistry
from app.repositories.database import get_session
from app.repositories.task_repository import TaskRepository
from app.services.direct_ocr_service import DirectOCRService
from app.services.document_converter import DocumentConverter
from app.services.document_service import DocumentService
from app.services.recognition_proxy_service import RecognitionProxyService
from app.services.request_service import RequestService
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.document_vector_service import DocumentVectorService
from app.services.document_convert_service import DocumentConvertService
from app.repositories.document_vector_repository import DocumentVectorRepository
from app.services.elma_service import ElmaService

# HTTPBearer схема для Swagger UI
http_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
) -> dict:
    """
    Проверяет JWT-токен и возвращает payload.
    Используется как зависимость для защищённых эндпоинтов.
    """
    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


async def get_task_repository(
    session: AsyncSession = Depends(get_session),
) -> TaskRepository:
    """Создаёт репозиторий задач с активной сессией БД."""
    return TaskRepository(session)


async def get_request_service() -> RequestService:
    """Создаёт сервис HTTP-запросов к n8n."""
    return RequestService()


async def get_document_converter() -> DocumentConverter:
    """Создаёт конвертер документов."""
    return DocumentConverter()


async def get_document_service(
    task_repository: TaskRepository = Depends(get_task_repository),
    request_service: RequestService = Depends(get_request_service),
    document_converter: DocumentConverter = Depends(get_document_converter),
) -> DocumentService:
    """Создаёт сервис обработки документов."""
    return DocumentService(
        request_service=request_service,
        task_repository=task_repository,
        document_converter=document_converter,
    )


async def get_direct_ocr_service(
    request_service: RequestService = Depends(get_request_service),
    document_converter: DocumentConverter = Depends(get_document_converter),
) -> DirectOCRService:
    """Создаёт сервис прямой OCR-обработки (без очереди)."""
    return DirectOCRService(
        request_service=request_service,
        document_converter=document_converter,
    )


async def get_recognition_proxy_service(
    request_service: RequestService = Depends(get_request_service),
    document_converter: DocumentConverter = Depends(get_document_converter),
) -> RecognitionProxyService:
    """Создаёт сервис проксирования запросов распознавания документов."""
    return RecognitionProxyService(
        request_service=request_service,
        document_converter=document_converter,
    )


def get_document_type_registry() -> DocumentTypeRegistry:
    """Создаёт реестр допустимых типов документов."""
    return DocumentTypeRegistry()


async def get_chunking_service() -> ChunkingService:
    """Создаёт сервис разбивки текста на чанки."""
    return ChunkingService()


async def get_embedding_service() -> EmbeddingService:
    """Создаёт сервис получения эмбеддингов через Ollama."""
    return EmbeddingService()


async def get_document_vector_repository(
    session: AsyncSession = Depends(get_session),
) -> DocumentVectorRepository:
    """Создаёт репозиторий векторов документов."""
    return DocumentVectorRepository(session)


async def get_document_vector_service(
    chunking_service: ChunkingService = Depends(get_chunking_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    repository: DocumentVectorRepository = Depends(get_document_vector_repository),
) -> DocumentVectorService:
    """Создаёт сервис векторизации документов."""
    return DocumentVectorService(
        chunking_service=chunking_service,
        embedding_service=embedding_service,
        repository=repository,
    )


async def get_document_convert_service(
    document_converter: DocumentConverter = Depends(get_document_converter),
) -> DocumentConvertService:
    """Создаёт сервис конвертации документов."""
    return DocumentConvertService(document_converter=document_converter)


async def get_elma_service() -> ElmaService:
    """Создаёт сервис для работы с ELMA365."""
    return ElmaService()
