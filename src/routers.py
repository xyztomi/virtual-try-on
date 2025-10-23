"""
API routers for the Virtual Try-On service.
Handles HTTP request flow and orchestrates business logic modules.
"""

import base64
import time
import json
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Request, HTTPException, Header, Depends
from pydantic import BaseModel, Field
import httpx

from src.config import logger, TEST_CODE, GEMINI_KEY
from src.core.validate_turnstile import validate_turnstile
from src.core import database_ops, storage_ops, rate_limit, user_history_ops
from src.core.gemini import virtual_tryon


# Initialize router
router = APIRouter(prefix="/api/v1", tags=["Virtual Try-On"])


# -------------------------
# Request/Response Models
# -------------------------
class AuditResult(BaseModel):
    """Audit result for try-on quality"""

    clothing_changed: bool
    matches_input_garments: bool
    visual_quality_score: float = Field(ge=0, le=100)
    issues: List[str] = Field(default_factory=list)
    summary: str


class TryOnResponse(BaseModel):
    """Response model for successful try-on operation"""

    success: bool
    record_id: str
    result_url: str
    body_url: str
    garment_urls: List[str]
    message: str
    audit: Optional[AuditResult] = None
    retry_count: int = Field(default=0, description="Number of generation retries")


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


async def audit_tryon_result(
    model_before: str,
    model_after: str,
    garment1: str,
    garment2: Optional[str] = None,
) -> Optional[AuditResult]:
    """
    Audit a try-on result using Gemini Vision API.

    Returns AuditResult if successful, None if audit fails.
    """
    try:
        from src.core.gemini import _prepare_image_input
        from src.core.prompt_templates import build_audit_prompt

        logger.info("Starting audit of try-on result")

        # Prepare images
        before_b64 = await _prepare_image_input(model_before, "model_before image")
        after_b64 = await _prepare_image_input(model_after, "model_after image")
        garment1_b64 = await _prepare_image_input(garment1, "garment1 image")
        garment2_b64 = None
        if garment2:
            garment2_b64 = await _prepare_image_input(garment2, "garment2 image")

        # Build audit prompt
        prompt = build_audit_prompt()

        # Prepare API request parts
        parts = [
            {"text": prompt},
            {"text": "model_before"},
            {"inline_data": {"mime_type": "image/jpeg", "data": before_b64}},
            {"text": "model_after"},
            {"inline_data": {"mime_type": "image/jpeg", "data": after_b64}},
            {"text": "garment1"},
            {"inline_data": {"mime_type": "image/jpeg", "data": garment1_b64}},
        ]

        if garment2_b64:
            parts.extend(
                [
                    {"text": "garment2"},
                    {"inline_data": {"mime_type": "image/jpeg", "data": garment2_b64}},
                ]
            )

        # Call Gemini API
        audit_url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash:generateContent"
        )

        payload_data = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "temperature": 0.2,
                "topK": 32,
                "topP": 0.9,
                "maxOutputTokens": 3048,
            },
        }

        headers = {"Content-Type": "application/json"}
        if GEMINI_KEY:
            headers["x-goog-api-key"] = GEMINI_KEY

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                audit_url,
                json=payload_data,
                headers=headers,
            )
            response.raise_for_status()
            api_result = response.json()

        # Check for API errors
        if "error" in api_result:
            error_msg = api_result["error"].get("message", "Unknown API error")
            logger.error(f"Gemini API error in audit: {error_msg}")
            return None

        # Extract text response
        if "candidates" not in api_result or not api_result["candidates"]:
            logger.error("Gemini audit returned no candidates")
            return None

        candidate = api_result["candidates"][0]

        # Check for safety filters or other blocking reasons
        if "finishReason" in candidate and candidate["finishReason"] != "STOP":
            finish_reason = candidate["finishReason"]
            logger.warning(f"Gemini audit response blocked: {finish_reason}")
            return None

        if "content" not in candidate or "parts" not in candidate["content"]:
            logger.error("Invalid Gemini audit response structure")
            return None

        result_text = ""
        for part in candidate["content"]["parts"]:
            if "text" in part:
                result_text += part["text"]

        if not result_text:
            logger.error("Audit response contained no text output")
            return None

        # Parse JSON from response
        cleaned = result_text.strip()

        # Remove markdown code block delimiters
        if cleaned.startswith("```"):
            first_newline = cleaned.find("\n")
            if first_newline > 0:
                cleaned = cleaned[first_newline + 1 :]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        audit_data = json.loads(cleaned)

        # Validate required keys
        expected_keys = {
            "clothing_changed",
            "matches_input_garments",
            "visual_quality_score",
            "issues",
            "summary",
        }

        missing_keys = expected_keys - set(audit_data.keys())
        if missing_keys:
            logger.error(f"Audit JSON missing keys: {missing_keys}")
            return None

        audit_result = AuditResult(**audit_data)

        logger.info(
            f"Audit successful: score={audit_result.visual_quality_score}, "
            f"changed={audit_result.clothing_changed}, "
            f"matches={audit_result.matches_input_garments}"
        )

        return audit_result

    except Exception as e:
        logger.error(f"Audit failed: {e}")
        return None


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
        # Step 4: Generate Try-On Result with Audit & Retry Logic
        # -------------------------
        logger.info("Generating virtual try-on with Gemini AI")
        start_time = time.time()

        result_base64 = None
        result_url = None
        final_audit = None
        retry_count = 0
        MAX_RETRIES = 2

        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Generation attempt {attempt + 1}/{MAX_RETRIES}")

                # Generate try-on image
                result = await virtual_tryon(
                    body_url=body_url, garment_urls=garment_urls
                )
                result_base64 = result["result_base64"]
                logger.info(
                    f"Virtual try-on generation successful (attempt {attempt + 1})"
                )

                # Upload result image to get URL for audit
                if not record_id:
                    raise Exception("Record ID is missing")

                result_bytes = base64.b64decode(result_base64)
                temp_result_url = await storage_ops.upload_result_image(
                    file_bytes=result_bytes,
                    filename=f"result_{record_id}_attempt{attempt + 1}.jpg",
                    content_type="image/jpeg",
                )
                logger.info(f"Result image uploaded: {temp_result_url}")

                # Audit the result
                garment2_url = garment_urls[1] if len(garment_urls) > 1 else None
                audit_result = await audit_tryon_result(
                    model_before=body_url,
                    model_after=temp_result_url,
                    garment1=garment_urls[0],
                    garment2=garment2_url,
                )

                if audit_result:
                    logger.info(
                        f"Audit score: {audit_result.visual_quality_score}, "
                        f"matches: {audit_result.matches_input_garments}, "
                        f"changed: {audit_result.clothing_changed}"
                    )

                    # Check if result is acceptable (score >= 60 and garments match)
                    if (
                        audit_result.visual_quality_score >= 60
                        and audit_result.matches_input_garments
                        and audit_result.clothing_changed
                    ):
                        logger.info(f"✅ Quality check passed on attempt {attempt + 1}")
                        result_url = temp_result_url
                        final_audit = audit_result
                        retry_count = attempt
                        break
                    else:
                        logger.warning(
                            f"⚠️ Quality check failed on attempt {attempt + 1}: "
                            f"score={audit_result.visual_quality_score}, "
                            f"matches={audit_result.matches_input_garments}, "
                            f"changed={audit_result.clothing_changed}"
                        )
                        # If this is the last attempt, use this result anyway
                        if attempt == MAX_RETRIES - 1:
                            logger.info(
                                "Last attempt, using result despite low quality"
                            )
                            result_url = temp_result_url
                            final_audit = audit_result
                            retry_count = attempt
                        else:
                            # Delete the failed result and retry
                            try:
                                path = temp_result_url.split("/images/")[-1]
                                await storage_ops.delete_file(path)
                                logger.debug(f"Deleted failed result: {path}")
                            except Exception as cleanup_err:
                                logger.warning(f"Failed to cleanup: {cleanup_err}")
                else:
                    logger.warning(
                        f"Audit failed on attempt {attempt + 1}, no result returned"
                    )
                    # If audit fails, use the result on last attempt
                    if attempt == MAX_RETRIES - 1:
                        logger.info("Last attempt, using result without audit")
                        result_url = temp_result_url
                        retry_count = attempt

            except Exception as e:
                logger.error(f"Generation attempt {attempt + 1} failed: {e}")
                # If this is the last attempt, raise error
                if attempt == MAX_RETRIES - 1:
                    if record_id:
                        await database_ops.mark_tryon_failed(
                            record_id,
                            reason=f"AI generation failed after {MAX_RETRIES} attempts: {str(e)}",
                        )
                    if user_history_record_id:
                        await user_history_ops.mark_user_tryon_failed(
                            record_id=user_history_record_id,
                            reason=f"AI generation failed: {str(e)}",
                            retry_count=attempt,
                        )
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to generate try-on result after {MAX_RETRIES} attempts: {str(e)}",
                    )
                # Otherwise, continue to next attempt
                continue

        # Check if we got a result
        if not result_url:
            error_msg = (
                f"Failed to generate acceptable result after {MAX_RETRIES} attempts"
            )
            logger.error(error_msg)
            if record_id:
                await database_ops.mark_tryon_failed(record_id, reason=error_msg)
            if user_history_record_id:
                await user_history_ops.mark_user_tryon_failed(
                    record_id=user_history_record_id,
                    reason=error_msg,
                    retry_count=MAX_RETRIES,
                )
            raise HTTPException(status_code=500, detail=error_msg)

        # -------------------------
        # Step 5: Update Database Record
        # -------------------------
        logger.info("Updating database record with result")

        await database_ops.update_tryon_result(
            record_id=record_id,  # type: ignore
            result_url=result_url,
        )

        # Update user history if authenticated
        if user_history_record_id:
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Prepare audit details for database
            audit_score = final_audit.visual_quality_score if final_audit else None
            audit_details = None
            if final_audit:
                audit_details = {
                    "clothing_changed": final_audit.clothing_changed,
                    "matches_input_garments": final_audit.matches_input_garments,
                    "visual_quality_score": final_audit.visual_quality_score,
                    "issues": final_audit.issues,
                    "summary": final_audit.summary,
                }

            await user_history_ops.update_user_tryon_result(
                record_id=user_history_record_id,
                result_url=result_url,
                processing_time_ms=processing_time_ms,
                audit_score=audit_score,
                audit_details=audit_details,
                retry_count=retry_count,
            )
            logger.info(f"User history record updated: {user_history_record_id}")

        logger.info(
            f"Virtual try-on completed successfully: {record_id} (retries: {retry_count})"
        )

        # -------------------------
        # Return Success Response
        # -------------------------
        if record_id is None:
            raise HTTPException(
                status_code=500,
                detail="Internal error: record_id is missing when constructing response.",
            )

        response = TryOnResponse(
            success=True,
            record_id=str(record_id),
            result_url=result_url,
            body_url=body_url,
            garment_urls=garment_urls,
            message="Virtual try-on completed successfully",
            audit=final_audit,
            retry_count=retry_count,
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
