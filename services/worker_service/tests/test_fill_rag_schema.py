"""
Модульные тесты для FillRagRequest схемы.
"""

import pytest
from pydantic import ValidationError

from app.schemas.schemas import FillRagRequest


class TestFillRagRequestCreation:
    """Тесты создания FillRagRequest."""

    def test_create_with_required_fields_using_aliases(self):
        """Создание с обязательными полями через алиасы (__id, __name, __createdAt)."""
        request = FillRagRequest(
            url="https://example.com/doc/1",
            __id="rec-001",
            __name="Test Document",
            __createdAt="2025-01-15T10:30:00Z",
        )

        assert request.url == "https://example.com/doc/1"
        assert request.id == "rec-001"
        assert request.name == "Test Document"
        assert request.created_at == "2025-01-15T10:30:00Z"

    def test_create_with_required_fields_using_field_names(self):
        """Создание с обязательными полями через имена полей (populate_by_name=True)."""
        request = FillRagRequest(
            url="https://example.com/doc/1",
            id="rec-001",
            name="Test Document",
            created_at="2025-01-15T10:30:00Z",
        )

        assert request.id == "rec-001"
        assert request.name == "Test Document"
        assert request.created_at == "2025-01-15T10:30:00Z"

    def test_create_with_all_fields(self):
        """Создание со всеми полями, включая опциональные."""
        request = FillRagRequest(
            url="https://example.com/doc/1",
            __id="rec-001",
            __name="Test Document",
            __createdAt="2025-01-15T10:30:00Z",
            subject="Test Subject",
            description="Test Description",
            counterparty="Test Counterparty",
            decisionMaker="Test Decision Maker",
            __register_name="Test Register",
            registrationDate="2025-01-10",
        )

        assert request.url == "https://example.com/doc/1"
        assert request.id == "rec-001"
        assert request.name == "Test Document"
        assert request.created_at == "2025-01-15T10:30:00Z"
        assert request.subject == "Test Subject"
        assert request.description == "Test Description"
        assert request.counterparty == "Test Counterparty"
        assert request.decision_maker == "Test Decision Maker"
        assert request.register_name == "Test Register"
        assert request.registration_date == "2025-01-10"

    def test_create_with_alias_fields(self):
        """Создание с alias полями (decisionMaker, __register_name, registrationDate)."""
        request = FillRagRequest(
            url="https://example.com/doc/1",
            __id="rec-001",
            __name="Test Document",
            __createdAt="2025-01-15T10:30:00Z",
            decisionMaker="John Doe",
            __register_name="Contracts",
            registrationDate="2025-06-01",
        )

        assert request.decision_maker == "John Doe"
        assert request.register_name == "Contracts"
        assert request.registration_date == "2025-06-01"

    def test_missing_required_url_raises_error(self):
        """Отсутствие url → ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            FillRagRequest(
                __id="rec-001",
                __name="Test",
                __createdAt="2025-01-15T10:30:00Z",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("url",) for e in errors)

    def test_missing_required_id_raises_error(self):
        """Отсутствие __id → ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            FillRagRequest(
                url="https://example.com",
                __name="Test",
                __createdAt="2025-01-15T10:30:00Z",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("__id",) for e in errors)

    def test_missing_required_name_raises_error(self):
        """Отсутствие __name → ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            FillRagRequest(
                url="https://example.com",
                __id="rec-001",
                __createdAt="2025-01-15T10:30:00Z",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("__name",) for e in errors)

    def test_missing_required_created_at_raises_error(self):
        """Отсутствие __createdAt → ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            FillRagRequest(
                url="https://example.com",
                __id="rec-001",
                __name="Test",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("__createdAt",) for e in errors)


class TestFillRagRequestOptionalDefaults:
    """Тесты значений по умолчанию для опциональных полей."""

    def test_optional_fields_default_to_none(self):
        """Опциональные поля по умолчанию None."""
        request = FillRagRequest(
            url="https://example.com/doc/1",
            __id="rec-001",
            __name="Test Document",
            __createdAt="2025-01-15T10:30:00Z",
        )

        assert request.task_id is None
        assert request.subject is None
        assert request.description is None
        assert request.counterparty is None
        assert request.decision_maker is None
        assert request.register_name is None
        assert request.registration_date is None


