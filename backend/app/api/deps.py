"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import decode_session_token
from app.db.session import get_db
from app.models import User

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def current_user_optional(
    request: Request, session: DbSession, settings: AppSettings
) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    claims = decode_session_token(token, settings)
    if not claims:
        return None
    try:
        user_id = int(claims.get("sub", ""))
    except ValueError:
        return None
    return session.get(User, user_id)


OptionalUser = Annotated["User | None", Depends(current_user_optional)]


def require_user(user: OptionalUser) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to continue."
        )
    return user


CurrentUser = Annotated[User, Depends(require_user)]
