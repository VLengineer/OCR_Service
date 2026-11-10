"""
Эндпоинты авторизации: получение JWT-токена.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.security import create_access_token

router = APIRouter(tags=["Authentication"])


class TokenRequest(BaseModel):
    """Запрос на получение токена."""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Ответ с JWT-токеном."""
    access_token: str
    token_type: str = "bearer"


@router.post(
    "/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Получение JWT-токена",
    description=(
        "Принимает username и password, возвращает JWT-токен. "
        "Для простоты принимает любые credentials и возвращает токен с sub=username."
    ),
)
async def login_for_access_token(request: TokenRequest):
    if not request.username or not request.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password required",
        )

    access_token = create_access_token(data={"sub": request.username})
    return TokenResponse(access_token=access_token)
