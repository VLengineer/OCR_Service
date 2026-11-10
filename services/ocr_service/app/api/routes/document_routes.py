"""
Эндпоинты для приёма документов на OCR-обработку (асинхронно, через очередь).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import get_current_user, get_document_service, get_document_type_registry
from app.core.document_type_registry import DocumentTypeRegistry
from app.schemas.schemas import Document
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ocr/documents", tags=["OCR"])


class DocumentAcceptedResponse(BaseModel):
    """Ответ при успешном приёме документа на обработку."""
    status: str
    document_id: str


@router.post(
    "",
    response_model=DocumentAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Принять документ на обработку",
    description=(
        "Принимает документ для асинхронной обработки. "
        "Определяет тип документа и маршрутизирует: "
        "Word/PDF с текстом → извлечение текста → отправка в n8n; "
        "Изображение/PDF-скан → создание OCR задачи. "
        "Требует JWT-авторизацию."
    ),
)
async def process_document(
    document: Document,
    document_service: DocumentService = Depends(get_document_service),
    current_user: dict = Depends(get_current_user),
    registry: DocumentTypeRegistry = Depends(get_document_type_registry),
) -> DocumentAcceptedResponse:
    if not registry.is_valid(document.document_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_type: {document.document_type}",
        )
    try:
        await document_service.processing(document)
        return DocumentAcceptedResponse(
            status="accepted",
            document_id=document.document_id,
        )
    except Exception as e:
        logger.error(f"Ошибка обработки документа {document.document_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document processing failed: {str(e)}",
        )
