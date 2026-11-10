"""
JWT-утилиты: создание и верификация токенов.
Алгоритм: HS256 (HMAC-SHA256).
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import settings


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """
    Создаёт JWT access-токен.

    Args:
        data: payload (например, {"sub": "username"})
        expires_delta: кастомное время жизни; по умолчанию — ACCESS_TOKEN_EXPIRE_MINUTES

    Returns:
        Закодированный JWT-токен.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(
        to_encode,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def verify_token(token: str) -> dict[str, Any] | None:
    """
    Декодирует и проверяет JWT-токен.

    Returns:
        Payload dict при успехе, None при невалидном/просроченном токене.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.PyJWTError:
        return None
