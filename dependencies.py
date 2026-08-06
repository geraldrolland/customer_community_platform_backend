"""Reusable FastAPI dependencies for authorization checks."""
from fastapi import HTTPException, Request, status


class RequirePermission:
    """Dependency that gates a route to authenticated users with an allowed role.

    Reads the authenticated user attached to the request by
    ``AuthMiddleware`` (``request.state.auth_user``) and rejects
    unauthenticated callers or users whose role is not permitted.
    """

    def __init__(self, roles: list[str]):
        """Store the roles allowed to access the guarded route.

        Args:
            roles: Role names allowed through, e.g. ``["customer"]``.
        """
        self.roles = roles

    def __call__(self, request: Request):
        """Validate the caller and return the authenticated user.

        Args:
            request: Incoming request carrying ``request.state.auth_user``
                as set by ``AuthMiddleware``.

        Returns:
            The authenticated user object.

        Raises:
            HTTPException: 403 when the caller is unauthenticated or its
                role is not in the allowed list.
        """
        auth_user = getattr(request.state, "auth_user", None)
        if auth_user is None or auth_user.role not in self.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        return auth_user
