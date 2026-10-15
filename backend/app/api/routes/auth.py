"""Authentication endpoints.

Google verifies the identity, the CAPTCHA provider verifies the request, and
this service only issues a signed, HttpOnly session cookie.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy import select

from app.api.deps import AppSettings, DbSession, OptionalUser
from app.core.security import (
    AuthError,
    GoogleIdentity,
    create_session_token,
    verify_captcha,
    verify_google_credential,
)
from app.db.base import utcnow
from app.models import User
from app.schemas.auth import (
    AuthConfigResponse,
    DevLoginRequest,
    GoogleLoginRequest,
    SessionResponse,
    SessionUser,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config", response_model=AuthConfigResponse)
def auth_config(settings: AppSettings) -> AuthConfigResponse:
    """Lets the frontend show the right sign-in state without guessing."""
    if settings.google_auth_configured:
        message = "Google sign-in is available."
    else:
        message = (
            "Google sign-in is not configured on this server. "
            "Set GOOGLE_CLIENT_ID (and NEXT_PUBLIC_GOOGLE_CLIENT_ID for the web app) to enable it."
        )
    return AuthConfigResponse(
        google_configured=settings.google_auth_configured,
        captcha_provider=settings.captcha_provider,
        captcha_configured=settings.captcha_configured,
        dev_bypass_enabled=settings.auth_dev_bypass and not settings.is_production,
        message=message,
    )


def _upsert_user(session, identity: GoogleIdentity) -> User:
    user = session.scalar(select(User).where(User.google_id == identity.google_id))
    if user is None:
        user = session.scalar(select(User).where(User.email == identity.email))
    if user is None:
        user = User(google_id=identity.google_id, email=identity.email, name=identity.name)
        session.add(user)
    else:
        user.google_id = identity.google_id
        user.email = identity.email
        user.name = identity.name or user.name
    user.last_login_at = utcnow()
    session.commit()
    session.refresh(user)
    return user


def _issue_session(response: Response, user: User, settings) -> SessionResponse:
    token = create_session_token(
        user_id=user.id, email=user.email, name=user.name, settings=settings
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    return SessionResponse(
        authenticated=True,
        user=SessionUser(id=user.id, email=user.email, name=user.name),
    )


@router.post("/google", response_model=SessionResponse)
def google_login(
    payload: GoogleLoginRequest,
    request: Request,
    response: Response,
    session: DbSession,
    settings: AppSettings,
) -> SessionResponse:
    captcha = verify_captcha(
        payload.captcha_token, request.client.host if request.client else None, settings
    )
    if not captcha.passed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=captcha.detail)
    try:
        identity = verify_google_credential(payload.credential, settings)
    except AuthError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    return _issue_session(response, _upsert_user(session, identity), settings)


@router.post("/dev-login", response_model=SessionResponse)
def dev_login(
    payload: DevLoginRequest,
    response: Response,
    session: DbSession,
    settings: AppSettings,
) -> SessionResponse:
    """Local development only. Refused in production and disabled by default."""
    if settings.is_production or not settings.auth_dev_bypass:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not available."
        )
    identity = GoogleIdentity(
        google_id=f"dev:{payload.email}", email=str(payload.email), name=payload.name
    )
    return _issue_session(response, _upsert_user(session, identity), settings)


@router.get("/me", response_model=SessionResponse)
def me(user: OptionalUser) -> SessionResponse:
    if user is None:
        return SessionResponse(authenticated=False)
    return SessionResponse(
        authenticated=True, user=SessionUser(id=user.id, email=user.email, name=user.name)
    )


@router.post("/logout", response_model=SessionResponse)
def logout(response: Response, settings: AppSettings) -> SessionResponse:
    response.delete_cookie(settings.session_cookie_name, path="/")
    return SessionResponse(authenticated=False)
