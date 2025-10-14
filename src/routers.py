"""
API routers for the Virtual Try-On service.
Handles HTTP request flow and orchestrates business logic modules.
"""

import base64
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Request, HTTPException, Header
from pydantic import BaseModel, Field

from src.config import logger, TEST_CODE
from src.core.validate_turnstile import validate_turnstile
from src.core import database_ops, storage_ops, rate_limit
from src.core.gemini import virtual_tryon


# Initialize router
router = APIRouter(prefix="/api/v1", tags=["Virtual Try-On"])


# -------------------------
# Request/Response Models
# -------------------------
class TryOnResponse(BaseModel):
    """Response model for successful try-on operation"""

    success: bool
    record_id: str
    result_url: str
    message: str


class ErrorResponse(BaseModel):
    """Response model for errors"""

    success: bool
    error: str
    record_id: Optional[str] = None


class TurnstileTestRequest(BaseModel):
    """Request payload for Turnstile test endpoint"""

    token: str


class TurnstileTestResponse(BaseModel):
    """Response payload for Turnstile test endpoint"""

    success: bool
    message: str
    error_codes: List[str] = Field(default_factory=list)
    challenge_ts: Optional[str] = None
    hostname: Optional[str] = None
    action: Optional[str] = None
    cdata: Optional[str] = None


class RateLimitResponse(BaseModel):
    """Response model for rate limit status"""

    allowed: bool
    remaining: int
    reset_at: str
    total_today: int
    limit: int
    message: str


