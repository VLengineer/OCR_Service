"""Тесты для Pydantic схем."""
import pytest
from uuid import uuid4, UUID
from datetime import datetime
from pydantic import ValidationError

from app.schemas.schemas import (
    State,
    CallType,
    ElmaDocument,
    Task,
    Document,
    CallbackResponse,
    OCRRequest,
    DocumentRequest,
    DocumentVectorizeRequest,
    DocumentVectorizeResponse,
    DocumentConvertRequest,
    DocumentConvertResponse,
)


class TestElmaDocument:
    """Тесты для схемы ElmaDocument."""

    def test_elma_document_all_fields_default_to_none(self):
        """Все поля ElmaDocument опциональны и по умолчанию None."""
        doc = ElmaDocument()
        assert doc.url is None
        assert doc.id_ is None
        assert doc.name_ is None
        assert doc.subject is None
        assert doc.description is None
        assert doc.created_at is None
        assert doc.counterparty is None
        assert doc.decision_maker is None
        assert doc.register_name_ is None
        assert doc.type_id_ is None
        assert doc.type_name_ is None
        assert doc.version_ is None
        assert doc.registration_date is None

    def test_elma_document_creation_with_python_names(self):
        """Создание ElmaDocument с Python-именами полей (populate_by_name)."""
        doc = ElmaDocument(
            id_="doc-123",
            name_="test_document.pdf",
            subject="Test subject",
            url="https://elma.example/doc/123",
        )
        assert doc.id_ == "doc-123"
        assert doc.name_ == "test_document.pdf"
        assert doc.subject == "Test subject"
        assert doc.url == "https://elma.example/doc/123"

    def test_elma_document_aliases_for_id_and_name(self):
        """Проверка алиасов '__id' и '__name' для полей id_ и name_."""
        doc = ElmaDocument.model_validate({
            "__id": "456",
            "__name": "document.docx",
            "__createdAt": "2024-01-15T10:30:00",
            "decisionMaker": "John Doe",
            "registrationDate": "2024-01-16",
        })
        assert doc.id_ == "456"
        assert doc.name_ == "document.docx"
        assert doc.created_at == "2024-01-15T10:30:00"
        assert doc.decision_maker == "John Doe"
        assert doc.registration_date == "2024-01-16"

    def test_elma_document_serialization_with_alias(self):
        """Сериализация ElmaDocument с by_alias=True использует алиасы."""
        doc = ElmaDocument(id_="789", name_="report.xlsx")
        data = doc.model_dump(by_alias=True)
        assert "__id" in data
        assert data["__id"] == "789"
        assert "__name" in data
        assert data["__name"] == "report.xlsx"

    def test_elma_document_serialization_without_alias(self):
        """Сериализация ElmaDocument с by_alias=False использует Python-имена."""
        doc = ElmaDocument(id_="789", name_="report.xlsx")
        data = doc.model_dump(by_alias=False)
        assert "id_" in data
        assert data["id_"] == "789"
        assert "name_" in data
        assert data["name_"] == "report.xlsx"


