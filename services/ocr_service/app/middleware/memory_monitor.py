"""
Middleware для мониторинга использования памяти.
Логирует потребление памяти до и после каждого запроса.
"""

import ctypes
import logging
import resource
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


def _malloc_trim() -> None:
    """Принудительно возвращает память glibc allocator обратно в ОС."""
    try:
        libc = ctypes.CDLL("libc.so.6")
        libc.malloc_trim(0)
    except (OSError, AttributeError):
        pass


def _get_memory_usage_mb() -> float:
    """Возвращает текущее использование памяти процессом в МБ (RSS из /proc/self/status)."""
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    # Формат: "VmRSS:    123456 kB"
                    return int(line.split()[1]) / 1024
    except (FileNotFoundError, ValueError, IndexError):
        pass
    # Fallback для не-Linux систем
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def _get_cgroup_memory_mb() -> float:
    """Возвращает реальное потребление памяти всем контейнером (cgroup) в МБ."""
    try:
        with open("/sys/fs/cgroup/memory.current") as f:
            return int(f.read().strip()) / (1024 * 1024)
    except (FileNotFoundError, ValueError):
        pass
    try:
        with open("/sys/fs/cgroup/memory/memory.usage_in_bytes") as f:
            return int(f.read().strip()) / (1024 * 1024)
    except (FileNotFoundError, ValueError):
        pass
    return 0.0


def _get_peak_memory_mb() -> float:
    """Возвращает пиковое использование памяти процессом в МБ."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


class MemoryMonitorMiddleware(BaseHTTPMiddleware):
    """Middleware для мониторинга использования памяти на каждом запросе."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Пропускаем health check
        if request.url.path in ["/", "/health"]:
            return await call_next(request)

        memory_before = _get_memory_usage_mb()
        cgroup_before = _get_cgroup_memory_mb()
        peak_before = _get_peak_memory_mb()
        start_time = time.time()

        logger.info(
            "Запрос начат: %s %s, process RSS: %.2f MB, cgroup: %.2f MB, пик: %.2f MB",
            request.method,
            request.url.path,
            memory_before,
            cgroup_before,
            peak_before,
        )

        try:
            response = await call_next(request)
        except Exception as e:
            memory_after = _get_memory_usage_mb()
            cgroup_after = _get_cgroup_memory_mb()
            peak_after = _get_peak_memory_mb()
            logger.error(
                "Запрос упал с ошибкой: %s %s, ошибка: %s, "
                "process RSS: %.2f MB (изменение: %+.2f MB), cgroup: %.2f MB (изменение: %+.2f MB), пик: %.2f MB",
                request.method,
                request.url.path,
                str(e),
                memory_after,
                memory_after - memory_before,
                cgroup_after,
                cgroup_after - cgroup_before,
                peak_after,
            )
            raise

        memory_after = _get_memory_usage_mb()
        cgroup_after = _get_cgroup_memory_mb()
        peak_after = _get_peak_memory_mb()
        duration = time.time() - start_time

        memory_change = memory_after - memory_before
        cgroup_change = cgroup_after - cgroup_before

        # Принудительно возвращаем память в ОС после каждого запроса
        import gc
        gc.collect()
        _malloc_trim()

        # Логируем с предупреждением, если память выросла значительно
        if cgroup_change > 100:  # Больше 100 MB
            logger.warning(
                "Запрос завершён: %s %s, длительность: %.2f сек, "
                "process RSS: %.2f MB (%+.2f MB), cgroup: %.2f MB (%+.2f MB ⚠️), пик: %.2f MB",
                request.method,
                request.url.path,
                duration,
                memory_after,
                memory_change,
                cgroup_after,
                cgroup_change,
                peak_after,
            )
        else:
            logger.info(
                "Запрос завершён: %s %s, длительность: %.2f сек, "
                "process RSS: %.2f MB (%+.2f MB), cgroup: %.2f MB (%+.2f MB), пик: %.2f MB",
                request.method,
                request.url.path,
                duration,
                memory_after,
                memory_change,
                cgroup_after,
                cgroup_change,
                peak_after,
            )

        return response
