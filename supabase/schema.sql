-- =====================================================
-- Virtual Try-On Authentication Schema Setup
-- =====================================================
-- Run this in your Supabase SQL Editor
-- =====================================================

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
    CONSTRAINT email_format CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY users_select_own ON users
    FOR SELECT
    USING (auth.uid()::text = id::text);

CREATE POLICY users_service_role_all ON users
    FOR ALL
    USING (auth.role() = 'service_role');

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_is_active ON sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY sessions_select_own ON sessions
    FOR SELECT
    USING (auth.uid()::text = user_id::text);

CREATE POLICY sessions_service_role_all ON sessions
    FOR ALL
    USING (auth.role() = 'service_role');

-- User-specific try-on history
CREATE TABLE IF NOT EXISTS user_tryon_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ip_address INET,
    user_agent TEXT,
    request_timestamp TIMESTAMPTZ DEFAULT NOW(),
    body_image_url TEXT NOT NULL,
    garment_image_urls TEXT[] NOT NULL,
    result_image_url TEXT,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'success', 'failed')),
    error_message TEXT,
    processing_time_ms INTEGER,
    audit_score DECIMAL(5,2),
    audit_details JSONB,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_user_tryon_history_user_id ON user_tryon_history(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tryon_history_status ON user_tryon_history(status);
CREATE INDEX IF NOT EXISTS idx_user_tryon_history_created_at ON user_tryon_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_tryon_history_user_created ON user_tryon_history(user_id, created_at DESC);
ALTER TABLE user_tryon_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_tryon_history_select_own ON user_tryon_history
    FOR SELECT
    USING (auth.uid()::text = user_id::text);

CREATE POLICY user_tryon_history_service_role_all ON user_tryon_history
    FOR ALL
    USING (auth.role() = 'service_role');

COMMENT ON TABLE user_tryon_history IS 'Stores try-on history for authenticated users with detailed audit trail';
COMMENT ON COLUMN user_tryon_history.audit_score IS 'Visual quality score from AI audit (0-100)';
COMMENT ON COLUMN user_tryon_history.audit_details IS 'Full audit response from Gemini Vision';
COMMENT ON COLUMN user_tryon_history.retry_count IS 'Number of regeneration attempts for quality';

-- Add user_id to tryon_history (if exists)
ALTER TABLE tryon_history 
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_tryon_history_user_id ON tryon_history(user_id);
ALTER TABLE tryon_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY tryon_history_select_own ON tryon_history
    FOR SELECT
    USING (auth.uid()::text = user_id::text OR user_id IS NULL);

CREATE POLICY tryon_history_service_role_all ON tryon_history
    FOR ALL
    USING (auth.role() = 'service_role');

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- Setup Complete!
-- =====================================================
