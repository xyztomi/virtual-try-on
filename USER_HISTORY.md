# User Try-On History Feature

## Overview

The user try-on history feature provides authenticated users with detailed tracking of their virtual try-on requests. This includes comprehensive metadata such as IP addresses, user agents, audit scores, retry counts, and processing times.

## Architecture

### Database Tables

#### `user_tryon_history`
Main table for authenticated user try-on records with the following fields:

- `id` (UUID): Primary key
- `user_id` (UUID): Foreign key to users table
- `ip_address` (INET): Client IP address
- `user_agent` (TEXT): Browser user agent string
- `request_timestamp` (TIMESTAMP): When the request was initiated
- `body_image_url` (TEXT): URL of the body/model image
- `garment_image_urls` (TEXT[]): Array of garment image URLs
- `result_image_url` (TEXT): URL of the generated result
- `status` (ENUM): pending, processing, success, or failed
- `error_message` (TEXT): Error details if failed
- `processing_time_ms` (INTEGER): Processing duration in milliseconds
- `audit_score` (DECIMAL): Quality score from audit (0-100)
- `audit_details` (JSONB): Full audit response
- `retry_count` (INTEGER): Number of generation retries
- `created_at` (TIMESTAMP): Record creation timestamp
- `completed_at` (TIMESTAMP): When processing finished
- `metadata` (JSONB): Additional flexible metadata

**Indexes:**
- `idx_user_tryon_history_user_id` on `user_id`
- `idx_user_tryon_history_status` on `status`
- `idx_user_tryon_history_created_at` on `created_at DESC`
- `idx_user_tryon_history_user_created` on `(user_id, created_at DESC)`

**RLS Policies:**
- Users can read only their own records
- `service_role` has full access for system operations

### Code Structure

#### `src/core/user_history_ops.py`
Database operations module with the following functions:

- `create_user_tryon_record()`: Create new history record
- `update_user_tryon_result()`: Update with successful result
- `mark_user_tryon_failed()`: Mark as failed with reason
- `get_user_tryon_record()`: Retrieve specific record
- `get_user_tryon_history()`: Get paginated history for user
- `delete_user_tryon_record()`: Delete a record (with ownership check)
- `get_user_stats()`: Get statistics (total, success rate, etc.)

#### `src/auth_routes.py`
API endpoints:

- `GET /api/v1/auth/history`: Get user's try-on history with pagination
- `GET /api/v1/auth/history/{record_id}`: Get specific history record
- `DELETE /api/v1/auth/history/{record_id}`: Delete a history record
- `GET /api/v1/auth/stats`: Get user's statistics

#### `src/routers.py`
Integration points:

- Optional authentication via `get_optional_user()` dependency
- Creates user history record if authenticated
- Tracks processing time and audit details
- Updates history on success/failure

## API Usage

### Authentication

All user history endpoints require a Bearer token in the Authorization header:

```http
Authorization: Bearer <token>
```

### Get User History

**Request:**
```http
GET /api/v1/auth/history?limit=20&offset=0&status=success
Authorization: Bearer <token>
```

**Query Parameters:**
- `limit` (optional): Maximum records to return (1-100, default: 20)
- `offset` (optional): Number of records to skip (default: 0)
- `status` (optional): Filter by status (pending, processing, success, failed)

**Response:**
```json
{
  "success": true,
  "records": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "request_timestamp": "2024-01-15T10:30:00Z",
      "body_image_url": "https://...",
      "garment_image_urls": ["https://...", "https://..."],
      "result_image_url": "https://...",
      "status": "success",
      "processing_time_ms": 5234,
      "audit_score": 87.5,
      "audit_details": {
        "clothing_changed": true,
        "matches_input_garments": true,
        "visual_quality_score": 87.5,
        "issues": [],
        "summary": "High quality result"
      },
      "retry_count": 1,
      "created_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:30:05Z",
      "metadata": {"test_mode": false}
    }
  ],
  "total": 50,
  "limit": 20,
  "offset": 0,
  "has_more": true
}
```

### Get Specific Record

**Request:**
```http
GET /api/v1/auth/history/{record_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "record": {
    "id": "uuid",
    "user_id": "uuid",
    // ... full record details
  }
}
```

### Delete History Record

