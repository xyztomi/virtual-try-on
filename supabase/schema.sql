-- =====================================================
-- Virtual Try-On Schema Setup for Supabase Auth
-- =====================================================
-- Run this in your Supabase SQL Editor
-- =====================================================
-- Note: Supabase Auth manages users in auth.users table
-- We extend it with a profiles table for additional data
-- =====================================================

-- Profiles table (extends auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    username VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_profiles_username ON public.profiles(username);
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY profiles_select_own ON public.profiles
    FOR SELECT
    USING (auth.uid() = id);

CREATE POLICY profiles_update_own ON public.profiles
    FOR UPDATE
    USING (auth.uid() = id);

CREATE POLICY profiles_service_role_all ON public.profiles
    FOR ALL
    USING (auth.role() = 'service_role');

-- Trigger to create profile on user signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, username, created_at)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'username', split_part(NEW.email, '@', 1)),
        NOW()
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();

-- Try-on history for all users (authenticated and guests)
CREATE TABLE IF NOT EXISTS public.user_tryon_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
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

CREATE INDEX IF NOT EXISTS idx_user_tryon_history_user_id ON public.user_tryon_history(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tryon_history_status ON public.user_tryon_history(status);
CREATE INDEX IF NOT EXISTS idx_user_tryon_history_created_at ON public.user_tryon_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_tryon_history_user_created ON public.user_tryon_history(user_id, created_at DESC);
ALTER TABLE public.user_tryon_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY user_tryon_history_select_own ON public.user_tryon_history
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY user_tryon_history_service_role_all ON public.user_tryon_history
    FOR ALL
    USING (auth.role() = 'service_role');

COMMENT ON TABLE public.user_tryon_history IS 'Stores try-on history for both authenticated users and guests with detailed audit trail';
COMMENT ON COLUMN public.user_tryon_history.user_id IS 'References auth.users(id) for authenticated users, NULL for guests';
COMMENT ON COLUMN public.user_tryon_history.audit_score IS 'Visual quality score from AI audit (0-100)';
COMMENT ON COLUMN public.user_tryon_history.audit_details IS 'Full audit response from Gemini Vision';
COMMENT ON COLUMN public.user_tryon_history.retry_count IS 'Number of regeneration attempts for quality';

-- Update timestamp trigger for profiles
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_profiles_updated_at ON public.profiles;
CREATE TRIGGER update_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- Setup Complete!
-- =====================================================
