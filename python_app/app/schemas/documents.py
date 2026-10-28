"""Pydantic schemas for document extraction requests/responses."""

from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    """Incoming request body for POST /api/v1/extract."""

    document_base64: str = Field(
        ...,
        description="Base64-encoded contents of the document file.",
        min_length=1,
    )


class ExtractResponse(BaseModel):
    """Successful response body for POST /api/v1/extract."""

    file_type: str = Field(
        ...,
        description="Detected MIME type of the document (e.g. 'application/pdf').",
    )
    pages_count: int = Field(
        ...,
        description="Number of pages. Always 1 for images and Word documents.",
    )
    text: str = Field(
        ...,
        description="Extracted (or OCR-recognized) text content.",
    )


class OcrRequest(BaseModel):
    """Body sent to the external n8n OCR endpoint."""

    image_base64: str = Field(..., description="Base64-encoded PNG/JPEG image.")


class OcrResponse(BaseModel):
    """Expected response from the external n8n OCR endpoint."""

    text: str = Field(default="", description="Recognized text.")
