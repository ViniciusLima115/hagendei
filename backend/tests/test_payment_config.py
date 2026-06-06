from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit

import pytest

from app import config
from app.services.payments.providers.mercadopago import MercadoPagoProvider, _format_mercadopago_datetime


PAYMENT_ENV_VARS = [
    "ENCRYPTION_KEY",
    "MERCADOPAGO_CLIENT_ID",
    "MERCADOPAGO_CLIENT_SECRET",
    "MERCADOPAGO_REDIRECT_URI",
    "MERCADOPAGO_WEBHOOK_SECRET",
]


def _clear_payment_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in PAYMENT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_development_allows_startup_without_mercadopago_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    _clear_payment_env(monkeypatch)

    config.validate_critical_config()


def test_production_requires_encryption_key(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    _clear_payment_env(monkeypatch)
    monkeypatch.setenv("MERCADOPAGO_CLIENT_ID", "client-id")
    monkeypatch.setenv("MERCADOPAGO_CLIENT_SECRET", "client-secret")
    monkeypatch.setenv("MERCADOPAGO_REDIRECT_URI", "https://api.example.com/payments/mercadopago/callback")
    monkeypatch.setenv("MERCADOPAGO_WEBHOOK_SECRET", "webhook-secret")

    with pytest.raises(config.CriticalConfigError, match="ENCRYPTION_KEY"):
        config.validate_critical_config()


def test_production_requires_mercadopago_credentials_and_webhook_secret(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    _clear_payment_env(monkeypatch)
    monkeypatch.setenv("ENCRYPTION_KEY", "12345678901234567890123456789012")

    with pytest.raises(config.CriticalConfigError) as exc_info:
        config.validate_critical_config()

    message = str(exc_info.value)
    assert "MERCADOPAGO_CLIENT_ID" in message
    assert "MERCADOPAGO_CLIENT_SECRET" in message
    assert "MERCADOPAGO_REDIRECT_URI" in message
    assert "MERCADOPAGO_WEBHOOK_SECRET" in message


def test_oauth_connect_url_requires_mercadopago_client_config_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    _clear_payment_env(monkeypatch)

    provider = MercadoPagoProvider()

    with pytest.raises(ValueError, match="MERCADOPAGO_CLIENT_ID"):
        provider.build_connect_url(state="state-test")


def test_oauth_connect_url_contains_required_mercadopago_params(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    _clear_payment_env(monkeypatch)
    monkeypatch.setenv("MERCADOPAGO_CLIENT_ID", "client-id")
    monkeypatch.setenv("MERCADOPAGO_REDIRECT_URI", "https://api.example.com/payments/mercadopago/callback")

    provider = MercadoPagoProvider()
    url = provider.build_connect_url(state="state-test")
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert query["client_id"] == ["client-id"]
    assert query["response_type"] == ["code"]
    assert query["platform_id"] == ["mp"]
    assert query["redirect_uri"] == ["https://api.example.com/payments/mercadopago/callback"]
    assert query["state"] == ["state-test"]


def test_oauth_connect_url_includes_pkce_params_when_provided(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    _clear_payment_env(monkeypatch)
    monkeypatch.setenv("MERCADOPAGO_CLIENT_ID", "client-id")
    monkeypatch.setenv("MERCADOPAGO_REDIRECT_URI", "https://api.example.com/payments/mercadopago/callback")

    provider = MercadoPagoProvider()
    url = provider.build_connect_url(state="state-test", code_challenge="challenge-test")
    query = parse_qs(urlsplit(url).query)

    assert query["code_challenge"] == ["challenge-test"]
    assert query["code_challenge_method"] == ["S256"]


def test_backend_url_prefers_backend_url_over_legacy_alias(monkeypatch):
    monkeypatch.setenv("BACKEND_URL", "https://api.example.com/")
    monkeypatch.setenv("BACKEND_PUBLIC_BASE_URL", "https://legacy.example.com")

    assert config.get_backend_url() == "https://api.example.com"


def test_mercadopago_datetime_treats_naive_values_as_utc():
    value = datetime(2026, 6, 6, 12, 30, 0)

    assert _format_mercadopago_datetime(value) == "2026-06-06T12:30:00+00:00"


def test_mercadopago_checkout_sends_ten_minute_pix_expiration(monkeypatch):
    captured_payload: dict = {}

    class Response:
        status_code = 201
        headers: dict = {}

        @staticmethod
        def json():
            return {
                "id": "preference-test",
                "init_point": "https://www.mercadopago.com.br/checkout/test",
            }

    def fake_post(*_args, **kwargs):
        captured_payload.update(kwargs["json"])
        return Response()

    monkeypatch.setattr("app.services.payments.providers.mercadopago.requests.post", fake_post)
    provider = MercadoPagoProvider()
    expires_at = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=10)

    provider.create_checkout(
        access_token="test-token",
        external_reference="booking:test",
        title="Agendamento",
        description="Pagamento",
        amount=10,
        payer_email="cliente@example.com",
        payer_name="Cliente",
        payer_phone="11999999999",
        metadata={"appointment_id": 1},
        notification_url="https://api.example.com/webhooks/mercadopago",
        back_urls={"success": "https://app.example.com/sucesso"},
        expires_at=expires_at,
    )

    assert captured_payload["date_of_expiration"] == expires_at.isoformat()
    assert captured_payload["expires"] is True
    assert captured_payload["expiration_date_to"] == expires_at.isoformat()
    start = datetime.fromisoformat(captured_payload["expiration_date_from"])
    end = datetime.fromisoformat(captured_payload["expiration_date_to"])
    assert timedelta(minutes=9, seconds=50) <= end - start <= timedelta(minutes=10, seconds=10)