**Request:**
```http
DELETE /api/v1/auth/history/{record_id}
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "message": "Record deleted successfully"
}
```

### Get User Statistics

**Request:**
```http
GET /api/v1/auth/stats
Authorization: Bearer <token>
```

**Response:**
```json
{
  "success": true,
  "stats": {
    "total_tryons": 50,
    "successful": 45,
    "failed": 3,
    "pending": 2,
    "success_rate": 90.0
  }
}
```

## Try-On Flow Integration

### Anonymous Users

Anonymous users (without Bearer token) continue to use the existing flow:
- Records saved to `tryon_history` table
- Rate limited by IP address
- No detailed history tracking

### Authenticated Users

Authenticated users get enhanced tracking:
1. System detects Bearer token via optional dependency
2. Creates record in both `tryon_history` and `user_tryon_history`
3. Tracks additional metadata:
   - Processing time in milliseconds
   - Full audit details (JSONB)
   - Retry count during auto-retry loop
   - User agent and IP address
4. Updates history on success/failure

### Example Try-On Request

**Anonymous:**
```http
POST /api/v1/tryon
X-Turnstile-Token: <token>
Content-Type: multipart/form-data

body_image=@body.jpg
garment_image1=@garment1.jpg
```

**Authenticated:**
```http
POST /api/v1/tryon
Authorization: Bearer <token>
X-Turnstile-Token: <token>
Content-Type: multipart/form-data

body_image=@body.jpg
garment_image1=@garment1.jpg
```

The authenticated request automatically logs to user history without any additional parameters.

## Database Setup

### Running the Schema

1. Copy the SQL from `database_schema.py`:
   ```python
   from database_schema import FULL_SCHEMA_SETUP
   print(FULL_SCHEMA_SETUP)
   ```

2. Execute in Supabase SQL Editor:
   - Go to https://app.supabase.com
   - Navigate to SQL Editor
   - Paste and run the `FULL_SCHEMA_SETUP` script

3. Verify tables created:
   ```sql
   SELECT tablename FROM pg_tables WHERE schemaname = 'public';
   ```

### RLS Policies

The schema includes Row Level Security policies:

**user_tryon_history_select_own:**
```sql
(auth.uid() = user_id)
```
Users can only read their own records.

**user_tryon_history_service_role:**
```sql
USING (true)
WITH CHECK (true)
```
Service role has full access for system operations.

## Frontend Integration

### Displaying User History

Example React component:

```typescript
import { useState, useEffect } from 'react';

interface TryOnRecord {
  id: string;
  body_image_url: string;
  garment_image_urls: string[];
  result_image_url: string;
  status: string;
  processing_time_ms: number;
  audit_score: number;
  created_at: string;
}

function UserHistoryPage() {
  const [records, setRecords] = useState<TryOnRecord[]>([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchHistory = async () => {
      const response = await fetch('/api/v1/auth/history?limit=20', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      });
      const data = await response.json();
      setRecords(data.records);
      setLoading(false);
    };
    
    fetchHistory();
  }, []);
  
  if (loading) return <div>Loading...</div>;
  
  return (
    <div>
      <h1>My Try-On History</h1>
      {records.map(record => (
        <div key={record.id}>
          <img src={record.result_image_url} alt="Try-on result" />
          <p>Status: {record.status}</p>
          <p>Processing Time: {record.processing_time_ms}ms</p>
          <p>Quality Score: {record.audit_score}</p>
          <p>Date: {new Date(record.created_at).toLocaleString()}</p>
        </div>
      ))}
    </div>
  );
}
```

### Pagination

```typescript
const [offset, setOffset] = useState(0);
const limit = 20;

const loadMore = () => {
  setOffset(prev => prev + limit);
};

// In fetch:
const response = await fetch(
  `/api/v1/auth/history?limit=${limit}&offset=${offset}`,
  { headers: { 'Authorization': `Bearer ${token}` } }
);
```

## Security Considerations

1. **RLS Policies**: Ensure users can only access their own records
2. **Token Validation**: Bearer tokens verified via session table
3. **Ownership Checks**: DELETE operations verify user_id matches
4. **IP Logging**: IP addresses stored for audit purposes
5. **Service Role**: Only backend uses service_role key for full access

## Performance Optimization

### Indexes

