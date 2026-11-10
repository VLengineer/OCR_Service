"""
Реестр допустимых типов документов.

Читает список валидных типов из JSON-файла при каждом вызове,
обеспечивая динамическое обновление без перезапуска сервиса.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Путь к файлу с типами документов (относительно этого модуля)
_DOCUMENT_TYPES_PATH = Path(__file__).parent / "document_types.json"


class DocumentTypeRegistry:
    """Реестр допустимых типов документов.

    Читает список типов из JSON-файла при каждом вызове,
    без кеширования. Это позволяет обновлять список типов
    без перезапуска сервиса.
    """

    def __init__(self, file_path: Path | None = None) -> None:
        """Инициализация реестра.

        Args:
            file_path: Путь к JSON-файлу с типами документов.
                Если не указан, используется путь по умолчанию
                относительно модуля.
        """
        self._file_path = file_path or _DOCUMENT_TYPES_PATH

    def get_valid_types(self) -> set[str]:
        """Возвращает множество допустимых типов документов.

        Читает файл при каждом вызове (без кеширования).

        Returns:
            set[str]: Множество допустимых типов документов.
                Пустое множество, если файл не найден или невалиден.
        """
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return set(data.get("document_types", []))
        except FileNotFoundError:
            logger.error(
                "Файл с типами документов не найден: %s", self._file_path
            )
            return set()
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(
                "Ошибка чтения файла с типами документов %s: %s",
                self._file_path,
                e,
            )
            return set()

    def is_valid(self, document_type: str | None) -> bool:
        """Проверяет, является ли тип документа допустимым.

        Args:
            document_type: Тип документа для проверки.

        Returns:
            bool: True, если тип допустим (None, пустая строка
                или присутствует в списке валидных типов).
        """
        if document_type is None or document_type == "":
            return True
        return document_type in self.get_valid_types()
