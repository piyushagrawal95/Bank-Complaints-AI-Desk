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
    rejection_reason TEXT,
    rejected_by_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    rejected_by_name TEXT,
    rejected_at TIMESTAMPTZ,
    dispatched_at TIMESTAMPTZ,
    email_dispatch_status TEXT,
    dispatched_to_email TEXT
);

CREATE INDEX IF NOT EXISTS idx_complaint_responses_status ON complaint_responses (status);
CREATE INDEX IF NOT EXISTS idx_complaint_responses_assigned ON complaint_responses (assigned_to_id);
