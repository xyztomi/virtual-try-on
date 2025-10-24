"""FastAPI router for virtual try-on endpoints."""

from typing import Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
)

from src.config import TEST_CODE, logger
from src.core import database_ops, rate_limit
from src.core.validate_turnstile import validate_turnstile
from src.services.tryon_service import TryOnJobContext, process_tryon_job

from .dependencies import get_optional_user
from .models import (
    RateLimitResponse,
    TryOnResponse,
    TurnstileTestRequest,
    TurnstileTestResponse,
)
from .services import create_tryon_records, store_images, validate_security
from .utils import build_rate_limit_key, cleanup_uploaded_files, get_client_ip

router = APIRouter(prefix="/api/v1", tags=["Virtual Try-On"])


@router.post("/turnstile/test", response_model=TurnstileTestResponse)
async def test_turnstile_token(
    payload: TurnstileTestRequest,
    request: Request,
) -> TurnstileTestResponse:
    """Validate a Turnstile token without invoking the full try-on flow."""

    client_ip = get_client_ip(request)
    logger.info("Turnstile test endpoint invoked", extra={"client_ip": client_ip})

    try:
        result = validate_turnstile(payload.token, client_ip)
    except Exception as exc:  # pragma: no cover - configuration guard
        logger.error("Turnstile validation error", extra={"error": str(exc)})
        raise HTTPException(
            status_code=500,
            detail=f"Turnstile validation error: {exc}",
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
    response: Response,
    background_tasks: BackgroundTasks,
    body_image: UploadFile = File(..., description="Body/model image"),
    garment_image1: UploadFile = File(..., description="First garment image"),
    garment_image2: Optional[UploadFile] = File(
        default=None, description="Second garment image (optional)"
    ),
    turnstile_token: Optional[str] = Header(default=None, alias="X-Turnstile-Token"),
    test_code: Optional[str] = Header(default=None, alias="test-code"),
    user: Optional[dict] = Depends(get_optional_user),
) -> TryOnResponse:
    """Submit a try-on job and queue background processing."""

    upload = None
    record_context = None
    security = None
    rate_limit_header_value = "unknown"

    try:
        logger.info("Virtual try-on request received")

        security = await validate_security(request, turnstile_token, test_code)

        if security.is_test_mode:
            rate_limit_header_value = "test-mode"
        elif security.rate_limit_status:
            rate_limit_header_value = str(
                security.rate_limit_status.get("remaining", "0")
            )

        upload = await store_images(body_image, garment_image1, garment_image2)

        record_context = await create_tryon_records(
            request=request,
            upload=upload,
            security=security,
            user=user,
        )

        if security.rate_limit_status:
            logger.info(
                "Rate limit status recorded",
                extra={
                    **security.rate_limit_status,
                    "rate_identifier": security.rate_limit_identifier
                    or security.client_ip,
                },
            )

        job_context = TryOnJobContext(
            record_id=record_context.record_id,
            body_url=upload.body_url,
            garment_urls=upload.garment_urls,
            user_history_record_id=record_context.user_history_record_id,
            client_ip=security.client_ip,
        )

        background_tasks.add_task(process_tryon_job, job_context)

        logger.info(
            "Background job scheduled",
            extra={
                "record_id": record_context.record_id,
                "user_history_record_id": record_context.user_history_record_id,
                "client_ip": security.client_ip,
                "user_agent_present": bool(security.user_agent),
            },
        )

        estimated_wait = 45 if not security.is_test_mode else 5
        message = (
            "Try-on request accepted. The result will be available shortly."
            if not security.is_test_mode
            else "Test mode enabled. Result will be generated using bypassed security checks."
        )

        if security.is_test_mode:
            rate_limit_header_value = "test-mode"
        elif security.client_ip:
            try:
                latest_status = await rate_limit.get_rate_limit_status(
                    security.client_ip,
                    security.user_agent,
                )
                rate_limit_header_value = str(latest_status.get("remaining", "0"))
            except Exception as status_exc:  # pragma: no cover - defensive guard
                logger.warning(
                    "Failed to refresh rate limit status",
                    extra={"error": str(status_exc)},
                )
                if security.rate_limit_status:
                    rate_limit_header_value = str(
                        security.rate_limit_status.get("remaining", "0")
                    )
        elif security.rate_limit_status:
            rate_limit_header_value = str(
                security.rate_limit_status.get("remaining", "0")
            )

        response.headers["X-RateLimit-Remaining"] = rate_limit_header_value

        return TryOnResponse(
            success=True,
            record_id=record_context.record_id,
            status="pending",
            body_url=upload.body_url,
            garment_urls=upload.garment_urls,
            message=message,
            estimated_wait_seconds=estimated_wait,
        )

    except HTTPException as http_exc:
        if upload:
            await cleanup_uploaded_files(upload.uploaded_urls)
        if rate_limit_header_value:
            headers = dict(http_exc.headers or {})
            headers.setdefault("X-RateLimit-Remaining", rate_limit_header_value)
            http_exc.headers = headers
        raise http_exc

    except Exception as exc:
        logger.error("Unexpected error in try-on request", exc_info=True)

        if record_context:
            try:
                await database_ops.mark_tryon_failed(
                    record_context.record_id,
                    reason=f"Unexpected error: {exc}",
                )
            except Exception as db_exc:
                logger.error(
                    "Failed to mark record as failed", extra={"error": str(db_exc)}
                )

        if upload:
            await cleanup_uploaded_files(upload.uploaded_urls)

        response.headers["X-RateLimit-Remaining"] = rate_limit_header_value

        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred: {exc}",
            headers={"X-RateLimit-Remaining": rate_limit_header_value},
        )


@router.get("/tryon/{record_id}")
async def get_tryon_status(
    record_id: str,
    request: Request,
    test_code: Optional[str] = Header(default=None, alias="test-code"),
) -> dict:
    """Retrieve the status and result metadata for a try-on request."""

    try:
        if test_code and TEST_CODE and test_code == TEST_CODE:
            logger.warning("TEST MODE: Status retrieval bypassed via test-code")
        else:
            logger.info("Authentication via secret header no longer required")

        logger.info("Retrieving try-on record", extra={"record_id": record_id})

        record = await database_ops.get_tryon_record(record_id)
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"Try-on record not found: {record_id}",
            )

        return {"success": True, "record": record}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Error retrieving try-on record",
            extra={"record_id": record_id, "error": str(exc)},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve record: {exc}",
        )


@router.get("/ratelimit", response_model=RateLimitResponse)
async def check_rate_limit_status(request: Request) -> RateLimitResponse:
    """Report the remaining requests for the caller's IP."""

    try:
        client_ip = get_client_ip(request)
        if not client_ip:
            raise HTTPException(
                status_code=400,
                detail="Unable to determine client IP address",
            )

        user_agent = request.headers.get("User-Agent")
        rate_key = build_rate_limit_key(request, client_ip) or client_ip

        logger.info(
            "Rate limit status check",
            extra={
                "client_ip": client_ip,
                "rate_key": rate_key,
                "user_agent_present": bool(user_agent),
            },
        )

        status = await rate_limit.get_rate_limit_status(client_ip, user_agent)

        message = (
            f"You have {status['remaining']} tries left"
            if status["allowed"]
            else "You have 0 tries left"
        )

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
    except Exception as exc:
        logger.error(
            "Error checking rate limit status",
            extra={"error": str(exc)},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to check rate limit: {exc}",
        )


@router.get("/health")
async def health_check() -> dict:
    """Simple health check endpoint."""

    return {
        "status": "healthy",
        "service": "virtual-try-on-api",
        "version": "1.0.0",
    }
