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


@auth_router.get("/health")
async def auth_health_check():
    """Health check for auth service"""
    return {"status": "healthy", "service": "authentication"}
