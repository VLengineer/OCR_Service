"""FastAPI dependency that validates the JWT bearer token."""

import logging
from typing import Any, Dict

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# `auto_error=False` lets us raise our own 401 with a proper detail message.
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_jwt(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """Validate the `Authorization: Bearer <jwt>` header.

    Returns the decoded token payload on success.
    Raises HTTPException(401) if the token is missing or invalid.
    """
    if credentials is None or not credentials.credentials:
        logger.warning("Missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated: missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload: Dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        logger.warning("JWT validation failed: token expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.PyJWTError as exc:
        logger.warning("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    return payload
