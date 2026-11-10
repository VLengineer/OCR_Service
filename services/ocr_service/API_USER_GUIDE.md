# OCR Service — Руководство пользователя API

> Документация для потребителей API (ELMA365, внешние клиенты).
> Базовый URL: `http://localhost:9010` (dev) / настраивается через `APP_HOST:APP_PORT`.

---

## Авторизация

Все эндпоинты защищены **JWT-токеном**. Токен передаётся в заголовке `Authorization`:

```
Authorization: Bearer <access_token>
```

### Получение токена

```bash
curl -X POST http://localhost:9010/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin"
```

Ответ:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

---

## Группировка эндпоинтов

| Группа | Префикс | Назначение |
|--------|---------|------------|
| Documents | `/api/v1/ocr/documents` | Приём документов на обработку (асинхронно, через очередь) |
| OCR | `/api/v1/ocr` | Прямая OCR-обработка и распознавание (синхронно) |
| Tasks | `/api/v1/tasks` | Управление задачами очереди |
| Vectors | `/api/v1/vectors` | Векторизация текста документа |
| Convert | `/api/v1/convert` | Конвертация документов |
| ELMA | `/api/v1/elma` | Интеграция с ELMA365 |

---

## 1. Documents — `/api/v1/ocr/documents`

### POST `/api/v1/ocr/documents`

Принимает документ для асинхронной обработки. Тип определяется автоматически:
- Word/PDF с текстом → извлечение текста → отправка в n8n
- Изображение/PDF-скан → создание OCR-задачи в очередь

**Запрос:**
```json
{
  "document_id": "elma-doc-123",
  "document_base64": "<base64 содержимое файла>",
  "document_type": "pdf_scan"
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|:---:|----------|
| `document_id` | string | ✅ | ID документа из ELMA365 |
| `document_base64` | string | ✅ | Документ в формате base64 |
| `document_type` | string \| null | ❌ | Тип документа (`image`, `pdf_scan`, `word`, `pdf_text`). Пустая строка и `null` допустимы — тип определяется автоматически |

**Ответ (202 Accepted):**
```json
{
  "status": "accepted",
  "document_id": "elma-doc-123"
}
```

**Ошибки:**
- `400` — невалидный `document_type`
- `401` — отсутствует/невалидный JWT
- `500` — внутренняя ошибка обработки

---

## 2. OCR — `/api/v1/ocr`

### POST `/api/v1/ocr/recognize`

Распознаёт документ и возвращает **только текст**. Тип документа определяется внутри сервиса.

**Запрос:**
```json
{
  "document_base64": "<base64 содержимое файла>"
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|:---:|----------|
| `document_base64` | string | ✅ | Документ в base64 (минимум 1 символ) |

**Ответ (200 OK):**
```json
{
  "extracted_text": "Распознанный текст документа..."
}
```

**Ошибки:**
- `400` — некорректный ответ от сервиса распознавания
- `401` — отсутствует/невалидный JWT
- `422` — пустой `document_base64`
- `500` — ошибка распознавания

---

### POST `/api/v1/ocr`

Универсальная прямая OCR-обработка (автоопределение типа). Обрабатывает синхронно, минуя очередь.

**Запрос:** (аналогично `/api/v1/documents`)
```json
{
  "document_id": "elma-doc-123",
  "document_base64": "<base64>",
  "document_type": "image"
}
```

**Ответ (200 OK):** Результат обработки от n8n (зависит от типа документа).

---

### POST `/api/v1/ocr/image`

Прямая OCR-обработка изображения (без очереди).

**Запрос:** (аналогично выше)

**Ответ (200 OK):** Результат OCR от n8n.

---

### POST `/api/v1/ocr/pdf-scan`

Прямая OCR-обработка PDF-скана (все страницы, без очереди).

**Запрос:** (аналогично выше)

**Ответ (200 OK):** Результат OCR от n8n.

---

## 3. Tasks — `/api/v1/tasks`

### GET `/api/v1/tasks`

Список задач с опциональным фильтром по состоянию.

**Параметры запроса:**
| Параметр | Тип | Описание |
|----------|-----|----------|
| `state` | string \| null | Фильтр: `waiting`, `processing`, `completed`, `error` |
| `limit` | int | Макс. количество (1–1000, по умолчанию 100) |

**Ответ (200 OK):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "document_id": "elma-doc-123",
    "document_type": "pdf_scan",
    "state": "waiting",
    "retry_count": 0,
    "base64_document": ["..."],
    "call_type": "ocr",
    "metadata": null,
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-01-01T00:00:00"
  }
]
```

---

### GET `/api/v1/tasks/queue`

Следующая задача в состоянии `waiting` (FIFO).

**Ответ (200 OK):** Объект `Task` или `404` если задач нет.

---

### GET `/api/v1/tasks/{task_id}`

Задача по ID.

**Ответ (200 OK):** Объект `Task` или `404`.

---

### POST `/api/v1/tasks/{task_id}/process`

Запускает обработку задачи: `waiting` → `processing` → `completed` / `error`.

**Ответ (200 OK):**
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "state": "completed",
  "updated_at": "2025-01-01T00:05:00"
}
```

