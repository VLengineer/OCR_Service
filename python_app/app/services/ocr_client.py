"""Async client for the external n8n OCR API."""

import logging

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class OcrApiError(Exception):
    """Raised when the external OCR API fails or times out.

    The orchestrator translates this into an HTTP 502 response.
    """


class OcrClient:
    """Thin wrapper around the n8n OCR webhook endpoint."""

    def __init__(self, settings: Settings) -> None:
        self._url: str = settings.ocr_api_url
        self._timeout: float = float(settings.ocr_api_timeout)

    async def recognize(self, image_base64: str) -> str:
        """Send a base64-encoded image to the OCR API and return recognized text.

        Raises:
            OcrApiError: on non-2xx response, malformed response body, or timeout.
        """
        payload = {"image_base64": image_base64}
        logger.info("Sending image to OCR API: %s", self._url)

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(self._url, json=payload)
        except httpx.TimeoutException as exc:
            logger.error("OCR API request timed out after %ss", self._timeout)
            raise OcrApiError(
                f"OCR API timeout: no response within {self._timeout} seconds"
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("OCR API connection error: %s", exc)
            raise OcrApiError(f"OCR API connection error: {exc}") from exc

        if not response.is_success:
            logger.error(
                "OCR API returned status %s: %s",
                response.status_code,
                response.text[:500],
            )
            raise OcrApiError(
                f"OCR API returned HTTP {response.status_code}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            logger.error("OCR API returned non-JSON response")
            raise OcrApiError("OCR API returned invalid (non-JSON) response body") from exc

        text = data.get("text")
        if not isinstance(text, str):
            logger.error("OCR API response missing 'text' field: %s", str(data)[:500])
            raise OcrApiError("OCR API response does not contain a 'text' string field")

        logger.info("OCR API returned %d characters of text", len(text))
        return text
