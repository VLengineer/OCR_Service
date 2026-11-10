from sqlalchemy import Column, String, JSON, DateTime, CheckConstraint, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.repositories.database import Base
from uuid import uuid4
from datetime import datetime


class TaskModel(Base):
    """
    SQLAlchemy модель таблицы task.
    Соответствует схеме из init_db/01_init_task_table.sql
    """
    __tablename__ = "task"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
        comment="ID задачи в очереди"
    )

    document_id = Column(
        String,
        nullable=False,
        comment="ID документа из ELMA365"
    )

    document_type = Column(
        String(50),
        nullable=True,
        comment="Тип документа из ELMA365"
    )

    state = Column(
        String(16),
        nullable=False,
        default="waiting",
        server_default="waiting",
        comment="Состояние задачи: waiting, processing, completed, error"
    )

    base64_document = Column(
        JSON,
        nullable=True,
        comment='Массив страниц в формате base64: [{"base64": "..."}, ...]'
    )

    retry_count = Column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Количество попыток обработки"
    )

    call_type = Column(
        String(16),
        nullable=False,
        default="ocr",
        server_default="ocr",
        comment="Тип вызова: ocr или fill_rag"
    )

    metadata_ = Column(
        "metadata",
        JSON,
        nullable=True,
        comment="Дополнительные метаданные задачи (например, данные документа из ELMA365)"
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        comment="Время создания задачи"
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Время последнего обновления"
    )

    __table_args__ = (
        CheckConstraint(
            "state IN ('waiting', 'processing', 'completed', 'error')",
            name="check_task_state"
        ),
        CheckConstraint(
            "call_type IN ('ocr', 'fill_rag')",
            name="check_task_call_type"
        ),
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, document_id={self.document_id}, state={self.state}, call_type={self.call_type})>"
