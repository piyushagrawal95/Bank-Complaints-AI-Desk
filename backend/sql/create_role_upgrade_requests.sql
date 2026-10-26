-- Role Upgrade Requests table for Agent -> Supervisor / Admin promotion approval workflow
CREATE TABLE IF NOT EXISTS role_upgrade_requests (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    from_role TEXT NOT NULL,
    to_role TEXT NOT NULL CHECK (to_role IN ('supervisor', 'admin')),
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by_id BIGINT
);

CREATE INDEX IF NOT EXISTS idx_role_requests_status ON role_upgrade_requests(status);
CREATE INDEX IF NOT EXISTS idx_role_requests_user ON role_upgrade_requests(user_id);
