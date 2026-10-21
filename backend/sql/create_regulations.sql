-- Regulation chunks table with pgvector for RAG
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS regulation_chunks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    regulation_name TEXT NOT NULL,
    section TEXT,
    page_number INT NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector(384) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reg_chunks_embedding 
ON regulation_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_reg_chunks_name 
ON regulation_chunks (regulation_name);
