"""
Эндпоинты для конвертации документов.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_document_convert_service
from app.schemas.schemas import DocumentConvertRequest, DocumentConvertResponse
from app.services.document_convert_service import DocumentConvertService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Convert"])


@router.post(
    "/convert",
    response_model=DocumentConvertResponse,
    status_code=status.HTTP_200_OK,
    summary="Конвертация документа",
    description=(
        "Конвертирует документ в унифицированный формат. "
        "Автоматически определяет тип документа и конвертирует: "
        "Word/PDF с текстом → извлечение текста → [text]; "
        "PDF-скан → конвертация страниц в изображения → [base64, ...]; "
        "Изображение → [base64_image]. "
        "Требует JWT-авторизацию."
    ),
)
async def convert_document(
    request: DocumentConvertRequest,
    service: DocumentConvertService = Depends(get_document_convert_service),
    current_user: dict = Depends(get_current_user),
) -> DocumentConvertResponse:
    try:
        result = await service.convert_document(request.document_base64)
        return result
    except ValueError as e:
        logger.warning(f"Невалидный документ для конвертации: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Ошибка конвертации документа: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document conversion failed: {str(e)}",
        )
