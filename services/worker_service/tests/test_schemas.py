"""
Unit-тесты для Pydantic-схем worker_service.

Тестируется поле document_type в моделях OCRRequest и DocumentRequest.
"""

import pytest
from uuid import uuid4

from app.schemas.schemas import OCRRequest, DocumentRequest


class TestOCRRequestDocumentType:
    """Тесты поля document_type в OCRRequest."""

    def test_ocr_request_with_valid_document_type(self):
        """OCRRequest принимает валидный document_type."""
        req = OCRRequest(
            task_id=uuid4(),
            document_id="doc-w-1",
            base64_document=["base64-page-1"],
            document_type="invoice",
        )
        assert req.document_type == "invoice"

    def test_ocr_request_without_document_type_defaults_to_none(self):
        """OCRRequest.document_type по умолчанию None."""
        req = OCRRequest(
            task_id=uuid4(),
            document_id="doc-w-2",
            base64_document=["base64-page-1"],
        )
        assert req.document_type is None

    def test_ocr_request_with_none_document_type(self):
        """OCRRequest принимает явный None для document_type."""
        req = OCRRequest(
            task_id=uuid4(),
            document_id="doc-w-3",
            base64_document=["base64-page-1"],
            document_type=None,
        )
        assert req.document_type is None

    def test_ocr_request_with_empty_string_document_type(self):
        """OCRRequest принимает пустую строку для document_type."""
        req = OCRRequest(
            task_id=uuid4(),
            document_id="doc-w-4",
            base64_document=["base64-page-1"],
            document_type="",
        )
        assert req.document_type == ""

    @pytest.mark.parametrize(
        "doc_type",
        ["incoming_correspondence", "outgoing_contract", "payment", "invoice"],
    )
    def test_ocr_request_with_various_valid_types(self, doc_type: str):
        """OCRRequest принимает различные валидные типы."""
        req = OCRRequest(
            task_id=uuid4(),
            document_id="doc-w-5",
            base64_document=["base64-page-1"],
            document_type=doc_type,
        )
        assert req.document_type == doc_type

    def test_ocr_request_serialization_with_document_type(self):
        """OCRRequest корректно сериализует document_type."""
        req = OCRRequest(
            task_id=uuid4(),
            document_id="doc-w-6",
            base64_document=["base64-page-1"],
            document_type="payment",
        )
        data = req.model_dump(mode="json")
        assert data["document_type"] == "payment"

    def test_ocr_request_serialization_with_none_document_type(self):
        """OCRRequest сериализует None document_type."""
        req = OCRRequest(
            task_id=uuid4(),
            document_id="doc-w-7",
            base64_document=["base64-page-1"],
        )
        data = req.model_dump(mode="json")
        assert data["document_type"] is None


class TestDocumentRequestDocumentType:
    """Тесты поля document_type в DocumentRequest."""

    def test_document_request_with_valid_document_type(self):
        """DocumentRequest принимает валидный document_type."""
        req = DocumentRequest(
            task_id=uuid4(),
            document_id="doc-w-10",
            raw_text="Some text",
            document_type="invoice",
        )
        assert req.document_type == "invoice"

    def test_document_request_without_document_type_defaults_to_none(self):
        """DocumentRequest.document_type по умолчанию None."""
        req = DocumentRequest(
            task_id=uuid4(),
            document_id="doc-w-11",
            raw_text="Some text",
        )
        assert req.document_type is None

    def test_document_request_with_none_document_type(self):
        """DocumentRequest принимает явный None для document_type."""
        req = DocumentRequest(
            task_id=uuid4(),
            document_id="doc-w-12",
            raw_text="Some text",
            document_type=None,
        )
        assert req.document_type is None

    def test_document_request_with_empty_string_document_type(self):
        """DocumentRequest принимает пустую строку для document_type."""
        req = DocumentRequest(
            task_id=uuid4(),
            document_id="doc-w-13",
            raw_text="Some text",
            document_type="",
        )
        assert req.document_type == ""

    @pytest.mark.parametrize(
        "doc_type",
        ["incoming_correspondence", "outgoing_contract", "payment", "invoice"],
    )
    def test_document_request_with_various_valid_types(self, doc_type: str):
        """DocumentRequest принимает различные валидные типы."""
        req = DocumentRequest(
            task_id=uuid4(),
            document_id="doc-w-14",
            raw_text="Text",
            document_type=doc_type,
        )
        assert req.document_type == doc_type

    def test_document_request_serialization_with_document_type(self):
        """DocumentRequest корректно сериализует document_type."""
        req = DocumentRequest(
            task_id=uuid4(),
            document_id="doc-w-15",
            raw_text="Text",
            document_type="payment",
        )
        data = req.model_dump(mode="json")
        assert data["document_type"] == "payment"

    def test_document_request_serialization_with_none_document_type(self):
        """DocumentRequest сериализует None document_type."""
        req = DocumentRequest(
            task_id=uuid4(),
            document_id="doc-w-16",
            raw_text="Text",
        )
        data = req.model_dump(mode="json")
        assert data["document_type"] is None
