-- Complaint embeddings for similar past complaints vector search
CREATE TABLE IF NOT EXISTS complaint_embeddings (
    complaint_id BIGINT PRIMARY KEY REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    embedding vector(384) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_complaint_embeddings_vector 
ON complaint_embeddings USING hnsw (embedding vector_cosine_ops);
