from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.admin_audit_log import AdminAuditLog


SENSITIVE_METADATA_KEYS = {
    "access_token",
    "client_secret",
    "webhook_secret",
    "credentials_encrypted",
    "authorization",
    "password",
    "senha",
    "card_number",
    "card",
    "cvv",
    "cvc",
    "security_code",
    "pan",
}
SENSITIVE_KEY_FRAGMENTS = ("token", "secret", "credential", "password", "senha", "card", "cvv", "cvc")
ALLOWED_AUDIT_ACTIONS = {
    "payment_credentials_created",
    "payment_credentials_updated",
    "payment_credentials_validated",
    "payment_credentials_disabled",
    "payment_checkout_test_created",
    "payment_credentials_validation_failed",
    "tenant_account_created",
    "tenant_account_updated",
    "tenant_account_disabled",
    "tenant_password_changed",
    "admin_mfa_enabled",
    "admin_mfa_disabled",
    "admin_mfa_login_verified",
    "admin_mfa_recovery_code_used",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_key(key: object) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(key).strip().lower())


def _is_sensitive_key(key: object) -> bool:
    normalized = _normalize_key(key)
    return normalized in SENSITIVE_METADATA_KEYS or any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS)


def _sanitize_metadata(value: Any, *, depth: int = 0) -> Any:
    if depth > 3:
        return None
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", value).strip()
        return cleaned[:500]
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = _normalize_key(raw_key)
            if not key or _is_sensitive_key(key):
                continue
            sanitized_value = _sanitize_metadata(raw_value, depth=depth + 1)
            if sanitized_value is not None:
                sanitized[key[:80]] = sanitized_value
        return sanitized
    if isinstance(value, (list, tuple)):
        items = [_sanitize_metadata(item, depth=depth + 1) for item in value[:20]]
        return [item for item in items if item is not None]
    return str(value)[:200]


def sanitize_audit_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    sanitized = _sanitize_metadata(metadata or {})
    return sanitized if isinstance(sanitized, dict) else {}


def create_admin_audit_log(
    db: Session,
    *,
    admin_user_id: str | None,
    establishment_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | str | None,
    ip_address: str | None,
    user_agent: str | None,
    metadata: dict[str, Any] | None = None,
) -> AdminAuditLog:
    if action not in ALLOWED_AUDIT_ACTIONS:
        raise ValueError("Acao de auditoria administrativa invalida.")

    log = AdminAuditLog(
        admin_user_id=(admin_user_id or "unknown")[:120],
        establishment_id=establishment_id,
        action=action,
        entity_type=entity_type[:80],
        entity_id=str(entity_id)[:120] if entity_id is not None else None,
        ip_address=(ip_address or "")[:80] or None,
        user_agent=(user_agent or "")[:500] or None,
        audit_metadata=sanitize_audit_metadata(metadata),
        created_at=_utcnow(),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
