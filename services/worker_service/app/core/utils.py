"""Утилиты приложения."""

from urllib.parse import urlsplit, urlunsplit


def sanitize_url(url: str) -> str:
    """Удаляет query/fragment и потенциально чувствительные userinfo из URL.

    Оставляет только схему, хост, порт и путь. Для невалидных URL возвращает
    исходную строку без выбрасывания исключений.
    """
    try:
        parsed = urlsplit(url)
    except Exception:
        return url

    try:
        sanitized_netloc = ""
        if parsed.netloc:
            hostname = parsed.hostname
            if hostname is None:
                sanitized_netloc = parsed.netloc.rsplit("@", 1)[-1]
            else:
                host = f"[{hostname}]" if ":" in hostname else hostname
                try:
                    port = parsed.port
                except ValueError:
                    port = None

                sanitized_netloc = f"{host}:{port}" if port is not None else host

        return urlunsplit((parsed.scheme, sanitized_netloc, parsed.path, "", ""))
    except Exception:
        return url
