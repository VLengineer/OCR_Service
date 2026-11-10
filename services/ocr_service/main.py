"""
OCR Service — точка входа FastAPI.

Запуск:
    uvicorn main:app --host 0.0.0.0 --port 8000

Swagger UI:
    http://localhost:8000/docs
    Кнопка "Authorize" → ввести Bearer <token>
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.repositories.database import init_db, close_db
from app.api.routes import auth_routes, document_routes, task_routes, direct_ocr_routes, recognition_routes, vector_routes, convert_routes, elma_routes

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом: инициализация БД при старте, закрытие при остановке."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("Starting OCR Service...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down OCR Service...")
    await close_db()


app = FastAPI(
    title="OCR Service API",
    version="1.0.0",
    description="Сервис OCR-обработки документов с JWT-авторизацией",
    lifespan=lifespan,
    # Swagger UI настройки
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware (разрешаем все origins для разработки)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(auth_routes.router)
app.include_router(document_routes.router)
app.include_router(task_routes.router)
app.include_router(direct_ocr_routes.router)
app.include_router(recognition_routes.router)
app.include_router(vector_routes.router)
app.include_router(convert_routes.router)
app.include_router(elma_routes.router)


@app.get("/", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "OCR Service"}
