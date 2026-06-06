import base64
import os

from cryptography.fernet import Fernet, InvalidToken


class SecretCryptoError(ValueError):
    """Raised when a sensitive value cannot be encrypted or decrypted safely."""


def _normalize_fernet_key(raw: str) -> bytes:
    value = raw.strip()
    if not value:
        raise ValueError("ENCRYPTION_KEY vazio.")

    # Fernet key already encoded.
    try:
        decoded = base64.urlsafe_b64decode(value.encode("utf-8"))
        if len(decoded) == 32:
            return value.encode("utf-8")
    except Exception:
        pass

    # 32-char textual key.
    if len(value) == 32:
        return base64.urlsafe_b64encode(value.encode("utf-8"))

    # Hex key.
    try:
        decoded_hex = bytes.fromhex(value)
        if len(decoded_hex) == 32:
            return base64.urlsafe_b64encode(decoded_hex)
    except Exception:
        pass

    raise ValueError("ENCRYPTION_KEY invalida. Use uma chave Fernet ou 32 bytes.")


def _build_fernet() -> Fernet:
    configured = os.getenv("ENCRYPTION_KEY", "").strip()

    if configured:
        return Fernet(_normalize_fernet_key(configured))

    raise RuntimeError("ENCRYPTION_KEY nao configurada para criptografia de tokens sensiveis.")


def encrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    fernet = _build_fernet()
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    fernet = _build_fernet()
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretCryptoError("Falha ao descriptografar valor sensivel.") from exc


def mask_secret(value: str | None, head: int = 6, tail: int = 4) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= head + tail:
        return "*" * len(text)
    return f"{text[:head]}***{text[-tail:]}"


def encrypt_sensitive_value(value: str | None) -> str | None:
    encrypted = encrypt_secret(value)
    return encrypted or None


def decrypt_sensitive_value(value: str | None) -> str | None:
    decrypted = decrypt_secret(value)
    return decrypted or None
