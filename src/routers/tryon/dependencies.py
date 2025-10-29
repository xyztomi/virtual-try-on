"""FastAPI dependencies shared across try-on endpoints."""

from typing import Optional

from fastapi import Header

from src.config import logger


async def get_optional_user(
    authorization: Optional[str] = Header(default=None),
) -> Optional[dict]:
    """
    Retrieve the authenticated user if the JWT access token is valid.
    Uses Supabase Auth for token verification.
    """
    if not authorization:
        return None

    try:
        from src.core import auth

        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        token = parts[1]
        # Verify JWT token using Supabase Auth
        user = await auth.verify_access_token(token)
        if not user:
            return None

        return user
    except Exception as exc:  # pragma: no cover - dependency failure should be silent
        logger.debug("Optional auth failed", extra={"error": str(exc)})
        return None
