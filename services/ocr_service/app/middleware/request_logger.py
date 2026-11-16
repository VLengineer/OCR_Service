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

    @staticmethod
    def _get_request_size(request: Request) -> int | None:
        """Возвращает размер тела запроса из заголовка Content-Length.

        Тело запроса не читается, чтобы не буферизовать большие
        base64-пейлоады в памяти: чтение request.body() загружает весь
        поток и может в разы увеличить потребление памяти на запрос.
        """
        content_length = request.headers.get("content-length")
        if content_length is None:
            return None
        try:
            return int(content_length)
        except ValueError:
            return None

    @staticmethod
    def _get_response_size(response: Response) -> int | None:
        """Возвращает размер тела ответа из заголовка Content-Length."""
        content_length = response.headers.get("content-length")
        if content_length is None:
            return None
        try:
            return int(content_length)
        except ValueError:
            return None

    async def dispatch(self, request: Request, call_next):
        """Обработка запроса с логированием."""
        start_time = time.time()
        request_size = self._get_request_size(request)

        # Логируем начало запроса (размер берём из Content-Length,
        # тело запроса не читаем, чтобы не нагружать память)
        if request_size is not None:
            logger.info(
                "→ %s %s | Client: %s | ReqSize: %d B",
                request.method,
                request.url.path,
                request.client.host if request.client else "unknown",
                request_size,
            )
        else:
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
            response_size = self._get_response_size(response)

            if response_size is not None:
                logger.info(
                    "← %s %s | Status: %d | Time: %.3fs | RespSize: %d B",
                    request.method,
                    request.url.path,
                    response.status_code,
                    process_time,
                    response_size,
                )
            else:
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
