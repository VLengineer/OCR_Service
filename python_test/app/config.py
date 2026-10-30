"""Application configuration loaded from environment variables / .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pydantic-settings configuration.

    All values can be provided via environment variables or a local `.env` file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # JWT authentication
    jwt_secret: str = "jxdsnHNwSugOWRGjJ5-ERdwHUUYMNnAtoweGm4PCh2g2H9VM5B1BAbiGka81Dlxv"
    jwt_algorithm: str = "HS256"

    # External OCR API (n8n webhook)
    ocr_api_url: str  # required, no default
    ocr_api_timeout: int = 60

    # Upload limits
    max_file_size_mb: int = 50


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
