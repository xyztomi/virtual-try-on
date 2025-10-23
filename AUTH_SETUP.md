# Authentication System Setup

This branch (`auth-feature`) implements a complete user authentication system with registration, login, and session management.

## Database Schema

### New Tables

#### 1. **users** table
Stores user account information with secure password hashing.

```sql
- id (UUID, primary key)
- email (VARCHAR, unique, not null)
- username (VARCHAR, not null)
- password_hash (VARCHAR, not null) - SHA256 hash
- password_salt (VARCHAR, not null) - Random salt for hashing
- created_at (TIMESTAMPTZ)
- updated_at (TIMESTAMPTZ)
- is_active (BOOLEAN)
```

#### 2. **sessions** table
Manages user authentication sessions and tokens.

```sql
- id (UUID, primary key)
- user_id (UUID, foreign key -> users)
- token (VARCHAR, unique) - Session token
- created_at (TIMESTAMPTZ)
- expires_at (TIMESTAMPTZ) - 7 days from creation
- is_active (BOOLEAN)
- last_used_at (TIMESTAMPTZ)
```

#### 3. **tryon_history** (updated)
Added `user_id` column to link try-on records to users.

```sql
- user_id (UUID, foreign key -> users, nullable)
```

### Setup Instructions

1. **Run the schema script:**
   ```bash
   python database_schema.py > schema.sql
   ```

2. **Execute in Supabase SQL Editor:**
   - Go to your Supabase project → SQL Editor
   - Copy the output from `schema.sql` or run `python database_schema.py`
   - Execute the SQL to create tables and policies

## API Endpoints

All authentication endpoints are prefixed with `/api/v1/auth`

### 1. Register
**POST** `/api/v1/auth/register`

Create a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123",
  "username": "optional_username"
}
```

**Response (201):**
```json
{
  "success": true,
  "message": "Registration successful",
  "token": "session_token_here",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "optional_username",
    "created_at": "2025-10-23T...",
    "is_active": true
  }
}
```

### 2. Login
**POST** `/api/v1/auth/login`

Authenticate with email and password.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200):**
```json
{
  "success": true,
  "message": "Login successful",
  "token": "session_token_here",
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "username",
    "created_at": "2025-10-23T...",
    "is_active": true
  }
}
```

### 3. Logout
**POST** `/api/v1/auth/logout`

Invalidate current session.

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "success": true,
  "message": "Logout successful"
}
```

### 4. Get Current User
**GET** `/api/v1/auth/me`

Get authenticated user's profile.

**Headers:**
```
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "success": true,
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "username": "username",
    "created_at": "2025-10-23T...",
    "is_active": true
  }
}
```

## Usage Examples

### Register a new user
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "mypassword123",
    "username": "testuser"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "mypassword123"
  }'
```

### Get user profile (with token)
```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Logout
```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Integration with Virtual Try-On

### Linking Try-Ons to Users

Update `database_ops.create_tryon_record` to accept an optional `user_id`:

```python
record = await database_ops.create_tryon_record(
    body_url=body_url,
    garment_urls=garment_urls,
    ip_address=client_ip,
    user_id=user.get("id") if user else None  # Add this
)
```

### Protected Routes Example

To protect the try-on endpoint (require authentication):

```python
from src.auth_routes import get_current_user

@router.post("/tryon", response_model=TryOnResponse)
async def create_virtual_tryon(
    request: Request,
    body_image: UploadFile = File(...),
    garment_image1: UploadFile = File(...),
    garment_image2: Optional[UploadFile] = File(None),
    user: dict = Depends(get_current_user),  # Add this dependency
):
    # Now you have access to authenticated user
    user_id = user["id"]
    # ... rest of the function
```

## Security Features

1. **Password Security:**
   - SHA256 hashing with random salt
   - Salt stored separately for each user
   - Passwords never stored in plain text

2. **Session Management:**
   - Secure random tokens (URL-safe)
   - 7-day expiration
   - Can be invalidated on logout

3. **Row Level Security (RLS):**
   - Users can only access their own data
   - Service role has full access for API operations
   - Enforced at database level

4. **Input Validation:**
   - Email format validation
   - Password minimum length (8 characters)
   - Username constraints

## Testing

1. **Start the server:**
   ```bash
   uvicorn src.main:app --reload
   ```

2. **Check API docs:**
   - Open http://localhost:8000/docs
   - You'll see the new `/api/v1/auth` endpoints

3. **Run tests:**
   ```bash
   # Register a user
   curl -X POST http://localhost:8000/api/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"password123"}'
   
   # Copy the token from response
   # Test authenticated endpoint
   curl -X GET http://localhost:8000/api/v1/auth/me \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```

## Files Added/Modified

### New Files:
- `src/core/auth.py` - Authentication logic and user management
- `src/auth_routes.py` - API routes for auth endpoints
- `database_schema.py` - SQL schema for tables
- `AUTH_SETUP.md` - This documentation

### Modified Files:
- `src/main.py` - Added auth_router
- (Optional) `src/core/database_ops.py` - Add user_id support

## Next Steps

1. **Run the database schema** in Supabase
2. **Test the endpoints** using curl or Postman
3. **Integrate with frontend** - store token in localStorage/cookies
4. **Add user_id to try-on records** for user history
5. **Create user dashboard** to view their try-on history

## Branch Information

- **Branch:** `auth-feature`
- **Base:** `main`
- **Status:** Ready for testing
- **Merge:** After testing and approval

To merge this feature:
```bash
git checkout main
git merge auth-feature
git push origin main
```
