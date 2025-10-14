"""
Rate limiting module for IP-based request throttling.
Limits requests to 5 per IP address per day.
Resets at midnight Jakarta time (WIB - UTC+7).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from supabase import Client

from src.config import logger, SUPABASE_URL, SUPABASE_SERVICE_KEY

# Jakarta timezone (WIB - UTC+7)
JAKARTA_TZ = timezone(timedelta(hours=7))


# Initialize Supabase client
_supabase_client: Optional[Client] = None


def _get_supabase_client() -> Client:
    """
    Get or create the Supabase client instance.

    Returns:
        Client: Supabase client instance

    Raises:
        ValueError: If SUPABASE_URL or SUPABASE_SERVICE_KEY is not configured
    """
    global _supabase_client

    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            error_msg = "SUPABASE_URL or SUPABASE_SERVICE_KEY is not configured"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            from supabase import create_client

            _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            logger.info("Supabase client initialized successfully for rate limiting")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise

    return _supabase_client


async def check_rate_limit(ip_address: str, max_requests: int = 5) -> Dict[str, Any]:
    """
    Check if an IP address has exceeded the daily rate limit.

    Args:
        ip_address: The IP address to check
        max_requests: Maximum requests allowed per day (default: 5)

    Returns:
        Dict containing:
            - allowed: bool - Whether the request is allowed
            - remaining: int - Remaining requests for today
            - reset_at: str - ISO timestamp when the limit resets
            - total_today: int - Total requests made today

    Raises:
        Exception: If database operation fails
    """
    try:
        client = _get_supabase_client()

        # Get current time in Jakarta timezone
        now_jakarta = datetime.now(JAKARTA_TZ)

        # Calculate start of today in Jakarta time (midnight WIB)
        today_start_jakarta = now_jakarta.replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        # Convert to UTC for database query (Supabase stores in UTC)
        today_start_utc = today_start_jakarta.astimezone(timezone.utc)
        today_start_iso = today_start_utc.isoformat()

        # Calculate reset time (midnight tomorrow in Jakarta)
        tomorrow_start_jakarta = today_start_jakarta + timedelta(days=1)
        reset_at = tomorrow_start_jakarta.isoformat()

        logger.debug(
            f"Checking rate limit for IP: {ip_address} "
            f"(Jakarta time: {now_jakarta.strftime('%Y-%m-%d %H:%M:%S %Z')})"
        )

        # Count requests from this IP today
        response = (
            client.table("tryon_history")
            .select("id", count="exact")  # type: ignore
            .eq("ip_address", ip_address)
            .gte("created_at", today_start_iso)
            .execute()
        )

        # Get count from response
        total_today = response.count if response.count is not None else 0

        # Calculate remaining requests
        remaining = max(0, max_requests - total_today)
        allowed = total_today < max_requests

        logger.info(
            f"Rate limit check for {ip_address}: {total_today}/{max_requests} requests today, "
            f"allowed={allowed}, remaining={remaining}"
        )

        return {
            "allowed": allowed,
            "remaining": remaining,
            "reset_at": reset_at,
            "total_today": total_today,
            "limit": max_requests,
        }

    except Exception as e:
        logger.error(f"Error checking rate limit for {ip_address}: {e}")
        raise


async def get_rate_limit_status(
    ip_address: str, max_requests: int = 5
) -> Dict[str, Any]:
    """
    Get the current rate limit status for an IP address without enforcing it.
    Useful for status endpoints.

    Args:
        ip_address: The IP address to check
        max_requests: Maximum requests allowed per day (default: 5)

    Returns:
        Dict containing rate limit status information
    """
    return await check_rate_limit(ip_address, max_requests)
