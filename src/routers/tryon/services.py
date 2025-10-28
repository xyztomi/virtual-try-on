"""Service helpers used by the try-on router."""

from typing import Optional

from fastapi import HTTPException, Request, UploadFile

from src.config import TEST_CODE, logger
from src.core import database_ops, rate_limit, storage_ops
from src.core.validate_turnstile import validate_turnstile

from .contexts import RecordContext, SecurityContext, UploadResult
from .utils import build_rate_limit_key, get_client_ip

USER_DAILY_LIMIT = 20
GUEST_DAILY_LIMIT = 5


async def validate_security(
    request: Request,
    turnstile_token: Optional[str],
    test_code: Optional[str],
    user: Optional[dict],
) -> SecurityContext:
    """Run rate-limit and Turnstile validation, respecting test mode."""

    client_ip = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")
    rate_limit_identifier = build_rate_limit_key(request, client_ip)
    user_id = user.get("id") if isinstance(user, dict) else None
    max_requests = USER_DAILY_LIMIT if user_id else GUEST_DAILY_LIMIT
    identifier = f"user:{user_id}" if user_id else (rate_limit_identifier or client_ip)
    is_test_mode = bool(test_code and TEST_CODE and test_code == TEST_CODE)
    rate_status: Optional[dict] = None

    logger.info(
        "Security validation started",
        extra={
            "client_ip": client_ip,
            "is_test_mode": is_test_mode,
            "user_agent_present": bool(user_agent),
            "rate_identifier": identifier,
        },
    )

    if is_test_mode:
        logger.warning("TEST MODE: Security checks bypassed via test-code")
        return SecurityContext(
            client_ip=client_ip,
            user_agent=user_agent,
            user_id=user_id,
            is_test_mode=True,
            rate_limit_identifier=identifier,
        )

    try:
        rate_status = None
        if user_id:
            rate_status = await rate_limit.check_rate_limit(
                user_id=user_id,
                max_requests=max_requests,
            )
        elif client_ip:
            rate_status = await rate_limit.check_rate_limit(
                ip_address=client_ip,
                user_agent=user_agent,
                max_requests=max_requests,
            )
        else:
            logger.debug("Client IP not detected; skipping rate limit check")

        if rate_status and not rate_status["allowed"]:
            logger.warning(
                "Rate limit exceeded",
                extra={
                    "identifier": identifier,
                    "total_today": rate_status["total_today"],
                    "limit": rate_status["limit"],
                },
            )
            raise HTTPException(
                status_code=429,
                detail=(
                    "Rate limit exceeded. You have made "
                    f"{rate_status['total_today']} requests today. "
                    f"Limit resets at {rate_status['reset_at']}"
                ),
                headers={
                    "X-RateLimit-Limit": str(rate_status["limit"]),
                    "X-RateLimit-Remaining": str(rate_status["remaining"]),
                    "X-RateLimit-Reset": rate_status["reset_at"],
                },
            )

        if not turnstile_token:
            logger.warning("Turnstile token missing")
            raise HTTPException(
                status_code=400,
                detail="Bad Request: X-Turnstile-Token header is required",
            )

        turnstile_result = validate_turnstile(turnstile_token, client_ip)
        if not turnstile_result.success:
            logger.warning(
                "Turnstile validation failed",
                extra={"error_codes": turnstile_result.error_codes},
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Captcha validation failed: "
                    f"{', '.join(turnstile_result.error_codes or ['unknown error'])}"
                ),
            )

        logger.info("Security validation successful")
        return SecurityContext(
            client_ip=client_ip,
            user_agent=user_agent,
            user_id=user_id,
            is_test_mode=False,
            rate_limit_status=rate_status,
            rate_limit_identifier=identifier,
        )

    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.error("Security validation error", extra={"error": str(exc)})
        raise HTTPException(
            status_code=500, detail=f"Security validation failed: {exc}"
        )


async def store_images(
    body_image: UploadFile,
    garment_image1: UploadFile,
    garment_image2: Optional[UploadFile],
) -> UploadResult:
    """Persist uploaded images and return their public URLs."""

    uploaded_urls = []

    try:
        logger.info("Uploading body image")
        body_bytes = await body_image.read()
        body_content_type = body_image.content_type or "image/jpeg"
        body_url = await storage_ops.upload_body_image(
            body_bytes,
            body_image.filename or "body.jpg",
            body_content_type,
        )
        uploaded_urls.append(body_url)

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

        logger.info(
            "Uploaded images to storage",
            extra={"body_url": body_url, "garment_count": len(garment_urls)},
        )

        return UploadResult(
            body_url=body_url,
            garment_urls=garment_urls,
            uploaded_urls=uploaded_urls,
        )

    except Exception as exc:
        logger.error("Image upload failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Failed to upload images: {exc}")


async def create_tryon_records(
    request: Request,
    upload: UploadResult,
    security: SecurityContext,
    user: Optional[dict],
) -> RecordContext:
    """Create persistent record for the try-on request in user_tryon_history."""

    user_id = security.user_id or (user.get("id") if isinstance(user, dict) else None)
    user_agent = security.user_agent or request.headers.get("User-Agent")

    try:
        record = await database_ops.create_tryon_record(
            body_url=upload.body_url,
            garment_urls=upload.garment_urls,
            ip_address=security.client_ip,
            user_id=user_id,
            user_agent=user_agent,
        )
        record_id = str(record.get("id"))
        logger.info(
            "Try-on record created in user_tryon_history",
            extra={
                "record_id": record_id,
                "user_id": user_id,
                "is_guest": user_id is None,
            },
        )
    except Exception as exc:
        logger.error("Failed to create try-on record", extra={"error": str(exc)})
        raise HTTPException(
            status_code=500, detail=f"Failed to create try-on record: {exc}"
        )

    return RecordContext(
        record_id=record_id,
        user_history_record_id=record_id,  # Same ID since it's the same record
    )