class TestFillRagRequestSerialization:
    """Тесты сериализации FillRagRequest."""

    def test_model_dump_by_alias_uses_alias_keys(self):
        """model_dump(by_alias=True) использует алиасы в ключах."""
        request = FillRagRequest(
            url="https://example.com/doc/1",
            __id="rec-001",
            __name="Test Document",
            __createdAt="2025-01-15T10:30:00Z",
            subject="Test Subject",
            decisionMaker="John Doe",
            __register_name="Contracts",
            registrationDate="2025-06-01",
        )

        dumped = request.model_dump(by_alias=True)

        # Проверяем что ключи — это алиасы
        assert "__id" in dumped
        assert "__name" in dumped
        assert "__createdAt" in dumped
        assert "decisionMaker" in dumped
        assert "__register_name" in dumped
        assert "registrationDate" in dumped
        assert "url" in dumped

        # Проверяем что имена полей НЕ используются как ключи
        assert "id" not in dumped
        assert "name" not in dumped
        assert "created_at" not in dumped
        assert "decision_maker" not in dumped
        assert "register_name" not in dumped
        assert "registration_date" not in dumped

    def test_model_dump_by_alias_values_correct(self):
        """model_dump(by_alias=True) содержит правильные значения."""
        request = FillRagRequest(
            url="https://example.com/doc/1",
            __id="rec-001",
            __name="Test Document",
            __createdAt="2025-01-15T10:30:00Z",
            decisionMaker="John Doe",
        )

        dumped = request.model_dump(by_alias=True)

        assert dumped["url"] == "https://example.com/doc/1"
        assert dumped["__id"] == "rec-001"
        assert dumped["__name"] == "Test Document"
        assert dumped["__createdAt"] == "2025-01-15T10:30:00Z"
        assert dumped["decisionMaker"] == "John Doe"

    def test_model_dump_without_alias_uses_field_names(self):
        """model_dump() без by_alias использует имена полей."""
        request = FillRagRequest(
            url="https://example.com/doc/1",
            __id="rec-001",
            __name="Test Document",
            __createdAt="2025-01-15T10:30:00Z",
        )

        dumped = request.model_dump()

        assert "id" in dumped
        assert "name" in dumped
        assert "created_at" in dumped
        assert "__id" not in dumped
        assert "__name" not in dumped
        assert "__createdAt" not in dumped


class TestFillRagRequestFromMetadata:
    """Тесты создания FillRagRequest из metadata dict (как делает worker_service)."""

    def test_create_from_metadata_dict(self):
        """Создание из metadata dict через **unpack (как в worker_service)."""
        metadata = {
            "url": "https://example.com/doc/123",
            "__id": "rec-abc-123",
            "__name": "Test Document",
            "__createdAt": "2025-01-15T10:30:00Z",
            "subject": "Test Subject",
            "description": "Test description",
            "counterparty": "Test Counterparty",
            "decisionMaker": "Test Decision Maker",
            "__register_name": "Test Register",
            "registrationDate": "2025-01-10",
        }

        request = FillRagRequest(**metadata)

        assert request.url == "https://example.com/doc/123"
        assert request.id == "rec-abc-123"
        assert request.name == "Test Document"
        assert request.created_at == "2025-01-15T10:30:00Z"
        assert request.subject == "Test Subject"
        assert request.description == "Test description"
        assert request.counterparty == "Test Counterparty"
        assert request.decision_maker == "Test Decision Maker"
        assert request.register_name == "Test Register"
        assert request.registration_date == "2025-01-10"

    def test_create_from_metadata_with_minimal_fields(self):
        """Создание из metadata dict с минимальными обязательными полями."""
        metadata = {
            "url": "https://example.com/doc/1",
            "__id": "rec-001",
            "__name": "Minimal Doc",
            "__createdAt": "2025-01-01T00:00:00Z",
        }

        request = FillRagRequest(**metadata)

        assert request.url == "https://example.com/doc/1"
        assert request.id == "rec-001"
        assert request.name == "Minimal Doc"
        assert request.created_at == "2025-01-01T00:00:00Z"
        # Опциональные поля — None
        assert request.subject is None
        assert request.description is None

    def test_create_from_metadata_with_extra_fields_ignored(self):
        """Лишние поля в metadata не вызывают ошибку (Pydantic по умолчанию игнорирует)."""
        metadata = {
            "url": "https://example.com/doc/1",
            "__id": "rec-001",
            "__name": "Test Doc",
            "__createdAt": "2025-01-01T00:00:00Z",
            "extra_field": "should be ignored",
            "another_extra": 42,
        }

        request = FillRagRequest(**metadata)

        assert request.url == "https://example.com/doc/1"
        assert request.id == "rec-001"

    def test_create_from_metadata_missing_required_raises(self):
        """Неполный metadata dict → ValidationError."""
        metadata = {
            "url": "https://example.com/doc/1",
            "__id": "rec-001",
            # отсутствует __name и __createdAt
        }

        with pytest.raises(ValidationError):
            FillRagRequest(**metadata)
