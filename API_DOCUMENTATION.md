# Virtual Try-On API Documentation

## Table of Contents
- [Overview](#overview)
- [Authentication](#authentication)
- [Base URL](#base-url)
- [Common Headers](#common-headers)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Endpoints](#endpoints)
  - [Authentication Endpoints](#authentication-endpoints)
  - [Try-On Endpoints](#try-on-endpoints)
  - [User History Endpoints](#user-history-endpoints)

---

## Overview

The Virtual Try-On API allows users to virtually try on garments by uploading body and garment images. The API supports both guest users (limited usage) and authenticated users (extended features and history tracking).

**Features:**
- Virtual garment try-on with AI processing
- User authentication with Supabase Auth
- Try-on history tracking
- Rate limiting (5 requests/day for guests, 20/day for authenticated users)
- Bot protection with Cloudflare Turnstile

---

## Authentication

The API uses **Supabase Auth** with JWT (JSON Web Tokens) for authentication.

### Token Types
- **Access Token**: Short-lived JWT (1 hour), used for API requests
- **Refresh Token**: Long-lived token (30 days), used to obtain new access tokens

### How to Authenticate Requests

Include the access token in the `Authorization` header:

```
Authorization: Bearer <your_access_token>
```

---

## Base URL

```
Production: https://your-domain.com
Development: http://localhost:8000
```

All endpoints are prefixed with `/api/v1/`

---

## Common Headers

### Required for All Requests
```http
Content-Type: application/json
```

### Required for Bot-Protected Endpoints
```http
X-Turnstile-Token: <turnstile_token>
```

**Bot-protected endpoints:**
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/tryon`

### Optional for Authenticated Requests
```http
Authorization: Bearer <access_token>
```

---

## Rate Limiting

| User Type | Daily Limit | Scope |
|-----------|-------------|-------|
| Guest | 5 requests | Per IP address |
| Authenticated | 20 requests | Per user account |

**Rate limit headers in response:**
```http
X-RateLimit-Limit: 20
X-RateLimit-Remaining: 15
X-RateLimit-Reset: 1698624000
```

When rate limit is exceeded, you'll receive a `429 Too Many Requests` error.

---

## Error Handling

### Standard Error Response Format

```json
{
  "detail": "Error message description"
}
```

### HTTP Status Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request successful |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error occurred |

---

## Endpoints

## Authentication Endpoints

### Register a New User

Create a new user account.

**Endpoint:** `POST /api/v1/auth/register`

**Headers:**
```http
Content-Type: application/json
X-Turnstile-Token: <turnstile_token>
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!",
  "username": "johndoe"
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Registration successful. Please check your email to verify your account.",
  "token": "email_verification_required",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "username": "johndoe",
    "created_at": "2025-10-29T10:30:00Z",
    "is_active": true
  }
}
```

**Notes:**
- Users must verify their email before they can log in
- Check your email inbox for verification link
- Username is optional; defaults to email prefix if not provided

---

### Login

Authenticate and receive access tokens.

**Endpoint:** `POST /api/v1/auth/login`

**Headers:**
```http
Content-Type: application/json
X-Turnstile-Token: <turnstile_token>
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Login successful",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "username": "johndoe",
    "created_at": "2025-10-29T10:30:00Z",
    "is_active": true
  }
}
```

**Notes:**
- Store both `token` (access token) and `refresh_token` securely
- Access token expires in 1 hour
- Use refresh token to obtain new access tokens

---

### Logout

Sign out the current user.

**Endpoint:** `POST /api/v1/auth/logout`

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Logout successful"
}
```

**Notes:**
- Tokens will expire naturally
- Clear stored tokens from client-side storage

---

### Request Password Reset

Request a password reset email.

**Endpoint:** `POST /api/v1/auth/reset-password`

**Headers:**
```http
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Query Parameters (Optional):**
- `redirect_to`: URL to redirect after password reset

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "If an account exists with this email, you will receive password reset instructions."
}
```

**Notes:**
- Always returns success to prevent email enumeration
- Password reset link expires in 1 hour
- Configure redirect URLs in Supabase dashboard

---

### Get Current User

Get the authenticated user's profile.

**Endpoint:** `GET /api/v1/auth/me`

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Response:** `200 OK`
```json
{
  "success": true,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "username": "johndoe",
    "created_at": "2025-10-29T10:30:00Z",
    "is_active": true
  }
}
```

---

### Health Check

Check authentication service health.

**Endpoint:** `GET /api/v1/auth/health`

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "service": "authentication"
}
```

---

## Try-On Endpoints

### Create Try-On Request

Submit a virtual try-on request with body and garment images.

**Endpoint:** `POST /api/v1/tryon`

**Headers:**
```http
Content-Type: multipart/form-data
X-Turnstile-Token: <turnstile_token>
Authorization: Bearer <access_token> (optional, for authenticated users)
```

**Request Body (multipart/form-data):**
```
body_image: <file> (required, max 10MB, jpg/jpeg/png/webp)
garment_images: <file> (required, max 10MB, jpg/jpeg/png/webp)
garment_images: <file> (optional, additional garments)
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Try-on request submitted successfully",
  "record_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "pending",
  "body_image_url": "https://storage.example.com/body_12345.jpg",
  "garment_image_urls": [
    "https://storage.example.com/garment_67890.jpg"
  ],
  "created_at": "2025-10-29T10:35:00Z"
}
```

**Rate Limits:**
- Guest users: 5 requests per day (tracked by IP)
- Authenticated users: 20 requests per day (tracked by user ID)

**File Requirements:**
- **Supported formats:** JPEG, JPG, PNG, WebP
- **Max file size:** 10 MB per file
- **Max garments:** 5 per request
- **Image dimensions:** Recommended 512x768 or similar aspect ratio

**Example with cURL:**
```bash
curl -X POST https://your-domain.com/api/v1/tryon \
  -H "X-Turnstile-Token: YOUR_TURNSTILE_TOKEN" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "body_image=@/path/to/body.jpg" \
  -F "garment_images=@/path/to/shirt.jpg" \
  -F "garment_images=@/path/to/pants.jpg"
```

---

### Get Try-On Result

Retrieve the result of a specific try-on request.

**Endpoint:** `GET /api/v1/tryon/{record_id}`

**Headers:**
```http
Authorization: Bearer <access_token> (optional, required for user-owned records)
```

**Path Parameters:**
- `record_id`: UUID of the try-on record

**Response:** `200 OK`
```json
{
  "success": true,
  "record": {
    "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "status": "success",
    "body_image_url": "https://storage.example.com/body_12345.jpg",
    "garment_image_urls": [
      "https://storage.example.com/garment_67890.jpg"
    ],
    "result_image_url": "https://storage.example.com/result_99999.jpg",
    "created_at": "2025-10-29T10:35:00Z",
    "completed_at": "2025-10-29T10:35:45Z",
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Status Values:**
- `pending`: Request queued, processing not started
- `processing`: AI model is processing the images
- `success`: Try-on completed successfully, result available
- `failed`: Processing failed (see `error_message` field)

**Error Response:** `404 Not Found`
```json
{
  "detail": "Record not found"
}
```

---

### Get Try-On Status

Check the status of a try-on request without full record details.

**Endpoint:** `GET /api/v1/tryon/{record_id}/status`

**Response:** `200 OK`
```json
{
  "success": true,
  "record_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "status": "processing",
  "created_at": "2025-10-29T10:35:00Z"
}
```

---

## User History Endpoints

### Get Try-On History

Retrieve the authenticated user's try-on history with pagination.

**Endpoint:** `GET /api/v1/auth/history`

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Query Parameters:**
- `limit` (optional, default: 20, max: 100): Number of records per page
- `offset` (optional, default: 0): Number of records to skip
- `status` (optional): Filter by status (`pending`, `processing`, `success`, `failed`)

**Example:**
```
GET /api/v1/auth/history?limit=10&offset=0&status=success
```

**Response:** `200 OK`
```json
{
  "success": true,
  "records": [
    {
      "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
      "status": "success",
      "body_image_url": "https://storage.example.com/body_12345.jpg",
      "garment_image_urls": [
        "https://storage.example.com/garment_67890.jpg"
      ],
      "result_image_url": "https://storage.example.com/result_99999.jpg",
      "created_at": "2025-10-29T10:35:00Z",
      "completed_at": "2025-10-29T10:35:45Z"
    }
  ],
  "total": 42,
  "limit": 10,
  "offset": 0,
  "has_more": true
}
```

---

### Get Single History Record

Retrieve a specific try-on record from user's history.

**Endpoint:** `GET /api/v1/auth/history/{record_id}`

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Path Parameters:**
- `record_id`: UUID of the try-on record

**Response:** `200 OK`
```json
{
  "success": true,
  "record": {
    "id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
    "status": "success",
    "body_image_url": "https://storage.example.com/body_12345.jpg",
    "garment_image_urls": [
      "https://storage.example.com/garment_67890.jpg"
    ],
    "result_image_url": "https://storage.example.com/result_99999.jpg",
    "created_at": "2025-10-29T10:35:00Z",
    "completed_at": "2025-10-29T10:35:45Z",
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Error Responses:**
- `404`: Record not found
- `403`: You don't have permission to access this record

---

### Delete History Record

Delete a specific try-on record from user's history.

**Endpoint:** `DELETE /api/v1/auth/history/{record_id}`

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Path Parameters:**
- `record_id`: UUID of the try-on record

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Record deleted successfully"
}
```

**Error Responses:**
- `404`: Record not found or you don't have permission to delete it

---

### Get User Statistics

Get aggregate statistics for the authenticated user's try-on history.

**Endpoint:** `GET /api/v1/auth/stats`

**Headers:**
```http
Authorization: Bearer <access_token>
```

**Response:** `200 OK`
```json
{
  "success": true,
  "stats": {
    "total_tryons": 42,
    "successful_tryons": 38,
    "failed_tryons": 2,
    "pending_tryons": 2,
    "success_rate": 0.95,
    "total_processing_time_ms": 95000,
    "average_processing_time_ms": 2500
  }
}
```

---

## Usage Examples

### Complete Authentication Flow

#### 1. Register a New User

```javascript
const response = await fetch('https://your-domain.com/api/v1/auth/register', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Turnstile-Token': turnstileToken
  },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'SecurePassword123!',
    username: 'johndoe'
  })
});

const data = await response.json();
// Check email for verification link
```

#### 2. Verify Email (via email link)

User clicks the verification link sent to their email.

#### 3. Login

```javascript
const response = await fetch('https://your-domain.com/api/v1/auth/login', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Turnstile-Token': turnstileToken
  },
  body: JSON.stringify({
    email: 'user@example.com',
    password: 'SecurePassword123!'
  })
});

const data = await response.json();
const accessToken = data.token;
const refreshToken = data.refresh_token;

// Store tokens securely (e.g., in memory or secure storage)
localStorage.setItem('access_token', accessToken);
localStorage.setItem('refresh_token', refreshToken);
```

---

### Complete Try-On Flow

#### 1. Submit Try-On Request

```javascript
const formData = new FormData();
formData.append('body_image', bodyImageFile);
formData.append('garment_images', garmentImageFile);

const response = await fetch('https://your-domain.com/api/v1/tryon', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'X-Turnstile-Token': turnstileToken
  },
  body: formData
});

const data = await response.json();
const recordId = data.record_id;
```

#### 2. Poll for Result

```javascript
async function pollForResult(recordId) {
  const maxAttempts = 60; // 1 minute with 1-second intervals
  let attempts = 0;
  
  while (attempts < maxAttempts) {
    const response = await fetch(
      `https://your-domain.com/api/v1/tryon/${recordId}`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );
    
    const data = await response.json();
    
    if (data.record.status === 'success') {
      return data.record.result_image_url;
    } else if (data.record.status === 'failed') {
      throw new Error('Try-on processing failed');
    }
    
    // Wait 1 second before next poll
    await new Promise(resolve => setTimeout(resolve, 1000));
    attempts++;
  }
  
  throw new Error('Timeout waiting for result');
}

const resultUrl = await pollForResult(recordId);
console.log('Result image URL:', resultUrl);
```

#### 3. View History

```javascript
const response = await fetch(
  'https://your-domain.com/api/v1/auth/history?limit=20&offset=0',
  {
    headers: {
      'Authorization': `Bearer ${accessToken}`
    }
  }
);

const data = await response.json();
console.log('Total try-ons:', data.total);
console.log('Records:', data.records);
```

---

## Python Example

```python
import requests
import time

# Configuration
BASE_URL = "https://your-domain.com/api/v1"
TURNSTILE_TOKEN = "your_turnstile_token"

# Register
register_response = requests.post(
    f"{BASE_URL}/auth/register",
    headers={"X-Turnstile-Token": TURNSTILE_TOKEN},
    json={
        "email": "user@example.com",
        "password": "SecurePassword123!",
        "username": "johndoe"
    }
)

# Login (after email verification)
login_response = requests.post(
    f"{BASE_URL}/auth/login",
    headers={"X-Turnstile-Token": TURNSTILE_TOKEN},
    json={
        "email": "user@example.com",
        "password": "SecurePassword123!"
    }
)

access_token = login_response.json()["token"]

# Submit try-on request
with open("body.jpg", "rb") as body_file, open("garment.jpg", "rb") as garment_file:
    files = {
        "body_image": body_file,
        "garment_images": garment_file
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Turnstile-Token": TURNSTILE_TOKEN
    }
    
    tryon_response = requests.post(
        f"{BASE_URL}/tryon",
        headers=headers,
        files=files
    )

record_id = tryon_response.json()["record_id"]

# Poll for result
max_attempts = 60
for _ in range(max_attempts):
    status_response = requests.get(
        f"{BASE_URL}/tryon/{record_id}",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    
    record = status_response.json()["record"]
    
    if record["status"] == "success":
        print(f"Result URL: {record['result_image_url']}")
        break
    elif record["status"] == "failed":
        print("Processing failed")
        break
    
    time.sleep(1)

# Get history
history_response = requests.get(
    f"{BASE_URL}/auth/history",
    headers={"Authorization": f"Bearer {access_token}"}
)

print(f"Total try-ons: {history_response.json()['total']}")
```

---

## Best Practices

### Security
1. **Never expose access tokens**: Don't log or transmit tokens in plain text
2. **Use HTTPS**: Always use secure connections in production
3. **Implement token refresh**: Use refresh tokens to obtain new access tokens
4. **Validate Turnstile**: Always include Turnstile tokens for bot-protected endpoints

### Performance
1. **Implement polling with backoff**: Use exponential backoff when polling for results
2. **Cache results**: Cache try-on results client-side to reduce API calls
3. **Optimize images**: Compress images before upload to reduce processing time
4. **Use pagination**: Always paginate when fetching history

### Error Handling
1. **Handle rate limits**: Implement retry logic with exponential backoff for 429 errors
2. **Check status codes**: Always check HTTP status codes before parsing response
3. **Validate file types**: Check file types and sizes before upload
4. **Display user-friendly messages**: Convert API errors to user-friendly messages

---


**Last Updated:** October 29, 2025
