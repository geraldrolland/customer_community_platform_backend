import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import settings
from database import SessionLocal
from models import Customer, VenueManager
from security import (
    create_access_token,
    create_auth_token,
    create_refresh_token,
    decode_token,
    unsign_value,
)

PROTECTED_ROUTES = (
    "/api/auth/me",
    "/api/auth/me/update",
    "/api/auth/logout",
    "/api/venue",
    "/api/event",
    "/api/vote",
    "/api/media/upload",
    )

COOKIE_KWARGS = {
    "httponly": True,
    "samesite": "lax",
    "secure": False,
    "path": "/",
}


def _find_user(db, role: str, user_id: int):
    if role == "customer":
        return db.query(Customer).filter(Customer.id == user_id).first()
    if role == "venue_manager":
        return db.query(VenueManager).filter(VenueManager.id == user_id).first()
    return None


def _clear_auth_cookie(response) -> JSONResponse:
    response.set_cookie(settings.AUTH_TOKEN_COOKIE, "", **COOKIE_KWARGS)
    return response


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
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
