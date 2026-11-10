-- Миграция: добавление поддержки нового типа задач fill_rag
-- Добавляет поле call_type для маршрутизации задач и metadata для хранения дополнительных данных

-- Добавляем поле call_type с ограничением на допустимые значения
ALTER TABLE task
ADD COLUMN IF NOT EXISTS call_type VARCHAR(20) NOT NULL DEFAULT 'ocr'
    CHECK (call_type IN ('ocr', 'fill_rag'));

-- Добавляем поле metadata для хранения дополнительных данных (для fill_rag)
ALTER TABLE task
ADD COLUMN IF NOT EXISTS metadata JSONB;

-- Удаляем старый индекс по state
DROP INDEX IF EXISTS ix_task_state;

-- Создаём новый составной индекс для учёта call_type
CREATE INDEX IF NOT EXISTS ix_task_state_call_type ON task (state, call_type);

-- Добавляем индекс для быстрого поиска waiting задач по call_type
CREATE INDEX IF NOT EXISTS ix_task_waiting_by_call_type ON task (created_at ASC)
    WHERE state = 'waiting';
