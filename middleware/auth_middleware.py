"""Authentication middleware for cookie-based session handling.

Protects a curated list of routes. Authenticates the signed ``auth_token``
cookie (access token with refresh fallback), binds the user to
``request.state.auth_user``, verifies the server-side ``session_id``, and
rotates the session + cookie on every protected request so a stolen cookie
is quickly invalidated. Invalid or expired sessions are cleared and
rejected with 401.
"""
import secrets

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


def _find_user(db, role: str, user_id: int):
    """Look up a user by role and id.

    Args:
        db: Database session.
        role: User role (``"customer"`` or ``"venue_manager"``).
        user_id: User primary key.

    Returns:
        The matching user row, or ``None`` when the role is unknown or the
        user does not exist.
    """
    if role == "customer":
        return db.query(Customer).filter(Customer.id == user_id).first()
    if role == "venue_manager":
        return db.query(VenueManager).filter(VenueManager.id == user_id).first()
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
            downstream response with a freshly rotated auth cookie.
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
            except Exception:
                try:
                    claims = decode_token(token_payload["refresh_token"])
                except Exception:
                    return _clear_auth_cookie(
                        JSONResponse(
                            status_code=401,
                            content={"detail": "session expired"},
                        )
                    )

            try:
                user = _find_user(db, claims.get("role"), int(claims.get("sub")))
            except (TypeError, ValueError):
                user = None

            if not user or user.session_id != claims.get("session_id"):
                return _clear_auth_cookie(
                    JSONResponse(
                        status_code=401,
                        content={"detail": "session expired"},
                    )
                )

            request.state.auth_user = user

            if request.url.path == "/auth/logout":
                return await call_next(request)

            new_session_id = secrets.token_urlsafe(32)
            user.session_id = new_session_id
            db.commit()

            new_access_token = create_access_token(
                new_session_id, user.id, user.role
            )
            new_refresh_token = create_refresh_token(
                new_session_id, user.id, user.role
            )
            new_auth_token = create_auth_token(
                new_access_token, new_refresh_token
            )

            response = await call_next(request)
            response.set_cookie(
                settings.AUTH_TOKEN_COOKIE, new_auth_token, **COOKIE_KWARGS
            )
            return response

        finally:
            db.close()
