"""Extraction orchestrator: base64 decoding, size check, MIME dispatch.

This module contains the main branching logic described in the spec:
image -> OCR API, editable PDF -> local text, scanned PDF -> sequential OCR,
DOCX -> python-docx, anything else -> 415.
"""

import base64
import binascii
import logging
from typing import Tuple

from app.config import Settings
from app.schemas.documents import ExtractResponse
from app.services import pdf_service, word_service
from app.services.file_detector import detect_mime_type
from app.services.ocr_client import OcrClient

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/bmp",
}

DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


class InvalidBase64Error(Exception):
    """Raised when the request payload is not valid base64."""


class FileTooLargeError(Exception):
    """Raised when the decoded file exceeds MAX_FILE_SIZE_MB."""


class UnsupportedFileTypeError(Exception):
    """Raised when the detected MIME type cannot be processed."""


def decode_base64(document_base64: str) -> bytes:
    """Decode a base64 string into raw bytes.

    Raises:
        InvalidBase64Error: if the string is not valid base64.
    """
    try:
        # validate=True rejects any non-base64 characters.
        data = base64.b64decode(document_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        logger.warning("Invalid base64 payload: %s", exc)
        raise InvalidBase64Error("Provided document_base64 is not valid base64") from exc

    if not data:
        raise InvalidBase64Error("Decoded document is empty")

    return data


def check_size(data: bytes, settings: Settings) -> None:
    """Ensure decoded file size does not exceed MAX_FILE_SIZE_MB.

    Raises:
        FileTooLargeError: if the file is too big.
    """
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        logger.warning(
            "File size %d bytes exceeds limit %d bytes (%d MB)",
            len(data),
            max_bytes,
            settings.max_file_size_mb,
        )
        raise FileTooLargeError(
            f"File size {len(data) / (1024 * 1024):.2f} MB exceeds "
            f"the limit of {settings.max_file_size_mb} MB"
        )


async def _process_image(
    document_base64: str, ocr_client: OcrClient, document_uuid: str
) -> Tuple[int, str]:
    """Send the original image base64 directly to the OCR API."""
    text = await ocr_client.recognize(document_base64, document_uuid)
    return 1, text


async def _process_pdf(
    data: bytes, document_base64: str, ocr_client: OcrClient, document_uuid: str
) -> Tuple[int, str]:
    """Process a PDF: editable -> local extraction; scanned -> sequential OCR."""
    result = await pdf_service.extract_editable_text(data)
    if result is not None:
        pages_count, text = result
        return pages_count, text
    return await pdf_service.ocr_scanned_pdf(data, ocr_client, document_uuid)


async def extract_document(
    document_base64: str,
    settings: Settings,
    ocr_client: OcrClient,
    document_uuid: str,
) -> ExtractResponse:
    """Full extraction pipeline for one base64-encoded document.

    Raises:
        InvalidBase64Error      -> 400
        FileTooLargeError       -> 413
        UnsupportedFileTypeError-> 415
        OcrApiError             -> 502 (propagated from OcrClient)
        PdfProcessingError / WordProcessingError -> 500
    """
    # 2. Decode base64.
    data = decode_base64(document_base64)

    # 3. Check size limit.
    check_size(data, settings)

    # 4. Detect MIME type by magic numbers.
    mime_type = detect_mime_type(data)
    logger.info("Processing document, MIME=%s, size=%d bytes", mime_type, len(data))

    # 5. Dispatch by type.
    if mime_type in SUPPORTED_IMAGE_TYPES:
        pages_count, text = await _process_image(
            document_base64, ocr_client, document_uuid
        )
    elif mime_type == "application/pdf":
        pages_count, text = await _process_pdf(
            data, document_base64, ocr_client, document_uuid
        )
    elif mime_type == DOCX_MIME_TYPE:
        pages_count, text = 1, await word_service.extract_text(data)
    else:
        logger.warning("Unsupported file type: %s", mime_type)
        raise UnsupportedFileTypeError(
            f"Unsupported file type: '{mime_type}'. Supported: images "
            f"(jpeg/png/tiff/bmp), PDF, DOCX."
        )

    return ExtractResponse(file_type=mime_type, pages_count=pages_count, text=text)
