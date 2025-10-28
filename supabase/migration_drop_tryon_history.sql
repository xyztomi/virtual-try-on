-- =====================================================
-- Migration: Drop tryon_history and use user_tryon_history for all records
-- =====================================================
-- This migration consolidates all try-on records into user_tryon_history
-- making user_id nullable to support both authenticated users and guests
-- =====================================================

-- Step 1: Make user_id nullable in user_tryon_history
ALTER TABLE user_tryon_history 
ALTER COLUMN user_id DROP NOT NULL;

-- Step 2: Copy any existing records from tryon_history to user_tryon_history (if needed)
-- Note: Only run this if you have existing data in tryon_history that you want to keep
/*
INSERT INTO user_tryon_history (
    id,
    user_id,
    ip_address,
    user_agent,
    body_image_url,
    garment_image_urls,
    result_image_url,
    status,
    error_message,
    created_at,
    completed_at
)
SELECT 
    id,
    user_id,
    ip_address,
    user_agent,
    body_image_url,
    garment_image_urls,
    result_image_url,
    status,
    error_message,
    created_at,
    completed_at
FROM tryon_history
WHERE id NOT IN (SELECT id FROM user_tryon_history)
ON CONFLICT (id) DO NOTHING;
*/

-- Step 3: Drop the tryon_history table
DROP TABLE IF EXISTS tryon_history CASCADE;

-- Step 4: Update comments to reflect new usage
COMMENT ON TABLE user_tryon_history IS 'Stores try-on history for both authenticated users and guests with detailed audit trail';
COMMENT ON COLUMN user_tryon_history.user_id IS 'NULL for guest users, populated for authenticated users';

-- =====================================================
-- Migration Complete!
-- The user_tryon_history table now handles all try-on records
-- =====================================================
