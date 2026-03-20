from typing import Annotated, Callable

import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_auth_scheme = HTTPBearer(auto_error=False)


def build_auth_dependency(secret_token: str) -> Callable[..., None]:
    def dependency(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(_auth_scheme),
        ],
    ) -> None:
        unauthorized = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": 'Bearer realm="api"'},
        )

        if credentials is None:
            raise unauthorized

        if credentials.scheme.lower() != "bearer":
            raise unauthorized

        if not secrets.compare_digest(credentials.credentials, secret_token):
            raise unauthorized

    return Depends(dependency)
