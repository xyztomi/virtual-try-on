"""FastAPI router providing authentication endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from src.config import logger
from src.core import auth, user_history_ops
from src.core.validate_turnstile import validate_turnstile

from .dependencies import get_current_user
from .models import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    PasswordResetRequest,
    RegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthResponse)
async def register(
    payload: RegisterRequest,
    request: Request,
    turnstile_token: Optional[str] = Header(default=None, alias="X-Turnstile-Token"),
) -> AuthResponse:
    """Register a new user using Supabase Auth and return an authentication token."""
    try:
        logger.info("Registration request", extra={"email": payload.email})

        if not turnstile_token:
            raise HTTPException(
                status_code=400,
                detail="X-Turnstile-Token header is required",
            )

        # Validate Turnstile token
        client_ip = request.client.host if request.client else None
        turnstile_result = validate_turnstile(turnstile_token, client_ip)
        if not turnstile_result.success:
            logger.warning(
                "Turnstile validation failed during registration",
                extra={"error_codes": turnstile_result.error_codes},
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Captcha validation failed: "
                    f"{', '.join(turnstile_result.error_codes or ['unknown error'])}"
                ),
            )

        user = await auth.create_user(
            email=payload.email,
            password=payload.password,
            username=payload.username,
        )

        logger.info("User registered with Supabase Auth", extra={"user_id": user["id"]})

        # For Supabase Auth, users need to verify their email before they can login
        # Return a token placeholder or require email verification
        return AuthResponse(
            success=True,
            message="Registration successful. Please check your email to verify your account.",
            token="email_verification_required",
            user=user,
        )

    except HTTPException:
        raise
    except Exception as exc:
        error_msg = str(exc)
        if "Email already registered" in error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        logger.error("Registration failed", extra={"error": error_msg})
        raise HTTPException(status_code=500, detail=f"Registration failed: {error_msg}")


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    turnstile_token: Optional[str] = Header(default=None, alias="X-Turnstile-Token"),
) -> AuthResponse:
    """Authenticate a user using Supabase Auth and return access tokens."""
    try:
        logger.info("Login request", extra={"email": payload.email})

        if not turnstile_token:
            raise HTTPException(
                status_code=400,
                detail="X-Turnstile-Token header is required",
            )

        # Validate Turnstile token
        client_ip = request.client.host if request.client else None
        turnstile_result = validate_turnstile(turnstile_token, client_ip)
        if not turnstile_result.success:
            logger.warning(
                "Turnstile validation failed during login",
                extra={"error_codes": turnstile_result.error_codes},
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    "Captcha validation failed: "
                    f"{', '.join(turnstile_result.error_codes or ['unknown error'])}"
                ),
            )

        user = await auth.authenticate_user(payload.email, payload.password)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Extract session data from Supabase Auth response
        session_data = user.pop("session", {})
        access_token = session_data.get("access_token", "")
        refresh_token = session_data.get("refresh_token", "")

        logger.info("User logged in with Supabase Auth", extra={"user_id": user["id"]})

        return AuthResponse(
            success=True,
            message="Login successful",
            token=access_token,
            refresh_token=refresh_token,
            user=user,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Login failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Login failed: {exc}")


@router.post("/logout", response_model=MessageResponse)
async def logout(
    authorization: Optional[str] = Header(default=None),
) -> MessageResponse:
    """Sign out the user using Supabase Auth."""
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header required")

        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=401, detail="Invalid authorization header format"
            )

        # With Supabase Auth, logout is handled client-side
        # The access token will expire naturally
        # Optionally, you can invalidate the token server-side if needed

        logger.info("User logout requested (token will expire naturally)")
        return MessageResponse(success=True, message="Logout successful")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Logout failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Logout failed: {exc}")


@router.post("/reset-password", response_model=MessageResponse)
async def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    redirect_to: Optional[str] = None,
) -> MessageResponse:
    """
    Request a password reset email.

    This endpoint sends a password reset link to the user's email using Supabase Auth.
    The user will receive an email with a link to reset their password.

    Note: This endpoint always returns success to prevent email enumeration attacks.

    Args:
        payload: Contains the user's email address
        redirect_to: Optional URL to redirect to after password reset

    Returns:
        Success message indicating the email was sent (if the email exists)
    """
    try:
        logger.info("Password reset requested", extra={"email": payload.email})

        await auth.request_password_reset(
            email=payload.email,
            redirect_to=redirect_to,
        )

        # Always return success to prevent email enumeration
        return MessageResponse(
            success=True,
            message="If an account exists with this email, you will receive password reset instructions.",
        )

    except Exception as exc:
        logger.error("Password reset request failed", extra={"error": str(exc)})
        # Still return success to prevent email enumeration
        return MessageResponse(
            success=True,
            message="If an account exists with this email, you will receive password reset instructions.",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: dict = Depends(get_current_user)) -> UserResponse:
    """Return the current authenticated user's profile."""
    return UserResponse(success=True, user=user)