class TestTask:
    """Тесты для схемы Task."""

    def test_task_creation_with_valid_data(self):
        """Создание Task с валидными данными."""
        task_id = uuid4()
        now = datetime.now()
        task = Task(
            id=task_id,
            document_id="doc-123",
            created_at=now,
            updated_at=now,
        )
        assert task.id == task_id
        assert task.document_id == "doc-123"
        assert task.state == State.WAITING
        assert task.retry_count == 0
        assert task.base64_document == []
        assert task.call_type == CallType.OCR
        assert task.metadata is None
        assert task.document_type is None

    def test_task_with_all_optional_fields(self):
        """Создание Task со всеми опциональными полями."""
        task_id = uuid4()
        now = datetime.now()
        task = Task(
            id=task_id,
            document_id="doc-456",
            document_type="contract",
            state=State.PROCESSING,
            retry_count=3,
            base64_document=["page1_base64", "page2_base64"],
            call_type=CallType.FILL_RAG,
            metadata={"key": "value"},
            created_at=now,
            updated_at=now,
        )
        assert task.document_type == "contract"
        assert task.state == State.PROCESSING
        assert task.retry_count == 3
        assert len(task.base64_document) == 2
        assert task.call_type == CallType.FILL_RAG
        assert task.metadata == {"key": "value"}

    def test_task_missing_required_fields(self):
        """Ошибка при отсутствии обязательных полей."""
        with pytest.raises(ValidationError):
            Task()

    def test_task_invalid_state_value(self):
        """Ошибка при невалидном значении state."""
        with pytest.raises(ValidationError):
            Task(
                id=uuid4(),
                document_id="doc-1",
                state="invalid_state",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def test_task_invalid_call_type(self):
        """Ошибка при невалидном значении call_type."""
        with pytest.raises(ValidationError):
            Task(
                id=uuid4(),
                document_id="doc-1",
                call_type="invalid_type",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )


class TestDocument:
    """Тесты для схемы Document."""

    def test_document_creation_with_valid_data(self):
        """Создание Document с валидными данными."""
        doc = Document(
            document_id="doc-100",
            document_base64="base64content",
        )
        assert doc.document_id == "doc-100"
        assert doc.document_base64 == "base64content"
        assert doc.document_type is None

    def test_document_with_type(self):
        """Создание Document с указанием типа."""
        doc = Document(
            document_id="doc-200",
            document_base64="content",
            document_type="pdf",
        )
        assert doc.document_type == "pdf"

    def test_document_missing_required_fields(self):
        """Ошибка при отсутствии обязательных полей."""
        with pytest.raises(ValidationError):
            Document()


class TestCallbackResponse:
    """Тесты для схемы CallbackResponse."""

    def test_callback_response_creation(self):
        """Создание CallbackResponse с валидными данными."""
        task_id = uuid4()
        now = datetime.now()
        response = CallbackResponse(
            task_id=task_id,
            state=State.COMPLETED,
            updated_at=now,
        )
        assert response.task_id == task_id
        assert response.state == State.COMPLETED
        assert response.updated_at == now

    @pytest.mark.parametrize("state", list(State))
    def test_callback_response_all_states(self, state):
        """CallbackResponse принимает все допустимые значения State."""
        response = CallbackResponse(
            task_id=uuid4(),
            state=state,
            updated_at=datetime.now(),
        )
        assert response.state == state

    def test_callback_response_missing_required_fields(self):
        """Ошибка при отсутствии обязательных полей."""
        with pytest.raises(ValidationError):
            CallbackResponse()


class TestOCRRequest:
    """Тесты для схемы OCRRequest."""

    def test_ocr_request_creation(self):
        """Создание OCRRequest с валидными данными."""
        request = OCRRequest(document_id="doc-123")
        assert request.document_id == "doc-123"
        assert request.task_id is None
        assert request.base64_document == []
        assert request.document_type is None

    def test_ocr_request_with_all_fields(self):
        """Создание OCRRequest со всеми полями."""
        task_id = uuid4()
        request = OCRRequest(
            task_id=task_id,
            document_id="doc-456",
            base64_document=["page1", "page2"],
            document_type="scan",
        )
        assert request.task_id == task_id
        assert len(request.base64_document) == 2
        assert request.document_type == "scan"

    def test_ocr_request_missing_document_id(self):
        """Ошибка при отсутствии document_id."""
        with pytest.raises(ValidationError):
            OCRRequest()


class TestDocumentRequest:
    """Тесты для схемы DocumentRequest."""

    def test_document_request_creation(self):
        """Создание DocumentRequest с валидными данными."""
        request = DocumentRequest(
            document_id="doc-456",
            raw_text="Распознанный текст документа",
        )
        assert request.document_id == "doc-456"
        assert request.raw_text == "Распознанный текст документа"
        assert request.task_id is None
        assert request.document_type is None

    def test_document_request_missing_required_fields(self):
        """Ошибка при отсутствии обязательных полей."""
        with pytest.raises(ValidationError):
            DocumentRequest()

    def test_document_request_missing_raw_text(self):
        """Ошибка при отсутствии raw_text."""
        with pytest.raises(ValidationError):
            DocumentRequest(document_id="doc-1")


class TestDocumentVectorizeRequest:
    """Тесты для схемы DocumentVectorizeRequest."""

    def test_vectorize_request_creation(self):
        """Создание DocumentVectorizeRequest с валидными данными."""
        request = DocumentVectorizeRequest(
            document_id="doc-1",
            content="Текст для векторизации",
        )
        assert request.document_id == "doc-1"
        assert request.content == "Текст для векторизации"
        assert request.response_id is None
        assert request.counterparty_id is None
        assert request.metadata is None

    def test_vectorize_request_with_all_fields(self):
        """Создание DocumentVectorizeRequest со всеми полями."""
        request = DocumentVectorizeRequest(
            document_id="doc-2",
            response_id="resp-1",
            counterparty_id="cp-1",
            content="Текст",
            metadata={"source": "ocr"},
        )
        assert request.response_id == "resp-1"
        assert request.counterparty_id == "cp-1"
        assert request.metadata == {"source": "ocr"}

    def test_vectorize_request_missing_content(self):
        """Ошибка при отсутствии content."""
        with pytest.raises(ValidationError):
            DocumentVectorizeRequest(document_id="doc-1")

    def test_vectorize_request_empty_content(self):
        """Ошибка при пустом content (min_length=1)."""
        with pytest.raises(ValidationError):
            DocumentVectorizeRequest(document_id="doc-1", content="")

    def test_vectorize_request_document_id_too_long(self):
        """Ошибка при document_id длиннее 50 символов (max_length=50)."""
        with pytest.raises(ValidationError):
            DocumentVectorizeRequest(
                document_id="x" * 51,
                content="Текст",
            )


class TestDocumentVectorizeResponse:
    """Тесты для схемы DocumentVectorizeResponse."""

    def test_vectorize_response_creation(self):
        """Создание DocumentVectorizeResponse с валидными данными."""
        response = DocumentVectorizeResponse(
            document_id="doc-1",
            chunks_count=10,
        )
        assert response.document_id == "doc-1"
        assert response.chunks_count == 10


class TestDocumentConvertRequest:
    """Тесты для схемы DocumentConvertRequest."""

    def test_convert_request_creation(self):
        """Создание DocumentConvertRequest с валидными данными."""
        request = DocumentConvertRequest(document_base64="base64content")
        assert request.document_base64 == "base64content"

    def test_convert_request_missing_document_base64(self):
        """Ошибка при отсутствии document_base64."""
        with pytest.raises(ValidationError):
            DocumentConvertRequest()


class TestDocumentConvertResponse:
    """Тесты для схемы DocumentConvertResponse."""

    def test_convert_response_creation(self):
        """Создание DocumentConvertResponse с валидными данными."""
        response = DocumentConvertResponse(
            document_type="pdf_text",
            document_sheets=["page1_base64", "page2_base64"],
        )
        assert response.document_type == "pdf_text"
        assert len(response.document_sheets) == 2

    def test_convert_response_empty_sheets(self):
        """Создание DocumentConvertResponse с пустым списком листов."""
        response = DocumentConvertResponse(
            document_type="image",
            document_sheets=[],
        )
        assert response.document_sheets == []
