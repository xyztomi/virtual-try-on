"""
Database operations for user-specific try-on history.
Handles CRUD operations for authenticated user's try-on records.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from supabase import Client, create_client

from src.config import logger, SUPABASE_URL, SUPABASE_SERVICE_KEY


# Initialize Supabase client
_supabase_client: Optional[Client] = None


def _get_supabase_client() -> Client:
    """Get or create the Supabase client instance."""
    global _supabase_client

    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            error_msg = "SUPABASE_URL or SUPABASE_SERVICE_KEY is not configured"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            logger.info(
                "Supabase client initialized successfully for user history operations"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise

    return _supabase_client


async def create_user_tryon_record(
    user_id: str,
    body_url: str,
    garment_urls: List[str],
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a new try-on history record for an authenticated user.

    Args:
        user_id: User's UUID
        body_url: URL of the uploaded body image
        garment_urls: List of URLs for garment images
        ip_address: Optional IP address of the requester
        user_agent: Optional user agent string
        metadata: Optional additional metadata

    Returns:
        Dict containing the created record with 'id' field

    Raises:
        Exception: If database operation fails
    """
    try:
        client = _get_supabase_client()

        record_data = {
            "user_id": user_id,
            "body_image_url": body_url,
            "garment_image_urls": garment_urls,
            "status": "pending",
            "ip_address": ip_address,
            "user_agent": user_agent,
            "request_timestamp": datetime.utcnow().isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "retry_count": 0,
        }

        logger.info(f"Creating user try-on record for user: {user_id}")

        response = client.table("user_tryon_history").insert(record_data).execute()

        if response.data and len(response.data) > 0:
            record = response.data[0]
            logger.info(
                f"Successfully created user try-on record with ID: {record.get('id')}"
            )
            return record
        else:
            error_msg = "Failed to create user try-on record: No data returned"
            logger.error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"Error creating user try-on record: {e}")
        raise


