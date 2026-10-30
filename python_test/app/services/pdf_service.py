"""PDF processing logic based on PyMuPDF (fitz).

Handles both editable PDFs (local text extraction) and scanned PDFs
(page rendering to PNG images for external OCR).
"""

import asyncio
import base64
import logging
from typing import List, Tuple

import fitz  # PyMuPDF

from app.services.ocr_client import OcrClient

logger = logging.getLogger(__name__)

# DPI used when rendering scanned pages to images for OCR.
OCR_RENDER_DPI = 300

# Separator inserted between texts of consecutive pages.
PAGE_BREAK_SEPARATOR = "\n\n--- Page Break ---\n\n"

# PDFs with legacy single-byte (cp1251) text encoding often come back from
# PyMuPDF as mojibake: Cyrillic bytes decoded as Latin-1/WinAnsi
# ("ÏÀÎ «Ãàçïðîì»"). See _looks_like_mojibake / _fix_mojibake below.


class PdfProcessingError(Exception):
    """Raised when a PDF document cannot be opened or parsed."""


def _has_meaningful_content(text: str) -> bool:
    """Return True if the text contains at least one letter or digit."""
    return any(ch.isalnum() for ch in text)


def _looks_like_mojibake(text: str) -> bool:
    """Heuristic: text is mostly ASCII/Latin-1 supplement but clearly was Cyrillic.

    Typical signature of cp1251-read-as-latin1: high share of U+0080–U+00FF
    characters and almost no real Cyrillic (U+0400–U+04FF).
    """
    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) < 10:
        return False
    latin_ext = sum(1 for ch in letters if "\u00c0" <= ch <= "\u00ff")
    cyrillic = sum(1 for ch in letters if "\u0400" <= ch <= "\u04ff")
    return latin_ext / len(letters) > 0.3 and cyrillic == 0


def _fix_mojibake(text: str) -> str:
    """Try to restore cp1251 text that was decoded as latin-1/cp1252.

    Returns the original text if recovery fails or produces nonsense.
    """
    for source_encoding in ("latin-1", "cp1252"):
        try:
            raw = text.encode(source_encoding, errors="strict")
        except (UnicodeEncodeError, LookupError):
            continue
        candidate = raw.decode("cp1251", errors="replace")
        # Sanity: replacement chars introduced by decoding mean wrong guess.
        if candidate.count("\ufffd") > len(candidate) * 0.05:
            continue
        cyrillic = sum(1 for ch in candidate if "\u0400" <= ch <= "\u04ff")
        if cyrillic > 0:
            logger.info(
                "Recovered cp1251 text from %s-decoded mojibake (%d Cyrillic chars)",
                source_encoding,
                cyrillic,
            )
            return candidate
    return text


def _extract_all_text_sync(data: bytes) -> Tuple[int, str]:
    """Extract embedded text from every page (blocking, runs in a thread).

    Returns:
        A tuple (pages_count, joined_text). If the combined text has no
        letters/digits, the PDF is considered a scan.
    """
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - fitz raises generic errors
        logger.error("Failed to open PDF: %s", exc)
        raise PdfProcessingError(f"Cannot open PDF document: {exc}") from exc

    try:
        page_texts: List[str] = []
        for page in document:
            page_text: str = page.get_text("text")
            page_texts.append(page_text)
        # Join non-empty pages only; a scanned PDF yields an empty string here.
        full_text = PAGE_BREAK_SEPARATOR.join(t.strip() for t in page_texts if t.strip())
        return document.page_count, full_text
    finally:
        document.close()


def _render_pages_to_base64_sync(data: bytes) -> List[str]:
    """Render every PDF page to a PNG image (DPI=300), base64-encoded.

    Blocking helper — executed inside a worker thread.
    """
    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to open PDF for rendering: %s", exc)
        raise PdfProcessingError(f"Cannot open PDF document: {exc}") from exc

    try:
        zoom = OCR_RENDER_DPI / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        images: List[str] = []
        for page in document:
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            png_bytes = pixmap.tobytes("png")
            images.append(base64.b64encode(png_bytes).decode("ascii"))
        return images
    finally:
        document.close()


async def extract_editable_text(data: bytes) -> Tuple[int, str]:
    """Try to extract embedded text from an editable PDF.

    Returns:
        (pages_count, text) if meaningful text exists, otherwise None.
    """
    pages_count, text = await asyncio.to_thread(_extract_all_text_sync, data)
    if _has_meaningful_content(text):
        # Fix legacy cp1251-as-latin1 mojibake if detected (no-op otherwise).
        if _looks_like_mojibake(text):
            text = _fix_mojibake(text)
        logger.info("Editable PDF detected: %d page(s), %d chars", pages_count, len(text))
        return pages_count, text
    logger.info("No embedded text found in PDF (%d page(s)) — treating as scan", pages_count)
    return None  # type: ignore[return-value]


async def ocr_scanned_pdf(
    data: bytes, ocr_client: OcrClient, document_uuid: str
) -> Tuple[int, str]:
    """OCR a scanned PDF: render each page and send it to the OCR API.

    Pages are processed STRICTLY SEQUENTIALLY (plain `for` loop,
    no asyncio.gather) as required by the specification.

    Returns:
        (pages_count, joined_text)
    """
    page_images = await asyncio.to_thread(_render_pages_to_base64_sync, data)
    pages_count = len(page_images)
    logger.info("Scanned PDF: %d page(s) to OCR sequentially", pages_count)

    page_texts: List[str] = []
    for index, image_b64 in enumerate(page_images, start=1):
        logger.info("OCR page %d/%d", index, pages_count)
        # Sequential await — do NOT parallelize these calls.
        page_text = await ocr_client.recognize(image_b64, document_uuid)
        page_texts.append(page_text.strip())

    combined_text = PAGE_BREAK_SEPARATOR.join(page_texts)
    return pages_count, combined_text
