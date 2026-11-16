from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Базовый класс для SQLAlchemy моделей"""
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
    expire_on_commit=True,  # Освобождать объекты после коммита для экономии памяти
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency для FastAPI.
    Возвращает сессию БД для использования в эндпоинтах.

    Контекстный менеджер async_session() сам закрывает сессию
    и возвращает соединение в пул, поэтому отдельный close() не нужен:
    двойное закрытие может маскировать утечку соединений.
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
            logger.debug("Сессия БД: транзакция зафиксирована")
        except Exception as exc:
            # Откатываем транзакцию, чтобы соединение не осталось
            # в «грязном» состоянии и не удерживало ресурсы пула
            await session.rollback()
            logger.error(
                "Сессия БД: ошибка, транзакция откачена: %s",
                type(exc).__name__,
            )
            raise

async def init_db():
    """
    Инициализация БД: создание таблиц.
    Вызывается при старте приложения.
    """
    async with engine.begin() as conn:
        logger.info("Creating database tables...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")

async def close_db():
    """
    Закрытие подключения к БД.
    Вызывается при остановке приложения.
    """
    await engine.dispose()
    logger.info("Database connection closed")
