# Migration to Supabase Auth

## Overview

Successfully migrated from custom authentication system to **Supabase Auth** for user registration, login, and session management. This provides better security, built-in email verification, password reset, and OAuth integrations.

## What Changed

### Before (Custom Auth)
- ❌ Manual password hashing with SHA256 + salt
- ❌ Custom session tokens stored in database
- ❌ Manual email verification (if needed)
- ❌ Custom password reset implementation
- ❌ Stored passwords in custom `users` table

### After (Supabase Auth)
- ✅ Supabase handles password hashing (bcrypt)
- ✅ JWT access tokens and refresh tokens
- ✅ Built-in email verification
- ✅ Built-in password reset via email
- ✅ Users managed by Supabase Auth system
- ✅ Ready for OAuth (Google, GitHub, etc.)

## Code Changes

### 1. Registration (`/api/v1/auth/register`)

**Before:**
```python
# Manual password hashing and database insert
user = await auth.create_user(email, password, username)
session = await auth.create_session(user["id"])
return {"token": session["token"]}
```

**After:**
```python
# Supabase Auth handles everything
response = client.auth.sign_up({
    "email": email,
    "password": password,
    "options": {"data": {"username": username}}
})
return {"token": "email_verification_required"}
```

### 2. Login (`/api/v1/auth/login`)

**Before:**
```python
# Manual password verification
user = await auth.authenticate_user(email, password)
session = await auth.create_session(user["id"])
return {"token": session["token"]}
```

**After:**
```python
# Supabase Auth with JWT tokens
response = client.auth.sign_in_with_password({
    "email": email,
    "password": password
})
return {"token": response.session.access_token}
```

### 3. Token Verification

**Before:**
```python
# Query sessions table
session = await auth.get_session(token)
user = session["users"]
```

**After:**
```python
# Verify JWT token with Supabase
response = client.auth.get_user(access_token)
user = response.user
```

## Email Verification Flow

### Important: Supabase Auth requires email verification by default

1. **User registers** → Receives confirmation email
2. **User clicks link** → Email verified
3. **User can login** → Gets access token

### Configure Email Templates

In Supabase Dashboard:
1. Go to **Authentication** → **Email Templates**
2. Customize **Confirm signup** template
3. Set confirmation URL: `https://yourdomain.com/verify?token={{ .TokenHash }}`

### Disable Email Verification (Development Only)

If you want to disable email verification for testing:

1. Go to **Authentication** → **Settings**
2. Turn OFF **Enable email confirmations**
3. **⚠️ Not recommended for production!**

## Database Schema Changes

### Old Schema (No Longer Used)
```sql
-- These tables are no longer needed:
DROP TABLE IF EXISTS sessions;       -- Session management now handled by Supabase
DROP TABLE IF EXISTS users;          -- User data now in auth.users (Supabase managed)
```

### Supabase Auth Schema
```sql
-- Supabase automatically creates:
-- auth.users (managed by Supabase)
-- auth.sessions (managed by Supabase)
-- auth.refresh_tokens (managed by Supabase)
```

### User Metadata

User data is now stored in Supabase Auth with metadata:

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "user_metadata": {
    "username": "johndoe"
  },
  "created_at": "2025-10-29T...",
  "email_confirmed_at": "2025-10-29T..."
}
```

## API Response Changes

### Registration Response

**Before:**
```json
{
  "success": true,
  "message": "Registration successful",
  "token": "actual-session-token",
  "user": {...}
}
```

**After:**
```json
{
  "success": true,
  "message": "Registration successful. Please check your email to verify your account.",
  "token": "email_verification_required",
  "user": {...}
}
```

### Login Response

**Before:**
```json
{
  "token": "custom-session-token"
}
```

**After:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  // JWT access token
}
```

The JWT token contains:
- User ID
- Email
- Expiration time
- Cryptographic signature

## Testing

### 1. Test Registration

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -H "X-Turnstile-Token: test-token" \
  -d '{
    "email": "test@example.com",
    "password": "securePassword123",
    "username": "testuser"
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Registration successful. Please check your email to verify your account.",
  "token": "email_verification_required",
  "user": {
    "id": "uuid",
    "email": "test@example.com",
    "username": "testuser"
  }
}
```

### 2. Verify Email (Click Link in Email)

Supabase sends email with verification link. After clicking:
- User's `email_confirmed_at` is set
- User can now login

### 3. Test Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-Turnstile-Token: test-token" \
  -d '{
    "email": "test@example.com",
    "password": "securePassword123"
  }'
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Login successful",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "uuid",
    "email": "test@example.com",
    "username": "testuser"
  }
}
```

### 4. Test Authenticated Request