async def update_user_tryon_result(
    record_id: str,
    result_url: str,
    processing_time_ms: Optional[int] = None,
    audit_score: Optional[float] = None,
    audit_details: Optional[Dict[str, Any]] = None,
    retry_count: int = 0,
) -> Dict[str, Any]:
    """
    Update a user try-on record with successful result.

    Args:
        record_id: ID of the record to update
        result_url: URL of the generated result image
        processing_time_ms: Processing time in milliseconds
        audit_score: Quality score from audit (0-100)
        audit_details: Full audit response details
        retry_count: Number of retries performed

    Returns:
        Dict containing the updated record

    Raises:
        Exception: If database operation fails
    """
    try:
        client = _get_supabase_client()

        update_data = {
            "status": "success",
            "result_image_url": result_url,
            "completed_at": datetime.utcnow().isoformat(),
            "processing_time_ms": processing_time_ms,
            "audit_score": audit_score,
            "retry_count": retry_count,
        }

        if audit_details:
            update_data["audit_details"] = audit_details

        logger.info(f"Updating user try-on record {record_id} with success status")

        response = (
            client.table("user_tryon_history")
            .update(update_data)
            .eq("id", record_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            record = response.data[0]
            logger.info(f"Successfully updated user try-on record {record_id}")
            return record
        else:
            error_msg = (
                f"Failed to update user try-on record {record_id}: No data returned"
            )
            logger.error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"Error updating user try-on record {record_id}: {e}")
        raise


async def mark_user_tryon_failed(
    record_id: str, reason: str, retry_count: int = 0
) -> Dict[str, Any]:
    """
    Mark a user try-on record as failed with a reason.

    Args:
        record_id: ID of the record to update
        reason: Reason for failure
        retry_count: Number of retries performed

    Returns:
        Dict containing the updated record

    Raises:
        Exception: If database operation fails
    """
    try:
        client = _get_supabase_client()

        update_data = {
            "status": "failed",
            "error_message": reason,
            "completed_at": datetime.utcnow().isoformat(),
            "retry_count": retry_count,
        }

        logger.warning(
            f"Marking user try-on record {record_id} as failed: {reason}"
        )

        response = (
            client.table("user_tryon_history")
            .update(update_data)
            .eq("id", record_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            record = response.data[0]
            logger.info(
                f"Successfully marked user try-on record {record_id} as failed"
            )
            return record
        else:
            error_msg = (
                f"Failed to update user try-on record {record_id}: No data returned"
            )
            logger.error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"Error marking user try-on record {record_id} as failed: {e}")
        raise


async def get_user_tryon_record(record_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a specific user try-on record by ID.

    Args:
        record_id: ID of the record to retrieve

    Returns:
        Dict containing the record data, or None if not found

    Raises:
        Exception: If database operation fails
    """
    try:
        client = _get_supabase_client()

        logger.debug(f"Retrieving user try-on record {record_id}")

        response = (
            client.table("user_tryon_history")
            .select("*")
            .eq("id", record_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            record = response.data[0]
            logger.debug(f"Successfully retrieved user try-on record {record_id}")
            return record
        else:
            logger.warning(f"User try-on record {record_id} not found")
            return None

    except Exception as e:
        logger.error(f"Error retrieving user try-on record {record_id}: {e}")
        raise


async def get_user_tryon_history(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get paginated try-on history for a specific user.

    Args:
        user_id: User's UUID
        limit: Maximum number of records to return (default: 20)
        offset: Number of records to skip for pagination (default: 0)
        status: Optional status filter ('pending', 'success', 'failed')

    Returns:
        Dict containing:
            - records: List of try-on records
            - total: Total count of records
            - limit: Limit used
            - offset: Offset used

    Raises:
        Exception: If database operation fails
    """
    try:
        client = _get_supabase_client()

        logger.info(
            f"Fetching user try-on history for user {user_id} (limit={limit}, offset={offset})"
        )

        # Build query
        query = (
            client.table("user_tryon_history")
            .select("*", count="exact")  # type: ignore
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )

        if status:
            query = query.eq("status", status)

        response = query.execute()

        records = response.data or []
        total = response.count if response.count is not None else 0

        logger.info(
            f"Retrieved {len(records)} records out of {total} total for user {user_id}"
        )

        return {
            "records": records,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        }

    except Exception as e:
        logger.error(f"Error fetching user try-on history for user {user_id}: {e}")
        raise


async def delete_user_tryon_record(record_id: str, user_id: str) -> bool:
    """
    Delete a user's try-on record.

    Args:
        record_id: ID of the record to delete
        user_id: User's UUID (for authorization check)

    Returns:
        True if deletion was successful

    Raises:
        Exception: If database operation fails
    """
    try:
        client = _get_supabase_client()

        logger.info(f"Deleting user try-on record {record_id} for user {user_id}")

        # Delete only if owned by user
        response = (
            client.table("user_tryon_history")
            .delete()
            .eq("id", record_id)
            .eq("user_id", user_id)
            .execute()
        )

        success = bool(response.data and len(response.data) > 0)

        if success:
            logger.info(f"Successfully deleted user try-on record {record_id}")
        else:
            logger.warning(
                f"Failed to delete user try-on record {record_id} - not found or unauthorized"
            )

        return success

    except Exception as e:
        logger.error(f"Error deleting user try-on record {record_id}: {e}")
        raise


async def get_user_stats(user_id: str) -> Dict[str, Any]:
    """
    Get statistics about a user's try-on history.

    Args:
        user_id: User's UUID

    Returns:
        Dict containing statistics

    Raises:
        Exception: If database operation fails
    """
    try:
        client = _get_supabase_client()

        logger.info(f"Fetching stats for user {user_id}")

        # Get total count
        total_response = (
            client.table("user_tryon_history")
            .select("id", count="exact")  # type: ignore
            .eq("user_id", user_id)
            .execute()
        )
        total_count = total_response.count if total_response.count is not None else 0

        # Get success count
        success_response = (
            client.table("user_tryon_history")
            .select("id", count="exact")  # type: ignore
            .eq("user_id", user_id)
            .eq("status", "success")
            .execute()
        )
        success_count = (
            success_response.count if success_response.count is not None else 0
        )

        # Get failed count
        failed_response = (
            client.table("user_tryon_history")
            .select("id", count="exact")  # type: ignore
            .eq("user_id", user_id)
            .eq("status", "failed")
            .execute()
        )
        failed_count = (
            failed_response.count if failed_response.count is not None else 0
        )

        stats = {
            "total_tryons": total_count,
            "successful": success_count,
            "failed": failed_count,
            "pending": total_count - success_count - failed_count,
            "success_rate": (
                round((success_count / total_count) * 100, 2) if total_count > 0 else 0
            ),
        }

        logger.info(f"Stats for user {user_id}: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Error fetching stats for user {user_id}: {e}")
        raise
