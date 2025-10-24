"""Utility helpers for the try-on router."""

import hashlib
from typing import List, Optional

from fastapi import Request

from src.config import logger
from src.core import storage_ops


def get_client_ip(request: Request) -> Optional[str]:
    """Extract the requester IP from common proxy headers."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip

    if request.client:
        return request.client.host

    return None


async def cleanup_uploaded_files(urls: List[str]) -> None:
    """Remove uploaded images after a failure."""
    for url in urls:
        try:
            if "/images/" in url:
                path = url.split("/images/")[-1]
                await storage_ops.delete_file(path)
                logger.debug("Cleaned up file", extra={"path": path})
        except Exception as exc:  # pragma: no cover - defensive guard
            logger.warning(
                "Failed to cleanup file", extra={"url": url, "error": str(exc)}
            )


def build_rate_limit_key(request: Request, client_ip: Optional[str]) -> Optional[str]:
    """Create a stable identifier for rate limiting using IP and user agent."""
    if not client_ip:
        return None

    user_agent = request.headers.get("User-Agent", "unknown")
    user_agent_hash = hashlib.sha256(user_agent.encode("utf-8")).hexdigest()
    return f"{client_ip}:{user_agent_hash}"
