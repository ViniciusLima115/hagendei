import pytest

from app.services.payments.crypto import (
    SecretCryptoError,
    decrypt_secret,
    encrypt_secret,
    mask_secret,
)


def test_encrypt_decrypt_secret_roundtrip(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ENCRYPTION_KEY", "12345678901234567890123456789012")

    token = "APP_USR-secret-access-token-123"
    encrypted = encrypt_secret(token)

    assert encrypted
    assert encrypted != token
    assert token not in encrypted
    assert decrypt_secret(encrypted) == token


def test_mask_secret_never_returns_full_value():
    token = "abc123456789xyz"
    masked = mask_secret(token, head=3, tail=3)

    assert masked == "abc***xyz"
    assert masked != token
    assert "123456789" not in masked


def test_empty_secret_values_are_safe(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ENCRYPTION_KEY", "12345678901234567890123456789012")

    assert encrypt_secret("") == ""
    assert decrypt_secret("") == ""
    assert mask_secret("") == ""
    assert encrypt_secret(None) == ""
    assert decrypt_secret(None) == ""
    assert mask_secret(None) == ""


def test_decrypt_invalid_secret_raises_controlled_error(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ENCRYPTION_KEY", "12345678901234567890123456789012")

    with pytest.raises(SecretCryptoError, match="Falha ao descriptografar"):
        decrypt_secret("valor-nao-criptografado")


def test_encrypt_secret_requires_encryption_key_even_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        encrypt_secret("token-development")


def test_encrypt_secret_requires_encryption_key_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

    with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
        encrypt_secret("token-producao")
