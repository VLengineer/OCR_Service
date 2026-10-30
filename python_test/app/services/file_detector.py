"""MIME type detection based on file magic numbers (python-magic).

NOTE: python-magic requires the system library `libmagic`
(e.g. `apt-get install libmagic1` on Debian/Ubuntu).
"""

import logging

import magic

logger = logging.getLogger(__name__)


def detect_mime_type(data: bytes) -> str:
    """Detect the MIME type of raw file bytes using libmagic.

    The extension is intentionally ignored — only magic numbers are used.
    """
    mime_type: str = magic.from_buffer(data, mime=True)
    logger.info("Detected MIME type: %s", mime_type)
    return mime_type
