import base64
<<<<<<< HEAD
import hashlib
import hmac
import json
=======
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
import os
import re

from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENVELOPE_VERSION = "v2"
KEY_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


<<<<<<< HEAD
def _decode_key(raw: str) -> bytes:
=======
class SecretCryptoError(ValueError):
    """Raised when a sensitive value cannot be encrypted or decrypted safely."""


def _normalize_fernet_key(raw: str) -> bytes:
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
    value = raw.strip()
    if not value:
        raise ValueError("Chave de criptografia vazia.")
    try:
        decoded = base64.urlsafe_b64decode(value.encode("ascii"))
        if len(decoded) == 32:
            return decoded
    except Exception:
        pass
    if len(value.encode("utf-8")) == 32:
        return value.encode("utf-8")
    try:
        decoded_hex = bytes.fromhex(value)
        if len(decoded_hex) == 32:
            return decoded_hex
    except ValueError:
        pass
    raise ValueError("Chave de criptografia invalida. Use exatamente 32 bytes.")


<<<<<<< HEAD
def _current_key_id() -> str:
    key_id = os.getenv("ENCRYPTION_KEY_ID", "primary").strip()
    if not KEY_ID_PATTERN.fullmatch(key_id):
        raise ValueError("ENCRYPTION_KEY_ID invalido.")
    return key_id


def _load_keyring() -> dict[str, bytes]:
    keys: dict[str, bytes] = {}
    current = os.getenv("ENCRYPTION_KEY", "").strip()
    if current:
        keys[_current_key_id()] = _decode_key(current)
