import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment_account import PaymentAccount
from app.models.payment_integration import PaymentIntegration
from app.repositories import notificacao_repository as notificacao_repo
from app.services.payments.constants import PAYMENT_PROVIDER_MERCADO_PAGO
from app.services.payments.crypto import (
    credentials_fingerprint,
    decrypt_json_payload,
    decrypt_sensitive_value,
    encrypt_json_payload,
    encrypt_sensitive_value,
    mask_secret,
)
from app.services.payments.provider_factory import get_payment_provider


logger = logging.getLogger(__name__)

ALLOWED_PROVIDERS = {PAYMENT_PROVIDER_MERCADO_PAGO, "picpay"}
ALLOWED_ENVIRONMENTS = {"sandbox", "production"}
ALLOWED_STATUSES = {"active", "inactive", "error", "pending_validation", "disconnected"}
ACTIVE_STATUSES = {"active"}
CREDENTIAL_FIELDS = ("public_key", "access_token", "client_id", "client_secret", "webhook_secret", "notes")
CLEARABLE_CREDENTIAL_FIELDS = {"public_key", "client_id", "client_secret", "webhook_secret", "notes"}
CREDENTIAL_FIELD_LIMITS = {
    "public_key": 300,
    "access_token": 700,
    "client_id": 180,
    "client_secret": 700,
    "webhook_secret": 700,
    "notes": 1000,
}
CREDENTIAL_FIELD_MIN_LENGTHS = {
    "public_key": 8,
    "access_token": 8,
    "client_id": 4,
    "client_secret": 8,
    "webhook_secret": 8,
}


