# Password Reset Implementation

## Overview

Implemented password reset functionality using Supabase Auth's `reset_password_for_email()` method. This allows users to request a password reset email if they forget their password.

## Endpoint

### `POST /api/v1/auth/reset-password`

Request a password reset email for a user.

#### Request Body

```json
{
  "email": "user@example.com"
}
```

#### Query Parameters (Optional)

- `redirect_to` (string): URL to redirect to after password reset. Must be configured in your Supabase project settings.

#### Response

```json
{
  "success": true,
  "message": "If an account exists with this email, you will receive password reset instructions."
}
```

**Note:** The endpoint always returns a success message, even if the email doesn't exist. This prevents email enumeration attacks where attackers could determine which emails are registered.

## Example Usage

### cURL

```bash
curl -X POST https://your-api.com/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com"}'
```

### JavaScript/TypeScript

```typescript
async function requestPasswordReset(email: string) {
  const response = await fetch('https://your-api.com/api/v1/auth/reset-password', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email }),
  });
  
  const data = await response.json();
  console.log(data.message);
}

// Usage
await requestPasswordReset('user@example.com');
```

### Python

```python
import requests

def request_password_reset(email: str):
    response = requests.post(
        'https://your-api.com/api/v1/auth/reset-password',
        json={'email': email}
    )
    data = response.json()
    print(data['message'])

# Usage
request_password_reset('user@example.com')
```

## Supabase Configuration Required

### 1. Configure Email Templates

In your Supabase Dashboard:

1. Go to **Authentication** → **Email Templates**
2. Find the **Reset Password** template
3. Customize the email content and styling
4. The template will include a magic link: `{{ .ConfirmationURL }}`

### 2. Configure Redirect URLs

In your Supabase Dashboard:

1. Go to **Authentication** → **URL Configuration**
2. Add your allowed redirect URLs to the **Redirect URLs** list
3. Example: `https://yourdomain.com/reset-password`

### 3. Enable Email Authentication

Ensure email authentication is enabled:

1. Go to **Authentication** → **Providers**
2. Make sure **Email** provider is enabled

## How It Works

1. **User requests password reset**: User submits their email via the endpoint
2. **Email validation**: System checks if email exists (but doesn't reveal this info)
3. **Supabase sends email**: If email exists, Supabase sends a password reset email with a magic link
4. **User clicks link**: Email contains a link like: `https://yourdomain.com/reset-password?token=xxx`
5. **Frontend handles reset**: Your frontend captures the token and allows user to set new password
6. **Update password**: Use Supabase's `updateUser()` method to set the new password

## Frontend Integration

After receiving the reset token, your frontend should:

```typescript
// 1. Extract token from URL
const urlParams = new URLSearchParams(window.location.search);
const token = urlParams.get('token');

// 2. Let user enter new password
const newPassword = document.getElementById('password-input').value;

// 3. Update password using Supabase client
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

const { data, error } = await supabase.auth.updateUser({
  password: newPassword
});

if (error) {
  console.error('Password reset failed:', error);
} else {
  console.log('Password reset successful!');
}
```

## Security Features

### Email Enumeration Prevention

The endpoint always returns the same success message, regardless of whether the email exists. This prevents attackers from discovering which emails are registered in your system.

### Rate Limiting (Recommended)

Consider adding rate limiting to this endpoint to prevent abuse:

```python
# Add to your rate limiting configuration
PASSWORD_RESET_LIMIT = 3  # Max 3 requests per hour per IP
```

## Database Changes

No database schema changes required! This feature uses:
- Supabase's built-in auth system
- Your existing `users` table (for email lookup)

## Testing

### Manual Test

1. **Request password reset**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/auth/reset-password \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com"}'
   ```

2. **Check your email** (or Supabase logs if in development mode)

3. **Click the reset link** in the email

4. **Set new password** via your frontend

### Test with Non-existent Email

Should still return success (security feature):
```bash
curl -X POST http://localhost:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{"email": "nonexistent@example.com"}'
```

Expected response:
```json
{
  "success": true,
  "message": "If an account exists with this email, you will receive password reset instructions."
}
```

## Files Modified

1. **`src/routers/auth/models.py`**
   - Added `PasswordResetRequest` model

2. **`src/core/auth.py`**
   - Added `request_password_reset()` function

3. **`src/routers/auth/router.py`**
   - Added `POST /reset-password` endpoint

## Troubleshooting

### Email Not Received

1. **Check Supabase email logs**: Dashboard → Authentication → Logs
2. **Verify email provider**: Ensure SMTP is configured in Supabase
3. **Check spam folder**: Reset emails might be flagged as spam
4. **Verify email exists**: User must be registered

### "Invalid redirect URL" Error

1. Add your redirect URL to Supabase's allowed list
2. Ensure the URL exactly matches (including protocol)
3. Wildcard patterns are supported: `https://*.yourdomain.com/*`

### Development Mode

In development, Supabase may show the reset link in the API response or logs instead of sending an actual email. Check your Supabase project settings.

## Next Steps

Consider implementing:

1. **Password strength validation** on the frontend
2. **Rate limiting** on the reset endpoint
3. **Password history** to prevent reusing old passwords
4. **Two-factor authentication** for added security
5. **Email verification** for new accounts

## References

- [Supabase Auth Reset Password Documentation](https://supabase.com/docs/reference/python/auth-resetpasswordforemail)
- [Supabase Email Templates Guide](https://supabase.com/docs/guides/auth/auth-email-templates)
- [Supabase Password Reset Flow](https://supabase.com/docs/guides/auth/auth-password-reset)
