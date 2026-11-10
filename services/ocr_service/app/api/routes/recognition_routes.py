"""
Эндпоинты для проксирования запросов распознавания документов через n8n.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    get_current_user,
    get_recognition_proxy_service,
)
from app.schemas.schemas import RecognitionRequest, RecognitionResponse
from app.services.recognition_proxy_service import RecognitionProxyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ocr", tags=["OCR"])


@router.post(
    "/recognize",
    response_model=RecognitionResponse,
    status_code=status.HTTP_200_OK,
    summary="Распознавание документа (только текст)",
    description=(
        "Проксирует запрос распознавания документа в n8n и возвращает только распознанный текст. "
        "Принимает документ в base64, тип определяется внутри сервиса. "
        "Требует JWT-авторизацию."
    ),
)
async def recognize_document(
    request: RecognitionRequest,
    service: RecognitionProxyService = Depends(get_recognition_proxy_service),
    current_user: dict = Depends(get_current_user),
) -> RecognitionResponse:
    try:
        extracted_text = await service.recognize(request)
        return RecognitionResponse(extracted_text=extracted_text)

    except ValueError as e:
        logger.warning(
            f"Некорректный ответ распознавания документа: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Ошибка распознавания документа: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recognition failed: {str(e)}",
        )
