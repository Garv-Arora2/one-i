"""Authentication schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuthConfigResponse(BaseModel):
    google_configured: bool
    captcha_provider: str
    captcha_configured: bool
    dev_bypass_enabled: bool
    message: str


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=10, description="Google ID token from the sign-in button")
    captcha_token: str | None = None


class DevLoginRequest(BaseModel):
    # Local development only, so a light pattern is enough and avoids pulling in
    # an email-validation dependency for a route that is disabled in production.
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=320)
    name: str | None = None


class SessionUser(BaseModel):
    id: int
    email: str
    name: str | None


class SessionResponse(BaseModel):
    authenticated: bool
    user: SessionUser | None = None
