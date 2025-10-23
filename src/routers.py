"""
API routers for the Virtual Try-On service.
Handles HTTP request flow and orchestrates business logic modules.
"""

import base64
import time
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Request, HTTPException, Header, Depends
from pydantic import BaseModel, Field

from src.config import logger, TEST_CODE
from src.core.validate_turnstile import validate_turnstile
from src.core import database_ops, storage_ops, rate_limit, user_history_ops
from src.core.gemini import virtual_tryon, audit_tryon_result


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


class TryOnAuditRequest(BaseModel):
    """Request payload for auditing a generated try-on result"""

    model_before: str = Field(..., description="Original model image (URL or base64)")
    model_after: str = Field(..., description="Generated try-on image (URL or base64)")
    garment1: str = Field(..., description="Primary garment reference (URL or base64)")
    garment2: Optional[str] = Field(
        None, description="Secondary garment reference (URL or base64)"
    )


class TryOnAuditResponse(BaseModel):
    """Response payload matching the audit schema"""

    clothing_changed: bool
    matches_input_garments: bool
    visual_quality_score: float = Field(ge=0, le=100)
    issues: List[str] = Field(default_factory=list)
    summary: str


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


async def get_optional_user(
    authorization: Optional[str] = Header(None),
) -> Optional[dict]:
    """
    Optional dependency to get authenticated user.
    Returns None if no valid token is provided.
    """
    if not authorization:
        return None

    try:
        from src.core import auth

        # Extract token from "Bearer <token>"
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None

        token = parts[1]

        # Validate session
        session = await auth.get_session(token)
        if not session or not session.get("users"):
            return None

        return session["users"]
    except Exception as e:
        logger.debug(f"Optional auth failed: {e}")
        return None


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
    user: Optional[dict] = Depends(get_optional_user),
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

        # Check if user is authenticated
        user_history_record_id = None
        if user:
            logger.info(f"Authenticated user detected: {user['id']}")
            # Create user-specific history record
            user_agent = request.headers.get("User-Agent")
            user_record = await user_history_ops.create_user_tryon_record(
                user_id=user["id"],
                body_url=body_url,
                garment_urls=garment_urls,
                ip_address=client_ip,
                user_agent=user_agent,
                metadata={"test_mode": is_test_mode},
            )
            user_history_record_id = user_record.get("id")
            logger.info(f"User history record created: {user_history_record_id}")

        record = await database_ops.create_tryon_record(
            body_url=body_url,
            garment_urls=garment_urls,
            ip_address=client_ip,
            user_id=user["id"] if user else None,
        )
        record_id = record.get("id")
        logger.info(f"Database record created: {record_id}")

        # -------------------------
        # Step 4: Generate Try-On Result
        # -------------------------
        logger.info("Generating virtual try-on with Gemini AI")
        start_time = time.time()

        result_base64 = None

        try:
            logger.info("Generating virtual try-on image")
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
            # Mark user history as failed if authenticated
            if user_history_record_id:
                await user_history_ops.mark_user_tryon_failed(
                    record_id=user_history_record_id,
                    reason=f"AI generation failed: {str(e)}",
                    retry_count=0,
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
            if not result_base64:
                raise Exception(
                    "Result image data is missing after generation attempts"
                )

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
            # Mark user history as failed if authenticated
            if user_history_record_id:
                await user_history_ops.mark_user_tryon_failed(
                    record_id=user_history_record_id,
                    reason=f"Failed to upload result: {str(e)}",
                    retry_count=0,
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

        # Update user history if authenticated
        if user_history_record_id:
            processing_time_ms = int((time.time() - start_time) * 1000)

            await user_history_ops.update_user_tryon_result(
                record_id=user_history_record_id,
                result_url=result_url,
                processing_time_ms=processing_time_ms,
                audit_score=None,  # Audit done separately via /tryon/audit endpoint
                audit_details=None,
                retry_count=0,
            )
            logger.info(f"User history record updated: {user_history_record_id}")

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


@router.post("/tryon/audit", response_model=TryOnAuditResponse)
async def audit_tryon_result_endpoint(
    payload: TryOnAuditRequest,
    request: Request,
    turnstile_token: Optional[str] = Header(None, alias="X-Turnstile-Token"),
    test_code: Optional[str] = Header(None, alias="test-code"),
):
    """
    Audit a try-on output using Gemini vision capabilities.
    
    Protected by Turnstile to prevent abuse.
    Useful for frontend to manually trigger quality checks and track audit history.
    
    **Headers:**
    - X-Turnstile-Token: Cloudflare Turnstile token (required, unless test-code provided)
    - test-code: Optional test bypass code
    
    **Body:**
    - model_before: Original model image (URL or base64)
    - model_after: Generated try-on image (URL or base64)
    - garment1: Primary garment reference (URL or base64)
    - garment2: Optional secondary garment reference (URL or base64)
    
    **Returns:**
    - clothing_changed: Whether clothing was successfully changed
    - matches_input_garments: Whether result matches input garments
    - visual_quality_score: Quality score 0-100
    - issues: List of detected issues
    - summary: Text summary of audit result
    """
    try:
        # Check for test_code bypass
        is_test_mode = False
        if test_code and TEST_CODE and test_code == TEST_CODE:
            logger.warning("⚠️  TEST MODE: Audit authentication bypassed with test_code")
            is_test_mode = True
        
        # Get client IP
        client_ip = get_client_ip(request)
        logger.info(f"Audit request from IP: {client_ip}")

        # Validate Turnstile token (skip in test mode)
        if not is_test_mode:
            if not turnstile_token:
                logger.warning("Turnstile token missing for audit request")
                raise HTTPException(
                    status_code=400,
                    detail="Bad Request: X-Turnstile-Token header is required",
                )

            turnstile_result = validate_turnstile(turnstile_token, client_ip)
            if not turnstile_result.success:
                logger.warning(
                    f"Turnstile validation failed for audit: {turnstile_result.error_codes}"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Captcha validation failed: {', '.join(turnstile_result.error_codes)}",
                )
            logger.info("Turnstile validation successful for audit")
        else:
            logger.info("Turnstile validation skipped for audit (test mode)")

        logger.info("Received try-on audit request")
        audit_result = await audit_tryon_result(
            model_before=payload.model_before,
            model_after=payload.model_after,
            garment1=payload.garment1,
            garment2=payload.garment2,
        )
        
        logger.info(
            f"Audit completed: score={audit_result.get('visual_quality_score')}, "
            f"changed={audit_result.get('clothing_changed')}, "
            f"matches={audit_result.get('matches_input_garments')}"
        )
        
        return TryOnAuditResponse(**audit_result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Try-on audit failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Audit failed: {exc}")


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
