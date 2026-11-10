"""
SQLAlchemy модель таблицы document_vector_store.
Соответствует схеме из init_db/02_init_vector_data_base.sql.

Примечание: поле embedding объявлено как Text, потому что pgvector
не подключён как SQLAlchemy-расширение. Каст к типу vector делается
в raw SQL при INSERT через sqlalchemy.text().
"""

from sqlalchemy import Column, String, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.repositories.database import Base


class DocumentVectorStoreModel(Base):
    """ORM-модель таблицы document_vector_store."""

    __tablename__ = "document_vector_store"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
        comment="Уникальный идентификатор записи",
    )

    document_id = Column(
        String(50),
        nullable=False,
        comment="ID документа",
    )

    response_id = Column(
        String(50),
        nullable=True,
        comment="ID ответа",
    )

    counterparty_id = Column(
        String(50),
        nullable=True,
        comment="ID контрагента",
    )

    content = Column(
        Text,
        nullable=True,
        comment="Текстовое содержимое чанка",
    )

    # Объявляем как Text, потому что тип VECTOR(768) не поддерживается
    # SQLAlchemy без pgvector-расширения. Каст делается в raw SQL.
    embedding = Column(
        Text,
        nullable=False,
        comment="Векторное представление (хранится как строка, кастится в raw SQL)",
    )

    metadata_ = Column(
        "metadata",
        JSON,
        nullable=True,
        comment="Дополнительные метаданные документа",
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentVectorStore(id={self.id}, document_id={self.document_id})>"
        )
