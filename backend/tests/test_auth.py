from app.core.config import Settings
from app.core.security import (
    AuthError,
    create_session_token,
    decode_session_token,
    verify_captcha,
    verify_google_credential,
)

import pytest


def settings(**overrides) -> Settings:
    defaults = dict(
        environment="test",
        session_secret="test-secret",
        google_client_id="",
        captcha_provider="none",
        captcha_secret_key="",
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_session_token_round_trip():
    config = settings()
    token = create_session_token(user_id=7, email="a@example.com", name="A", settings=config)
    claims = decode_session_token(token, config)
    assert claims["sub"] == "7"
    assert claims["email"] == "a@example.com"


def test_session_token_from_another_secret_is_rejected():
    token = create_session_token(user_id=7, email="a@example.com", name="A", settings=settings())
    assert decode_session_token(token, settings(session_secret="different")) is None


def test_garbage_token_is_rejected():
    assert decode_session_token("not-a-token", settings()) is None


def test_google_login_requires_configuration():
    with pytest.raises(AuthError):
        verify_google_credential("anything", settings())


def test_captcha_is_skipped_but_reported_in_development():
    result = verify_captcha(None, None, settings(environment="development"))
    assert result.passed is True
    assert "skipped" in result.detail


def test_captcha_can_be_turned_off_deliberately_in_production():
    result = verify_captcha(None, None, settings(environment="production"))
    assert result.passed is True
    assert "disabled" in result.detail


def test_half_configured_captcha_is_refused_in_production():
    config = settings(environment="production", captcha_provider="turnstile")
    assert verify_captcha(None, None, config).passed is False


def test_captcha_token_is_required_when_provider_configured():
    config = settings(captcha_provider="turnstile", captcha_secret_key="secret")
    assert verify_captcha(None, None, config).passed is False


def test_auth_config_endpoint_reports_state(client):
    body = client.get("/auth/config").json()
    assert body["google_configured"] is False
    assert "GOOGLE_CLIENT_ID" in body["message"]


def test_me_is_unauthenticated_without_a_cookie(client):
    assert client.get("/auth/me").json() == {"authenticated": False, "user": None}


def test_dev_login_is_disabled_by_default(client):
    response = client.post("/auth/dev-login", json={"email": "a@example.com"})
    assert response.status_code == 404


def test_google_login_without_configuration_is_rejected(client):
    response = client.post("/auth/google", json={"credential": "x" * 20})
    assert response.status_code == 401
    assert "not configured" in response.json()["detail"]


def test_google_login_validates_the_request_body(client):
    assert client.post("/auth/google", json={"credential": "short"}).status_code == 422


def test_logout_clears_the_session(client):
    assert client.post("/auth/logout").json()["authenticated"] is False
