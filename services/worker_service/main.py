"""
Worker Service — точка входа FastAPI.

Запуск:
    uvicorn main:app --host 0.0.0.0 --port 8001

Воркер запускается как background task в lifespan.
Health check доступен на GET /
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import settings
from app.repositories.database import init_db, close_db
from app.services.request_service import RequestService
from app.services.worker_service import Worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Управление жизненным циклом:
    - Startup: инициализация БД, запуск воркера
    - Shutdown: остановка воркера, закрытие БД
    """
    # Настройка логирования
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting Worker Service...")

    # Инициализация БД
    await init_db()
    logger.info("Database initialized")

    # Создание сервисов
    request_service = RequestService()
    worker = Worker(request_service)

    # Запуск воркера как background task
    worker_task = asyncio.create_task(worker.start())
    logger.info("Worker task started")

    yield

    # Shutdown
    logger.info("Shutting down Worker Service...")

    # Остановка воркера
    await worker.stop()
    await worker_task
    logger.info("Worker stopped")

    # Закрытие HTTP клиента
    await request_service.close()
    logger.info("HTTP client closed")

    # Закрытие БД
    await close_db()
    logger.info("Database connection closed")


app = FastAPI(
    title="Worker Service",
    version="1.0.0",
    description="Воркер для обработки OCR задач из очереди",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


@app.get("/", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Worker OCR"}