@dataclass(frozen=True)
class ActivePaymentCredentials:
    provider: str
    access_token: str
    checkout_hold_minutes: int
    payment_integration_id: int | None = None
    payment_account_id: int | None = None
    environment: str | None = None
    webhook_secret: str | None = None
    external_account_id: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_provider(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized == "mercado_pago":
        return PAYMENT_PROVIDER_MERCADO_PAGO
    return normalized


def normalize_environment(environment: str | None) -> str:
    normalized = (environment or "production").strip().lower()
    if normalized not in ALLOWED_ENVIRONMENTS:
        raise ValueError("Ambiente de pagamento invalido. Use sandbox ou production.")
    return normalized


def normalize_status(status: str | None) -> str:
    normalized = (status or "pending_validation").strip().lower()
    if normalized == "revoked":
        normalized = "disconnected"
    if normalized not in ALLOWED_STATUSES:
        raise ValueError("Status de integracao de pagamento invalido.")
    return normalized


def _safe_validation_error(message: str | None) -> str | None:
    if not message:
        return None
    return str(message).strip()[:240]


def _get_default_environment() -> str:
    configured = (
        os.getenv("PAYMENT_DEFAULT_ENVIRONMENT", "").strip()
        or os.getenv("MERCADOPAGO_DEFAULT_ENVIRONMENT", "").strip()
        or "production"
    )
    try:
        return normalize_environment(configured)
    except ValueError:
        return "production"


def _clean_optional(value: str | None, *, field: str | None = None) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if field == "notes":
        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", cleaned)
    if field:
        limit = CREDENTIAL_FIELD_LIMITS.get(field)
        if limit and len(cleaned) > limit:
            raise ValueError(f"{field} excede o tamanho maximo permitido.")
        min_length = CREDENTIAL_FIELD_MIN_LENGTHS.get(field)
        if min_length and len(cleaned) < min_length:
            raise ValueError(f"{field} deve ter pelo menos {min_length} caracteres.")
    return cleaned


def _merge_payload(existing: dict, incoming: dict[str, str | None], allowed_fields: tuple[str, ...]) -> dict:
    merged = dict(existing or {})
    for field in allowed_fields:
        if field not in incoming:
            continue
        cleaned = _clean_optional(incoming[field], field=field)
        if cleaned is not None:
            merged[field] = cleaned
    return {key: value for key, value in merged.items() if value is not None and str(value).strip()}


def _clear_payload_fields(payload: dict, clear_fields: set[str] | None) -> dict:
    cleaned = dict(payload or {})
    for field in clear_fields or set():
        if field in CLEARABLE_CREDENTIAL_FIELDS:
            cleaned.pop(field, None)
    return cleaned


def _load_integration_credentials(integration: PaymentIntegration) -> dict:
    credentials = decrypt_json_payload(integration.credentials_encrypted)

    # Compatibilidade com registros criados antes de public_key/notes entrarem
    # no mesmo JSON criptografado de credentials_encrypted.
    legacy_public_metadata = decrypt_json_payload(integration.public_metadata_encrypted)
    if legacy_public_metadata.get("public_key") and not credentials.get("public_key"):
        credentials["public_key"] = legacy_public_metadata["public_key"]
    if integration.internal_notes and not credentials.get("notes"):
        credentials["notes"] = integration.internal_notes
    return credentials


def get_payment_integration_credentials(integration: PaymentIntegration) -> dict:
    return _load_integration_credentials(integration)


def get_payment_integration(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
    environment: str | None = "production",
) -> PaymentIntegration | None:
    normalized_provider = normalize_provider(provider)
    normalized_environment = normalize_environment(environment)
    return (
        db.query(PaymentIntegration)
        .filter(
            PaymentIntegration.establishment_id == establishment_id,
            PaymentIntegration.provider == normalized_provider,
            PaymentIntegration.environment == normalized_environment,
        )
        .first()
    )


def get_preferred_payment_integration(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> PaymentIntegration | None:
    normalized_provider = normalize_provider(provider)
    preferred_environment = _get_default_environment()
    rows = (
        db.query(PaymentIntegration)
        .filter(
            PaymentIntegration.establishment_id == establishment_id,
            PaymentIntegration.provider == normalized_provider,
        )
        .all()
    )
    if not rows:
        return None

    def score(row: PaymentIntegration) -> tuple[int, int, datetime]:
        is_active = 1 if row.status == "active" else 0
        is_preferred_env = 1 if row.environment == preferred_environment else 0
        updated = row.updated_at or row.created_at or datetime.min
        return (is_active, is_preferred_env, updated)

    return sorted(rows, key=score, reverse=True)[0]


def _assert_fingerprint_available(
    db: Session,
    *,
    provider: str,
    environment: str,
    fingerprint: str | None,
    integration_id: int | None,
    establishment_id: int,
) -> None:
    if not fingerprint:
        return
    existing = (
        db.query(PaymentIntegration)
        .filter(
            PaymentIntegration.provider == provider,
            PaymentIntegration.environment == environment,
            PaymentIntegration.credentials_fingerprint == fingerprint,
        )
        .first()
    )
    if existing and existing.id != integration_id and existing.establishment_id != establishment_id:
        raise ValueError("Esta credencial Mercado Pago ja esta vinculada a outro estabelecimento.")


def _validate_credentials_for_status(credentials: dict, status: str) -> tuple[str, str | None, datetime | None]:
    access_token = _clean_optional(credentials.get("access_token"))
    if not access_token:
        return "invalid", "access_token e obrigatorio para salvar credenciais Mercado Pago.", None
    if status == "active":
        return "not_validated", None, None
    if status == "pending_validation":
        return "not_validated", None, None
    return "not_validated", None, None


def _notify_integration_attention(
    db: Session,
    *,
    establishment_id: int,
    status: str,
) -> None:
    if status not in {"inactive", "error", "disconnected"}:
        return
    try:
        notificacao_repo.criar(
            db,
            estabelecimento_id=establishment_id,
            tipo="conta_pagamento_desconectada",
            titulo="Integracao Mercado Pago requer atencao",
            corpo="A administracao alterou o status da integracao de pagamento deste estabelecimento.",
        )
    except Exception:
        logger.exception(
            "Falha ao criar notificacao de integracao de pagamento (establishment_id=%s)",
            establishment_id,
        )


def _sync_legacy_payment_account(
    db: Session,
    *,
    integration: PaymentIntegration,
    credentials: dict,
    admin_sub: str | None,
) -> None:
    if integration.provider != PAYMENT_PROVIDER_MERCADO_PAGO:
        return

    account = (
        db.query(PaymentAccount)
        .filter(
            PaymentAccount.establishment_id == integration.establishment_id,
            PaymentAccount.provider == integration.provider,
        )
        .first()
    )
    if account is None:
        account = PaymentAccount(
            establishment_id=integration.establishment_id,
            provider=integration.provider,
            access_token_encrypted="",
            status="inactive",
            created_by_admin_id=integration.created_by_admin_id or admin_sub,
        )
        db.add(account)

    account.account_name = integration.account_name
    account.client_id_encrypted = encrypt_sensitive_value(credentials.get("client_id"))
    account.client_secret_encrypted = encrypt_sensitive_value(credentials.get("client_secret"))
    account.access_token_encrypted = encrypt_sensitive_value(credentials.get("access_token")) or ""
    account.public_key_encrypted = encrypt_sensitive_value(credentials.get("public_key"))
    account.internal_notes = None
    account.checkout_hold_minutes = integration.checkout_hold_minutes
    if integration.status == "active" and integration.validation_status != "valid":
        account.status = "inactive"
    else:
        account.status = "revoked" if integration.status == "disconnected" else integration.status
    account.updated_by_admin_id = admin_sub
    account.updated_at = _utcnow()
    if integration.status == "active":
        account.last_sync_at = integration.last_validated_at or _utcnow()


def upsert_admin_payment_integration(
    db: Session,
    *,
    establishment_id: int,
    admin_sub: str | None,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
    environment: str | None = "production",
    account_name: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    access_token: str | None = None,
    public_key: str | None = None,
    webhook_secret: str | None = None,
    status: str = "active",
    internal_notes: str | None = None,
    checkout_hold_minutes: int = 10,
    clear_fields: set[str] | None = None,
) -> PaymentIntegration:
    normalized_provider = normalize_provider(provider)
    if normalized_provider not in ALLOWED_PROVIDERS:
        raise ValueError("Provider de pagamento nao suportado.")
    if normalized_provider != PAYMENT_PROVIDER_MERCADO_PAGO:
        raise ValueError("Provider de pagamento ainda nao implementado.")

    normalized_environment = normalize_environment(environment)
    normalized_status = normalize_status(status)
    if checkout_hold_minutes < 5 or checkout_hold_minutes > 60:
        raise ValueError("checkout_hold_minutes deve ficar entre 5 e 60 minutos.")

    integration = get_payment_integration(
        db,
        establishment_id=establishment_id,
        provider=normalized_provider,
        environment=normalized_environment,
    )
    is_new = integration is None
    if integration is None:
        integration = PaymentIntegration(
            establishment_id=establishment_id,
            provider=normalized_provider,
            environment=normalized_environment,
            status="pending_validation",
            credentials_encrypted=encrypt_json_payload({}),
            public_metadata_encrypted=encrypt_json_payload({}),
            created_by_admin_id=admin_sub,
        )
        db.add(integration)
        db.flush()

    existing_credentials = _load_integration_credentials(integration)
    previous_fingerprint = integration.credentials_fingerprint
    previous_validation_status = integration.validation_status
    previous_validated_at = integration.last_validated_at
    existing_credentials = _clear_payload_fields(existing_credentials, clear_fields)
    credentials = _merge_payload(
        existing_credentials,
        {
            "public_key": public_key,
            "access_token": access_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "webhook_secret": webhook_secret,
            "notes": internal_notes,
        },
        CREDENTIAL_FIELDS,
    )

    validation_status, validation_error, validated_at = _validate_credentials_for_status(
        credentials,
        normalized_status,
    )
    if validation_error:
        integration.validation_status = validation_status
        integration.validation_error = _safe_validation_error(validation_error)
        raise ValueError(validation_error)

    fingerprint = credentials_fingerprint(credentials)
    if (
        normalized_status == "active"
        and not is_new
        and fingerprint == previous_fingerprint
        and previous_validation_status == "valid"
    ):
        validation_status = "valid"
        validated_at = previous_validated_at
    _assert_fingerprint_available(
        db,
        provider=normalized_provider,
        environment=normalized_environment,
        fingerprint=fingerprint,
        integration_id=integration.id,
        establishment_id=establishment_id,
    )

    now = _utcnow()
    previous_status = integration.status
    integration.account_name = _clean_optional(account_name)
    integration.internal_notes = None
    integration.checkout_hold_minutes = checkout_hold_minutes
    integration.credentials_encrypted = encrypt_json_payload(credentials)
    integration.credentials_fingerprint = fingerprint
    integration.public_metadata_encrypted = encrypt_json_payload({})
    integration.status = normalized_status
    integration.validation_status = validation_status
    integration.validation_error = None
    integration.last_validated_at = validated_at
    integration.updated_by_admin_id = admin_sub
    integration.updated_at = now
    if normalized_status == "active" and (is_new or previous_status != "active" or not integration.connected_at):
        integration.connected_at = now
        integration.disconnected_at = None
    if normalized_status == "disconnected":
        integration.disconnected_at = now

    _sync_legacy_payment_account(
        db,
        integration=integration,
        credentials=credentials,
        admin_sub=admin_sub,
    )

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Ja existe uma integracao de pagamento conflitante para estes dados.") from exc

    db.refresh(integration)

    logger.info(
        "Integracao de pagamento atualizada (provider=%s, environment=%s, establishment_id=%s, status=%s, admin=%s)",
        integration.provider,
        integration.environment,
        integration.establishment_id,
        integration.status,
        mask_secret(admin_sub),
    )
    return integration


def validate_admin_payment_integration(
    db: Session,
    *,
    integration: PaymentIntegration,
    admin_sub: str | None,
) -> tuple[bool, str, str, datetime]:
    credentials = _load_integration_credentials(integration)
    access_token = _clean_optional(credentials.get("access_token"))
    if not access_token:
        raise ValueError("Integracao Mercado Pago sem access_token.")

    provider_impl = get_payment_provider(integration.provider)
    validator = getattr(provider_impl, "validate_access_token", None)
    if not callable(validator):
        raise ValueError("Provider de pagamento nao suporta validacao administrativa.")

    now = _utcnow()
    try:
        result = validator(access_token=access_token)
    except Exception:
        logger.exception(
            "Falha segura ao validar credencial Mercado Pago (establishment_id=%s, integration_id=%s)",
            integration.establishment_id,
            integration.id,
        )
        integration.validation_status = "error"
        integration.validation_error = "Nao foi possivel validar a credencial no momento."
        integration.last_validated_at = now
        integration.updated_by_admin_id = admin_sub
        integration.updated_at = now
        db.commit()
        db.refresh(integration)
        return False, "error", integration.validation_error, now

    valid = bool(result.get("valid"))
    message = str(result.get("message") or ("Credencial valida." if valid else "Credencial invalida."))
    integration.validation_status = "valid" if valid else "invalid"
    external_user_id = _clean_optional(result.get("external_user_id"))
    if valid and external_user_id:
        credentials["external_user_id"] = external_user_id
        integration.credentials_encrypted = encrypt_json_payload(credentials)
    integration.validation_error = None if valid else _safe_validation_error(message)
    integration.last_validated_at = now
    integration.updated_by_admin_id = admin_sub
    integration.updated_at = now
    _sync_legacy_payment_account(
        db,
        integration=integration,
        credentials=credentials,
        admin_sub=admin_sub,
    )
    db.commit()
    db.refresh(integration)
    return valid, integration.validation_status, message[:240], now


def create_admin_payment_integration_test_checkout(
    db: Session,
    *,
    integration: PaymentIntegration,
    admin_sub: str | None,
    confirm_production: bool = False,
) -> dict:
    if integration.environment == "production" and not confirm_production:
        raise ValueError("Checkout de teste em production exige confirm_production=true.")

    credentials = _load_integration_credentials(integration)
    access_token = _clean_optional(credentials.get("access_token"))
    if not access_token:
        raise ValueError("Integracao Mercado Pago sem access_token.")

    provider_impl = get_payment_provider(integration.provider)
    external_reference = f"admin-test:{integration.establishment_id}:{uuid4()}"
    backend_base = (
        os.getenv("BACKEND_PUBLIC_BASE_URL", "").strip()
        or os.getenv("BACKEND_URL", "").strip()
        or "http://127.0.0.1:8000"
    ).rstrip("/")
    frontend_base = (
        os.getenv("BOOKING_PUBLIC_BASE_URL", "").strip()
        or os.getenv("FRONTEND_URL", "").strip()
        or "http://localhost:3000"
    ).rstrip("/")
    return_query = urlencode({"external_reference": external_reference})
    checkout = provider_impl.create_checkout(
        access_token=access_token,
        idempotency_key=external_reference,
        external_reference=external_reference,
        title="Teste de integracao Mercado Pago",
        description="Preferencia de teste administrativo sem agendamento vinculado.",
        amount=1.0,
        payer_email=None,
        payer_name=None,
        payer_phone=None,
        metadata={
            "test": True,
            "admin": True,
            "establishment_id": integration.establishment_id,
            "payment_integration_id": integration.id,
            "environment": integration.environment,
        },
        notification_url=f"{backend_base}/webhooks/mercadopago?admin_test=true",
        return_urls={
            "success": f"{frontend_base}/agendamento/pagamento/sucesso?{return_query}",
            "pending": f"{frontend_base}/agendamento/pagamento/pendente?{return_query}",
            "failure": f"{frontend_base}/agendamento/pagamento/falha?{return_query}",
        },
        expires_at=None,
    )
    integration.updated_by_admin_id = admin_sub
    integration.updated_at = _utcnow()
    db.commit()
    db.refresh(integration)
    return checkout


def update_admin_payment_integration_status(
    db: Session,
    *,
    establishment_id: int,
    admin_sub: str | None,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
    environment: str | None = "production",
    status: str,
) -> PaymentIntegration:
    integration = get_payment_integration(
        db,
        establishment_id=establishment_id,
        provider=provider,
        environment=environment,
    )
    if not integration:
        raise ValueError("Integracao de pagamento nao configurada para este estabelecimento.")

    normalized_status = normalize_status(status)
    credentials = _load_integration_credentials(integration)
    validation_status, validation_error, validated_at = _validate_credentials_for_status(
        credentials,
        normalized_status,
    )
    if validation_error:
        raise ValueError(validation_error)

    now = _utcnow()
    integration.status = normalized_status
    integration.validation_status = validation_status
    integration.validation_error = None
    integration.last_validated_at = validated_at
    integration.updated_by_admin_id = admin_sub
    integration.updated_at = now
    if normalized_status == "active":
        integration.connected_at = integration.connected_at or now
        integration.disconnected_at = None
    if normalized_status == "disconnected":
        integration.disconnected_at = now

    _sync_legacy_payment_account(
        db,
        integration=integration,
        credentials=credentials,
        admin_sub=admin_sub,
    )
    _notify_integration_attention(db, establishment_id=integration.establishment_id, status=normalized_status)
    db.commit()
    db.refresh(integration)
    return integration


def get_masked_admin_integration_credentials(integration: PaymentIntegration) -> dict[str, str | None]:
    credentials = _load_integration_credentials(integration)
    return {
        "client_id_masked": mask_secret(credentials.get("client_id")),
        "client_secret_masked": mask_secret(credentials.get("client_secret")),
        "access_token_masked": mask_secret(credentials.get("access_token")),
        "webhook_secret_masked": mask_secret(credentials.get("webhook_secret")),
        "public_key_masked": mask_secret(credentials.get("public_key")),
        "internal_notes": credentials.get("notes"),
    }


def get_decrypted_integration_access_token(integration: PaymentIntegration) -> str:
    credentials = _load_integration_credentials(integration)
    token = _clean_optional(credentials.get("access_token"))
    if not token:
        raise ValueError("Integracao de pagamento sem access token valido.")
    return token


def get_active_payment_integration(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> PaymentIntegration | None:
    normalized_provider = normalize_provider(provider)
    preferred_environment = _get_default_environment()
    integrations = (
        db.query(PaymentIntegration)
        .filter(
            PaymentIntegration.establishment_id == establishment_id,
            PaymentIntegration.provider == normalized_provider,
            PaymentIntegration.status == "active",
            PaymentIntegration.validation_status == "valid",
        )
        .all()
    )
    if not integrations:
        return None
    for integration in integrations:
        if integration.environment == preferred_environment:
            return integration
    for integration in integrations:
        if integration.environment == "production":
            return integration
    return integrations[0]


def get_active_payment_credentials(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> ActivePaymentCredentials | None:
    normalized_provider = normalize_provider(provider)
    integration = get_active_payment_integration(
        db,
        establishment_id=establishment_id,
        provider=normalized_provider,
    )
    if integration:
        credentials = _load_integration_credentials(integration)
        access_token = _clean_optional(credentials.get("access_token"))
        if not access_token:
            raise ValueError("Integracao de pagamento sem access token valido.")
        return ActivePaymentCredentials(
            provider=integration.provider,
            environment=integration.environment,
            access_token=access_token,
            webhook_secret=_clean_optional(credentials.get("webhook_secret")),
            external_account_id=_clean_optional(credentials.get("external_user_id")),
            checkout_hold_minutes=integration.checkout_hold_minutes or 10,
            payment_integration_id=integration.id,
        )

    if get_preferred_payment_integration(
        db,
        establishment_id=establishment_id,
        provider=normalized_provider,
    ):
        return None

    account = (
        db.query(PaymentAccount)
        .filter(
            PaymentAccount.establishment_id == establishment_id,
            PaymentAccount.provider == normalized_provider,
            PaymentAccount.status == "active",
        )
        .first()
    )
    if not account:
        return None
    token = decrypt_sensitive_value(account.access_token_encrypted)
    if not token:
        raise ValueError("Conta de pagamento sem access token valido.")
    return ActivePaymentCredentials(
        provider=account.provider,
        environment=None,
        access_token=token,
        checkout_hold_minutes=account.checkout_hold_minutes or 10,
        payment_account_id=account.id,
        external_account_id=_clean_optional(account.external_user_id),
        webhook_secret=_clean_optional(os.getenv("MERCADOPAGO_WEBHOOK_SECRET")),
    )
