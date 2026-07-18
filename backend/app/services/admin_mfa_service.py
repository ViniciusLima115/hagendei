from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import secrets
from datetime import timedelta

import pyotp
import qrcode
from sqlalchemy.orm import Session

from app.models.admin_mfa import AdminMfaChallenge, AdminMfaSetting
from app.security import hash_senha, verificar_senha
from app.services.payments.crypto import decrypt_sensitive_value, encrypt_sensitive_value
from app.time_utils import utcnow_naive

MFA_CHALLENGE_TTL_SECONDS = 300
MFA_ISSUER = os.getenv("MFA_ISSUER", "Hagendei").strip()[:64] or "Hagendei"
_OTP_CODE = re.compile(r"^\d{6}$")


def _username(value: str) -> str:
    return value.strip().lower()[:120]


def _hash_challenge(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def get_or_create_setting(db: Session, admin_username: str) -> AdminMfaSetting:
    username = _username(admin_username)
    setting = db.get(AdminMfaSetting, username)
    if setting:
        return setting
    setting = AdminMfaSetting(admin_username=username)
    db.add(setting)
    db.commit()
    db.refresh(setting)
    return setting


def create_login_challenge(db: Session, admin_username: str) -> str:
    now = utcnow_naive()
    db.query(AdminMfaChallenge).filter(AdminMfaChallenge.expires_at < now).delete(synchronize_session=False)
    challenge = secrets.token_urlsafe(32)
    db.add(
        AdminMfaChallenge(
            challenge_hash=_hash_challenge(challenge),
            admin_username=_username(admin_username),
            purpose="login",
            expires_at=now + timedelta(seconds=MFA_CHALLENGE_TTL_SECONDS),
        )
    )
    db.commit()
    return challenge


def consume_login_challenge(db: Session, admin_username: str, challenge: str) -> bool:
    if not challenge or len(challenge) > 200:
        return False
    row = db.get(AdminMfaChallenge, _hash_challenge(challenge))
    now = utcnow_naive()
    if (
        not row
        or row.admin_username != _username(admin_username)
        or row.purpose != "login"
        or row.used_at is not None
        or row.expires_at < now
    ):
        return False
    row.used_at = now
    db.commit()
    return True


def get_login_challenge_username(db: Session, challenge: str) -> str | None:
    if not challenge or len(challenge) > 200:
        return None
    row = db.get(AdminMfaChallenge, _hash_challenge(challenge))
    now = utcnow_naive()
    if not row or row.purpose != "login" or row.used_at is not None or row.expires_at < now:
        return None
    return row.admin_username


def create_setup_payload(db: Session, admin_username: str) -> dict[str, str]:
    setting = get_or_create_setting(db, admin_username)
    if setting.enabled:
        raise ValueError("MFA ja esta ativo para este administrador.")
    secret = _get_pending_secret(setting) if setting.pending_secret_encrypted else None
    if not secret:
        secret = pyotp.random_base32()
        setting.pending_secret_encrypted = encrypt_sensitive_value(secret, purpose="admin-mfa")
        db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=_username(admin_username), issuer_name=MFA_ISSUER)
    image = qrcode.make(uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {
        "manual_key": secret,
        "otpauth_uri": uri,
        "qr_code_data_url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii"),
    }


def _get_pending_secret(setting: AdminMfaSetting) -> str | None:
    return decrypt_sensitive_value(setting.pending_secret_encrypted, purpose="admin-mfa") if setting.pending_secret_encrypted else None


def _get_active_secret(setting: AdminMfaSetting) -> str | None:
    return decrypt_sensitive_value(setting.secret_encrypted, purpose="admin-mfa") if setting.secret_encrypted else None


def verify_totp(secret: str | None, code: str) -> bool:
    normalized = (code or "").replace(" ", "")
    return bool(secret and _OTP_CODE.fullmatch(normalized) and pyotp.TOTP(secret).verify(normalized, valid_window=1))


def _generate_recovery_codes() -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ["".join(secrets.choice(alphabet) for _ in range(4)) + "-" + "".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(10)]


def enable_mfa(db: Session, admin_username: str, code: str) -> list[str]:
    setting = get_or_create_setting(db, admin_username)
    secret = _get_pending_secret(setting)
    if not verify_totp(secret, code):
        raise ValueError("Codigo do autenticador invalido ou expirado.")
    recovery_codes = _generate_recovery_codes()
    setting.secret_encrypted = setting.pending_secret_encrypted
    setting.pending_secret_encrypted = None
    setting.recovery_code_hashes = [hash_senha(item) for item in recovery_codes]
    setting.enabled = True
    setting.enabled_at = utcnow_naive()
    setting.session_version = int(setting.session_version or 0) + 1
    db.commit()
    return recovery_codes


def verify_active_factor(setting: AdminMfaSetting, code: str) -> tuple[bool, bool]:
    secret = _get_active_secret(setting)
    if verify_totp(secret, code):
        return True, False
    normalized = (code or "").strip().upper().replace(" ", "")
    hashes = list(setting.recovery_code_hashes or [])
    for index, stored_hash in enumerate(hashes):
        if verificar_senha(normalized, stored_hash):
            hashes.pop(index)
            setting.recovery_code_hashes = hashes
            return True, True
    return False, False


def disable_mfa(db: Session, admin_username: str) -> None:
    setting = get_or_create_setting(db, admin_username)
    setting.enabled = False
    setting.secret_encrypted = None
    setting.pending_secret_encrypted = None
    setting.recovery_code_hashes = None
    setting.enabled_at = None
    setting.session_version = int(setting.session_version or 0) + 1
    db.commit()
