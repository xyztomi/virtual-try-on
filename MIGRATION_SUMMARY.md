# Migration: Dropped tryon_history Table

## Summary

Successfully removed the `tryon_history` table and consolidated all try-on records into `user_tryon_history`. The system now uses a single table for both authenticated users and guest users.

## Changes Made

### 1. Database Schema (`supabase/schema.sql`)
- **Modified `user_tryon_history` table**: Changed `user_id` from `NOT NULL` to nullable
- **Removed `tryon_history` references**: Deleted all ALTER TABLE statements and policies for `tryon_history`
- **Updated comments**: Clarified that the table now handles both authenticated and guest users

### 2. Database Operations (`src/core/database_ops.py`)
- Updated all operations to use `user_tryon_history` table:
  - `create_tryon_record()` - Creates records in `user_tryon_history`
  - `update_tryon_result()` - Updates records in `user_tryon_history`
  - `mark_tryon_failed()` - Marks failures in `user_tryon_history`
  - `get_tryon_record()` - Retrieves records from `user_tryon_history`

### 3. Rate Limiting (`src/core/rate_limit.py`)
- Updated `check_rate_limit()` to query `user_tryon_history` instead of `tryon_history`

### 4. Try-On Services (`src/routers/tryon/services.py`)
- **Simplified `create_tryon_records()`**: Now creates only ONE record in `user_tryon_history`
- Removed duplicate record creation logic
- `RecordContext` now uses the same ID for both `record_id` and `user_history_record_id`
- Removed unused `user_history_ops` import

### 5. Background Job Processing (`src/services/tryon_service.py`)
- **Simplified `_update_result()`**: Removed duplicate update to user_history_ops
- **Simplified `_mark_failure()`**: Removed duplicate failure marking
- Removed unused `user_history_ops` import

### 6. Migration Script
- Created `supabase/migration_drop_tryon_history.sql` for database migration

## How Guest Records Work

### Before (Two Tables)
- **Guests**: Records in `tryon_history` with `user_id = NULL`, `ip_address` populated
- **Authenticated Users**: Records in both `tryon_history` AND `user_tryon_history`

### After (One Table)
- **Guests**: Records in `user_tryon_history` with `user_id = NULL`, `ip_address` populated
- **Authenticated Users**: Records in `user_tryon_history` with `user_id` populated

## Database Migration Steps

1. **Make user_id nullable**:
   ```sql
   ALTER TABLE user_tryon_history 
   ALTER COLUMN user_id DROP NOT NULL;
   ```

2. **(Optional) Copy existing data** from `tryon_history` if you want to preserve it

3. **Drop the old table**:
   ```sql
   DROP TABLE IF EXISTS tryon_history CASCADE;
   ```

4. Run the complete migration script:
   ```bash
   # In Supabase SQL Editor, run:
   supabase/migration_drop_tryon_history.sql
   ```

## Benefits

1. **Simplified architecture**: Single source of truth for all try-on records
2. **Reduced complexity**: No need to maintain two separate tables
3. **Easier querying**: All records in one place
4. **Consistent behavior**: Same fields and structure for guests and authenticated users
5. **Better performance**: Single insert instead of two separate inserts for authenticated users

## Testing Checklist

- [ ] Guest users can create try-on requests
- [ ] Authenticated users can create try-on requests
- [ ] Record retrieval works with `GET /tryon/{record_id}`
- [ ] Rate limiting works correctly for guests (IP-based)
- [ ] Rate limiting works correctly for authenticated users (user_id-based)
- [ ] Background processing updates the correct record
- [ ] Failed try-ons are marked correctly
- [ ] User history endpoint shows correct records for authenticated users

## Notes

- The `user_history_ops.py` module still exists and is used by auth endpoints for user-specific queries (history, stats, etc.)
- All CRUD operations for try-on records now go through `database_ops.py` which targets `user_tryon_history`
- Rate limiting correctly scopes by `user_id` (authenticated) or `ip_address + user_agent` (guests)
