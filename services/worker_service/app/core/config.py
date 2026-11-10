"""
Конфигурация worker_service.
Значения читаются из переменных окружения (или .env файла).
Без JWT — воркер является внутренним сервисом.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


class Settings(BaseSettings):
    """Конфигурация воркера."""

    # ──────────────────────────────────────────────
    # Приложение
    # ──────────────────────────────────────────────
    app_host: str = Field(default="0.0.0.0", description="Хост FastAPI-сервера")
    app_port: int = Field(default=8001, description="Порт FastAPI-сервера")
    log_level: str = Field(default="INFO", description="Уровень логирования")

    # ──────────────────────────────────────────────
    # База данных (PostgreSQL)
    # ──────────────────────────────────────────────
    postgres_user: str = Field(default="postgres", description="Пользователь PostgreSQL")
    postgres_password: str = Field(default="postgres", description="Пароль PostgreSQL")
    postgres_db: str = Field(default="ocr_db", description="Имя базы данных PostgreSQL")
    postgres_host: str = Field(default="postgres", description="Хост PostgreSQL")
    postgres_port: int = Field(default=5432, description="Порт PostgreSQL")

    @property
    def database_url(self) -> str:
        """Строка подключения к PostgreSQL для asyncpg через SQLAlchemy."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ──────────────────────────────────────────────
    # n8n вебхуки
    # ──────────────────────────────────────────────
    n8n_base_url: str = Field(
        default="http://localhost:5678",
        description="Базовый URL n8n",
    )
    n8n_ocr_webhook_path: str = Field(
        default="/webhook/ocr",
        description="Путь вебхука для OCR-запросов",
    )
    n8n_create_doc_webhook_path: str = Field(
        default="/webhook/create_document",
        description="Путь вебхука для создания документа",
    )
    n8n_fill_rag_webhook_path: str = Field(
        default="/webhook-test/fill_rag",
        description="Путь вебхука для fill_rag задач",
    )
    n8n_request_timeout_sec: int = Field(
        default=30,
        description="Таймаут HTTP-запросов к n8n (секунды)",
    )

    @property
    def n8n_ocr_webhook_url(self) -> str:
        return f"{self.n8n_base_url.rstrip('/')}{self.n8n_ocr_webhook_path}"

    @property
    def n8n_create_doc_webhook_url(self) -> str:
        return f"{self.n8n_base_url.rstrip('/')}{self.n8n_create_doc_webhook_path}"

    @property
    def n8n_fill_rag_webhook_url(self) -> str:
        return f"{self.n8n_base_url.rstrip('/')}{self.n8n_fill_rag_webhook_path}"

    # ──────────────────────────────────────────────
    # Воркер
    # ──────────────────────────────────────────────
    worker_poll_interval_sec: int = Field(
        default=5,
        description="Интервал опроса БД в секундах",
    )
    worker_max_retries: int = Field(
        default=3,
        description="Максимальное количество retry для задачи",
    )

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
