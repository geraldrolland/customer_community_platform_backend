import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from itsdangerous import BadSignature, URLSafeSerializer

from config import settings

cookie_serializer = URLSafeSerializer(
    settings.COOKIE_SIGNING_SECRET,
    salt="event-platform-cookie",
    signer_kwargs={"digest_method": hashlib.sha256},
)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def _create_token(payload: dict, expires_at: datetime) -> str:
    token_payload = {**payload, "exp": expires_at}
    return jwt.encode(
        token_payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM
    )


def create_verification_token(user_id: int, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES
    )
    return _create_token(
        {"sub": str(user_id), "role": role}, expires_at
    )


def create_access_token(session_id: str, user_id: int, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return _create_token(
        {"sub": str(user_id), "role": role, "session_id": session_id},
        expires_at,
    )


def create_refresh_token(session_id: str, user_id: int, role: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    return _create_token(
        {"sub": str(user_id), "role": role, "session_id": session_id},
        expires_at,
    )


def create_auth_token(access_token: str, refresh_token: str) -> str:
    return cookie_serializer.dumps(
        {"access_token": access_token, "refresh_token": refresh_token}
    )


def unsign_value(signed: str):
    return cookie_serializer.loads(signed)


def create_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def decode_token(token: str) -> dict:
    return jwt.decode(
        token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
    )
