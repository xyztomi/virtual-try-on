"""FastAPI dependencies shared across try-on endpoints."""

from typing import Optional

from fastapi import Header

from src.config import logger


async def get_optional_user(
    authorization: Optional[str] = Header(default=None),
) -> Optional[dict]:
    """Retrieve the authenticated user if the session token is valid."""
    if not authorization:
        return None

    try:
        from src.core import auth

        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        token = parts[1]
        session = await auth.get_session(token)
        if not session or not session.get("users"):
            return None

        return session["users"]
    except Exception as exc:  # pragma: no cover - dependency failure should be silent
        logger.debug("Optional auth failed", extra={"error": str(exc)})
        return None