The schema includes optimized indexes for common queries:

1. **User Lookup**: `(user_id, created_at DESC)` for user history
2. **Status Filter**: `status` for filtering by status
3. **Time Range**: `created_at DESC` for recent records

### Query Patterns

**Get recent history:**
```sql
SELECT * FROM user_tryon_history
WHERE user_id = ?
ORDER BY created_at DESC
LIMIT 20 OFFSET 0;
```

**Filter by status:**
```sql
SELECT * FROM user_tryon_history
WHERE user_id = ? AND status = 'success'
ORDER BY created_at DESC
LIMIT 20;
```

**Get statistics:**
```sql
SELECT 
  COUNT(*) as total_tryons,
  SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful,
  SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
FROM user_tryon_history
WHERE user_id = ?;
```

## Monitoring & Analytics

### Key Metrics

Track these metrics for insights:

1. **Success Rate**: `successful / total_tryons * 100`
2. **Average Processing Time**: `AVG(processing_time_ms)`
3. **Average Audit Score**: `AVG(audit_score) WHERE status = 'success'`
4. **Retry Distribution**: `GROUP BY retry_count`
5. **Failure Reasons**: `GROUP BY error_message WHERE status = 'failed'`

### Example Analytics Query

```sql
SELECT 
  DATE(created_at) as date,
  COUNT(*) as total,
  AVG(processing_time_ms) as avg_processing_time,
  AVG(audit_score) as avg_quality,
  COUNT(*) FILTER (WHERE status = 'success') as successful
FROM user_tryon_history
WHERE user_id = ?
  AND created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

## Future Enhancements

Potential improvements:

1. **Favorites**: Add `is_favorite` flag for users to mark favorite results
2. **Collections**: Group related try-ons into collections/albums
3. **Sharing**: Generate shareable links for specific results
4. **Export**: Allow users to export their history as JSON/CSV
5. **Webhooks**: Notify users when processing completes (via email/push)
6. **Comparison**: Side-by-side comparison of different garment combinations
7. **Analytics Dashboard**: Rich visualization of user's try-on patterns
8. **Recommendations**: Suggest garment combinations based on history

## Troubleshooting

### Common Issues

**"Record not found" when accessing history:**
- Verify token is valid and not expired
- Check RLS policies are enabled
- Ensure user_id matches session user

**"Permission denied" on delete:**
- Verify user owns the record
- Check service_role key if calling from backend

**Slow queries with large history:**
- Ensure indexes are created
- Use pagination with appropriate limits
- Consider archiving old records

### Debug Mode

To see detailed logs:

```bash
# Check Supabase logs
# Dashboard > Logs > Database

# Check API logs
grep "user history" /var/log/app.log
```

## Testing

### Unit Tests

```python
import pytest
from src.core import user_history_ops

@pytest.mark.asyncio
async def test_create_user_history():
    record = await user_history_ops.create_user_tryon_record(
        user_id="test-user-id",
        body_url="https://example.com/body.jpg",
        garment_urls=["https://example.com/garment.jpg"],
        ip_address="192.168.1.1",
    )
    assert record["status"] == "pending"
    assert record["user_id"] == "test-user-id"
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_tryon_with_auth(client, auth_token):
    response = await client.post(
        "/api/v1/tryon",
        headers={"Authorization": f"Bearer {auth_token}"},
        files={
            "body_image": open("test_body.jpg", "rb"),
            "garment_image1": open("test_garment.jpg", "rb"),
        }
    )
    assert response.status_code == 200
    
    # Verify history created
    history = await client.get(
        "/api/v1/auth/history",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert len(history.json()["records"]) > 0
```

## Migration Guide

If you have existing user try-on data in other tables:

```sql
-- Migrate existing data to user_tryon_history
INSERT INTO user_tryon_history (
  user_id, body_image_url, garment_image_urls, 
  result_image_url, status, created_at
)
SELECT 
  user_id, body_image_url, garment_image_urls,
  result_image_url, status, created_at
FROM legacy_tryon_table
WHERE user_id IS NOT NULL;
```

## Support

For issues or questions:
- Check Supabase logs for database errors
- Review API logs for request failures
- Verify RLS policies with `EXPLAIN` queries
- Contact support with record IDs for specific issues
