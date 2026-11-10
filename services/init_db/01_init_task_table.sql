CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS task (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id text NOT NULL,
    document_type VARCHAR(50),
    state VARCHAR(16) NOT NULL DEFAULT 'waiting'
               CHECK (state IN ('waiting', 'processing', 'completed', 'error')),
    retry_count INTEGER NOT NULL DEFAULT 0,
    base64_document JSONB, -- [{"base64 string sheet 0"}, ..., {"base64 string sheet n"}]
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_task_state ON task (state);
CREATE INDEX IF NOT EXISTS ix_task_created_at ON task (created_at DESC);