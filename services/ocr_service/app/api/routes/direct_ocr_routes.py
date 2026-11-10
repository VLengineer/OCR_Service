"""
Эндпоинты для прямой OCR-обработки документов (без очереди).
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, get_direct_ocr_service, get_document_type_registry
from app.core.document_type_registry import DocumentTypeRegistry
from app.schemas.schemas import Document
from app.services.direct_ocr_service import DirectOCRService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ocr", tags=["OCR"])


@router.post(
    "/image",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Прямая OCR изображения",
    description=(
        "Прямая OCR-обработка изображения без очереди. "
        "Принимает изображение и напрямую отправляет на OCR в n8n webhook, "
        "минуя очередь задач. Требует JWT-авторизацию."
    ),
)
async def direct_ocr_image(
    document: Document,
    service: DirectOCRService = Depends(get_direct_ocr_service),
    current_user: dict = Depends(get_current_user),
    registry: DocumentTypeRegistry = Depends(get_document_type_registry),
) -> dict[str, Any]:
    if not registry.is_valid(document.document_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_type: {document.document_type}",
        )
    try:
        result = await service.process_image(document)
        return result
    except ValueError as e:
        logger.warning(
            f"Некорректный тип документа для /image: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Ошибка прямой OCR-обработки изображения "
            f"{document.document_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Direct OCR processing failed: {str(e)}",
        )


@router.post(
    "/pdf-scan",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Прямая OCR PDF-скана",
    description=(
        "Прямая OCR-обработка PDF-скана без очереди. "
        "Принимает PDF-скан и напрямую отправляет все страницы на OCR в n8n webhook, "
        "минуя очередь задач. Требует JWT-авторизацию."
    ),
)
async def direct_ocr_pdf_scan(
    document: Document,
    service: DirectOCRService = Depends(get_direct_ocr_service),
    current_user: dict = Depends(get_current_user),
    registry: DocumentTypeRegistry = Depends(get_document_type_registry),
) -> dict[str, Any]:
    if not registry.is_valid(document.document_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_type: {document.document_type}",
        )
    try:
        result = await service.process_pdf_scan(document)
        return result
    except ValueError as e:
        logger.warning(
            f"Некорректный тип документа для /pdf-scan: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Ошибка прямой OCR-обработки PDF-скана "
            f"{document.document_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Direct OCR processing failed: {str(e)}",
        )


@router.post(
    "",
    response_model=dict[str, Any] | None,
    status_code=status.HTTP_200_OK,
    summary="Универсальная прямая OCR",
    description=(
        "Универсальная прямая OCR-обработка с автоопределением типа. "
        "Автоматически определяет тип документа и маршрутизирует: "
        "IMAGE → прямая OCR-обработка; "
        "PDF_SCAN → прямая OCR-обработка всех страниц; "
        "WORD/PDF_TEXT → извлечение текста и отправка в create_document. "
        "Требует JWT-авторизацию."
    ),
)
async def direct_ocr(
    document: Document,
    service: DirectOCRService = Depends(get_direct_ocr_service),
    current_user: dict = Depends(get_current_user),
    registry: DocumentTypeRegistry = Depends(get_document_type_registry),
) -> dict[str, Any] | None:
    if not registry.is_valid(document.document_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_type: {document.document_type}",
        )
    try:
        result = await service.process(document)
        return result
    except ValueError as e:
        logger.warning(
            f"Некорректный тип документа для direct-ocr: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Ошибка прямой обработки документа "
            f"{document.document_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Direct OCR processing failed: {str(e)}",
        )
