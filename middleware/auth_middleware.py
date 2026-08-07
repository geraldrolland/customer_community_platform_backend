"""Authentication middleware for cookie-based session handling.

Protects a curated list of routes. Authenticates the signed ``auth_token``
cookie (access token with refresh fallback), binds the user to
``request.state.auth_user``, and verifies the server-side ``session_id``.
The session is rotated only when a request arrives with an expired access
token (the refresh fallback); requests that carry the just-rotated-away
session id are still accepted within a short grace window and re-issued
a cookie for the current session, so concurrent requests never race into
a 401. Invalid or expired sessions are cleared and rejected with 401.
"""
import secrets
import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.settings import settings
from database import SessionLocal
from models import Customer, VenueManager
from security import (
    create_access_token,
    create_auth_token,
    create_refresh_token,
    decode_token,
    unsign_value,
)

# Routes that require a valid session; the CSRF middleware relies on the
# same list to decide which writes need a matching CSRF header.
PROTECTED_ROUTES = (
    "/api/auth/me",
    "/api/auth/me/update",
    "/api/auth/logout",
    "/api/venue",
    "/api/event",
    "/api/vote",
    "/api/media/upload",
    )

# Shared cookie attributes: HttpOnly, SameSite=Lax (cross-site requests
# do not carry the cookie), path-scoped to the whole API. ``secure`` is
# disabled for local HTTP development.
COOKIE_KWARGS = {
    "httponly": True,
    "samesite": "lax",
    "secure": False,
    "path": "/",
}

# How long a request carrying the session id that was just rotated away
# is still accepted. Parallel requests crossing the access-token expiry
# boundary all carry the same pre-rotation cookie; the first one to
# rotate must not invalidate the rest.
SESSION_ROTATION_GRACE_SECONDS = 60

# (role, user_id) -> (current_session_id, previous_session_id, rotated_at)
_recent_rotations: dict[tuple[str, int], tuple[str, str, float]] = {}


def _record_rotation(role: str, user_id: int, current: str, previous: str) -> None:
    """Store a rotation so one-behind cookies stay valid during the grace window.

    Args:
        role: User role (``"customer"`` or ``"venue_manager"``).
        user_id: ID of the user whose session rotated.
        current: The session id now stored in the database.
        previous: The session id that was just replaced.
    """
    now = time.time()
    for stale in [
        key
        for key, (_, _, rotated_at) in _recent_rotations.items()
        if now - rotated_at > SESSION_ROTATION_GRACE_SECONDS
    ]:
        _recent_rotations.pop(stale, None)
    _recent_rotations[(role, user_id)] = (current, previous, now)


def _grace_user(db, role: str, session_id: str):
    """Resolve a user whose session was rotated away from ``session_id`` recently.

    Args:
        db: Database session.
        role: User role (``"customer"`` or ``"venue_manager"``).
        session_id: The session id claimed by the cookie.

    Returns:
        The user when the cookie's session id was replaced by a rotation
        within the grace window, otherwise ``None``.
    """
    now = time.time()
    for (entry_role, user_id), (current, previous, rotated_at) in _recent_rotations.items():
        if now - rotated_at > SESSION_ROTATION_GRACE_SECONDS:
            continue
        if entry_role != role or previous != session_id:
            continue
        user = _find_user(db, role, current)
        if user is not None and user.id == user_id:
            return user
    return None


def _find_user(db, role: str, session_id: str):
    """Look up a user by role and session id.

    Args:
        db: Database session.
        role: User role (``"customer"`` or ``"venue_manager"``).
        session_id: Current server-side session id.

    Returns:
        The matching user row, or ``None`` when the role is unknown or no
        user holds the given session id.
    """
    if role == "customer":
        return (
            db.query(Customer)
            .filter(Customer.session_id == session_id)
            .first()
        )
    if role == "venue_manager":
        return (
            db.query(VenueManager)
            .filter(VenueManager.session_id == session_id)
            .first()
        )
    return None


def _clear_auth_cookie(response) -> JSONResponse:
    """Expire the auth cookie on the given response.

    Args:
        response: Response to attach the clearing Set-Cookie to.

    Returns:
        The same response with the auth cookie emptied.
    """
    response.set_cookie(settings.AUTH_TOKEN_COOKIE, "", **COOKIE_KWARGS)
    return response


class AuthMiddleware(BaseHTTPMiddleware):
    """Authenticate protected requests from the signed auth cookie."""

    async def dispatch(self, request: Request, call_next):
        """Validate the session cookie and attach the authenticated user.

        Args:
            request: Incoming HTTP request.
            call_next: Callable that invokes the next middleware/route.

        Returns:
            Response: The downstream response, a 401 rejection, or the
            downstream response with an updated auth cookie (refresh
            fallback only).
        """
        request.state.auth_user = None

        if not any(
            request.url.path == route or request.url.path.startswith(route + "/")
            for route in PROTECTED_ROUTES
        ):
            return await call_next(request)

        auth_token = request.cookies.get(settings.AUTH_TOKEN_COOKIE)

        if not auth_token:
            return JSONResponse(
                status_code=401,
                content={"detail": "auth token missing"},
            )

        try:
            token_payload = unsign_value(auth_token)
        except Exception:
            return _clear_auth_cookie(
                JSONResponse(
                    status_code=401,
                    content={"detail": "tampered session"},
                )
            )

        db = SessionLocal()

        try:
            try:
                claims = decode_token(token_payload["access_token"])
                used_refresh = False
            except Exception:
                try:
                    claims = decode_token(token_payload["refresh_token"])
                    used_refresh = True
                except Exception:
                    return _clear_auth_cookie(
                        JSONResponse(
                            status_code=401,
                            content={"detail": "session expired"},
                        )
                    )

            session_id = claims.get("session_id")
            if not session_id:
                return _clear_auth_cookie(
                    JSONResponse(
                        status_code=401,
                        content={"detail": "session expired"},
                    )
                )

            role = claims.get("role")
            user = _find_user(db, role, session_id)
            rotate_now = False

            if used_refresh:
                if user is None:
                    user = _grace_user(db, role, session_id)
                elif request.url.path != "/api/auth/logout":
                    rotate_now = True

            if user is None:
                return _clear_auth_cookie(
                    JSONResponse(
                        status_code=401,
                        content={"detail": "session expired"},
                    )
                )

            if rotate_now:
                previous_session_id = user.session_id
                new_session_id = secrets.token_urlsafe(32)
                user.session_id = new_session_id
                db.commit()
                _record_rotation(
                    role, user.id, new_session_id, previous_session_id
                )

            request.state.auth_user = user

            response = await call_next(request)

            if used_refresh and request.url.path != "/api/auth/logout":
                current_session_id = user.session_id
                response.set_cookie(
                    settings.AUTH_TOKEN_COOKIE,
                    create_auth_token(
                        create_access_token(current_session_id, user.role),
                        create_refresh_token(current_session_id, user.role),
                    ),
                    **COOKIE_KWARGS,
                )

            return response

        finally:
            db.close()
