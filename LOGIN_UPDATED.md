# Login Endpoint Updated to Official Supabase Docs

## Changes Made

Updated the login endpoint to strictly follow the official Supabase Python documentation:
- [Official Docs: sign_in_with_password](https://supabase.com/docs/reference/python/auth-signinwithpassword)

## What Changed

### 1. Response Model (`AuthResponse`)

**Before:**
```python
class AuthResponse(BaseModel):
    success: bool
    message: str
    token: str
    user: dict
```

**After:**
```python
class AuthResponse(BaseModel):
    success: bool
    message: str
    token: str
    refresh_token: Optional[str] = None  # Added refresh token
    user: dict
```

### 2. Login Endpoint

**Now returns both tokens:**
```python
return AuthResponse(
    success=True,
    message="Login successful",
    token=access_token,          # JWT access token
    refresh_token=refresh_token,  # Refresh token for renewing sessions
    user=user,
)
```

### 3. Auth Core (`authenticate_user`)

Enhanced to return complete session data:
```python
"session": {
    "access_token": response.session.access_token,
    "refresh_token": response.session.refresh_token,
    "expires_at": response.session.expires_at,
    "expires_in": response.session.expires_in,
    "token_type": response.session.token_type,
}
```

## API Response Example

### Request
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-Turnstile-Token: test-token" \
  -d '{
    "email": "user@example.com",
    "password": "securePassword123"
  }'
```

### Response
```json
{
  "success": true,
  "message": "Login successful",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "v1_refresh_token_xyz123...",
  "user": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "email": "user@example.com",
    "username": "user",
    "created_at": "2025-10-29T12:00:00Z",
    "is_active": true
  }
}
```

## Token Usage

### Access Token (Short-lived)
- **Duration**: Typically 1 hour
- **Usage**: Include in Authorization header for API requests
- **Format**: `Authorization: Bearer {access_token}`

```typescript
// Store access token
localStorage.setItem('access_token', response.token);

// Use in requests
fetch('/api/v1/auth/me', {
  headers: {
    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
  }
});
```

### Refresh Token (Long-lived)
- **Duration**: Typically 30 days
- **Usage**: Get a new access token when it expires
- **Storage**: Store securely (HttpOnly cookie recommended)

```typescript
// Store refresh token securely
localStorage.setItem('refresh_token', response.refresh_token);

// Use to refresh session (implement a refresh endpoint)
async function refreshSession() {
  const response = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      refresh_token: localStorage.getItem('refresh_token')
    })
  });
  
  const data = await response.json();
  localStorage.setItem('access_token', data.token);
  return data.token;
}
```

## Session Flow

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Supabase

    Client->>API: POST /login (email, password)
    API->>Supabase: sign_in_with_password()
    Supabase-->>API: {user, session}
    API-->>Client: {token, refresh_token, user}
    
    Note over Client: Store tokens
    
    Client->>API: GET /me (Authorization: Bearer token)
    API->>Supabase: verify token
    Supabase-->>API: user data
    API-->>Client: {user}
    
    Note over Client: Token expires after 1 hour
    
    Client->>API: POST /refresh (refresh_token)
    API->>Supabase: refresh session
    Supabase-->>API: new session
    API-->>Client: {new_token, new_refresh_token}
```

## Frontend Integration

### Complete Login Flow

```typescript
interface LoginResponse {
  success: boolean;
  message: string;
  token: string;
  refresh_token: string;
  user: {
    id: string;
    email: string;
    username: string;
    created_at: string;
    is_active: boolean;
  };
}

async function login(email: string, password: string): Promise<LoginResponse> {
  const response = await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Turnstile-Token': await getTurnstileToken(),
    },
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Login failed');
  }

  const data: LoginResponse = await response.json();
  
  // Store tokens
  localStorage.setItem('access_token', data.token);
  localStorage.setItem('refresh_token', data.refresh_token);
  localStorage.setItem('user', JSON.stringify(data.user));

  return data;
}

// Auto-refresh token before expiration
let refreshTimeout: NodeJS.Timeout;

function scheduleTokenRefresh(expiresIn: number) {
  // Refresh 5 minutes before expiration
  const refreshTime = (expiresIn - 300) * 1000;
  
  refreshTimeout = setTimeout(async () => {
    try {
      await refreshSession();
    } catch (error) {
      console.error('Token refresh failed:', error);
      // Redirect to login
      window.location.href = '/login';
    }
  }, refreshTime);
}

// Use after login
const loginData = await login('user@example.com', 'password123');
scheduleTokenRefresh(3600); // Supabase default is 3600 seconds (1 hour)
```

### Axios Interceptor for Auto Token Refresh

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000',
});

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 errors and refresh token
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const newToken = await refreshSession();
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed, redirect to login
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);
```

## Security Best Practices

### 1. Token Storage

**Access Token:**
- ✅ localStorage (acceptable for web apps)
- ✅ sessionStorage (more secure, lost on tab close)
- ⚠️ Cookie (use HttpOnly flag)

**Refresh Token:**
- ❌ localStorage (vulnerable to XSS)
- ✅ HttpOnly Cookie (recommended)
- ✅ Secure backend session

### 2. Token Transmission

```typescript
// Always use HTTPS in production
const API_URL = process.env.NODE_ENV === 'production' 
  ? 'https://api.yourdomain.com'
  : 'http://localhost:8000';
```

### 3. Token Validation

The backend automatically validates:
- ✅ Token signature
- ✅ Token expiration
- ✅ Token issuer
- ✅ User existence

## Error Handling

### Common Login Errors

**401 Unauthorized:**
```json
{
  "detail": "Invalid email or password"
}
```
- Wrong credentials
- User doesn't exist
- Email not verified (if required)

**400 Bad Request:**
```json
{
  "detail": "X-Turnstile-Token header is required"
}
```
- Missing Turnstile token
- Invalid Turnstile token

**500 Internal Server Error:**
```json
{
  "detail": "Login failed: {error_message}"
}
```
- Server error
- Supabase connection issue

## Testing

### Test Login

```bash
# Successful login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-Turnstile-Token: test-token" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'

# Expected: 200 OK with tokens

# Invalid credentials
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "X-Turnstile-Token: test-token" \
  -d '{
    "email": "wrong@example.com",
    "password": "wrongpass"
  }'

# Expected: 401 Unauthorized
```

### Test Authenticated Request

```bash
# Use the token from login response
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."

# Expected: 200 OK with user data
```

## Next Steps

1. **Implement Token Refresh Endpoint** (recommended):
   ```python
   @router.post("/refresh")
   async def refresh_token(refresh_token: str):
       # Use Supabase's refresh_session method
       pass
   ```

2. **Add Token Expiration Handling** in frontend

3. **Implement Logout** (invalidate refresh token)

4. **Set up HttpOnly Cookies** for refresh token storage

5. **Add Rate Limiting** to prevent brute force attacks

## References

- [Supabase Auth - Sign In with Password](https://supabase.com/docs/reference/python/auth-signinwithpassword)
- [Supabase Auth - Session Management](https://supabase.com/docs/guides/auth/sessions)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)
