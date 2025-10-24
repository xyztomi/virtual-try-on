"""Pydantic models used by the try-on router."""

from typing import List, Optional

from pydantic import BaseModel, Field


class TryOnResponse(BaseModel):
    """Response model for try-on job submission."""

    success: bool
    record_id: str
    status: str = Field(..., description="Current processing status for the try-on job")
    body_url: Optional[str] = Field(None, description="Uploaded body image URL")
    garment_urls: List[str] = Field(
        default_factory=list, description="Uploaded garment image URLs"
    )
    message: str
    estimated_wait_seconds: Optional[int] = Field(
        None, description="Approximate wait time before result is ready"
    )


class ErrorResponse(BaseModel):
    """Generic error payload."""

    success: bool
    error: str
    record_id: Optional[str] = None


class TurnstileTestRequest(BaseModel):
    """Request payload for Turnstile sanity checks."""

    token: str


class TurnstileTestResponse(BaseModel):
    """Turnstile validation response payload."""

    success: bool
    message: str
    error_codes: List[str] = Field(default_factory=list)
    challenge_ts: Optional[str] = None
    hostname: Optional[str] = None
    action: Optional[str] = None
    cdata: Optional[str] = None


class RateLimitResponse(BaseModel):
    """Rate limit status details for the requester."""

    allowed: bool
    remaining: int
    reset_at: str
    total_today: int
    limit: int
    message: str
