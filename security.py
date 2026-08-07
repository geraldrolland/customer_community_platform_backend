"""Security primitives: password hashing, JWT tokens, and cookie signing.

Centralizes token creation/decoding (access, refresh), signed-cookie
serialization for the auth token, and CSRF token generation. All tokens
are bound to the configured JWT secret.
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from itsdangerous import BadSignature, URLSafeSerializer

from core.settings import settings

cookie_serializer = URLSafeSerializer(
    settings.COOKIE_SIGNING_SECRET,
    salt="event-platform-cookie",
    signer_kwargs={"digest_method": hashlib.sha256},
)


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt and a random salt.

    Args:
        password: Plaintext password to hash.

    Returns:
        The bcrypt hash string, safe for storage.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash.

    Args:
        password: Plaintext password to check.
        hashed_password: Stored bcrypt hash.

    Returns:
        ``True`` when the password matches the hash.
    """
    return bcrypt.checkpw(
        password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def _create_token(payload: dict, expires_at: datetime) -> str:
    """Encode a JWT with the given payload and expiry.

    Args:
        payload: Claims to embed (subject, role, session id, ...).
        expires_at: Token expiration timestamp.

    Returns:
        The signed JWT string.
    """
    token_payload = {**payload, "exp": expires_at}
    return jwt.encode(
        token_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )


def create_access_token(session_id: str, role: str) -> str:
    """Create a short-lived access JWT bound to a session.

    Args:
        session_id: Current server-side session id for rotation checks.
        role: User role.

    Returns:
        A signed access JWT.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return _create_token(
        {"role": role, "session_id": session_id},
        expires_at,
    )


def create_refresh_token(session_id: str, role: str) -> str:
    """Create a long-lived refresh JWT bound to a session.

    Args:
        session_id: Current server-side session id for rotation checks.
        role: User role.

    Returns:
        A signed refresh JWT.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    return _create_token(
        {"role": role, "session_id": session_id},
        expires_at,
    )


def create_auth_token(access_token: str, refresh_token: str) -> str:
    """Package access and refresh JWTs into a single signed cookie value.

    Args:
        access_token: Signed access JWT.
        refresh_token: Signed refresh JWT.

    Returns:
        A URL-safe signed blob stored in the ``auth_token`` cookie.
    """
    return cookie_serializer.dumps(
        {"access_token": access_token, "refresh_token": refresh_token}
    )


def unsign_value(signed: str):
    """Decode and validate a value previously created by :func:`create_auth_token`.

    Args:
        signed: Signed cookie value.

    Returns:
        The original payload dict.

    Raises:
        BadSignature: When the value was tampered with or the signature is
            invalid.
    """
    return cookie_serializer.loads(signed)


def create_csrf_token() -> str:
    """Generate a cryptographically random CSRF token.

    Returns:
        A URL-safe random token (e.g. 43 characters).
    """
    return secrets.token_urlsafe(32)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT.

    Args:
        token: Signed JWT string.

    Returns:
        The token claims as a dict.

    Raises:
        jwt.PyJWTError: When the token is invalid or expired.
    """
    return jwt.decode(
        token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
    )
