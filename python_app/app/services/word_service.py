"""Word (.docx) text extraction using python-docx."""

import asyncio
import io
import logging

from docx import Document
from docx.opc.exceptions import PackageNotFoundError

logger = logging.getLogger(__name__)


class WordProcessingError(Exception):
    """Raised when a DOCX document cannot be parsed."""


def _extract_text_sync(data: bytes) -> str:
    """Blocking extraction of paragraph text from a DOCX file."""
    try:
        document = Document(io.BytesIO(data))
    except (PackageNotFoundError, KeyError, ValueError) as exc:
        logger.error("Failed to open DOCX document: %s", exc)
        raise WordProcessingError(f"Cannot open Word document: {exc}") from exc

    paragraphs = [p.text for p in document.paragraphs]
    # Also pull text out of tables, if any.
    table_texts: list[str] = []
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    table_texts.append(cell.text.strip())

    parts = [t for t in paragraphs if t.strip()]
    parts.extend(table_texts)
    return "\n".join(parts)


async def extract_text(data: bytes) -> str:
    """Extract text from a DOCX payload asynchronously (thread offload)."""
    text = await asyncio.to_thread(_extract_text_sync, data)
    logger.info("Word document extracted: %d chars", len(text))
    return text
