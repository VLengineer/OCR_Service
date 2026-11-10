"""
Подключение к PostgreSQL через SQLAlchemy async.
Аналогично ocr_service, но без dependency-генератора сессий —
воркер управляет сессиями самостоятельно.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Базовый класс для SQLAlchemy моделей."""
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.log_level == "DEBUG",
    pool_size=5,
    max_overflow=5,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Инициализация БД: создание таблиц. Вызывается при старте."""
    async with engine.begin() as conn:
        logger.info("Creating database tables...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")


async def close_db() -> None:
    """Закрытие подключения к БД. Вызывается при остановке."""
    await engine.dispose()
    logger.info("Database connection closed")
