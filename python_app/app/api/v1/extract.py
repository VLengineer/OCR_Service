"""Router for POST /api/v1/extract."""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from app.config import Settings, get_settings
from app.dependencies import verify_jwt
from app.schemas.documents import ExtractRequest, ExtractResponse
from app.services.extraction import (
    FileTooLargeError,
    InvalidBase64Error,
    UnsupportedFileTypeError,
    extract_document,
)
from app.services.ocr_client import OcrApiError, OcrClient
from app.services.pdf_service import PdfProcessingError
from app.services.word_service import WordProcessingError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["extraction"])


@router.post(
    "/extract",
    response_model=ExtractResponse,
    responses={
        400: {"model": Dict[str, str], "description": "Invalid base64 or request body"},
        401: {"model": Dict[str, str], "description": "Missing or invalid JWT"},
        413: {"model": Dict[str, str], "description": "File too large"},
        415: {"model": Dict[str, str], "description": "Unsupported media type"},
        422: {"model": Dict[str, str], "description": "Malformed JSON body / unknown field"},
        502: {"model": Dict[str, str], "description": "External OCR API error"},
    },
)
async def extract(
    request: Request,
    payload: Dict[str, Any] = Body(
        ...,
        examples=[{"document_base64": "<base64-кодированный файл>"}],
    ),
    settings: Settings = Depends(get_settings),
    _token_payload: Dict[str, Any] = Depends(verify_jwt),
) -> ExtractResponse:
    """Extract text from a base64-encoded document (JWT-protected).

    Принимает JSON вида ``{"document_base64": "..."}``. Дополнительно
    допускаются поля ``fileName``/``fileType`` (Elma365 может присылать их) —
    они игнорируются. Это защищает от 422, когда вызывающая сторона шлёт
    лишние поля или неверно именуемое поле.
    """
    # Гибкий разбор тела: документированное поле + частые варианты от Elma365.
    document_b64 = payload.get("document_base64")
    if document_b64 is None:
        for alt in ("documentBase64", "file_base64", "base64", "data"):
            if isinstance(payload.get(alt), str):
                document_b64 = payload[alt]
                logger.warning(
                    "Field %r used as document_base64; send 'document_base64' instead",
                    alt,
                )
                break

    try:
        request_model = ExtractRequest(document_base64=document_b64)
    except Exception as exc:  # pydantic.ValidationError
        logger.warning("Validation failed for /extract body: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Request body must be a JSON object with a non-empty string "
                "field 'document_base64'"
            ),
        ) from exc

    ocr_client = OcrClient(settings)

    try:
        result = await extract_document(
            document_base64=request_model.document_base64,
            settings=settings,
            ocr_client=ocr_client,
        )
    except InvalidBase64Error as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except FileTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc
    except UnsupportedFileTypeError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc)
        ) from exc
    except OcrApiError as exc:
        logger.error("Upstream OCR failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OCR API error: {exc}",
        ) from exc
    except (PdfProcessingError, WordProcessingError) as exc:
        logger.error("Document processing failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document processing error: {exc}",
        ) from exc

    logger.info(
        "Extraction succeeded: type=%s, pages=%d, chars=%d",
        result.file_type,
        result.pages_count,
        len(result.text),
    )
    return result