---

### DELETE `/api/v1/tasks/{task_id}`

Удаляет задачу.

**Ответ (200 OK):**
```json
{
  "status": "deleted",
  "task_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 4. Vectors — `/api/v1/vectors`

### POST `/api/v1/vectors`

Векторизация текста документа: чанкинг → эмбеддинги (Ollama) → сохранение в БД.

**Запрос:**
```json
{
  "document_id": "elma-doc-123",
  "response_id": "resp-456",
  "counterparty_id": "cp-789",
  "content": "Текст документа для векторизации...",
  "metadata": { "key": "value" }
}
```

| Поле | Тип | Обязательное | Описание |
|------|-----|:---:|----------|
| `document_id` | string (max 50) | ✅ | ID документа |
| `response_id` | string (max 50) | ❌ | ID ответа |
| `counterparty_id` | string (max 50) | ❌ | ID контрагента |
| `content` | string (min 1) | ✅ | Текст для векторизации |
| `metadata` | object \| null | ❌ | Дополнительные метаданные |

**Ответ (200 OK):**
```json
{
  "document_id": "elma-doc-123",
  "chunks_count": 12
}
```

---

## 5. Convert — `/api/v1/convert`

### POST `/api/v1/convert`

Конвертация документа в унифицированный формат. Автоопределение типа:
- Word/PDF с текстом → `[text]`
- PDF-скан → `[base64_image, ...]`
- Изображение → `[base64_image]`

**Запрос:**
```json
{
  "document_base64": "<base64 содержимое файла>"
}
```

**Ответ (200 OK):**
```json
{
  "document_type": "pdf_scan",
  "document_sheets": ["<base64 страницы 1>", "<base64 страницы 2>"]
}
```

---

## 6. ELMA — `/api/v1/elma`

### GET `/api/v1/elma/documents`

Получить список документов из ELMA365.

**Ответ (200 OK):**
```json
[
  {
    "url": "https://elma365.example.com/docs/123",
    "__id": "doc-123",
    "__name": "Договор №42",
    "subject": "Поставка оборудования",
    "description": "...",
    "__createdAt": "2025-01-01T00:00:00Z",
    "counterparty": "ООО Пример",
    "decisionMaker": "Иванов И.И.",
    "__register_name": "Договоры",
    "__type_id": "type-1",
    "__type_name": "Договор поставки",
    "__version": "1",
    "registrationDate": "2025-01-01"
  }
]
```

---

### POST `/api/v1/elma/documents/{document_id}/process`

Создать задачу на обработку конкретного документа из ELMA365 (тип `FILL_RAG`).

**Ответ (200 OK):** Объект `Task`.

---

### POST `/api/v1/elma/load-documents`

Загрузить все документы из ELMA365 и создать задачи на обработку.

**Ответ (200 OK):** Массив объектов `Task`.

---

## Состояния задач (State)

| Значение | Описание |
|----------|----------|
| `waiting` | Ожидает обработки |
| `processing` | Обрабатывается |
| `completed` | Обработка завершена |
| `error` | Ошибка при обработке |

## Типы вызовов (CallType)

| Значение | Описание |
|----------|----------|
| `ocr` | OCR-обработка документа |
| `fill_rag` | Заполнение RAG (скачивание по URL) |

---

## Swagger UI

Интерактивная документация доступна по адресу:
```
http://localhost:9010/docs
```

Для авторизации в Swagger UI нажмите **Authorize** и введите:
```
Bearer <ваш_access_token>
```
