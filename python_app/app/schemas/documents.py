"""Pydantic schemas for document extraction requests/responses."""

import uuid as uuid_module

from pydantic import BaseModel, Field, field_validator


class ExtractRequest(BaseModel):
    """Incoming request body for POST /api/v1/extract."""

    document_base64: str = Field(
        ...,
        description="Base64-encoded contents of the document file.",
        min_length=1,
    )
    uuid: str = Field(
        ...,
        description=(
            "Document UUID (string). Passed through to the external n8n OCR API."
        ),
        min_length=1,
    )

    @field_validator("uuid")
    @classmethod
    def validate_uuid(cls, value: str) -> str:
        """Ensure the value is a syntactically valid UUID string."""
        try:
            uuid_module.UUID(value)
        except ValueError as exc:
            raise ValueError(f"'{value}' is not a valid UUID") from exc
        return value


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
    uuid: str = Field(
        ...,
        description="Document UUID forwarded from the /extract request.",
    )


class OcrResponse(BaseModel):
    """Expected response from the external n8n OCR endpoint."""

    text: str = Field(default="", description="Recognized text.")
