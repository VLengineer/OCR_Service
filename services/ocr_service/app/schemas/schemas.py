from pydantic import Field, BaseModel
from uuid import uuid4, UUID
from enum import StrEnum
from typing import List, Optional
from datetime import datetime

class State(StrEnum):
    WAITING = "waiting"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class CallType(StrEnum):
    OCR = "ocr"
    FILL_RAG = "fill_rag"

class ElmaDocument(BaseModel):
    """
    Модель документа, полученного из ELMA365.
    Pydantic v2 не поддерживает поля с leading underscores,
    поэтому Python-имена отличаются от JSON-ключей (aliases).
    """
    url: str | None = Field(default=None, description="URL документа в ELMA365")
    id_: str | None = Field(default=None, alias="__id", description="ID документа в ELMA365")
    name_: str | None = Field(default=None, alias="__name", description="Имя документа")
    subject: str | None = Field(default=None, description="Тема документа")
    description: str | None = Field(default=None, description="Описание документа")
    created_at: str | None = Field(default=None, alias="__createdAt", description="Дата создания")
    counterparty: str | None = Field(default=None, description="Контрагент")
    decision_maker: str | None = Field(default=None, alias="decisionMaker", description="Ответственный")
    register_name_: str | None = Field(default=None, alias="__register_name", description="Имя реестра")
    type_id_: str | None = Field(default=None, alias="__type_id", description="ID типа документа")
    type_name_: str | None = Field(default=None, alias="__type_name", description="Имя типа документа")
    version_: str | None = Field(default=None, alias="__version", description="Версия документа")
    registration_date: str | None = Field(default=None, alias="registrationDate", description="Дата регистрации")

    model_config = {"populate_by_name": True}

class Task(BaseModel):
    """
    Очередь задач (соответствует модели БД)
    """
    id: UUID = Field(description="ID задачи в очереди")
    document_id: str = Field(description="ID документа из ELMA365")
    document_type: str | None = Field(default=None, description="Тип документа из ELMA365")
    state: State = Field(default=State.WAITING, description="Состояние задачи")
    retry_count: int = Field(default=0, description="Количество попыток обработки")
    base64_document: List[str] = Field(default_factory=list, description="Массив страниц в формате base64")
    call_type: CallType = Field(default=CallType.OCR, description="Тип вызова: ocr или fill_rag")
    metadata: Optional[dict] = Field(default=None, description="Дополнительные метаданные задачи")
    created_at: datetime = Field(description="Время создания задачи")
    updated_at: datetime = Field(description="Время последнего обновления")

    model_config = {"from_attributes": True}

class Document(BaseModel):
    """
    Тело запроса полученное из ELMA365
    """
    document_id: str = Field(description="ID документа из ELMA365")
    document_base64: str = Field(description="Документ в формате base64")
    document_type: str | None = Field(default=None, description="Тип документа")

class CallbackResponse(BaseModel):
    """
    Ответ для callback (например, в ELMA365)
    """
    task_id: UUID = Field(description="ID задачи")
    state: State = Field(description="Текущее состояние задачи")
    updated_at: datetime = Field(description="Время обновления состояния")

class OCRRequest(BaseModel):
    """
    Запрос к n8n webhook/ocr для распознавания текста
    """
    task_id: UUID | None = Field(default=None, description="ID задачи")
    document_id: str = Field(description="ID документа из ELMA365")
    base64_document: List[str] = Field(default_factory=list, description="Массив страниц в формате base64")
    document_type: str | None = Field(default=None, description="Тип документа")

class DocumentRequest(BaseModel):
    """
    Запрос к n8n webhook/create_document для создания документа с распознанным текстом
    """
    task_id: UUID | None = Field(default=None, description="ID задачи")
    document_id: str = Field(description="ID документа из ELMA365")
    raw_text: str = Field(description="Распознанный текст из документа")
    document_type: str | None = Field(default=None, description="Тип документа")


class DocumentVectorizeRequest(BaseModel):
    """Запрос на векторизацию текста документа."""
    document_id: str = Field(..., max_length=50, description="ID документа")
    response_id: str | None = Field(default=None, max_length=50, description="ID ответа")
    counterparty_id: str | None = Field(default=None, max_length=50, description="ID контрагента")
    content: str = Field(..., min_length=1, description="Текст документа для векторизации")
    metadata: dict | None = Field(default=None, description="Метаданные документа")


class DocumentVectorizeResponse(BaseModel):
    """Ответ после векторизации документа."""
    document_id: str = Field(description="ID документа")
    chunks_count: int = Field(description="Количество созданных чанков/векторов")


class DocumentConvertRequest(BaseModel):
    """Запрос на конвертацию документа."""
    document_base64: str = Field(description="Документ в формате base64")


class DocumentConvertResponse(BaseModel):
    """Ответ после конвертации документа."""
    document_type: str = Field(description="Тип документа: word, pdf_text, pdf_scan, image")
    document_sheets: List[str] = Field(description="Массив страниц/листов в base64 или текст")


class RecognitionRequest(BaseModel):
    """Запрос на распознавание документа. Принимает только base64, тип определяется внутри."""
    document_base64: str = Field(..., min_length=1, description="Документ в формате base64")


class RecognitionResponse(BaseModel):
    """Ответ распознавания. Содержит только распознанный текст."""
    extracted_text: str = Field(description="Распознанный текст из документа")