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

-- Performance indexes for filtering and pagination across millions of records
CREATE INDEX IF NOT EXISTS idx_complaints_date_received ON complaints (date_received DESC);
CREATE INDEX IF NOT EXISTS idx_complaints_product ON complaints (product);
CREATE INDEX IF NOT EXISTS idx_complaints_company ON complaints (company);
CREATE INDEX IF NOT EXISTS idx_complaints_state ON complaints (state);
CREATE INDEX IF NOT EXISTS idx_complaints_consumer_email ON complaints (consumer_email);