```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

## Frontend Integration

### Registration Flow

```typescript
async function register(email: string, password: string, username: string) {
  const response = await fetch('/api/v1/auth/register', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Turnstile-Token': turnstileToken,
    },
    body: JSON.stringify({ email, password, username }),
  });
  
  const data = await response.json();
  
  if (data.success) {
    // Show message: "Check your email to verify your account"
    showEmailVerificationMessage();
  }
}
```

### Login Flow

```typescript
async function login(email: string, password: string) {
  const response = await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Turnstile-Token': turnstileToken,
    },
    body: JSON.stringify({ email, password }),
  });
  
  const data = await response.json();
  
  if (data.success) {
    // Store JWT token
    localStorage.setItem('access_token', data.token);
    
    // Use token for authenticated requests
    makeAuthenticatedRequest();
  }
}
```

### Authenticated Requests

```typescript
async function makeAuthenticatedRequest() {
  const token = localStorage.getItem('access_token');
  
  const response = await fetch('/api/v1/auth/me', {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });
  
  const data = await response.json();
  console.log('Current user:', data.user);
}
```

### Token Refresh (Optional)

JWT tokens expire. If you receive a 401 error, you may need to refresh:

```typescript
// This would require implementing a refresh token endpoint
async function refreshToken() {
  const refreshToken = localStorage.getItem('refresh_token');
  
  const response = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  
  const data = await response.json();
  localStorage.setItem('access_token', data.token);
}
```

## Migration Steps for Existing Users

If you have existing users in the old system:

### Option 1: Fresh Start (Recommended for Development)
1. Drop old `users` and `sessions` tables
2. All users need to re-register with Supabase Auth
3. Clean slate with proper email verification

### Option 2: Migrate Existing Users
1. Export users from old `users` table
2. Use Supabase CLI or Admin API to bulk import:
   ```bash
   supabase db seed
   ```
3. Users will need to reset passwords (Supabase doesn't accept pre-hashed passwords)

## Configuration Required

### 1. Enable Email Provider

In Supabase Dashboard:
- Go to **Authentication** → **Providers**
- Enable **Email** provider
- Configure SMTP settings (or use Supabase's built-in email)

### 2. Configure Site URL

In Supabase Dashboard:
- Go to **Authentication** → **URL Configuration**
- Set **Site URL**: `https://yourdomain.com`
- Add **Redirect URLs**: `https://yourdomain.com/verify`, `https://yourdomain.com/reset-password`

### 3. Email Templates

Customize email templates in **Authentication** → **Email Templates**:
- Confirm signup
- Magic Link
- Reset Password
- Email Change

## Benefits of Migration

1. **Security**: Industry-standard authentication (bcrypt, JWT)
2. **Email Verification**: Built-in email confirmation
3. **Password Reset**: Already implemented via Supabase
4. **OAuth Ready**: Easy to add Google, GitHub, etc.
5. **Session Management**: Automatic token refresh
6. **Rate Limiting**: Built-in protection against brute force
7. **Audit Logs**: Supabase tracks all auth events
8. **Compliance**: GDPR, SOC2 compliant

## Files Modified

1. **`src/core/auth.py`**
   - `create_user()` now uses `client.auth.sign_up()`
   - `authenticate_user()` now uses `client.auth.sign_in_with_password()`
   - Added `verify_access_token()` for JWT verification
   - Removed manual password hashing functions (kept for backward compatibility)

2. **`src/routers/auth/router.py`**
   - Updated `/register` endpoint
   - Updated `/login` endpoint
   - Updated `/logout` endpoint (simplified)

3. **`src/routers/auth/dependencies.py`**
   - `get_current_user()` now verifies JWT tokens

## Troubleshooting

### "Email not confirmed"
- User needs to click verification link in email
- Check Supabase email logs
- Disable email confirmation for testing (not recommended for production)

### "Invalid credentials"
- Password must meet requirements (min 6 characters by default)
- Email must be valid format
- Check Supabase auth logs

### Token expired
- JWT tokens expire (default: 1 hour)
- Implement token refresh mechanism
- Store refresh token to get new access token

### SMTP not configured
- Use Supabase's built-in email for development
- Configure custom SMTP in production
- Check email provider settings

## Next Steps

1. **Test thoroughly** with email verification flow
2. **Implement token refresh** for long sessions
3. **Add OAuth providers** (Google, GitHub, etc.)
4. **Configure email templates** to match your brand
5. **Set up rate limiting** in Supabase settings
6. **Monitor auth logs** in Supabase Dashboard

## References

- [Supabase Auth Documentation](https://supabase.com/docs/guides/auth)
- [Sign Up Documentation](https://supabase.com/docs/reference/python/auth-signup)
- [Sign In Documentation](https://supabase.com/docs/reference/python/auth-signinwithpassword)
- [JWT Verification](https://supabase.com/docs/reference/python/auth-getuser)
