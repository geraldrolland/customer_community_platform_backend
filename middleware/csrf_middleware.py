"""CSRF protection middleware using the double-submit cookie pattern.

For state-changing requests (non-GET/HEAD/OPTIONS) targeting protected
routes, the ``x-csrf-token`` header must match the value of the
``csrf_token`` cookie. Safe methods and unprotected routes pass through
unchecked. Comparison uses a constant-time function.
"""
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.settings import settings
from middleware.auth_middleware import PROTECTED_ROUTES

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class CsrfMiddleware(BaseHTTPMiddleware):
    """Reject protected write requests whose CSRF header does not match the cookie."""

    async def dispatch(self, request: Request, call_next):
        """Enforce CSRF token equality on protected, state-changing requests.

        Args:
            request: Incoming HTTP request.
            call_next: Callable that invokes the next middleware/route.

        Returns:
            Response: A 403 JSON response when the check fails, otherwise
            the downstream response.
        """
        if request.method in SAFE_METHODS:
            return await call_next(request)

        if not any(
            request.url.path == route or request.url.path.startswith(route + "/")
            for route in PROTECTED_ROUTES
        ):
            return await call_next(request)

        header_token = request.headers.get("x-csrf-token")
        cookie_token = request.cookies.get(settings.CSRF_TOKEN_COOKIE)

        if not header_token or not cookie_token or not secrets.compare_digest(
            header_token, cookie_token
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Permission denied, invalid csrf token present in header x-csrf-token"
                },
            )

        return await call_next(request)
