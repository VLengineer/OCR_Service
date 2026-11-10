"""
Unit-тесты для DocumentTypeRegistry.

Тестируются методы:
- get_valid_types(): возврат множества валидных типов из JSON
- is_valid(): проверка валидности типа документа
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.document_type_registry import DocumentTypeRegistry


VALID_TYPES = [
    "incoming_correspondence",
    "outgoing_contract",
    "invoice",
    "payment",
]


@pytest.fixture
def tmp_json_file(tmp_path: Path) -> Path:
    """Создаёт временный JSON-файл с валидными типами."""
    file_path = tmp_path / "document_types.json"
    file_path.write_text(
        json.dumps({"document_types": VALID_TYPES}),
        encoding="utf-8",
    )
    return file_path


@pytest.fixture
def registry(tmp_json_file: Path) -> DocumentTypeRegistry:
    """Создаёт DocumentTypeRegistry с временным JSON-файлом."""
    return DocumentTypeRegistry(file_path=tmp_json_file)


class TestGetValidTypes:
    """Тесты метода get_valid_types."""

    def test_returns_set_of_valid_types(self, registry: DocumentTypeRegistry):
        """get_valid_types возвращает множество валидных типов из JSON."""
        result = registry.get_valid_types()
        assert result == set(VALID_TYPES)

    def test_returns_empty_set_when_file_not_found(self, tmp_path: Path):
        """get_valid_types возвращает пустое множество, если файл не найден."""
        missing_path = tmp_path / "nonexistent.json"
        registry = DocumentTypeRegistry(file_path=missing_path)
        assert registry.get_valid_types() == set()

    def test_returns_empty_set_when_invalid_json(self, tmp_path: Path):
        """get_valid_types возвращает пустое множество при невалидном JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json{{{", encoding="utf-8")
        registry = DocumentTypeRegistry(file_path=bad_file)
        assert registry.get_valid_types() == set()

    def test_returns_empty_set_when_key_missing(self, tmp_path: Path):
        """get_valid_types возвращает пустое множество, если ключ отсутствует."""
        file_path = tmp_path / "no_key.json"
        file_path.write_text(json.dumps({"other_key": []}), encoding="utf-8")
        registry = DocumentTypeRegistry(file_path=file_path)
        assert registry.get_valid_types() == set()


class TestIsValid:
    """Тесты метода is_valid."""

    def test_is_valid_with_valid_type(self, registry: DocumentTypeRegistry):
        """is_valid возвращает True для типа из списка."""
        assert registry.is_valid("invoice") is True

    def test_is_valid_with_invalid_type(self, registry: DocumentTypeRegistry):
        """is_valid возвращает False для неизвестного типа."""
        assert registry.is_valid("nonexistent_type") is False

    def test_is_valid_with_none(self, registry: DocumentTypeRegistry):
        """is_valid возвращает True для None (None всегда валиден)."""
        assert registry.is_valid(None) is True

    def test_is_valid_with_empty_string(self, registry: DocumentTypeRegistry):
        """is_valid возвращает True для пустой строки."""
        assert registry.is_valid("") is True

    @pytest.mark.parametrize("doc_type", VALID_TYPES)
    def test_is_valid_with_all_valid_types(
        self, registry: DocumentTypeRegistry, doc_type: str
    ):
        """is_valid возвращает True для каждого валидного типа."""
        assert registry.is_valid(doc_type) is True

    def test_is_valid_case_sensitive(self, registry: DocumentTypeRegistry):
        """is_valid регистрозависим."""
        assert registry.is_valid("Invoice") is False
        assert registry.is_valid("INVOICE") is False


class TestDynamicReload:
    """Тесты динамической перезагрузки JSON-файла."""

    def test_dynamic_reload_picks_up_new_types(self, tmp_json_file: Path):
        """При изменении файла get_valid_types возвращает обновлённый список."""
        registry = DocumentTypeRegistry(file_path=tmp_json_file)

        # Первоначальный набор
        initial_types = registry.get_valid_types()
        assert initial_types == set(VALID_TYPES)

        # Обновляем файл — добавляем новый тип
        updated_types = VALID_TYPES + ["new_document_type"]
        tmp_json_file.write_text(
            json.dumps({"document_types": updated_types}),
            encoding="utf-8",
        )

        # После изменения файла — новый тип должен появиться
        reloaded_types = registry.get_valid_types()
        assert "new_document_type" in reloaded_types
        assert reloaded_types == set(updated_types)

    def test_dynamic_reload_picks_up_removed_types(self, tmp_json_file: Path):
        """При удалении типа из файла он перестаёт быть валидным."""
        registry = DocumentTypeRegistry(file_path=tmp_json_file)

        assert registry.is_valid("invoice") is True

        # Удаляем "invoice" из файла
        remaining = [t for t in VALID_TYPES if t != "invoice"]
        tmp_json_file.write_text(
            json.dumps({"document_types": remaining}),
            encoding="utf-8",
        )

        assert registry.is_valid("invoice") is False

    def test_returns_empty_set_after_file_deleted(self, tmp_json_file: Path):
        """После удаления файла get_valid_types возвращает пустое множество."""
        registry = DocumentTypeRegistry(file_path=tmp_json_file)
        assert len(registry.get_valid_types()) > 0

        tmp_json_file.unlink()
        assert registry.get_valid_types() == set()
