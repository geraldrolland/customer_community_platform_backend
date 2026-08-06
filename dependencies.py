from fastapi import HTTPException, Request, status


class RequirePermission:
    def __init__(self, roles: list[str]):
        self.roles = roles

    def __call__(self, request: Request):
        auth_user = getattr(request.state, "auth_user", None)
        if auth_user is None or auth_user.role not in self.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        return auth_user
