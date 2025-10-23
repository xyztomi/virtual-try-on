"""
SQL schema for authentication tables.
Run these queries in your Supabase SQL editor.
"""

CREATE_USERS_TABLE = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) NOT NULL,
    password_hash VARCHAR(64) NOT NULL,
    password_salt VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$')
);

-- Create index on email for faster lookups
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

-- Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read their own data
CREATE POLICY users_select_own ON users
    FOR SELECT
    USING (auth.uid()::text = id::text);

-- Policy: Service role can do everything (for API)
CREATE POLICY users_service_role_all ON users
    FOR ALL
    USING (auth.role() = 'service_role');
"""

CREATE_SESSIONS_TABLE = """
-- Sessions table for authentication tokens
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_is_active ON sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

-- Enable Row Level Security
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read their own sessions
CREATE POLICY sessions_select_own ON sessions
    FOR SELECT
    USING (auth.uid()::text = user_id::text);

-- Policy: Service role can do everything
CREATE POLICY sessions_service_role_all ON sessions
    FOR ALL
    USING (auth.role() = 'service_role');
"""

UPDATE_TRYON_HISTORY_TABLE = """
-- Add user_id to tryon_history table to link records to users
ALTER TABLE tryon_history 
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE SET NULL;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_tryon_history_user_id ON tryon_history(user_id);

-- Update RLS policies
ALTER TABLE tryon_history ENABLE ROW LEVEL SECURITY;

-- Policy: Users can read their own try-on history
CREATE POLICY tryon_history_select_own ON tryon_history
    FOR SELECT
    USING (auth.uid()::text = user_id::text OR user_id IS NULL);

-- Policy: Service role can do everything
CREATE POLICY tryon_history_service_role_all ON tryon_history
    FOR ALL
    USING (auth.role() = 'service_role');
"""

CREATE_UPDATED_AT_TRIGGER = """
-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for users table
DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
"""

# Combined setup script
FULL_SCHEMA_SETUP = f"""
-- =====================================================
-- Virtual Try-On Authentication Schema Setup
-- =====================================================
-- Run this in your Supabase SQL Editor
-- =====================================================

{CREATE_USERS_TABLE}

{CREATE_SESSIONS_TABLE}

{UPDATE_TRYON_HISTORY_TABLE}

{CREATE_UPDATED_AT_TRIGGER}

-- =====================================================
-- Setup Complete!
-- =====================================================
"""

if __name__ == "__main__":
    print(FULL_SCHEMA_SETUP)
