# ── OCR Service Dockerfile ──
FROM python:3.11-slim AS base

# Системные зависимости для PyMuPDF, Pillow, asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        libmupdf-dev \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Установка Python-зависимостей (отдельный слой для кэширования)
COPY requirement.txt .
RUN pip install --no-cache-dir -r requirement.txt

# Копирование исходного кода
COPY . .

# Порт берётся из переменной окружения APP_PORT (по умолчанию 8000)
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000

EXPOSE ${APP_PORT}

# Healthcheck через встроенный endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${APP_PORT}/ || exit 1

CMD ["sh", "-c", "uvicorn main:app --reload --host ${APP_HOST} --port ${APP_PORT}"]
