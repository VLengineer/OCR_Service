"""
Pydantic-модели для worker_service.
Скопированы из ocr_service без изменений для совместимости.
"""

from pydantic import Field, BaseModel
from uuid import UUID
from enum import StrEnum
from typing import List, Optional
from datetime import datetime


class State(StrEnum):
    WAITING = "waiting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class CallType(StrEnum):
    """Типы задач, поддерживаемых воркером."""
    OCR = "ocr"
    FILL_RAG = "fill_rag"


class Task(BaseModel):
    """Очередь задач (соответствует модели БД)."""

    id: UUID = Field(description="ID задачи в очереди")
    document_id: str = Field(description="ID документа из ELMA365")
    document_type: str | None = Field(default=None, description="Тип документа из ELMA365")
    state: State = Field(default=State.WAITING, description="Состояние задачи")
    retry_count: int = Field(default=0, description="Количество попыток обработки")
    base64_document: List[str] = Field(
        default_factory=list,
        description="Массив страниц в формате base64",
    )
    call_type: CallType = Field(default=CallType.OCR, description="Тип задачи")
    metadata: Optional[dict] = Field(default=None, description="Дополнительные данные задачи")
    created_at: datetime = Field(description="Время создания задачи")
    updated_at: datetime = Field(description="Время последнего обновления")

    model_config = {"from_attributes": True}


class OCRRequest(BaseModel):
    """Запрос к n8n webhook/ocr для распознавания текста."""

    task_id: UUID | None = Field(default=None, description="ID задачи")
    document_id: str = Field(description="ID документа из ELMA365")
    base64_document: List[str] = Field(
        default_factory=list,
        description="Массив страниц в формате base64",
    )
    document_type: str | None = Field(default=None, description="Тип документа")


class DocumentRequest(BaseModel):
    """Запрос к n8n webhook/create_document для создания документа."""

    task_id: UUID | None = Field(default=None, description="ID задачи")
    document_id: str = Field(description="ID документа из ELMA365")
    raw_text: str = Field(description="Распознанный текст из документа")
    document_type: str | None = Field(default=None, description="Тип документа")


class FillRagRequest(BaseModel):
    """Запрос к n8n webhook/fill_rag для заполнения RAG данными."""

    model_config = {"populate_by_name": True}

    task_id: UUID | None = Field(default=None, description="ID задачи")
    url: str = Field(description="URL документа")
    id: str = Field(alias="__id", description="ID записи")
    name: str = Field(alias="__name", description="Имя записи")
    subject: Optional[str] = Field(default=None, description="Тема/предмет")
    description: Optional[str] = Field(default=None, description="Описание")
    created_at: str = Field(alias="__createdAt", description="Дата создания записи")
    counterparty: Optional[str] = Field(default=None, description="Контрагент")
    decision_maker: Optional[str] = Field(default=None, alias="decisionMaker", description="Лицо, принимающее решение")
    register_name: Optional[str] = Field(default=None, alias="__register_name", description="Имя реестра")
    registration_date: Optional[str] = Field(default=None, alias="registrationDate", description="Дата регистрации")
