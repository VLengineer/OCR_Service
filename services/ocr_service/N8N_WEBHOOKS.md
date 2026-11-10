# OCR Service — Документация n8n вебхуков

> Документация для разработчиков n8n workflow.
> Описывает вебхуки, на которые OCR-сервис отправляет запросы.

---

## Конфигурация

Адреса вебхуков формируются из переменных окружения:

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `N8N_BASE_URL` | Базовый URL n8n | `http://localhost:5678` |
| `N8N_OCR_WEBHOOK_PATH` | Путь для OCR-запросов | `/webhook/ocr` |
| `N8N_CREATE_DOC_WEBHOOK_PATH` | Путь для создания документа | `/webhook/create_elma_document` |
| `N8N_RECOGNIZE_WEBHOOK_PATH` | Путь для распознавания | `/webhook/recognize_document` |
| `N8N_REQUEST_TIMEOUT_SEC` | Таймаут HTTP-запросов (сек) | `30` |
| `N8N_TOKEN` | Токен доступа к n8n | `token` |

**Итоговые URL (пример):**
```
POST http://localhost:5678/webhook/ocr
POST http://localhost:5678/webhook/create_elma_document
POST http://localhost:5678/webhook/recognize_document
```

---

## 1. Webhook: `/webhook/ocr`

**Назначение:** OCR-обработка документа (отправка страниц на распознавание).

**Вызывается из:** `RequestService.ocr_request()` при обработке задачи через `POST /api/v1/tasks/{task_id}/process`.

### Формат запроса

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_id": "elma-doc-123",
  "base64_document": ["<base64 страницы 1>", "<base64 страницы 2>"],
  "document_type": "pdf_scan"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `task_id` | UUID \| null | ID задачи в очереди OCR-сервиса |
| `document_id` | string | ID документа из ELMA365 |
| `base64_document` | string[] | Массив страниц документа в base64 |
| `document_type` | string \| null | Тип документа (если определён) |

### Ожидаемый ответ

n8n должен вернуть JSON с результатом OCR. Структура определяется workflow.

### Заголовки

```
Content-Type: application/json
```

---

## 2. Webhook: `/webhook/create_elma_document`

**Назначение:** Создание документа с распознанным текстом в ELMA365.

**Вызывается из:** `RequestService.create_document()` после успешного распознавания текстовых документов (Word, PDF с текстом).

### Формат запроса

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_id": "elma-doc-123",
  "raw_text": "Распознанный текст документа...",
  "document_type": "word"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `task_id` | UUID \| null | ID задачи в очереди OCR-сервиса |
| `document_id` | string | ID документа из ELMA365 |
| `raw_text` | string | Распознанный/извлечённый текст документа |
| `document_type` | string \| null | Тип документа |

### Ожидаемый ответ

n8n должен вернуть JSON с результатом создания документа. Структура определяется workflow.

### Заголовки

```
Content-Type: application/json
```

---

## 3. Webhook: `/webhook/recognize_document`

**Назначение:** Распознавание документа (используется в `RecognitionProxyService`).

**Вызывается из:** `RequestService.recognize_document()` при вызове `POST /api/v1/ocr/recognize`.

### Формат запроса

```json
{
  "document_id": "auto-detected-id",
  "document_base64": "<base64 содержимое файла>",
  "document_type": "pdf_scan"
}
```

| Поле | Тип | Описание |
|------|-----|----------|
| `document_id` | string | ID документа (генерируется внутри сервиса) |
| `document_base64` | string | Документ в base64 |
| `document_type` | string | Тип документа (определяется автоматически через `DocumentConverter`) |

### Ожидаемый ответ

n8n должен вернуть JSON с полем `extracted_text`:

```json
{
  "extracted_text": "Распознанный текст документа..."
}
```

### Заголовки

```
Content-Type: application/json
```

---

## Схема взаимодействия

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Клиент    │────▶│   OCR Service    │────▶│     n8n     │
│  (ELMA365)  │     │  (FastAPI)       │     │  (workflow) │
└─────────────┘     └──────────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  PostgreSQL  │
                    │  (очередь)   │
                    └──────────────┘
```

### Поток обработки документа (асинхронный)

```
1. POST /api/v1/ocr/documents
   └─▶ Определение типа документа
   └─▶ Если IMAGE/PDF_SCAN → создание задачи в БД (state: waiting)
   └─▶ Если WORD/PDF_TEXT → извлечение текста → POST /webhook/create_elma_document

2. POST /api/v1/tasks/{task_id}/process
   └─▶ state: waiting → processing
   └─▶ POST /webhook/ocr (отправка страниц на распознавание)
   └─▶ state: processing → completed / error
```

### Поток распознавания (синхронный)

```
POST /api/v1/ocr/recognize
  └─▶ Определение типа документа (DocumentConverter)
  └─▶ POST /webhook/recognize_document
  └─▶ Возврат extracted_text клиенту
```

---

## Обработка ошибок

| Ситуация | Действие OCR-сервиса |
|----------|----------------------|
| Таймаут n8n (>30 сек) | Логирование + проброс ошибки (`httpx.TimeoutException`) |
| HTTP 4xx/5xx от n8n | Логирование + проброс ошибки (`httpx.HTTPStatusError`) |
| Невалидный JSON ответ | Логирование + `ValueError` → HTTP 400 клиенту |
| Недоступность n8n | Логирование + `ConnectionError` → HTTP 500 клиенту |

---

## Примеры curl для тестирования вебхуков

### Тест `/webhook/ocr`

```bash
curl -X POST http://localhost:5678/webhook/ocr \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "document_id": "test-doc-001",
    "base64_document": ["iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="],
    "document_type": "image"
  }'
```

### Тест `/webhook/create_elma_document`

```bash
curl -X POST http://localhost:5678/webhook/create_elma_document \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "550e8400-e29b-41d4-a716-446655440000",
    "document_id": "test-doc-001",
    "raw_text": "Тестовый текст документа",
    "document_type": "word"
  }'
```

### Тест `/webhook/recognize_document`

```bash
curl -X POST http://localhost:5678/webhook/recognize_document \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "auto-001",
    "document_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
    "document_type": "image"
  }'
```

---

## Настройка n8n workflow

Для каждого вебхука в n8n необходимо:

1. Создать **Webhook** ноду с соответствующим путём (`/webhook/ocr`, `/webhook/create_elma_document`, `/webhook/recognize_document`)
2. Установить метод **POST**
3. Установить **Response Mode** = "When waiting for Webhook response" (для синхронного ответа)
4. Обработать входящий JSON и вернуть результат

### Требования к n8n workflow

- Вебхуки должны принимать `Content-Type: application/json`
- Для `/webhook/recognize_document` — обязательно вернуть JSON с полем `extracted_text`
- Обработка ошибок должна возвращать соответствующие HTTP-статусы (4xx/5xx)
