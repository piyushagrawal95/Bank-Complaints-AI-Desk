-- Official Bank Complaint Response & Approval Audit Trail
CREATE TABLE IF NOT EXISTS complaint_responses (
    complaint_id BIGINT PRIMARY KEY REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    response_text TEXT NOT NULL,
    approved_by_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    approved_by_name TEXT,
    approved_by_role TEXT,
    status TEXT NOT NULL DEFAULT 'approved',
    approved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    dispatched_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_complaint_responses_status ON complaint_responses (status);