@router.get("/history")
async def get_user_history(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    user: dict = Depends(get_current_user),
) -> dict:
    """Fetch the authenticated user's try-on history."""
    try:
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=400, detail="Limit must be between 1 and 100"
            )
        if offset < 0:
            raise HTTPException(status_code=400, detail="Offset must be non-negative")
        if status and status not in {"pending", "processing", "success", "failed"}:
            raise HTTPException(
                status_code=400,
                detail="Status must be one of: pending, processing, success, failed",
            )

        logger.info(
            "Fetching user history",
            extra={
                "user_id": user["id"],
                "limit": limit,
                "offset": offset,
                "status": status,
            },
        )

        history = await user_history_ops.get_user_tryon_history(
            user_id=user["id"],
            limit=limit,
            offset=offset,
            status=status,
        )

        return {
            "success": True,
            "records": history["records"],
            "total": history["total"],
            "limit": history["limit"],
            "offset": history["offset"],
            "has_more": history["has_more"],
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch user history", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {exc}")


@router.get("/history/{record_id}")
async def get_user_history_record(
    record_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Fetch a single try-on history record by ID."""
    try:
        logger.info(
            "Fetching history record",
            extra={"record_id": record_id, "user_id": user["id"]},
        )

        record = await user_history_ops.get_user_tryon_record(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Record not found")
        if record.get("user_id") != user["id"]:
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to access this record",
            )

        return {"success": True, "record": record}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to fetch history record",
            extra={"error": str(exc), "record_id": record_id},
        )
        raise HTTPException(status_code=500, detail=f"Failed to fetch record: {exc}")


@router.delete("/history/{record_id}")
async def delete_user_history_record(
    record_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Delete a try-on history record owned by the user."""
    try:
        logger.info(
            "Deleting history record",
            extra={"record_id": record_id, "user_id": user["id"]},
        )

        success = await user_history_ops.delete_user_tryon_record(
            record_id=record_id,
            user_id=user["id"],
        )
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Record not found or you don't have permission to delete it",
            )

        return {"success": True, "message": "Record deleted successfully"}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to delete history record",
            extra={"error": str(exc), "record_id": record_id},
        )
        raise HTTPException(status_code=500, detail=f"Failed to delete record: {exc}")


@router.get("/stats")
async def get_user_stats(user: dict = Depends(get_current_user)) -> dict:
    """Return aggregate statistics for the user's try-on history."""
    try:
        logger.info("Fetching user stats", extra={"user_id": user["id"]})

        stats = await user_history_ops.get_user_stats(user["id"])
        return {"success": True, "stats": stats}

    except Exception as exc:
        logger.error("Failed to fetch user stats", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {exc}")


@router.get("/health")
async def auth_health_check() -> dict:
    """Health check endpoint for the authentication service."""
    return {"status": "healthy", "service": "authentication"}
