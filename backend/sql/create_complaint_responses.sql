-- Official Bank Complaint Response & Approval Audit Trail
CREATE TABLE IF NOT EXISTS complaint_responses (
    complaint_id BIGINT PRIMARY KEY REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    response_text TEXT NOT NULL,
    requested_by_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    requested_by_name TEXT,
    requested_by_role TEXT,
    requested_at TIMESTAMPTZ,
    assigned_to_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    assigned_to_name TEXT,
    assigned_to_email TEXT,
    approved_by_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    approved_by_name TEXT,
    approved_by_role TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    approved_at TIMESTAMPTZ,
    dispatched_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_complaint_responses_status ON complaint_responses (status);
