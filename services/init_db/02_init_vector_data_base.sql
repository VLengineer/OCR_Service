CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS document_vector_store (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id VARCHAR(50) NOT NULL,
    response_id VARCHAR(50),
    counterparty_id VARCHAR(50),
    content TEXT,
    embedding VECTOR(768) NOT NULL,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS ix_document_vector_store_vector_hnsw ON document_vector_store USING hnsw (embedding vector_cosine_ops);
