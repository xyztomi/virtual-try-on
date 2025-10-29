"""Pydantic models for authentication endpoints."""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request payload for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    username: Optional[str] = Field(None, max_length=100)


class LoginRequest(BaseModel):
    """Request payload for user login."""

    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    """Request payload for password reset."""

    email: EmailStr


class AuthResponse(BaseModel):
    """Response payload for successful authentication."""

    success: bool
    message: str
    token: str
    refresh_token: Optional[str] = None
    user: dict


class MessageResponse(BaseModel):
    """Generic success response with message."""

    success: bool
    message: str


class UserResponse(BaseModel):
    """Response payload for current user information."""

    success: bool
    user: dict
