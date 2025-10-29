"""Authentication-related FastAPI dependencies."""

from typing import Optional

from fastapi import Header, HTTPException

from src.core import auth


async def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    """Retrieve the authenticated user from a Supabase Auth Bearer token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401, detail="Invalid authorization header format"
        )

    access_token = parts[1]

    # Verify token with Supabase Auth
    user = await auth.verify_access_token(access_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user
