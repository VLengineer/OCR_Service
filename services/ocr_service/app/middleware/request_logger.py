"""
Middleware для логирования всех HTTP запросов.
"""
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для логирования всех входящих HTTP запросов."""

    async def dispatch(self, request: Request, call_next):
        """Обработка запроса с логированием."""
        start_time = time.time()
        
        # Логируем начало запроса
        logger.info(
            "→ %s %s | Client: %s",
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown"
        )
        
        # Логируем query параметры если есть
        if request.url.query:
            logger.debug("Query params: %s", request.url.query)
        
        try:
            # Выполняем запрос
            response = await call_next(request)
            
            # Логируем результат
            process_time = time.time() - start_time
            logger.info(
                "← %s %s | Status: %d | Time: %.3fs",
                request.method,
                request.url.path,
                response.status_code,
                process_time
            )
            
            # Добавляем заголовок с временем обработки
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as e:
            # Логируем исключения
            process_time = time.time() - start_time
            logger.error(
                "✗ %s %s | Error: %s | Time: %.3fs",
                request.method,
                request.url.path,
                str(e),
                process_time,
                exc_info=True
            )
            raise
