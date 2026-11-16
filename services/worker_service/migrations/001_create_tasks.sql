CREATE TABLE IF NOT EXISTS task (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id VARCHAR NOT NULL,
    document_type VARCHAR(50),
    state VARCHAR(16) NOT NULL DEFAULT 'waiting',
    retry_count INTEGER NOT NULL DEFAULT 0,
    base64_document JSON,
    call_type VARCHAR(20) NOT NULL DEFAULT 'ocr',
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT check_task_state CHECK (state IN ('waiting', 'processing', 'completed', 'error')),
    CONSTRAINT check_task_call_type CHECK (call_type IN ('ocr', 'fill_rag'))
);
