from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict


class Settings(BaseSettings):
    """
    Конфигурация приложения.
    Значения читаются из переменных окружения (или .env файла).
    """

    # ──────────────────────────────────────────────
    # Приложение
    # ──────────────────────────────────────────────
    app_host: str = Field(default="0.0.0.0", description="Хост FastAPI-сервера")
    app_port: int = Field(default=8000, description="Порт FastAPI-сервера")
    log_level: str = Field(default="INFO", description="Уровень логирования")

    # ──────────────────────────────────────────────
    # База данных (PostgreSQL)
    # ──────────────────────────────────────────────
    postgres_user: str = Field(default="postgres", description="Пользователь PostgreSQL")
    postgres_password: str = Field(default="postgres", description="Пароль PostgreSQL")
    postgres_db: str = Field(default="ocr_db", description="Имя базы данных PostgreSQL")
    postgres_host: str = Field(default="postgres", description="Хост PostgreSQL (имя сервиса в docker-compose)")
    postgres_port: int = Field(default=5432, description="Порт PostgreSQL")

    @property
    def database_url(self) -> str:
        """Строка подключения к PostgreSQL для asyncpg"""
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

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
        default="/webhook/create_elma_document",
        description="Путь вебхука для создания документа в ELMA365",
    )
    n8n_recognize_webhook_path: str = Field(
        default="/webhook/recognize_document",
        description="Путь вебхука n8n для распознавания документа",
    )
    n8n_request_timeout_sec: int = Field(
        default=30,
        description="Таймаут HTTP-запросов к n8n (секунды)",
    )
    n8n_token: str = Field(
        default='token',
        description="Токен доступа к n8n"
    )

    # ──────────────────────────────────────────────
    # JWT авторизация
    # ──────────────────────────────────────────────
    jwt_secret: str = Field(
        default="your-secret-key-change-in-production",
        description="Секретный ключ для подписи JWT (HS256)",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="Алгоритм подписи JWT",
    )
    access_token_expire_minutes: int = Field(
        default=30,
        description="Время жизни access-токена в минутах",
    )

    # ──────────────────────────────────────────────
    # Ollama Embeddings
    # ──────────────────────────────────────────────
    ollama_host: str = Field(default="ollama", description="Хост Ollama")
    ollama_port: int = Field(default=11435, description="Порт Ollama")
    ollama_embedding_model: str = Field(
        default="hf.co/unsloth/embeddinggemma-2-GGUF:UD-Q6_K_XL",
        description="Модель эмбеддингов Ollama",
    )

    # ──────────────────────────────────────────────
    # ELMA365 API
    # ──────────────────────────────────────────────
    elma_base_url: str = Field(
        default="https://elma365.example.com",
        description="Базовый URL ELMA365",
    )
    elma_token: str = Field(
        default="token",
        description="Токен доступа к ELMA365 API",
    )
    elma_list_path: str = Field(
        default="/api/documents",
        description="Путь для получения списка документов",
    )
    elma_request_timeout_sec: int = Field(
        default=30,
        description="Таймаут HTTP-запросов к ELMA365 (секунды)",
    )

    # ──────────────────────────────────────────────
    # Chunking
    # ──────────────────────────────────────────────
    chunk_size: int = Field(default=500, description="Размер чанка в символах")
    chunk_overlap: int = Field(default=50, description="Overlap между чанками в символах")

    # ──────────────────────────────────────────────
    # Обработка документов
    # ──────────────────────────────────────────────
    max_sheets_per_task: int = Field(
        default=50,
        description="Максимальное количество страниц в одной OCR-задаче",
    )
    supported_image_types: list[str] = Field(
        default=["image/png", "image/jpeg", "image/tiff"],
        description="Поддерживаемые MIME-типы изображений",
    )
    supported_doc_types: list[str] = Field(
        default=[
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ],
        description="Поддерживаемые MIME-типы документов",
    )

    @property
    def n8n_ocr_webhook_url(self) -> str:
        return f"{self.n8n_base_url.rstrip('/')}{self.n8n_ocr_webhook_path}"

    @property
    def n8n_create_doc_webhook_url(self) -> str:
        return f"{self.n8n_base_url.rstrip('/')}{self.n8n_create_doc_webhook_path}"

    @property
    def n8n_recognize_webhook_url(self) -> str:
        return f"{self.n8n_base_url.rstrip('/')}{self.n8n_recognize_webhook_path}"

    @property
    def elma_list_url(self) -> str:
        return f"{self.elma_base_url.rstrip('/')}{self.elma_list_path}"

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
