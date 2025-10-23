"""
Authentication API routes for user registration, login, and session management.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, EmailStr, Field

from src.config import logger
from src.core import auth


# Initialize router
auth_router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


# -------------------------
# Request/Response Models
# -------------------------
class RegisterRequest(BaseModel):
    """Request model for user registration"""

    email: EmailStr
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    username: Optional[str] = Field(None, max_length=100)


class LoginRequest(BaseModel):
    """Request model for user login"""

    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Response model for successful authentication"""

    success: bool
    message: str
    token: str
    user: dict


class MessageResponse(BaseModel):
    """Generic message response"""

    success: bool
    message: str


class UserResponse(BaseModel):
    """Response model for user data"""

    success: bool
    user: dict


# -------------------------
# Dependency Functions
# -------------------------
async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Dependency to get current authenticated user from token.

    Args:
        authorization: Bearer token from Authorization header

    Returns:
        User dict

    Raises:
        HTTPException: If token is invalid or missing
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401, detail="Invalid authorization header format"
        )

    token = parts[1]

    # Validate session
    session = await auth.get_session(token)
    if not session or not session.get("users"):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return session["users"]


# -------------------------
# Endpoints
# -------------------------
@auth_router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest):
    """
    Register a new user account.

    **Flow:**
    1. Validate email is not already registered
    2. Hash password securely
    3. Create user record
    4. Create initial session
    5. Return token and user data

    **Returns:**
    - token: Session token for authentication
    - user: User profile data
    """
    try:
        logger.info(f"Registration request for email: {payload.email}")

        # Create user
        user = await auth.create_user(
            email=payload.email,
            password=payload.password,
            username=payload.username,
        )

        # Create session
        session = await auth.create_session(user["id"])

        logger.info(f"Successfully registered user: {user['id']}")

        return AuthResponse(
            success=True,
            message="Registration successful",
            token=session["token"],
            user=user,
        )

    except Exception as e:
        error_msg = str(e)
        if "Email already registered" in error_msg:
            raise HTTPException(status_code=400, detail=error_msg)
        logger.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {error_msg}")


@auth_router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest):
    """
    Login with email and password.

    **Flow:**
    1. Verify email and password
    2. Create new session
    3. Return token and user data

    **Returns:**
    - token: Session token for authentication
    - user: User profile data
    """
    try:
        logger.info(f"Login request for email: {payload.email}")

        # Authenticate user
        user = await auth.authenticate_user(payload.email, payload.password)

        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Create session
        session = await auth.create_session(user["id"])

        logger.info(f"Successfully logged in user: {user['id']}")

        return AuthResponse(
            success=True,
            message="Login successful",
            token=session["token"],
            user=user,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@auth_router.post("/logout", response_model=MessageResponse)
async def logout(authorization: Optional[str] = Header(None)):
    """
    Logout current user by invalidating session.

    **Headers:**
    - Authorization: Bearer <token>

    **Returns:**
    - success: Whether logout was successful
    """
    try:
        if not authorization:
            raise HTTPException(status_code=401, detail="Authorization header required")

        # Extract token
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(
                status_code=401, detail="Invalid authorization header format"
            )

        token = parts[1]

        # Invalidate session
        success = await auth.invalidate_session(token)

        if not success:
            raise HTTPException(status_code=400, detail="Failed to logout")

        logger.info("User logged out successfully")

        return MessageResponse(success=True, message="Logout successful")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")


@auth_router.get("/me", response_model=UserResponse)
async def get_current_user_info(user: dict = Depends(get_current_user)):
    """
    Get current authenticated user's profile.

    **Headers:**
    - Authorization: Bearer <token>

    **Returns:**
    - user: User profile data
    """
    return UserResponse(success=True, user=user)


@auth_router.get("/history")
async def get_user_history(
    limit: int = 20,
    offset: int = 0,
    status: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    """
    Get authenticated user's try-on history with pagination.

    **Query Parameters:**
    - limit: Maximum records to return (default: 20, max: 100)
    - offset: Number of records to skip (default: 0)
    - status: Filter by status ('pending', 'processing', 'success', 'failed')

    **Headers:**
    - Authorization: Bearer <token>

    **Returns:**
    - records: List of try-on history records
    - total: Total count of records
    - has_more: Whether more records are available
    """
    try:
        from src.core import user_history_ops

        # Validate limit
        if limit < 1 or limit > 100:
            raise HTTPException(
                status_code=400, detail="Limit must be between 1 and 100"
            )

        if offset < 0:
            raise HTTPException(status_code=400, detail="Offset must be non-negative")

        # Validate status filter
        if status and status not in ["pending", "processing", "success", "failed"]:
            raise HTTPException(
                status_code=400,
                detail="Status must be one of: pending, processing, success, failed",
            )

        logger.info(f"Fetching history for user {user['id']} (limit={limit}, offset={offset}, status={status})")

        history = await user_history_ops.get_user_tryon_history(
            user_id=user["id"], limit=limit, offset=offset, status=status
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
    except Exception as e:
        logger.error(f"Failed to fetch user history: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch history: {str(e)}"
        )


@auth_router.get("/history/{record_id}")
async def get_user_history_record(
    record_id: str, user: dict = Depends(get_current_user)
):
    """
    Get a specific try-on history record by ID.

    **Path Parameters:**
    - record_id: UUID of the history record

    **Headers:**
    - Authorization: Bearer <token>

    **Returns:**
    - record: Try-on history record details
    """
    try:
        from src.core import user_history_ops

        logger.info(f"Fetching record {record_id} for user {user['id']}")

        record = await user_history_ops.get_user_tryon_record(record_id)

        if not record:
            raise HTTPException(status_code=404, detail="Record not found")

        # Verify ownership
        if record["user_id"] != user["id"]:
            raise HTTPException(
                status_code=403, detail="You don't have permission to access this record"
            )

        return {"success": True, "record": record}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch record {record_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch record: {str(e)}"
        )


@auth_router.delete("/history/{record_id}")
async def delete_user_history_record(
    record_id: str, user: dict = Depends(get_current_user)
):
    """
    Delete a specific try-on history record.

    **Path Parameters:**
    - record_id: UUID of the history record

    **Headers:**
    - Authorization: Bearer <token>

    **Returns:**
    - success: Whether deletion was successful
    """
    try:
        from src.core import user_history_ops

        logger.info(f"Deleting record {record_id} for user {user['id']}")

        success = await user_history_ops.delete_user_tryon_record(
            record_id=record_id, user_id=user["id"]
        )

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Record not found or you don't have permission to delete it",
            )

        return {"success": True, "message": "Record deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete record {record_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete record: {str(e)}"
        )


@auth_router.get("/stats")
async def get_user_stats(user: dict = Depends(get_current_user)):
    """
    Get statistics about user's try-on history.

    **Headers:**
    - Authorization: Bearer <token>

    **Returns:**
    - total_tryons: Total number of try-ons
    - successful: Number of successful try-ons
    - failed: Number of failed try-ons
    - pending: Number of pending try-ons
    - success_rate: Success rate percentage
    """
    try:
        from src.core import user_history_ops

        logger.info(f"Fetching stats for user {user['id']}")

        stats = await user_history_ops.get_user_stats(user["id"])

        return {"success": True, "stats": stats}

    except Exception as e:
        logger.error(f"Failed to fetch user stats: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch stats: {str(e)}"
        )


@auth_router.get("/health")
async def auth_health_check():
    """Health check for auth service"""
    return {"status": "healthy", "service": "authentication"}
