"""
Authentication module for user registration, login, and token management.
Uses Supabase for user storage and JWT for session management.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets
import hashlib
from supabase import Client

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
            from supabase import create_client
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            logger.info("Supabase client initialized successfully for auth operations")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise

    return _supabase_client


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hash a password using SHA256 with salt.

    Args:
        password: Plain text password
        salt: Optional salt (will generate if not provided)

    Returns:
        Tuple of (hashed_password, salt)
    """
    if not salt:
        salt = secrets.token_hex(32)
    
    # Combine password and salt, then hash
    pwd_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return pwd_hash, salt


def verify_password(password: str, hashed_password: str, salt: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        password: Plain text password to verify
        hashed_password: Stored hash
        salt: Salt used for hashing

    Returns:
        True if password matches, False otherwise
    """
    computed_hash, _ = hash_password(password, salt)
    return computed_hash == hashed_password


def generate_session_token() -> str:
    """Generate a secure random session token."""
    return secrets.token_urlsafe(32)


async def create_user(
    email: str,
    password: str,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new user account.

    Args:
        email: User email address
        password: Plain text password
        username: Optional username

    Returns:
        Dict containing user data (without password/salt)

    Raises:
        Exception: If user creation fails or email already exists
    """
    try:
        client = _get_supabase_client()

        # Check if email already exists
        existing = client.table("users").select("id").eq("email", email).execute()
        if existing.data and len(existing.data) > 0:
            raise Exception("Email already registered")

        # Hash password
        hashed_pwd, salt = hash_password(password)

        # Prepare user data
        user_data = {
            "email": email,
            "username": username or email.split("@")[0],
            "password_hash": hashed_pwd,
            "password_salt": salt,
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True,
        }

        logger.info(f"Creating new user: {email}")

        # Insert user
        response = client.table("users").insert(user_data).execute()

        if response.data and len(response.data) > 0:
            user = response.data[0]
            # Remove sensitive data before returning
            user.pop("password_hash", None)
            user.pop("password_salt", None)
            logger.info(f"Successfully created user with ID: {user.get('id')}")
            return user
        else:
            error_msg = "Failed to create user: No data returned"
            logger.error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"Error creating user: {e}")
        raise


async def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user with email and password.

    Args:
        email: User email
        password: Plain text password

    Returns:
        User dict if authentication successful, None otherwise
    """
    try:
        client = _get_supabase_client()

        logger.info(f"Authenticating user: {email}")

        # Get user by email
        response = (
            client.table("users")
            .select("*")
            .eq("email", email)
            .eq("is_active", True)
            .execute()
        )

        if not response.data or len(response.data) == 0:
            logger.warning(f"User not found or inactive: {email}")
            return None

        user = response.data[0]

        # Verify password
        if not verify_password(
            password, user["password_hash"], user["password_salt"]
        ):
            logger.warning(f"Invalid password for user: {email}")
            return None

        # Remove sensitive data
        user.pop("password_hash", None)
        user.pop("password_salt", None)

        logger.info(f"Successfully authenticated user: {email}")
        return user

    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        return None


async def create_session(user_id: str) -> Dict[str, Any]:
    """
    Create a new session for a user.

    Args:
        user_id: User ID

    Returns:
        Dict containing session data including token

    Raises:
        Exception: If session creation fails
    """
    try:
        client = _get_supabase_client()

        # Generate session token
        token = generate_session_token()
        expires_at = datetime.utcnow() + timedelta(days=7)  # 7 day expiry

        session_data = {
            "user_id": user_id,
            "token": token,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
            "is_active": True,
        }

        logger.info(f"Creating session for user: {user_id}")

        response = client.table("sessions").insert(session_data).execute()

        if response.data and len(response.data) > 0:
            session = response.data[0]
            logger.info(f"Successfully created session: {session.get('id')}")
            return session
        else:
            error_msg = "Failed to create session: No data returned"
            logger.error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise


async def get_session(token: str) -> Optional[Dict[str, Any]]:
    """
    Get session by token if valid and not expired.

    Args:
        token: Session token

    Returns:
        Session dict with user data if valid, None otherwise
    """
    try:
        client = _get_supabase_client()

        # Get session with user data
        response = (
            client.table("sessions")
            .select("*, users(*)")
            .eq("token", token)
            .eq("is_active", True)
            .execute()
        )

        if not response.data or len(response.data) == 0:
            return None

        session = response.data[0]

        # Check expiry
        expires_at = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
        if expires_at < datetime.utcnow().replace(tzinfo=expires_at.tzinfo):
            logger.warning(f"Session expired: {session.get('id')}")
            return None

        # Remove sensitive data from user
        if "users" in session and session["users"]:
            session["users"].pop("password_hash", None)
            session["users"].pop("password_salt", None)

        return session

    except Exception as e:
        logger.error(f"Error getting session: {e}")
        return None


async def invalidate_session(token: str) -> bool:
    """
    Invalidate a session (logout).

    Args:
        token: Session token

    Returns:
        True if successful, False otherwise
    """
    try:
        client = _get_supabase_client()

        logger.info("Invalidating session")

        response = (
            client.table("sessions")
            .update({"is_active": False})
            .eq("token", token)
            .execute()
        )

        return bool(response.data and len(response.data) > 0)

    except Exception as e:
        logger.error(f"Error invalidating session: {e}")
        return False


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user by ID.

    Args:
        user_id: User ID

    Returns:
        User dict if found, None otherwise
    """
    try:
        client = _get_supabase_client()

        response = client.table("users").select("*").eq("id", user_id).execute()

        if response.data and len(response.data) > 0:
            user = response.data[0]
            # Remove sensitive data
            user.pop("password_hash", None)
            user.pop("password_salt", None)
            return user

        return None

    except Exception as e:
        logger.error(f"Error getting user by ID: {e}")
        return None
