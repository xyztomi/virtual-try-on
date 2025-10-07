"""
Storage operations module for Supabase Storage.
Handles all file upload operations for body, garment, and result images.
"""

from typing import Optional, Dict, List, Any
from supabase import Client, create_client
import uuid

from src.config import logger, SUPABASE_URL, SUPABASE_SERVICE_KEY


# Initialize Supabase client
_supabase_client: Optional[Client] = None

# Storage bucket name
STORAGE_BUCKET = "images"


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
                "Supabase client initialized successfully for storage operations"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise

    return _supabase_client


def generate_public_url(path: str) -> str:
    """
    Generate a public URL for a file in Supabase Storage.

    Args:
        path: Path to the file in storage (e.g., 'body/filename.jpg')

    Returns:
        str: Public URL to access the file
    """
    try:
        client = _get_supabase_client()

        # Get public URL from Supabase Storage
        public_url = client.storage.from_(STORAGE_BUCKET).get_public_url(path)

        logger.debug(f"Generated public URL for path: {path}")
        return public_url

    except Exception as e:
        logger.error(f"Error generating public URL for path {path}: {e}")
        raise


async def upload_body_image(
    file_bytes: bytes, filename: str, content_type: str = "image/jpeg"
) -> str:
    """
    Upload a body image to Supabase Storage.

    Args:
        file_bytes: Image file content as bytes
        filename: Original filename (will be sanitized and made unique)
        content_type: MIME type of the file (default: image/jpeg)

    Returns:
        str: Public URL of the uploaded file

    Raises:
        Exception: If upload fails
    """
    try:
        client = _get_supabase_client()

        # Generate unique filename
        file_extension = filename.split(".")[-1] if "." in filename else "jpg"
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        storage_path = f"body/{unique_filename}"

        logger.info(f"Uploading body image: {unique_filename}")

        # Upload file to storage
        client.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type},
        )

        # Generate public URL
        public_url = generate_public_url(storage_path)

        logger.info(f"Successfully uploaded body image to: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"Error uploading body image: {e}")
        raise


async def upload_garment_images(files: List[Dict[str, Any]]) -> List[str]:
    """
    Upload multiple garment images to Supabase Storage.

    Args:
        files: List of dicts with 'bytes', 'filename', and optional 'content_type' keys
               Example: [{'bytes': b'...', 'filename': 'shirt.jpg', 'content_type': 'image/jpeg'}]

    Returns:
        List[str]: List of public URLs for uploaded files

    Raises:
        Exception: If any upload fails
    """
    try:
        client = _get_supabase_client()
        uploaded_urls = []

        logger.info(f"Uploading {len(files)} garment image(s)")

        for idx, file_data in enumerate(files):
            file_bytes = file_data["bytes"]
            filename = file_data["filename"]
            content_type = file_data.get("content_type", "image/jpeg")

            # Generate unique filename
            file_extension = filename.split(".")[-1] if "." in filename else "jpg"
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            storage_path = f"garments/{unique_filename}"

            logger.debug(
                f"Uploading garment image {idx + 1}/{len(files)}: {unique_filename}"
            )

            # Upload file to storage
            client.storage.from_(STORAGE_BUCKET).upload(
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": content_type},
            )

            # Generate public URL
            public_url = generate_public_url(storage_path)
            uploaded_urls.append(public_url)

            logger.debug(f"Successfully uploaded garment image to: {public_url}")

        logger.info(f"Successfully uploaded all {len(files)} garment image(s)")
        return uploaded_urls

    except Exception as e:
        logger.error(f"Error uploading garment images: {e}")
        raise


async def upload_result_image(
    file_bytes: bytes, filename: str, content_type: str = "image/jpeg"
) -> str:
    """
    Upload a result image to Supabase Storage.

    Args:
        file_bytes: Image file content as bytes
        filename: Original filename (will be sanitized and made unique)
        content_type: MIME type of the file (default: image/jpeg)

    Returns:
        str: Public URL of the uploaded file

    Raises:
        Exception: If upload fails
    """
    try:
        client = _get_supabase_client()

        # Generate unique filename
        file_extension = filename.split(".")[-1] if "." in filename else "jpg"
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        storage_path = f"result/{unique_filename}"

        logger.info(f"Uploading result image: {unique_filename}")

        # Upload file to storage
        client.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": content_type},
        )

        # Generate public URL
        public_url = generate_public_url(storage_path)

        logger.info(f"Successfully uploaded result image to: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"Error uploading result image: {e}")
        raise


async def delete_file(path: str) -> bool:
    """
    Delete a file from Supabase Storage.

    Args:
        path: Path to the file in storage (e.g., 'body/filename.jpg')

    Returns:
        bool: True if deletion was successful

    Raises:
        Exception: If deletion fails
    """
    try:
        client = _get_supabase_client()

        logger.info(f"Deleting file: {path}")

        # Delete file from storage
        client.storage.from_(STORAGE_BUCKET).remove([path])

        logger.info(f"Successfully deleted file: {path}")
        return True

    except Exception as e:
        logger.error(f"Error deleting file {path}: {e}")
        raise
