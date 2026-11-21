"""Shared API dependencies: database session, signed-in user, permission checks."""

from collections.abc import Callable, Iterator

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_access_token
from app.db.models import User
from app.db.session import SessionLocal
from app.domain.permissions import Action
from app.services.cases import PermissionDenied, authorize

bearer = HTTPBearer(auto_error=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_session),
) -> User:
    """The signed-in user from the bearer token (401 if missing or invalid)."""
    unauthorised = HTTPException(
        401, "Sign in first", headers={"WWW-Authenticate": "Bearer"}
    )
    if creds is None:
        raise unauthorised
    try:
        claims = decode_access_token(creds.credentials)
    except TokenError:
        raise unauthorised from None
    user = session.get(User, claims.get("sub"))
    if user is None or not user.is_active:
        raise unauthorised
    return user


def require(action: Action) -> Callable[..., User]:
    """Dependency: the user must be allowed to do `action` (403 otherwise).

    A refused attempt is audited and committed before the 403 is returned.
    """

    def dependency(
        user: User = Depends(current_user), session: Session = Depends(get_session)
    ) -> User:
        try:
            authorize(session, user, action, "api")
        except PermissionDenied as exc:
            session.commit()  # keep the ACCESS_DENIED audit entry
            raise HTTPException(403, str(exc)) from exc
        return user

    return dependency
