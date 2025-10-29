# Frontend Integration Guide - Virtual Try-On

## Table of Contents
- [Overview](#overview)
- [User Experience Flows](#user-experience-flows)
- [Implementation Guide](#implementation-guide)
- [State Management](#state-management)
- [UI Components](#ui-components)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)
- [Complete Code Examples](#complete-code-examples)

---

## Overview

This guide provides everything you need to integrate the Virtual Try-On API into your frontend application, including detailed UX flows, UI patterns, and complete implementation examples.

**Key Features:**
- Guest mode (5 tries/day) and authenticated mode (20 tries/day)
- Bot protection with Cloudflare Turnstile
- Real-time processing status updates
- Quality audit scoring with AI
- User history and analytics

**Tech Stack Compatibility:**
- React, Vue, Angular, Svelte, or vanilla JavaScript
- Works with any HTTP client (fetch, axios, etc.)
- Responsive design patterns included

---

## User Experience Flows

### Flow 1: Guest User Journey

```
┌─────────────────────────────────────────────────────────────┐
│                    LANDING PAGE                              │
│  - Hero section with demo try-on examples                   │
│  - "Try Now" CTA button                                      │
│  - "Sign Up for More" link                                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   TRY-ON INTERFACE                           │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │  Upload Body     │  │  Upload Garment  │                │
│  │  Image           │  │  Image(s)        │                │
│  │  [Drop zone]     │  │  [Drop zone]     │                │
│  └──────────────────┘  └──────────────────┘                │
│                                                              │
│  Tips:                                                       │
│  • Use clear, well-lit photos                               │
│  • Stand straight, arms slightly apart                      │
│  • Supported: JPG, PNG, WebP (max 10MB)                    │
│                                                              │
│  [Turnstile Captcha Widget]                                │
│                                                              │
│  [Generate Try-On] button                                   │
│                                                              │
│  Remaining tries today: 4/5 (Guest)                        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   PROCESSING SCREEN                          │
│                                                              │
│           🔄  Generating your try-on...                     │
│                                                              │
│  [████████░░░░░░░░░░] 40%                                   │
│                                                              │
│  Status: Processing with AI                                 │
│  Estimated time: 20-30 seconds                              │
│                                                              │
│  ⚠️ Don't close this page                                   │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                   RESULT SCREEN                              │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   Original  │    │   Garment   │    │   Result    │    │
│  │   [Image]   │ +  │   [Image]   │ =  │   [Image]   │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│                                                              │
│  Quality Score: ⭐ 85/100                                   │
│  Processing Time: 2.5s                                      │
│                                                              │
│  [Download Result] [Try Another] [Sign Up to Save]         │
│                                                              │
│  💡 Sign up to:                                             │
│  • Save your try-ons                                        │
│  • Get 20 tries per day                                     │
│  • Access history & analytics                               │
└─────────────────────────────────────────────────────────────┘
```

**Key UX Considerations:**
- Show try count remaining prominently
- Display clear upload guidelines
- Provide real-time processing feedback
- Encourage sign-up after successful try-on
- Handle rate limits gracefully

---

### Flow 2: New User Registration

```
┌─────────────────────────────────────────────────────────────┐
│                  SIGN UP SCREEN                              │
│                                                              │
│  Create Your Account                                         │
│                                                              │
│  Email:     [________________]                              │
│  Password:  [________________]                              │
│             (min 8 chars, include numbers)                   │
│  Username:  [________________] (optional)                   │
│                                                              │
│  [Turnstile Captcha Widget]                                │
│                                                              │
│  [Create Account] button                                     │
│                                                              │
│  Already have an account? [Log In]                          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              EMAIL VERIFICATION SCREEN                       │
│                                                              │
│           ✉️  Check your email!                             │
│                                                              │
│  We sent a verification link to:                            │
│  user@example.com                                           │
│                                                              │
│  Click the link to activate your account                    │
│                                                              │
│  Didn't receive it? [Resend Email]                         │
│                                                              │
│  [Back to Login]                                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
                   (User clicks email link)
                           ↓
┌─────────────────────────────────────────────────────────────┐
│            EMAIL VERIFIED - AUTO LOGIN                       │
│                                                              │
│           ✅  Account verified!                             │
│                                                              │
│  Redirecting to try-on interface...                         │
└─────────────────────────────────────────────────────────────┘
```

**Key UX Considerations:**
- Password strength indicator
- Clear validation errors
- Resend verification email option
- Auto-login after email verification (if clicked from same browser)

---

### Flow 3: Authenticated User Journey

```
┌─────────────────────────────────────────────────────────────┐
│                    LOGIN SCREEN                              │
│                                                              │
│  Welcome Back!                                               │
│                                                              │
│  Email:     [________________]                              │
│  Password:  [________________]                              │
│                                                              │
│  [Turnstile Captcha Widget]                                │
│                                                              │
│  [Log In] button                                             │
│                                                              │
│  [Forgot Password?]                                         │
│  Don't have an account? [Sign Up]                          │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              AUTHENTICATED DASHBOARD                         │
│                                                              │
│  👤 Welcome back, John!                    [Logout]         │
│                                                              │
│  📊 Your Stats:                                             │
│  • Total try-ons: 42                                        │
│  • Success rate: 95%                                        │
│  • Remaining today: 15/20                                   │
│                                                              │
│  [New Try-On] [View History] [Account Settings]            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                TRY-ON HISTORY PAGE                           │
│                                                              │
│  📚 Your Try-On History                                     │
│                                                              │
│  Filters: [All] [Successful] [Failed] [Pending]            │
│  Sort by: [Newest First ▼]                                 │
│                                                              │
│  ┌──────────────────────────────────────────────┐          │
│  │ Oct 29, 2025 - 10:35 AM      Quality: ⭐ 85  │          │
│  │ [Thumbnail] [Thumbnail] → [Result]            │          │
│  │ Processing: 2.5s              [View] [Delete] │          │
│  └──────────────────────────────────────────────┘          │
│                                                              │
│  ┌──────────────────────────────────────────────┐          │
│  │ Oct 28, 2025 - 3:20 PM       Quality: ⭐ 92  │          │
│  │ [Thumbnail] [Thumbnail] → [Result]            │          │
│  │ Processing: 2.1s              [View] [Delete] │          │
│  └──────────────────────────────────────────────┘          │
│                                                              │
│  [Load More]                                                 │
│  Showing 20 of 42 results                                   │
└─────────────────────────────────────────────────────────────┘
```

**Key UX Considerations:**
- Persistent authentication (remember user)
- Quick access to new try-on and history
- Clear stats display
- Easy history filtering and sorting
- Bulk actions (delete multiple)

---

### Flow 4: Password Reset

```
┌─────────────────────────────────────────────────────────────┐
│              FORGOT PASSWORD SCREEN                          │
│                                                              │
│  Reset Your Password                                         │
│                                                              │
│  Enter your email address and we'll send                    │
│  you a link to reset your password.                         │
│                                                              │
│  Email: [________________]                                  │
│                                                              │
│  [Send Reset Link]                                          │
│                                                              │
│  [Back to Login]                                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│            PASSWORD RESET EMAIL SENT                         │
│                                                              │
│           ✉️  Check your email!                             │
│                                                              │
│  If an account exists with that email,                      │
│  you'll receive reset instructions shortly.                 │
│                                                              │
│  [Back to Login]                                            │
└─────────────────────────────────────────────────────────────┘
```

**Key UX Considerations:**
- Generic success message (security: don't reveal if email exists)
- Clear instructions
- Link expiration time mentioned in email

---

## Implementation Guide

### 1. Environment Setup

```bash
# Required environment variables
VITE_API_BASE_URL=https://your-api-domain.com/api/v1
VITE_TURNSTILE_SITE_KEY=your_turnstile_site_key
```

### 2. Install Turnstile (Bot Protection)

**HTML:**
```html
<!-- Add to index.html -->
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
```

**React Component:**
```jsx
import { useEffect, useRef } from 'react';

export function TurnstileWidget({ onVerify }) {
  const containerRef = useRef(null);
  const widgetId = useRef(null);

  useEffect(() => {
    if (window.turnstile && containerRef.current) {
      widgetId.current = window.turnstile.render(containerRef.current, {
        sitekey: import.meta.env.VITE_TURNSTILE_SITE_KEY,
        callback: (token) => {
          onVerify(token);
        },
        'error-callback': () => {
          onVerify(null);
        },
      });
    }

    return () => {
      if (widgetId.current) {
        window.turnstile.remove(widgetId.current);
      }
    };
  }, [onVerify]);

  return <div ref={containerRef} />;
}
```

### 3. API Client Setup

```javascript
// api/client.js
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

class APIClient {
  constructor() {
    this.accessToken = localStorage.getItem('access_token');
    this.refreshToken = localStorage.getItem('refresh_token');
  }

  setTokens(accessToken, refreshToken) {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
  }

  clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }

  async request(endpoint, options = {}) {
    const headers = {
      ...options.headers,
    };

    // Add authorization header if token exists
    if (this.accessToken && !options.skipAuth) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    // Add Turnstile token if provided
    if (options.turnstileToken) {
      headers['X-Turnstile-Token'] = options.turnstileToken;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    // Handle 401 (could implement token refresh here)
    if (response.status === 401) {
      this.clearTokens();
      window.location.href = '/login';
      throw new Error('Session expired');
    }

    // Handle rate limiting
    if (response.status === 429) {
      const resetTime = response.headers.get('X-RateLimit-Reset');
      throw new Error(`Rate limit exceeded. Try again later.`);
    }

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Request failed');
    }

    return response.json();
  }

  // Auth methods
  async register(email, password, username, turnstileToken) {
    return this.request('/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, username }),
      turnstileToken,
      skipAuth: true,
    });
  }

  async login(email, password, turnstileToken) {
    const data = await this.request('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
      turnstileToken,
      skipAuth: true,
    });

    this.setTokens(data.token, data.refresh_token);
    return data;
  }

  async logout() {
    await this.request('/auth/logout', { method: 'POST' });
    this.clearTokens();
  }

  async resetPassword(email) {
    return this.request('/auth/reset-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
      skipAuth: true,
    });
  }

  async getCurrentUser() {
    return this.request('/auth/me');
  }

  async getUserStats() {
    return this.request('/auth/stats');
  }

  // Try-on methods
  async createTryOn(bodyImage, garmentImages, turnstileToken) {
    const formData = new FormData();
    formData.append('body_image', bodyImage);
    
    garmentImages.forEach(image => {
      formData.append('garment_images', image);
    });

    return this.request('/tryon', {
      method: 'POST',
      body: formData,
      turnstileToken,
      skipAuth: !this.accessToken, // Skip auth for guest users
    });
  }

  async getTryOnResult(recordId) {
    return this.request(`/tryon/${recordId}`);
  }

  async getTryOnStatus(recordId) {
    return this.request(`/tryon/${recordId}/status`);
  }

  // History methods
  async getHistory(limit = 20, offset = 0, status = null) {
    const params = new URLSearchParams({ limit, offset });
    if (status) params.append('status', status);
    return this.request(`/auth/history?${params}`);
  }

  async getHistoryRecord(recordId) {
    return this.request(`/auth/history/${recordId}`);
  }

  async deleteHistoryRecord(recordId) {
    return this.request(`/auth/history/${recordId}`, { method: 'DELETE' });
  }
}

export const apiClient = new APIClient();
```

---

## State Management

### React Context Example

```jsx
// context/AuthContext.jsx
import { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '../api/client';

const AuthContext = createContext();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (token) {
        const userData = await apiClient.getCurrentUser();
        setUser(userData.user);
        setIsAuthenticated(true);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      apiClient.clearTokens();
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password, turnstileToken) => {
    const data = await apiClient.login(email, password, turnstileToken);
    setUser(data.user);
    setIsAuthenticated(true);
    return data;
  };

  const logout = async () => {
    await apiClient.logout();
    setUser(null);
    setIsAuthenticated(false);
  };

  const register = async (email, password, username, turnstileToken) => {
    return apiClient.register(email, password, username, turnstileToken);
  };

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      isAuthenticated,
      login,
      logout,
      register,
      checkAuth,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
```

---

## UI Components

### 1. Image Upload Component

```jsx
// components/ImageUpload.jsx
import { useState, useRef } from 'react';

export function ImageUpload({ 
  label, 
  accept = "image/jpeg,image/jpg,image/png,image/webp",
  maxSize = 10 * 1024 * 1024, // 10MB
  multiple = false,
  onUpload 
}) {
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const validateFile = (file) => {
    if (file.size > maxSize) {
      throw new Error('File size must be less than 10MB');
    }

    const validTypes = accept.split(',');
    if (!validTypes.some(type => file.type.includes(type.replace('image/', '')))) {
      throw new Error('Invalid file type. Use JPG, PNG, or WebP');
    }
  };

  const handleFiles = (files) => {
    setError('');
    
    try {
      const fileArray = Array.from(files);
      
      fileArray.forEach(validateFile);

      // Create preview for first file
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target.result);
      reader.readAsDataURL(fileArray[0]);

      onUpload(multiple ? fileArray : fileArray[0]);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  return (
    <div className="image-upload">
      <label className="image-upload__label">{label}</label>
      
      <div
        className={`image-upload__dropzone ${isDragging ? 'dragging' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
      >
        {preview ? (
          <img src={preview} alt="Preview" className="image-upload__preview" />
        ) : (
          <div className="image-upload__placeholder">
            <svg className="image-upload__icon" /* upload icon SVG */ />
            <p>Drop image here or click to upload</p>
            <small>JPG, PNG, WebP (max 10MB)</small>
          </div>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={(e) => handleFiles(e.target.files)}
        style={{ display: 'none' }}
      />

      {error && <p className="image-upload__error">{error}</p>}
    </div>
  );
}
```

### 2. Try-On Processing Component

```jsx
// components/TryOnProcessing.jsx
import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';

export function TryOnProcessing({ recordId, onComplete, onError }) {
  const [status, setStatus] = useState('pending');
  const [progress, setProgress] = useState(0);
  const [elapsedTime, setElapsedTime] = useState(0);

  useEffect(() => {
    const startTime = Date.now();
    
    // Update elapsed time
    const timeInterval = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    // Poll for status
    const pollInterval = setInterval(async () => {
      try {
        const result = await apiClient.getTryOnResult(recordId);
        
        setStatus(result.record.status);

        // Update progress based on status
        if (result.record.status === 'processing') {
          setProgress(prev => Math.min(prev + 5, 90));
        } else if (result.record.status === 'success') {
          setProgress(100);
          clearInterval(pollInterval);
          clearInterval(timeInterval);
          setTimeout(() => onComplete(result.record), 500);
        } else if (result.record.status === 'failed') {
          clearInterval(pollInterval);
          clearInterval(timeInterval);
          onError(result.record.error_message || 'Processing failed');
        }
      } catch (error) {
        clearInterval(pollInterval);
        clearInterval(timeInterval);
        onError(error.message);
      }
    }, 2000); // Poll every 2 seconds

    // Timeout after 2 minutes
    const timeout = setTimeout(() => {
      clearInterval(pollInterval);
      clearInterval(timeInterval);
      onError('Processing timeout - please try again');
    }, 120000);

    return () => {
      clearInterval(pollInterval);
      clearInterval(timeInterval);
      clearTimeout(timeout);
    };
  }, [recordId, onComplete, onError]);

  return (
    <div className="tryon-processing">
      <div className="processing-spinner">
        <div className="spinner" />
      </div>

      <h2>Generating your try-on...</h2>

      <div className="progress-bar">
        <div 
          className="progress-bar__fill" 
          style={{ width: `${progress}%` }}
        />
      </div>

      <p className="processing-status">
        Status: {status === 'pending' ? 'Queued' : 'Processing with AI'}
      </p>

      <p className="processing-time">
        Elapsed: {elapsedTime}s
        {elapsedTime < 30 && ' • Estimated: 20-30 seconds'}
      </p>

      <p className="processing-warning">
        ⚠️ Don't close this page
      </p>
    </div>
  );
}
```

### 3. Result Display Component

```jsx
// components/TryOnResult.jsx
export function TryOnResult({ result, onNewTryOn }) {
  const downloadImage = () => {
    const link = document.createElement('a');
    link.href = result.result_image_url;
    link.download = `tryon-${result.id}.jpg`;
    link.click();
  };

  const shareResult = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Virtual Try-On Result',
          text: 'Check out my virtual try-on!',
          url: window.location.href,
        });
      } catch (err) {
        console.log('Share failed:', err);
      }
    }
  };

  return (
    <div className="tryon-result">
      <h2>✨ Your Try-On Result</h2>

      <div className="result-comparison">
        <div className="result-image">
          <label>Original</label>
          <img src={result.body_image_url} alt="Original" />
        </div>

        <div className="result-operator">+</div>

        <div className="result-image">
          <label>Garment</label>
          <img src={result.garment_image_urls[0]} alt="Garment" />
        </div>

        <div className="result-operator">=</div>

        <div className="result-image result-image--main">
          <label>Result</label>
          <img src={result.result_image_url} alt="Result" />
        </div>
      </div>

      {result.audit_score && (
        <div className="result-quality">
          <label>Quality Score:</label>
          <div className="quality-score">
            <span className="score-value">⭐ {result.audit_score}/100</span>
            <div className="score-bar">
              <div 
                className="score-bar__fill" 
                style={{ width: `${result.audit_score}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {result.processing_time_ms && (
        <p className="result-meta">
          Processing Time: {(result.processing_time_ms / 1000).toFixed(1)}s
        </p>
      )}

      <div className="result-actions">
        <button onClick={downloadImage} className="btn btn-primary">
          📥 Download Result
        </button>
        <button onClick={shareResult} className="btn btn-secondary">
          🔗 Share
        </button>
        <button onClick={onNewTryOn} className="btn btn-secondary">
          🔄 Try Another
        </button>
      </div>
    </div>
  );
}
```

### 4. Rate Limit Display

```jsx
// components/RateLimitIndicator.jsx
import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';

export function RateLimitIndicator() {
  const { isAuthenticated, user } = useAuth();
  const [remaining, setRemaining] = useState(null);
  const [limit, setLimit] = useState(null);

  useEffect(() => {
    // Set initial limits based on auth status
    setLimit(isAuthenticated ? 20 : 5);
    
    // You might want to fetch actual usage from API
    // For now, we'll track locally
    const used = parseInt(localStorage.getItem('tryons_today') || '0');
    setRemaining((isAuthenticated ? 20 : 5) - used);
  }, [isAuthenticated]);

  if (remaining === null) return null;

  const percentage = (remaining / limit) * 100;
  const isLow = percentage < 30;
  const isVeryLow = percentage < 10;

  return (
    <div className={`rate-limit ${isLow ? 'low' : ''} ${isVeryLow ? 'very-low' : ''}`}>
      <div className="rate-limit__content">
        <span className="rate-limit__label">
          {isAuthenticated ? '🔐 Authenticated' : '👤 Guest Mode'}
        </span>
        <span className="rate-limit__count">
          {remaining}/{limit} tries remaining today
        </span>
      </div>
      
      <div className="rate-limit__bar">
        <div 
          className="rate-limit__fill" 
          style={{ width: `${percentage}%` }}
        />
      </div>

      {!isAuthenticated && remaining < 3 && (
        <p className="rate-limit__upgrade">
          💡 Sign up to get {20 - limit} more tries per day!
        </p>
      )}
    </div>
  );
}
```

---

## Error Handling

### Error Handler Utility

```javascript
// utils/errorHandler.js
export class APIError extends Error {
  constructor(message, status, code) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export const handleAPIError = (error) => {
  // Network errors
  if (error.message === 'Failed to fetch') {
    return {
      title: 'Connection Error',
      message: 'Unable to connect to server. Check your internet connection.',
      action: 'Retry',
    };
  }

  // Rate limit
  if (error.message.includes('Rate limit exceeded')) {
    return {
      title: 'Rate Limit Reached',
      message: 'You\'ve reached your daily limit. Upgrade to get more tries!',
      action: 'Upgrade',
    };
  }

  // Authentication errors
  if (error.message.includes('Session expired')) {
    return {
      title: 'Session Expired',
      message: 'Please log in again to continue.',
      action: 'Login',
    };
  }

  // Validation errors
  if (error.message.includes('Invalid file')) {
    return {
      title: 'Invalid File',
      message: error.message,
      action: 'Try Again',
    };
  }

  // Default error
  return {
    title: 'Something Went Wrong',
    message: error.message || 'An unexpected error occurred.',
    action: 'Try Again',
  };
};
```

### Error Toast Component

```jsx
// components/ErrorToast.jsx
import { useEffect } from 'react';

export function ErrorToast({ error, onClose, duration = 5000 }) {
  useEffect(() => {
    if (duration) {
      const timer = setTimeout(onClose, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, onClose]);

  if (!error) return null;

  const errorInfo = handleAPIError(error);

  return (
    <div className="error-toast">
      <div className="error-toast__content">
        <strong>{errorInfo.title}</strong>
        <p>{errorInfo.message}</p>
      </div>
      <button onClick={onClose} className="error-toast__close">
        ✕
      </button>
    </div>
  );
}
```

---

## Best Practices

### 1. Image Optimization

```javascript
// utils/imageUtils.js
export const optimizeImage = async (file, maxWidth = 1024, maxHeight = 1536) => {
  return new Promise((resolve) => {
    const reader = new FileReader();
    
    reader.onload = (e) => {
      const img = new Image();
      
      img.onload = () => {
        const canvas = document.createElement('canvas');
        let width = img.width;
        let height = img.height;

        // Calculate new dimensions maintaining aspect ratio
        if (width > maxWidth || height > maxHeight) {
          const ratio = Math.min(maxWidth / width, maxHeight / height);
          width = width * ratio;
          height = height * ratio;
        }

        canvas.width = width;
        canvas.height = height;

        const ctx = canvas.getContext('2d');
        ctx.drawImage(img, 0, 0, width, height);

        canvas.toBlob((blob) => {
          resolve(new File([blob], file.name, { type: 'image/jpeg' }));
        }, 'image/jpeg', 0.9);
      };

      img.src = e.target.result;
    };

    reader.readAsDataURL(file);
  });
};
```

### 2. Responsive Design

```css
/* Mobile-first approach */
.tryon-interface {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
}

.result-comparison {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Tablet and up */
@media (min-width: 768px) {
  .tryon-interface {
    flex-direction: row;
    padding: 2rem;
  }

  .result-comparison {
    flex-direction: row;
    align-items: center;
  }
}

/* Desktop */
@media (min-width: 1024px) {
  .tryon-interface {
    max-width: 1200px;
    margin: 0 auto;
  }
}
```

### 3. Accessibility

```jsx
// Always include:
// - Proper alt text for images
// - ARIA labels for interactive elements
// - Keyboard navigation support
// - Focus indicators
// - Screen reader announcements

<button
  onClick={handleSubmit}
  disabled={isLoading}
  aria-label="Generate virtual try-on"
  aria-busy={isLoading}
>
  {isLoading ? 'Processing...' : 'Generate Try-On'}
</button>

// Announce status changes
<div role="status" aria-live="polite" aria-atomic="true">
  {status === 'processing' && 'Processing your try-on...'}
  {status === 'success' && 'Try-on completed successfully!'}
</div>
```

### 4. Performance Optimization

```javascript
// Lazy load components
const TryOnHistory = lazy(() => import('./components/TryOnHistory'));
const UserSettings = lazy(() => import('./components/UserSettings'));

// Debounce file uploads
import { debounce } from 'lodash';

const debouncedUpload = debounce((file) => {
  handleFileUpload(file);
}, 300);

// Memoize expensive computations
const memoizedStats = useMemo(() => {
  return calculateStats(userData);
}, [userData]);

// Implement virtual scrolling for long lists
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={600}
  itemCount={items.length}
  itemSize={100}
>
  {Row}
</FixedSizeList>
```

---

## Complete Code Examples

### Complete Try-On Page (React)

```jsx
// pages/TryOn.jsx
import { useState } from 'react';
import { ImageUpload } from '../components/ImageUpload';
import { TurnstileWidget } from '../components/TurnstileWidget';
import { TryOnProcessing } from '../components/TryOnProcessing';
import { TryOnResult } from '../components/TryOnResult';
import { RateLimitIndicator } from '../components/RateLimitIndicator';
import { ErrorToast } from '../components/ErrorToast';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';

export function TryOnPage() {
  const { isAuthenticated } = useAuth();
  const [bodyImage, setBodyImage] = useState(null);
  const [garmentImages, setGarmentImages] = useState([]);
  const [turnstileToken, setTurnstileToken] = useState(null);
  const [stage, setStage] = useState('upload'); // upload, processing, result
  const [recordId, setRecordId] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canSubmit = bodyImage && garmentImages.length > 0 && turnstileToken;

  const handleSubmit = async () => {
    if (!canSubmit) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await apiClient.createTryOn(
        bodyImage,
        garmentImages,
        turnstileToken
      );

      // Track usage
      const used = parseInt(localStorage.getItem('tryons_today') || '0');
      localStorage.setItem('tryons_today', (used + 1).toString());

      setRecordId(response.record_id);
      setStage('processing');
    } catch (err) {
      setError(err);
      // Reset Turnstile
      setTurnstileToken(null);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleProcessingComplete = (completedResult) => {
    setResult(completedResult);
    setStage('result');
  };

  const handleProcessingError = (errorMessage) => {
    setError(new Error(errorMessage));
    setStage('upload');
    setTurnstileToken(null);
  };

  const handleNewTryOn = () => {
    setStage('upload');
    setBodyImage(null);
    setGarmentImages([]);
    setTurnstileToken(null);
    setRecordId(null);
    setResult(null);
  };

  return (
    <div className="tryon-page">
      <header className="tryon-header">
        <h1>✨ Virtual Try-On</h1>
        <RateLimitIndicator />
      </header>

      {stage === 'upload' && (
        <div className="tryon-upload">
          <div className="upload-grid">
            <ImageUpload
              label="Upload Body Image"
              onUpload={setBodyImage}
            />
            
            <ImageUpload
              label="Upload Garment Image(s)"
              multiple
              onUpload={(files) => setGarmentImages(Array.isArray(files) ? files : [files])}
            />
          </div>

          <div className="upload-tips">
            <h3>📸 Tips for Best Results:</h3>
            <ul>
              <li>Use clear, well-lit photos</li>
              <li>Stand straight with arms slightly apart</li>
              <li>Wear fitted clothing for body image</li>
              <li>Use high-quality garment photos</li>
              <li>Supported formats: JPG, PNG, WebP (max 10MB)</li>
            </ul>
          </div>

          <div className="upload-captcha">
            <TurnstileWidget onVerify={setTurnstileToken} />
          </div>

          <button
            onClick={handleSubmit}
            disabled={!canSubmit || isSubmitting}
            className="btn btn-primary btn-large"
          >
            {isSubmitting ? '⏳ Submitting...' : '✨ Generate Try-On'}
          </button>

          {!isAuthenticated && (
            <div className="upgrade-prompt">
              <p>💡 Want more tries and access to history?</p>
              <a href="/register" className="btn btn-secondary">
                Sign Up for Free
              </a>
            </div>
          )}
        </div>
      )}

      {stage === 'processing' && (
        <TryOnProcessing
          recordId={recordId}
          onComplete={handleProcessingComplete}
          onError={handleProcessingError}
        />
      )}

      {stage === 'result' && (
        <TryOnResult
          result={result}
          onNewTryOn={handleNewTryOn}
        />
      )}

      <ErrorToast
        error={error}
        onClose={() => setError(null)}
      />
    </div>
  );
}
```

### Complete Login Page

```jsx
// pages/Login.jsx
import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { TurnstileWidget } from '../components/TurnstileWidget';
import { ErrorToast } from '../components/ErrorToast';
import { useAuth } from '../context/AuthContext';

export function LoginPage() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [turnstileToken, setTurnstileToken] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!turnstileToken) {
      setError(new Error('Please complete the captcha'));
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await login(email, password, turnstileToken);
      navigate('/dashboard');
    } catch (err) {
      setError(err);
      setTurnstileToken(null);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-container">
        <h1>Welcome Back!</h1>
        <p className="subtitle">Log in to your account</p>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <div className="form-captcha">
            <TurnstileWidget onVerify={setTurnstileToken} />
          </div>

          <button
            type="submit"
            disabled={!turnstileToken || isSubmitting}
            className="btn btn-primary btn-large"
          >
            {isSubmitting ? 'Logging in...' : 'Log In'}
          </button>

          <div className="form-links">
            <Link to="/reset-password">Forgot Password?</Link>
          </div>
        </form>

        <div className="form-footer">
          <p>
            Don't have an account?{' '}
            <Link to="/register">Sign Up</Link>
          </p>
        </div>
      </div>

      <ErrorToast error={error} onClose={() => setError(null)} />
    </div>
  );
}
```

---

## Testing Checklist

### Functional Testing
- [ ] Guest user can perform try-on (max 5/day)
- [ ] Registration flow works with email verification
- [ ] Login with correct/incorrect credentials
- [ ] Password reset sends email
- [ ] Authenticated users can perform 20 try-ons/day
- [ ] Try-on processing completes successfully
- [ ] Results display correctly with quality scores
- [ ] History page loads and filters work
- [ ] Delete history records works
- [ ] Logout clears session

### UX Testing
- [ ] Loading states are clear
- [ ] Error messages are helpful
- [ ] Rate limits are visible
- [ ] Image upload provides feedback
- [ ] Processing time is acceptable
- [ ] Results are visually appealing
- [ ] Mobile experience is smooth

### Edge Cases
- [ ] Handle network errors gracefully
- [ ] Handle rate limit exceeded
- [ ] Handle invalid file types/sizes
- [ ] Handle session expiration
- [ ] Handle processing timeout
- [ ] Handle concurrent requests

---

## Support & Resources

**API Documentation:** See `API_DOCUMENTATION.md` for full API reference

**Common Issues:**
1. **Turnstile not loading** - Check site key configuration
2. **Rate limit errors** - Implement proper client-side tracking
3. **Processing timeout** - Implement retry mechanism
4. **Image quality issues** - Validate and optimize before upload

**Performance Tips:**
- Implement image compression before upload
- Use lazy loading for history pages
- Cache API responses where appropriate
- Implement optimistic UI updates

---

**Last Updated:** October 29, 2025
