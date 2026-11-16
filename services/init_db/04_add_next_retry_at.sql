-- Миграция: добавление поля next_retry_at для вторичных повторных попыток
-- Поле используется для планирования retry задач, находящихся в состоянии error.
-- Если next_retry_at IS NULL — задача не запланирована к повторной обработке.
-- Если next_retry_at <= NOW() — задача готова к повторной обработке.

ALTER TABLE task
ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMPTZ;

-- Индекс для быстрого поиска задач с наступившим временем retry
CREATE INDEX IF NOT EXISTS ix_task_next_retry_at ON task (next_retry_at)
    WHERE state = 'error' AND next_retry_at IS NOT NULL;