# -------------------------
# Utility Functions
# -------------------------
def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP address from request headers or connection info"""
    # Check for forwarded IP (common with proxies/load balancers)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Check Cloudflare header
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip

    # Fallback to direct connection IP
    if request.client:
        return request.client.host

    return None


async def cleanup_uploaded_files(urls: List[str]) -> None:
    """Helper to clean up uploaded files in case of error"""
    for url in urls:
        try:
            # Extract path from URL
            # Assuming URL format: https://.../storage/v1/object/public/images/{path}
            if "/images/" in url:
                path = url.split("/images/")[-1]
                await storage_ops.delete_file(path)
                logger.debug(f"Cleaned up file: {path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup file {url}: {e}")


# -------------------------
# Endpoints
# -------------------------


@router.post("/turnstile/test", response_model=TurnstileTestResponse)
async def test_turnstile_token(
    payload: TurnstileTestRequest,
    request: Request,
):
    """Validate a Turnstile token without running the full try-on flow."""

    client_ip = get_client_ip(request)
    logger.info("Turnstile test endpoint invoked")

    try:
        result = validate_turnstile(payload.token, client_ip)
    except Exception as exc:  # pragma: no cover - defensive guard for config issues
        logger.error(f"Turnstile validation error: {exc}")
        raise HTTPException(
            status_code=500, detail=f"Turnstile validation error: {str(exc)}"
        )

    message = (
        "Turnstile verification passed"
        if result.success
        else "Turnstile verification failed"
    )

    return TurnstileTestResponse(
        success=result.success,
        message=message,
        error_codes=result.error_codes,
        challenge_ts=result.challenge_ts,
        hostname=result.hostname,
        action=result.action,
        cdata=result.cdata,
    )


@router.post("/tryon", response_model=TryOnResponse)
async def create_virtual_tryon(
    request: Request,
    body_image: UploadFile = File(..., description="Body/model image"),
    garment_image1: UploadFile = File(..., description="First garment image"),
    garment_image2: Optional[UploadFile] = File(
        None, description="Second garment image (optional)"
    ),
    turnstile_token: Optional[str] = Header(None, alias="X-Turnstile-Token"),
    test_code: Optional[str] = Header(None, alias="test-code"),
):
    """
    Create a virtual try-on by combining body and garment images.

    **Flow:**
    1. Validate request (rate limit & turnstile)
    2. Upload images to storage
    3. Create database record with status='pending'
    4. Generate try-on result using Gemini AI
    5. Upload result image
    6. Update database record with result

    **Returns:**
    - record_id: Database record ID for tracking
    - result_url: Public URL of the generated try-on image
    """
    record_id = None
    uploaded_urls = []

    try:
        # -------------------------
        # Step 1: Security Validation
        # -------------------------
        logger.info("Starting virtual try-on request")

        # Check for test_code bypass
        is_test_mode = False
        if test_code and TEST_CODE and test_code == TEST_CODE:
            logger.warning("⚠️  TEST MODE: Authentication bypassed with test_code")
            is_test_mode = True
        else:
            logger.info("Authentication via secret header no longer required")

        # Get client IP for rate limiting and logging
        client_ip = get_client_ip(request)
        logger.info(f"Request from IP: {client_ip}")

        # Check rate limit (skip in test mode)
        if not is_test_mode and client_ip:
            rate_limit_status = await rate_limit.check_rate_limit(client_ip)
            if not rate_limit_status["allowed"]:
                logger.warning(
                    f"Rate limit exceeded for IP {client_ip}: "
                    f"{rate_limit_status['total_today']}/{rate_limit_status['limit']} requests today"
                )
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. You have made {rate_limit_status['total_today']} requests today. "
                    f"Limit resets at {rate_limit_status['reset_at']}",
                    headers={
                        "X-RateLimit-Limit": str(rate_limit_status["limit"]),
                        "X-RateLimit-Remaining": str(rate_limit_status["remaining"]),
                        "X-RateLimit-Reset": rate_limit_status["reset_at"],
                    },
                )
            logger.info(
                f"Rate limit check passed: {rate_limit_status['remaining']} requests remaining"
            )

        # Validate Turnstile token (skip in test mode)
        if not is_test_mode:
            # Require Turnstile token
            if not turnstile_token:
                logger.warning("Turnstile token missing")
                raise HTTPException(
                    status_code=400,
                    detail="Bad Request: X-Turnstile-Token header is required",
                )

            # Validate the token
            turnstile_result = validate_turnstile(turnstile_token, client_ip)
            if not turnstile_result.success:
                logger.warning(
                    f"Turnstile validation failed: {turnstile_result.error_codes}"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Captcha validation failed: {', '.join(turnstile_result.error_codes)}",
                )
            logger.info("Turnstile validation successful")
        else:
            logger.info("Turnstile validation skipped (test mode)")

        # -------------------------
        # Step 2: Upload Images to Storage
        # -------------------------
        logger.info("Uploading images to storage")

        # Upload body image
        body_bytes = await body_image.read()
        body_content_type = body_image.content_type or "image/jpeg"
        body_url = await storage_ops.upload_body_image(
            body_bytes, body_image.filename or "body.jpg", body_content_type
        )
        uploaded_urls.append(body_url)
        logger.info(f"Body image uploaded: {body_url}")

        # Upload garment images
        garment_files = [
            {
                "bytes": await garment_image1.read(),
                "filename": garment_image1.filename or "garment1.jpg",
                "content_type": garment_image1.content_type or "image/jpeg",
            }
        ]

        if garment_image2:
            garment_files.append(
                {
                    "bytes": await garment_image2.read(),
                    "filename": garment_image2.filename or "garment2.jpg",
                    "content_type": garment_image2.content_type or "image/jpeg",
                }
            )

        garment_urls = await storage_ops.upload_garment_images(garment_files)
        uploaded_urls.extend(garment_urls)
        logger.info(f"Uploaded {len(garment_urls)} garment image(s)")

        # -------------------------
        # Step 3: Create Database Record
        # -------------------------
        logger.info("Creating database record")

        record = await database_ops.create_tryon_record(
            body_url=body_url, garment_urls=garment_urls, ip_address=client_ip
        )
        record_id = record.get("id")
        logger.info(f"Database record created: {record_id}")

        # -------------------------
        # Step 4: Generate Try-On Result
        # -------------------------
        logger.info("Generating virtual try-on with Gemini AI")

        try:
            result = await virtual_tryon(body_url=body_url, garment_urls=garment_urls)
            result_base64 = result["result_base64"]
            logger.info("Virtual try-on generation successful")

        except Exception as e:
            logger.error(f"Gemini AI generation failed: {e}")
            # Mark record as failed
            if record_id:
                await database_ops.mark_tryon_failed(
                    record_id, reason=f"AI generation failed: {str(e)}"
                )
            raise HTTPException(
                status_code=500, detail=f"Failed to generate try-on result: {str(e)}"
            )

        # -------------------------
        # Step 5: Upload Result Image
        # -------------------------
        logger.info("Uploading result image to storage")

        try:
            # Decode base64 to bytes
            result_bytes = base64.b64decode(result_base64)

            # Upload result
            if not record_id:
                raise Exception("Record ID is missing")

            result_url = await storage_ops.upload_result_image(
                file_bytes=result_bytes,
                filename=f"result_{record_id}.jpg",
                content_type="image/jpeg",
            )
            logger.info(f"Result image uploaded: {result_url}")

        except Exception as e:
            logger.error(f"Failed to upload result image: {e}")
            if record_id:
                await database_ops.mark_tryon_failed(
                    record_id, reason=f"Failed to upload result: {str(e)}"
                )
            raise HTTPException(
                status_code=500, detail=f"Failed to upload result image: {str(e)}"
            )

        # -------------------------
        # Step 6: Update Database Record
        # -------------------------
        logger.info("Updating database record with result")

        await database_ops.update_tryon_result(
            record_id=record_id, result_url=result_url
        )

        logger.info(f"Virtual try-on completed successfully: {record_id}")

        # -------------------------
        # Return Success Response
        # -------------------------
        response = TryOnResponse(
            success=True,
            record_id=record_id,
            result_url=result_url,
            message="Virtual try-on completed successfully",
        )

        # Add rate limit headers if not in test mode
        if not is_test_mode and client_ip:
            # Get updated rate limit status after this request
            updated_status = await rate_limit.get_rate_limit_status(client_ip)
            # Note: FastAPI will automatically add these to response headers if we return a Response object
            # For now, we'll just log them
            logger.info(
                f"Rate limit after request - Remaining: {updated_status['remaining']}, "
                f"Total: {updated_status['total_today']}/{updated_status['limit']}"
            )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions (they're already properly formatted)
        raise

    except Exception as e:
        # Handle unexpected errors
        logger.error(f"Unexpected error in virtual try-on: {e}", exc_info=True)

        # Mark record as failed if we have a record_id
        if record_id:
            try:
                await database_ops.mark_tryon_failed(
                    record_id, reason=f"Unexpected error: {str(e)}"
                )
            except Exception as db_error:
                logger.error(f"Failed to mark record as failed: {db_error}")

        # Cleanup uploaded files
        if uploaded_urls:
            await cleanup_uploaded_files(uploaded_urls)

        raise HTTPException(
            status_code=500, detail=f"An unexpected error occurred: {str(e)}"
        )


@router.get("/tryon/{record_id}")
async def get_tryon_status(
    record_id: str,
    request: Request,
    test_code: Optional[str] = Header(None, alias="test-code"),
):
    """
    Get the status and result of a try-on operation.

    **Returns:**
    - Record with status: 'pending', 'success', or 'failed'
    - result_url if status is 'success'
    - error_message if status is 'failed'
    """
    try:
        # Check for test_code bypass
        if test_code and TEST_CODE and test_code == TEST_CODE:
            logger.warning("⚠️  TEST MODE: Authentication bypassed with test_code")
        else:
            logger.info("Authentication via secret header no longer required")

        logger.info(f"Retrieving try-on record: {record_id}")

        # Get record from database
        record = await database_ops.get_tryon_record(record_id)

        if not record:
            raise HTTPException(
                status_code=404, detail=f"Try-on record not found: {record_id}"
            )

        return {"success": True, "record": record}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving try-on record {record_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to retrieve record: {str(e)}"
        )


@router.get("/ratelimit", response_model=RateLimitResponse)
async def check_rate_limit_status(request: Request):
    """
    Check the current rate limit status for the requesting IP.

    **Returns:**
    - allowed: Whether more requests are allowed today
    - remaining: Number of requests remaining today
    - reset_at: ISO timestamp when the limit resets
    - total_today: Total requests made today
    - limit: Maximum requests allowed per day
    - message: Human-readable status message
    """
    try:
        # Get client IP
        client_ip = get_client_ip(request)

        if not client_ip:
            raise HTTPException(
                status_code=400, detail="Unable to determine client IP address"
            )

        logger.info(f"Rate limit status check for IP: {client_ip}")

        # Get rate limit status
        status = await rate_limit.get_rate_limit_status(client_ip)

        # Create response message
        if status["allowed"]:
            message = f"You have {status['remaining']} requests remaining today."
        else:
            message = f"Rate limit exceeded. Limit resets at {status['reset_at']}."

        return RateLimitResponse(
            allowed=status["allowed"],
            remaining=status["remaining"],
            reset_at=status["reset_at"],
            total_today=status["total_today"],
            limit=status["limit"],
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking rate limit status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to check rate limit: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "service": "virtual-try-on-api", "version": "1.0.0"}
