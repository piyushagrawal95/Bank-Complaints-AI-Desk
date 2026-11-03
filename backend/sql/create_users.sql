-- Users table with RBAC (agent, supervisor, admin)
CREATE TABLE IF NOT EXISTS users (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'agent' CHECK (role IN ('agent', 'supervisor', 'admin')),
    is_active BOOLEAN NOT NULL DEFAULT true,
    supervisor_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    token_version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Ensure token_version column exists on pre-existing installations
ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INT NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS idx_users_supervisor_id ON users (supervisor_id);
