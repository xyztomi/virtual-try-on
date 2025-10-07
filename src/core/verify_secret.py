"""
Secret header validation for protecting endpoints from unauthorized access
"""

from fastapi import HTTPException, Request
from typing import Optional

__all__ = ["verify_secret_header"]


def verify_secret_header(
    request: Request, expected_secret: Optional[str] = None
) -> bool:
    """
    Validate the X-App-Secret header sent from Cloudflare Worker.

    Args:
        request: FastAPI Request object
        expected_secret: Expected secret value. If None, must be provided via config.

    Returns:
        True if validation succeeds

    Raises:
        HTTPException: 400 if header is missing, 403 if invalid, 500 if not configured
    """
    if not expected_secret:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: APP_SECRET not configured",
        )

    secret = request.headers.get("X-App-Secret")

    if not secret:
        raise HTTPException(status_code=400, detail="Missing X-App-Secret header")

    if secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid X-App-Secret header")

    return True
