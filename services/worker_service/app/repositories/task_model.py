"""
SQLAlchemy модель таблицы task.
Идентична модели из ocr_service для совместимости с общей БД.
"""

from sqlalchemy import Column, Integer, String, JSON, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.repositories.database import Base
from uuid import uuid4
from typing import Optional


class TaskModel(Base):
    """SQLAlchemy модель таблицы task."""

    __tablename__ = "task"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
        comment="ID задачи в очереди",
    )

    document_id = Column(
        String,
        nullable=False,
        comment="ID документа из ELMA365",
    )

    document_type = Column(
        String(50),
        nullable=True,
        comment="Тип документа из ELMA365",
    )

    state = Column(
        String(16),
        nullable=False,
        default="waiting",
        server_default="waiting",
        comment="Состояние задачи: waiting, processing, completed, error",
    )

    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Количество попыток обработки",
    )

    base64_document = Column(
        JSON,
        nullable=True,
        comment='Массив страниц в формате base64: [{"base64": "..."}, ...]',
    )

    call_type = Column(
        String(20),
        nullable=False,
        default="ocr",
        server_default="ocr",
        comment="Тип задачи: ocr, fill_rag",
    )

    metadata_ = Column(
        "metadata",
        JSONB,
        nullable=True,
        comment="Дополнительные данные задачи (для fill_rag)",
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        comment="Время создания задачи",
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Время последнего обновления",
    )

    __table_args__ = (
        CheckConstraint(
            "state IN ('waiting', 'processing', 'completed', 'error')",
            name="check_task_state",
        ),
        CheckConstraint(
            "call_type IN ('ocr', 'fill_rag')",
            name="check_task_call_type",
        ),
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, document_id={self.document_id}, state={self.state})>"
