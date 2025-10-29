"""
Authentication module for user registration, login, and token management.
Uses Supabase Auth for authentication and JWT for session management.
"""

from typing import Optional, Dict, Any
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


# Note: Password hashing and session token generation are now handled by Supabase Auth
# No need for custom implementations


async def create_user(
    email: str,
    password: str,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a new user account using Supabase Auth.

    Args:
        email: User email address
        password: Plain text password
        username: Optional username (stored in user metadata)

    Returns:
        Dict containing user data from Supabase Auth

    Raises:
        Exception: If user creation fails or email already exists
    """
    try:
        client = _get_supabase_client()

        logger.info(f"Creating new user with Supabase Auth: {email}")

        # Prepare user metadata
        user_metadata = {}
        if username:
            user_metadata["username"] = username
        else:
            user_metadata["username"] = email.split("@")[0]

        # Use Supabase Auth sign_up
        response = client.auth.sign_up(
            {"email": email, "password": password, "options": {"data": user_metadata}}
        )

        if response.user:
            user_data = {
                "id": response.user.id,
                "email": response.user.email,
                "username": user_metadata.get("username"),
                "created_at": response.user.created_at,
                "is_active": True,
            }
            logger.info(f"Successfully created user with ID: {response.user.id}")
            return user_data
        else:
            error_msg = "Failed to create user: No user data returned"
            logger.error(error_msg)
            raise Exception(error_msg)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error creating user: {error_msg}")

        # Handle common Supabase auth errors
        if (
            "already registered" in error_msg.lower()
            or "already exists" in error_msg.lower()
        ):
            raise Exception("Email already registered")

        raise Exception(f"Failed to create user: {error_msg}")


async def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user with email and password using Supabase Auth.
    Uses the official sign_in_with_password method from Supabase Auth.

    Args:
        email: User email
        password: Plain text password

    Returns:
        Dict containing user data and session tokens if authentication successful, None otherwise
    """
    try:
        client = _get_supabase_client()

        logger.info(f"Authenticating user with Supabase Auth: {email}")

        # Use Supabase Auth sign_in_with_password as per official docs
        # https://supabase.com/docs/reference/python/auth-signinwithpassword
        response = client.auth.sign_in_with_password(
            {"email": email, "password": password}
        )

        if response.user and response.session:
            user_email = response.user.email or email
            user_data = {
                "id": response.user.id,
                "email": user_email,
                "username": response.user.user_metadata.get(
                    "username", user_email.split("@")[0]
                ),
                "created_at": response.user.created_at,
                "is_active": True,
                "session": {
                    "access_token": response.session.access_token,
                    "refresh_token": response.session.refresh_token,
                    "expires_at": response.session.expires_at,
                    "expires_in": response.session.expires_in,
                    "token_type": response.session.token_type,
                },
            }
            logger.info(f"Successfully authenticated user: {email}")
            return user_data
        else:
            logger.warning(f"Authentication failed for user: {email}")
            return None

    except Exception as e:
        logger.error(f"Error authenticating user: {e}")
        return None


# Note: Session management is now handled entirely by Supabase Auth
# JWT tokens are validated using verify_access_token() below


async def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user profile by ID from the profiles table.

    Args:
        user_id: User ID (auth.users UUID)

    Returns:
        User profile dict if found, None otherwise
    """
    try:
        client = _get_supabase_client()

        # Query the profiles table which extends auth.users
        response = client.table("profiles").select("*").eq("id", user_id).execute()

        if response.data and len(response.data) > 0:
            profile = response.data[0]
            return profile

        return None

    except Exception as e:
        logger.error(f"Error getting user profile by ID: {e}")
        return None


async def verify_access_token(access_token: str) -> Optional[Dict[str, Any]]:
    """
    Verify a Supabase Auth access token and return user data.

    Args:
        access_token: JWT access token from Supabase Auth

    Returns:
        User dict if token is valid, None otherwise
    """
    try:
        client = _get_supabase_client()

        logger.debug("Verifying Supabase Auth access token")

        # Get user from access token
        response = client.auth.get_user(access_token)

        if response and hasattr(response, "user") and response.user:
            user_email = response.user.email or ""
            user_data = {
                "id": response.user.id,
                "email": user_email,
                "username": response.user.user_metadata.get(
                    "username", user_email.split("@")[0] if user_email else "user"
                ),
                "created_at": response.user.created_at,
                "is_active": True,
            }
            logger.debug(f"Token verified for user: {response.user.id}")
            return user_data
        else:
            logger.warning("Invalid or expired access token")
            return None

    except Exception as e:
        logger.error(f"Error verifying access token: {e}")
        return None


async def request_password_reset(email: str, redirect_to: Optional[str] = None) -> bool:
    """
    Request a password reset email for a user using Supabase Auth.
    Follows official documentation: https://supabase.com/docs/reference/python/auth-resetpasswordforemail

    Args:
        email: User email address
        redirect_to: Optional URL to redirect to after reset (must be configured in Supabase)

    Returns:
        True if request was processed successfully

    Note:
        - This uses Supabase's built-in auth.reset_password_for_email() method
        - Always returns True to prevent email enumeration attacks
        - Configure email templates in your Supabase dashboard
        - Set up allowed redirect URLs in Supabase Auth settings
        - Bot protection is handled by Turnstile on the API endpoint level
    """
    try:
        client = _get_supabase_client()

        logger.info(f"Password reset requested via Supabase Auth for email: {email}")

        # Use Supabase Auth's reset_password_for_email as per official docs
        # https://supabase.com/docs/reference/python/auth-resetpasswordforemail
        if redirect_to:
            options = {"redirect_to": redirect_to}
            client.auth.reset_password_for_email(email, options)  # type: ignore
            logger.info(
                f"Password reset email sent to: {email} with redirect_to: {redirect_to}"
            )
        else:
            client.auth.reset_password_for_email(email)
            logger.info(f"Password reset email sent to: {email}")

        return True

    except Exception as e:
        logger.error(f"Error requesting password reset: {e}")
        # Return True anyway to prevent email enumeration
        return True
