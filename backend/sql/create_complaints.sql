-- Enable pg_trgm extension for high-performance substring search across millions of records
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- CFPB Complaints table with optimized indexes
CREATE TABLE IF NOT EXISTS complaints (
    complaint_id BIGINT PRIMARY KEY,
    date_received DATE NOT NULL,
    product TEXT NOT NULL,
    sub_product TEXT,
    issue TEXT NOT NULL,
    sub_issue TEXT,
    narrative TEXT,
    company_public_response TEXT,
    company TEXT NOT NULL,
    state TEXT,
    zip_code TEXT,
    tags TEXT,
    submitted_via TEXT,
    date_sent_to_company DATE,
    company_response_to_consumer TEXT,
    timely_response BOOLEAN,
    consumer_email TEXT
);

-- Performance B-Tree indexes for filtering and pagination across millions of records
CREATE INDEX IF NOT EXISTS idx_complaints_date_received ON complaints (date_received DESC);
CREATE INDEX IF NOT EXISTS idx_complaints_product ON complaints (product);
CREATE INDEX IF NOT EXISTS idx_complaints_company ON complaints (company);
CREATE INDEX IF NOT EXISTS idx_complaints_state ON complaints (state);
CREATE INDEX IF NOT EXISTS idx_complaints_consumer_email ON complaints (consumer_email);

-- Trigram GIN indexes for fast ILIKE substring search on millions of rows
CREATE INDEX IF NOT EXISTS idx_complaints_company_trgm ON complaints USING gin (company gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_complaints_issue_trgm ON complaints USING gin (issue gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_complaints_sub_issue_trgm ON complaints USING gin (sub_issue gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_complaints_email_trgm ON complaints USING gin (consumer_email gin_trgm_ops);

-- Composite indexes for time-series trend analysis and anomaly detection
CREATE INDEX IF NOT EXISTS idx_complaints_trends_product ON complaints (date_received, product);
CREATE INDEX IF NOT EXISTS idx_complaints_trends_issue ON complaints (date_received, issue);
CREATE INDEX IF NOT EXISTS idx_complaints_trends_company ON complaints (date_received, company);

-- Daily aggregation rollup table for instant anomaly calculations without full-table scans
CREATE TABLE IF NOT EXISTS complaints_daily_rollup (
    date_received DATE NOT NULL,
    dimension_type TEXT NOT NULL CHECK (dimension_type IN ('product', 'issue', 'company')),
    dimension_value TEXT NOT NULL,
    complaint_count INT NOT NULL DEFAULT 0,
    PRIMARY KEY (date_received, dimension_type, dimension_value)
);

CREATE INDEX IF NOT EXISTS idx_complaints_daily_rollup_lookup 
ON complaints_daily_rollup (dimension_type, dimension_value, date_received DESC);
