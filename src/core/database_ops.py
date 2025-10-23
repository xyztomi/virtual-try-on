"""
Database operations module for Supabase tryon_history table.
Handles all CRUD operations for virtual try-on records.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from supabase import Client, create_client

from src.config import logger, SUPABASE_URL, SUPABASE_SERVICE_KEY


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
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            logger.info(
                "Supabase client initialized successfully for database operations"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise

    return _supabase_client


async def create_tryon_record(
    body_url: str,
    garment_urls: list[str],
    ip_address: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new try-on record in the database.

    Args:
        body_url: URL of the uploaded body image
        garment_urls: List of URLs for garment images
        ip_address: Optional IP address of the requester
        user_id: Optional user ID if authenticated

    Returns:
        Dict containing the created record with 'id' field

    Raises:
        Exception: If database operation fails
    """
    try:
        client = _get_supabase_client()

        # Prepare record data
        record_data = {
            "body_image_url": body_url,
            "garment_image_urls": garment_urls,
            "status": "pending",
            "ip_address": ip_address,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            f"Creating try-on record for IP: {ip_address}, User: {user_id or 'anonymous'}"
        )

        # Insert record
        response = client.table("tryon_history").insert(record_data).execute()

        if response.data and len(response.data) > 0:
            record = response.data[0]
            logger.info(
                f"Successfully created try-on record with ID: {record.get('id')}"
            )
            return record
        else:
            error_msg = "Failed to create try-on record: No data returned"
            logger.error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"Error creating try-on record: {e}")
        raise


async def update_tryon_result(record_id: str, result_url: str) -> Dict[str, Any]:
    """
    Update a try-on record with successful result.

    Args:
        record_id: ID of the record to update
        result_url: URL of the generated result image

    Returns:
        Dict containing the updated record

    Raises:
        Exception: If database operation fails
    """
    try:
        client = _get_supabase_client()

        # Prepare update data
        update_data = {
            "status": "success",
            "result_image_url": result_url,
            "completed_at": datetime.utcnow().isoformat(),
        }

        logger.info(f"Updating try-on record {record_id} with success status")

        # Update record
        response = (
            client.table("tryon_history")
            .update(update_data)
            .eq("id", record_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            record = response.data[0]
            logger.info(f"Successfully updated try-on record {record_id}")
            return record
        else:
            error_msg = f"Failed to update try-on record {record_id}: No data returned"
            logger.error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"Error updating try-on record {record_id}: {e}")
        raise


async def mark_tryon_failed(record_id: str, reason: str) -> Dict[str, Any]:
    """
    Mark a try-on record as failed with a reason.

    Args:
        record_id: ID of the record to update
        reason: Reason for failure

    Returns:
        Dict containing the updated record

    Raises:
        Exception: If database operation fails
    """
    try:
        client = _get_supabase_client()

        # Prepare update data
        update_data = {
            "status": "failed",
            "error_message": reason,
            "completed_at": datetime.utcnow().isoformat(),
        }

        logger.warning(f"Marking try-on record {record_id} as failed: {reason}")

        # Update record
        response = (
            client.table("tryon_history")
            .update(update_data)
            .eq("id", record_id)
            .execute()
        )

        if response.data and len(response.data) > 0:
            record = response.data[0]
            logger.info(f"Successfully marked try-on record {record_id} as failed")
            return record
        else:
            error_msg = f"Failed to update try-on record {record_id}: No data returned"
            logger.error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"Error marking try-on record {record_id} as failed: {e}")
        raise


async def get_tryon_record(record_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a specific try-on record by ID.

    Args:
        record_id: ID of the record to retrieve

    Returns:
        Dict containing the record data, or None if not found

    Raises:
        Exception: If database operation fails
    """
    try:
        client = _get_supabase_client()

        logger.debug(f"Retrieving try-on record {record_id}")

        # Query record
        response = (
            client.table("tryon_history").select("*").eq("id", record_id).execute()
        )

        if response.data and len(response.data) > 0:
            record = response.data[0]
            logger.debug(f"Successfully retrieved try-on record {record_id}")
            return record
        else:
            logger.warning(f"Try-on record {record_id} not found")
            return None

    except Exception as e:
        logger.error(f"Error retrieving try-on record {record_id}: {e}")
        raise
