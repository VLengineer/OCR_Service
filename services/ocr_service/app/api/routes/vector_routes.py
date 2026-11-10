"""
Эндпоинты для векторизации документов.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_document_vector_service
from app.schemas.schemas import DocumentVectorizeRequest, DocumentVectorizeResponse
from app.services.document_vector_service import DocumentVectorService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/vectors",
    tags=["Document Vectors"],
)


@router.post(
    "",
    response_model=DocumentVectorizeResponse,
    status_code=status.HTTP_200_OK,
    summary="Векторизация документа",
    description="Разбивает текст документа на чанки, векторизирует через Ollama и сохраняет в БД. Требует JWT-авторизацию.",
)
async def vectorize_document(
    request: DocumentVectorizeRequest,
    service: DocumentVectorService = Depends(get_document_vector_service),
    _current_user: dict = Depends(get_current_user),
) -> DocumentVectorizeResponse:
    try:
        result = await service.vectorize(request)
        return result
    except Exception as e:
        logger.error("Ошибка векторизации документа %s: %s", request.document_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка при векторизации документа",
        ) from e