=======
def _build_fernet() -> Fernet:
    configured = os.getenv("ENCRYPTION_KEY", "").strip()
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478

    raw_keyring = os.getenv("ENCRYPTION_KEYRING", "").strip()
    if raw_keyring:
        try:
            parsed = json.loads(raw_keyring)
        except json.JSONDecodeError as exc:
            raise ValueError("ENCRYPTION_KEYRING deve ser um objeto JSON.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("ENCRYPTION_KEYRING deve ser um objeto JSON.")
        for key_id, raw_key in parsed.items():
            if not isinstance(key_id, str) or not KEY_ID_PATTERN.fullmatch(key_id):
                raise ValueError("ENCRYPTION_KEYRING contem identificador invalido.")
            if not isinstance(raw_key, str):
                raise ValueError("ENCRYPTION_KEYRING contem chave invalida.")
            keys.setdefault(key_id, _decode_key(raw_key))

<<<<<<< HEAD
    if not keys:
        app_env = os.getenv("APP_ENV", "development").strip().lower()
        if app_env in {"prod", "production"}:
            raise RuntimeError("ENCRYPTION_KEY e obrigatoria em producao.")
        raise ValueError("ENCRYPTION_KEY nao configurada.")
    return keys


def _aad(key_id: str) -> bytes:
    return f"hagendei:payment-credentials:{key_id}".encode("ascii")


def _legacy_fernets() -> list[Fernet]:
    keyring = _load_keyring()
    current_id = _current_key_id()
    ordered_keys = [keyring[current_id]] if current_id in keyring else []
    ordered_keys.extend(key for key_id, key in keyring.items() if key_id != current_id)
    return [Fernet(base64.urlsafe_b64encode(key)) for key in ordered_keys]


def ensure_encryption_key_for_production() -> None:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env not in {"prod", "production"}:
        return
    _load_keyring()
    pepper = os.getenv("PAYMENT_CREDENTIALS_PEPPER", "").strip()
    if len(pepper.encode("utf-8")) < 32:
        raise RuntimeError("PAYMENT_CREDENTIALS_PEPPER deve ter ao menos 32 bytes em producao.")
=======
    raise RuntimeError("ENCRYPTION_KEY nao configurada para criptografia de tokens sensiveis.")
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478


def encrypt_secret(value: str | None) -> str:
    if not value:
<<<<<<< HEAD
        return None
    key_id = _current_key_id()
    key = _load_keyring().get(key_id)
    if key is None:
        raise ValueError("Chave de criptografia atual nao encontrada no keyring.")
    nonce = os.urandom(12)
    ciphertext_and_tag = AESGCM(key).encrypt(nonce, value.encode("utf-8"), _aad(key_id))
    encoded = base64.urlsafe_b64encode(nonce + ciphertext_and_tag).decode("ascii")
    return f"{ENVELOPE_VERSION}:{key_id}:{encoded}"
=======
        return ""
    fernet = _build_fernet()
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478


def decrypt_secret(value: str | None) -> str:
    if not value:
<<<<<<< HEAD
        return None
    if value.startswith(f"{ENVELOPE_VERSION}:"):
        try:
            _, key_id, encoded = value.split(":", 2)
            key = _load_keyring().get(key_id)
            if key is None:
                raise ValueError("Chave de criptografia nao encontrada no keyring.")
            raw = base64.urlsafe_b64decode(encoded.encode("ascii"))
            if len(raw) < 29:
                raise ValueError("Envelope criptografado invalido.")
            plaintext = AESGCM(key).decrypt(raw[:12], raw[12:], _aad(key_id))
            return plaintext.decode("utf-8")
        except (InvalidTag, UnicodeDecodeError, ValueError) as exc:
            raise ValueError("Falha ao descriptografar valor sensivel.") from exc

    for cipher in _legacy_fernets():
        try:
            return cipher.decrypt(value.encode("utf-8")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError):
            continue
    raise ValueError("Falha ao descriptografar valor sensivel.")


def encrypt_json_payload(payload: dict | None) -> str:
    serialized = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    encrypted = encrypt_sensitive_value(serialized)
    if not encrypted:
        raise ValueError("Falha ao criptografar payload sensivel.")
    return encrypted


def decrypt_json_payload(value: str | None) -> dict:
    if not value:
        return {}
    decrypted = decrypt_sensitive_value(value)
    try:
        data = json.loads(decrypted or "")
    except json.JSONDecodeError as exc:
        raise ValueError("Payload sensivel criptografado invalido.") from exc
    if not isinstance(data, dict):
        raise ValueError("Payload sensivel criptografado deve ser um objeto JSON.")
    return data
=======
        return ""
    fernet = _build_fernet()
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise SecretCryptoError("Falha ao descriptografar valor sensivel.") from exc
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478


def encrypt_secret(value: str | dict | None) -> str | None:
    return encrypt_json_payload(value) if isinstance(value, dict) else encrypt_sensitive_value(value)


def decrypt_secret(value: str | None) -> str | None:
    return decrypt_sensitive_value(value)


def credentials_fingerprint(payload: dict | None) -> str | None:
    data = {
        key: str(value).strip()
        for key, value in (payload or {}).items()
        if value is not None and str(value).strip()
    }
    if not data:
        return None
    if data.get("access_token"):
        data = {"access_token": data["access_token"]}

    pepper = os.getenv("PAYMENT_CREDENTIALS_PEPPER", "").strip()
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if app_env in {"prod", "production"} and len(pepper.encode("utf-8")) < 32:
        raise RuntimeError("PAYMENT_CREDENTIALS_PEPPER deve ter ao menos 32 bytes em producao.")
    if not pepper:
        pepper = "development-only-fingerprint-pepper"

    canonical = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hmac.new(pepper.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def create_credential_fingerprint(value: str | dict | None) -> str | None:
    if isinstance(value, str):
        return credentials_fingerprint({"access_token": value})
    return credentials_fingerprint(value)


def mask_secret(value: str | None, head: int = 2, tail: int = 2) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= max(8, head + tail):
        return "*" * len(text)
    return f"{text[:head]}***{text[-tail:]}"


<<<<<<< HEAD
encryptSecret = encrypt_secret
decryptSecret = decrypt_secret
maskSecret = mask_secret
createCredentialFingerprint = create_credential_fingerprint
=======
def encrypt_sensitive_value(value: str | None) -> str | None:
    encrypted = encrypt_secret(value)
    return encrypted or None


def decrypt_sensitive_value(value: str | None) -> str | None:
    decrypted = decrypt_secret(value)
    return decrypted or None
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
