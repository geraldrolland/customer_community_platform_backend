"""Middleware that logs every request with its method, path, and status.

Sits at the outermost position of the middleware stack so that requests
rejected by any inner middleware (CORS, Auth, CSRF, TrustedHost) are
still logged with the status code they received.
"""
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Log one INFO line per request: method, url path, and status code."""

    async def dispatch(self, request: Request, call_next):
        """Process the request and log the resulting status.

        Args:
            request: Incoming HTTP request.
            call_next: Callable that invokes the next middleware/route.

        Returns:
            Response: The response produced downstream.
        """
        response = await call_next(request)
        logger.info(
            "method=%s url_path=%s status=%s",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response
