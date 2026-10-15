"""Authentication helpers.

ONE I never stores passwords and never implements OAuth by hand. Identity comes
from a Google ID token verified with Google's own library; CAPTCHA is verified
with the provider's siteverify endpoint. This module only issues and reads a
short-lived signed session cookie.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import Settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"


class AuthError(Exception):
    """Authentication could not be completed."""


@dataclass(frozen=True)
class GoogleIdentity:
    google_id: str
    email: str
    name: str | None


@dataclass(frozen=True)
class CaptchaResult:
    passed: bool
    detail: str


def create_session_token(
    *, user_id: int, email: str, name: str | None, settings: Settings
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "name": name or "",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=settings.session_ttl_hours)).timestamp()),
    }
    return jwt.encode(payload, settings.session_secret, algorithm=ALGORITHM)


def decode_session_token(token: str, settings: Settings) -> dict | None:
    try:
        return jwt.decode(token, settings.session_secret, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None


def verify_google_credential(credential: str, settings: Settings) -> GoogleIdentity:
    """Verify a Google ID token using Google's own verification library."""
    if not settings.google_auth_configured:
        raise AuthError("Google sign-in is not configured on this server.")
    try:
        claims = google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), settings.google_client_id
        )
    except ValueError as error:
        raise AuthError(f"Google rejected the sign-in token: {error}") from error

    subject = claims.get("sub")
    email = claims.get("email")
    if not subject or not email:
        raise AuthError("Google token did not contain an account identifier.")
    if claims.get("email_verified") is False:
        raise AuthError("The Google account email is not verified.")
    return GoogleIdentity(google_id=str(subject), email=str(email), name=claims.get("name"))


def verify_captcha(token: str | None, remote_ip: str | None, settings: Settings) -> CaptchaResult:
    """Verify a CAPTCHA token with the configured provider.

    CAPTCHA_PROVIDER=none turns CAPTCHA off deliberately (Google sign-in only)
    and is reported as skipped. A chosen provider without its secret key is a
    misconfiguration: skipped in development, refused in production.
    """
    if settings.captcha_provider == "none":
        return CaptchaResult(True, "CAPTCHA disabled (CAPTCHA_PROVIDER=none); verification skipped.")
    if not settings.captcha_configured:
        if settings.is_production:
            return CaptchaResult(False, "CAPTCHA is required but not configured on this server.")
        return CaptchaResult(True, "CAPTCHA not configured; verification skipped in development.")
    if not token:
        return CaptchaResult(False, "CAPTCHA response is missing.")

    url = (
        settings.captcha_verify_url_turnstile
        if settings.captcha_provider == "turnstile"
        else settings.captcha_verify_url_recaptcha
    )
    payload = {"secret": settings.captcha_secret_key, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip
    try:
        with httpx.Client(timeout=settings.http_timeout_seconds) as client:
            response = client.post(url, data=payload)
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("CAPTCHA verification failed to complete: %s", error)
        return CaptchaResult(False, "CAPTCHA verification could not be completed.")

    if body.get("success") is True:
        return CaptchaResult(True, "CAPTCHA verified.")
    codes = ", ".join(body.get("error-codes") or []) or "rejected"
    return CaptchaResult(False, f"CAPTCHA verification failed ({codes}).")
