-- Caching table for LLM classification and summaries
CREATE TABLE IF NOT EXISTS complaint_analysis (
    complaint_id BIGINT PRIMARY KEY REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    model TEXT NOT NULL,
    basis TEXT NOT NULL DEFAULT 'narrative',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_complaint_analysis_category ON complaint_analysis (category);
