# Document Text Extraction Microservice (OCR & Text Extraction)

Асинхронный микросервис на **FastAPI**: принимает документ в base64, определяет его тип
по магическим числам (`python-magic`) и извлекает текст.

- **Изображения** (jpeg/png/tiff/bmp) → внешний OCR API (n8n webhook).
- **Редактируемый PDF** → локальное извлечение текста (PyMuPDF).
- **Сканированный PDF** (нет извлекаемого текста) → рендер страниц в PNG (DPI=300)
  и **строго последовательные** вызовы OCR API (без `asyncio.gather`).
- **Word (.docx)** → локальное извлечение (python-docx).
- Доступ защищён **JWT** (заголовок `Authorization: Bearer <token>`).

## Структура проекта

```
app/
├── main.py              # FastAPI app, логирование, роутеры, обработчик 500
├── config.py            # Pydantic Settings (.env)
├── dependencies.py      # Зависимость проверки JWT
├── schemas/documents.py # Pydantic модели Request/Response
├── services/
│   ├── file_detector.py # Определение MIME-типа (magic.from_buffer)
│   ├── ocr_client.py    # Асинхронный клиент n8n OCR API (httpx)
│   ├── pdf_service.py   # PyMuPDF: текстовый extract / рендер + OCR
│   ├── word_service.py  # python-docx extraction
│   └── extraction.py    # Оркестратор (ветвление по MIME-типу)
└── api/v1/extract.py    # Роутер POST /api/v1/extract
```

## Конфигурация (.env)

| Переменная         | Тип  | По умолчанию | Описание                          |
|--------------------|------|--------------|-----------------------------------|
| `JWT_SECRET`       | str  | — (обязат.)  | Секрет подписи JWT                |
| `JWT_ALGORITHM`    | str  | `HS256`      | Алгоритм JWT                      |
| `OCR_API_URL`      | str  | — (обязат.)  | URL вебхука n8n для распознавания |
| `OCR_API_TIMEOUT`  | int  | `60`         | Таймаут OCR-запроса, сек          |
| `MAX_FILE_SIZE_MB` | int  | `50`         | Максимальный размер файла, МБ     |

См. `.env.example`.

## Системные зависимости

`python-magic` требует системную библиотеку **libmagic**:

```bash
apt-get install -y libmagic1   # Debian/Ubuntu
brew install libmagic          # macOS
```

В Docker-образе она устанавливается автоматически (см. `Dockerfile`).

## Запуск локально

```bash
pip install -r requirements.txt
cp .env.example .env   # заполните JWT_SECRET и OCR_API_URL
uvicorn app.main:app --reload
```

Swagger UI: http://127.0.0.1:8000/docs

## Запуск в Docker

```bash
docker build -t doc-extractor .
docker run --env-file .env -p 8000:8000 doc-extractor
# или
docker compose up --build
```

## Контракт API

### `POST /api/v1/extract`

Заголовки: `Authorization: Bearer <jwt_token>`, `Content-Type: application/json`

Запрос:
```json
{ "document_base64": "<base64 файла>" }
```

Ответ `200 OK`:
```json
{
  "file_type": "application/pdf",
  "pages_count": 5,
  "text": "извлечённый текст ..."
}
```
Для изображений и Word `pages_count = 1`. Тексты страниц сканированного PDF
разделены `\n\n--- Page Break ---\n\n`.

### Вызов внешнего OCR API (n8n)

`POST {OCR_API_URL}` с телом `{"image_base64": "..."}`, ожидается ответ `{"text": "..."}`.

## Коды ошибок (единый формат `{"detail": "..."}`)

| Код | Причина                                         |
|-----|-------------------------------------------------|
| 400 | Невалидный base64 / некорректное тело запроса   |
| 401 | Отсутствует/невалидный JWT                      |
| 413 | Файл больше `MAX_FILE_SIZE_MB`                  |
| 415 | Неподдерживаемый MIME-тип                       |
| 500 | Внутренняя ошибка (в т.ч. повреждённый PDF/DOCX)|
| 502 | Ошибка/таймаут внешнего OCR API                 |

## Пример использования

```bash
TOKEN=$(python -c "import jwt; print(jwt.encode({'sub':'demo'}, 'change-me-super-secret', algorithm='HS256'))")
B64=$(base64 -w0 scan.pdf)
curl -X POST http://localhost:8000/api/v1/extract \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"document_base64\": \"$B64\"}"
```
