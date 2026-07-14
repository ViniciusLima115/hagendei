import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.payment_account import PaymentAccount
from app.models.payment_oauth_state import PaymentOAuthState
from app.repositories import notificacao_repository as notificacao_repo
from app.services.payments.constants import (
    PAYMENT_ACCOUNT_STATUS_CONNECTED,
    PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
    PAYMENT_ACCOUNT_STATUS_ERROR,
    PAYMENT_ACCOUNT_STATUS_EXPIRED,
    PAYMENT_PROVIDER_MERCADO_PAGO,
    PAYMENT_PROVIDER_PICPAY,
    SUPPORTED_PAYMENT_ACCOUNT_STATUSES,
    SUPPORTED_PAYMENT_PROVIDERS,
    is_payment_account_connected,
    normalize_payment_account_status,
    normalize_payment_provider,
)
from app.services.payments.crypto import decrypt_sensitive_value, encrypt_sensitive_value, mask_secret
from app.services.payments.provider_factory import get_payment_provider
from app.services.payments.providers.base import PaymentTokenRefreshError


logger = logging.getLogger(__name__)

STATE_TTL_MINUTES = 15


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_provider(provider: str) -> str:
    normalized = normalize_payment_provider(provider)
    if normalized not in SUPPORTED_PAYMENT_PROVIDERS:
        raise ValueError("Provider de pagamento nao suportado.")
    return normalized


def _provider_label(provider: str | None) -> str:
    normalized = normalize_payment_provider(provider)
    if normalized == PAYMENT_PROVIDER_PICPAY:
        return "PicPay"
    return "Mercado Pago"


def _provider_account_label(provider: str | None) -> str:
    normalized = normalize_payment_provider(provider)
    if normalized == PAYMENT_PROVIDER_PICPAY:
        return "PicPay"
    return "do Mercado Pago"


def _build_pkce_pair() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def _notify_account_event(
    db: Session,
    *,
    establishment_id: int,
    title: str,
    body: str | None = None,
) -> None:
    try:
        notificacao_repo.criar(
            db,
            estabelecimento_id=establishment_id,
            tipo="conta_pagamento_desconectada",
            titulo=title,
            corpo=body,
        )
    except Exception:
        logger.exception(
            "Falha ao criar notificacao de conta de pagamento (establishment_id=%s)",
            establishment_id,
        )


def start_connect_flow(
    db: Session,
    *,
    establishment_id: int,
    user_sub: str | None,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> str:
    normalized_provider = _normalize_provider(provider)
    provider_impl = get_payment_provider(normalized_provider)

    oauth_state = secrets.token_urlsafe(48)
    code_verifier, code_challenge = _build_pkce_pair()
    expires_at = _utcnow() + timedelta(minutes=STATE_TTL_MINUTES)
    state_row = PaymentOAuthState(
        provider=normalized_provider,
        establishment_id=establishment_id,
        user_sub=user_sub,
        state=oauth_state,
        code_verifier=code_verifier,
        expires_at=expires_at,
    )
    db.add(state_row)
    db.commit()

    logger.info(
        "Fluxo OAuth iniciado (provider=%s, establishment_id=%s)",
        normalized_provider,
        establishment_id,
    )

    return provider_impl.build_connect_url(state=oauth_state, code_challenge=code_challenge)


def _consume_state(
    db: Session,
    *,
    provider: str,
    state: str,
) -> PaymentOAuthState:
    now = _utcnow()
    row = (
        db.query(PaymentOAuthState)
        .filter(
            PaymentOAuthState.provider == provider,
            PaymentOAuthState.state == state,
            PaymentOAuthState.consumed_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if not row:
        raise ValueError("State OAuth invalido.")
    if row.expires_at < now:
        row.consumed_at = now
        db.commit()
        raise ValueError("State OAuth expirado.")
    row.consumed_at = now
    db.commit()
    db.refresh(row)
    return row


def get_payment_account(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> PaymentAccount | None:
    normalized_provider = _normalize_provider(provider)
    return (
        db.query(PaymentAccount)
        .filter(
            PaymentAccount.establishment_id == establishment_id,
            PaymentAccount.provider == normalized_provider,
        )
        .first()
    )


def get_active_payment_account(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> PaymentAccount | None:
    row = get_payment_account(
        db,
        establishment_id=establishment_id,
        provider=provider,
    )
    if not row:
        return None
    if not is_payment_account_connected(row.status):
        return None
    return row


def get_decrypted_access_token(payment_account: PaymentAccount) -> str:
    token = decrypt_sensitive_value(payment_account.access_token_encrypted)
    if not token:
        raise ValueError("Conta de pagamento sem token valido.")
    return token


def _token_requires_refresh(payment_account: PaymentAccount) -> bool:
    expires_at = payment_account.token_expires_at
    if not expires_at:
        return False
    if expires_at.tzinfo is not None:
        expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
    return expires_at <= _utcnow() + timedelta(minutes=5)


def _mark_refresh_failure(
    db: Session,
    payment_account: PaymentAccount,
    *,
    status: str,
    title: str,
    body: str,
) -> None:
    was_connected = is_payment_account_connected(payment_account.status)
    payment_account.status = status
    payment_account.updated_at = _utcnow()
    if was_connected and status in {PAYMENT_ACCOUNT_STATUS_EXPIRED, PAYMENT_ACCOUNT_STATUS_ERROR}:
        payment_account.disconnected_at = _utcnow()
    _notify_account_event(
        db,
        establishment_id=payment_account.establishment_id,
        title=title,
        body=body,
    )
    db.commit()


def _refresh_payment_account_token(db: Session, payment_account: PaymentAccount) -> str:
    refresh_token = decrypt_sensitive_value(payment_account.refresh_token_encrypted)
    if not refresh_token:
        _mark_refresh_failure(
            db,
            payment_account,
            status=PAYMENT_ACCOUNT_STATUS_EXPIRED,
            title="Reconecte o Mercado Pago",
            body="A autorizacao Mercado Pago expirou e precisa ser conectada novamente.",
        )
        raise ValueError("Conta de pagamento sem refresh token para renovar acesso.")

    provider_impl = get_payment_provider(payment_account.provider)
    try:
        refreshed = provider_impl.refresh_access_token(refresh_token=refresh_token)
    except PaymentTokenRefreshError as exc:
        if exc.authorization_revoked:
            _mark_refresh_failure(
                db,
                payment_account,
                status=PAYMENT_ACCOUNT_STATUS_EXPIRED,
                title="Reconecte o Mercado Pago",
                body="A autorizacao Mercado Pago foi expirada ou revogada. Conecte a conta novamente.",
            )
            raise ValueError("Autorizacao Mercado Pago expirada ou revogada. Reconecte a conta.") from exc
        _mark_refresh_failure(
            db,
            payment_account,
            status=PAYMENT_ACCOUNT_STATUS_ERROR,
            title="Erro ao renovar Mercado Pago",
            body="Nao foi possivel renovar automaticamente a autorizacao Mercado Pago.",
        )
        raise ValueError("Nao foi possivel renovar o token do Mercado Pago.") from exc
    except Exception as exc:
        _mark_refresh_failure(
            db,
            payment_account,
            status=PAYMENT_ACCOUNT_STATUS_ERROR,
            title="Erro ao renovar Mercado Pago",
            body="Nao foi possivel renovar automaticamente a autorizacao Mercado Pago.",
        )
        raise ValueError("Nao foi possivel renovar o token do Mercado Pago.") from exc

    new_access_token = str(refreshed.get("access_token") or "").strip()
    if not new_access_token:
        _mark_refresh_failure(
            db,
            payment_account,
            status=PAYMENT_ACCOUNT_STATUS_ERROR,
            title="Erro ao renovar Mercado Pago",
            body="O Mercado Pago retornou uma resposta invalida ao renovar a autorizacao.",
        )
        raise ValueError("Resposta de refresh OAuth sem access_token.")

    payment_account.access_token_encrypted = encrypt_sensitive_value(new_access_token) or ""
    if refreshed.get("refresh_token"):
        payment_account.refresh_token_encrypted = encrypt_sensitive_value(refreshed.get("refresh_token"))
    if refreshed.get("public_key"):
        payment_account.public_key = str(refreshed.get("public_key") or "").strip() or None
    payment_account.token_expires_at = refreshed.get("token_expires_at")
    payment_account.status = PAYMENT_ACCOUNT_STATUS_CONNECTED
    payment_account.connected_at = payment_account.connected_at or _utcnow()
    payment_account.disconnected_at = None
    payment_account.last_sync_at = _utcnow()
    payment_account.updated_at = _utcnow()
    db.commit()
    db.refresh(payment_account)

    logger.info(
        "Token Mercado Pago renovado (establishment_id=%s, provider=%s)",
        payment_account.establishment_id,
        payment_account.provider,
    )
    return new_access_token


def refresh_mercadopago_token(db: Session, payment_integration_id: int) -> str:
    account = (
        db.query(PaymentAccount)
        .filter(
            PaymentAccount.id == payment_integration_id,
            PaymentAccount.provider == PAYMENT_PROVIDER_MERCADO_PAGO,
        )
        .first()
    )
    if not account:
        raise ValueError("Integracao Mercado Pago nao encontrada.")
    if not is_payment_account_connected(account.status):
        raise ValueError("Integracao Mercado Pago nao conectada.")
    return _refresh_payment_account_token(db, account)


def get_valid_access_token(db: Session, payment_account: PaymentAccount) -> str:
    if not is_payment_account_connected(payment_account.status):
        raise ValueError(f"Conta {_provider_label(payment_account.provider)} nao conectada.")

    if payment_account.provider != PAYMENT_PROVIDER_MERCADO_PAGO:
        return get_decrypted_access_token(payment_account)

    token = decrypt_sensitive_value(payment_account.access_token_encrypted)
    if token and not _token_requires_refresh(payment_account):
        return token

    return _refresh_payment_account_token(db, payment_account)


def get_valid_mercadopago_access_token(db: Session, *, establishment_id: int) -> str:
    account = get_active_payment_account(
        db,
        establishment_id=establishment_id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
    )
    if not account:
        raise ValueError("Mercado Pago nao conectado para este estabelecimento.")
    return get_valid_access_token(db, account)


def validate_mercadopago_connection(db: Session, *, establishment_id: int) -> PaymentAccount:
    account = get_active_payment_account(
        db,
        establishment_id=establishment_id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
    )
    if not account:
        raise ValueError("Mercado Pago nao conectado para este estabelecimento.")

    access_token = get_valid_access_token(db, account)
    provider_impl = get_payment_provider(account.provider)
    provider_data = provider_impl.validate_access_token(access_token=access_token)

    provider_account_id = str(
        provider_data.get("provider_account_id") or provider_data.get("external_user_id") or ""
    ).strip() or None
    provider_account_email = provider_data.get("provider_account_email") or provider_data.get("external_account_email")

    if provider_account_id:
        existing_for_other = (
            db.query(PaymentAccount)
            .filter(
                PaymentAccount.provider == account.provider,
                PaymentAccount.provider_account_id == provider_account_id,
                PaymentAccount.establishment_id != account.establishment_id,
            )
            .first()
        )
        if existing_for_other:
            _mark_refresh_failure(
                db,
                account,
                status=PAYMENT_ACCOUNT_STATUS_ERROR,
                title="Erro na conta Mercado Pago",
                body="A conta Mercado Pago validada ja esta vinculada a outro estabelecimento.",
            )
            raise ValueError("Conta Mercado Pago ja vinculada a outro estabelecimento.")
        if account.provider_account_id and account.provider_account_id != provider_account_id:
            _mark_refresh_failure(
                db,
                account,
                status=PAYMENT_ACCOUNT_STATUS_ERROR,
                title="Erro na conta Mercado Pago",
                body="O token Mercado Pago validado pertence a uma conta diferente da integracao salva.",
            )
            raise ValueError("Token Mercado Pago pertence a outra conta.")
        account.provider_account_id = provider_account_id

    if provider_account_email:
        account.provider_account_email = provider_account_email
    account.last_sync_at = _utcnow()
    account.updated_at = _utcnow()
    db.commit()
    db.refresh(account)
    return account


def _set_encrypted_if_provided(payment_account: PaymentAccount, field_name: str, value: str | None) -> bool:
    if value is None:
        return False
    cleaned = value.strip()
    if not cleaned:
        return False
    setattr(payment_account, field_name, encrypt_sensitive_value(cleaned) or "")
    return True


def upsert_admin_payment_account(
    db: Session,
    *,
    establishment_id: int,
    admin_sub: str | None,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
    account_name: str | None = None,
    provider_account_id: str | None = None,
    provider_account_email: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    access_token: str | None = None,
    refresh_token: str | None = None,
    public_key: str | None = None,
    status: str = PAYMENT_ACCOUNT_STATUS_CONNECTED,
    internal_notes: str | None = None,
    checkout_hold_minutes: int = 10,
) -> PaymentAccount:
    normalized_provider = _normalize_provider(provider)
    if checkout_hold_minutes < 5 or checkout_hold_minutes > 60:
        raise ValueError("checkout_hold_minutes deve ficar entre 5 e 60 minutos.")

    normalized_status = normalize_payment_account_status(
        status,
        default=PAYMENT_ACCOUNT_STATUS_CONNECTED,
    )
    if normalized_status not in SUPPORTED_PAYMENT_ACCOUNT_STATUSES:
        raise ValueError("Status de conta de pagamento invalido.")

    account = get_payment_account(
        db,
        establishment_id=establishment_id,
        provider=normalized_provider,
    )
    is_new = account is None
    if account is None:
        account = PaymentAccount(
            establishment_id=establishment_id,
            provider=normalized_provider,
            access_token_encrypted="",
            status=PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
            created_by_admin_id=admin_sub,
        )
        db.add(account)

    account.account_name = account_name.strip() if account_name and account_name.strip() else None
    account.internal_notes = internal_notes.strip() if internal_notes and internal_notes.strip() else None
    account.checkout_hold_minutes = checkout_hold_minutes
    account.updated_by_admin_id = admin_sub
    account.updated_at = _utcnow()

    cleaned_provider_account_id = provider_account_id.strip() if provider_account_id and provider_account_id.strip() else None
    cleaned_provider_account_email = (
        provider_account_email.strip() if provider_account_email and provider_account_email.strip() else None
    )
    if cleaned_provider_account_id:
        existing_for_other = (
            db.query(PaymentAccount)
            .filter(
                PaymentAccount.provider == normalized_provider,
                PaymentAccount.provider_account_id == cleaned_provider_account_id,
                PaymentAccount.establishment_id != establishment_id,
            )
            .first()
        )
        if existing_for_other:
            raise ValueError("Conta do provider ja vinculada a outro estabelecimento.")
        account.provider_account_id = cleaned_provider_account_id
    if cleaned_provider_account_email:
        account.provider_account_email = cleaned_provider_account_email

    token_changed = _set_encrypted_if_provided(account, "access_token_encrypted", access_token)
    seller_token_changed = _set_encrypted_if_provided(account, "refresh_token_encrypted", refresh_token)
    _set_encrypted_if_provided(account, "client_id_encrypted", client_id)
    _set_encrypted_if_provided(account, "client_secret_encrypted", client_secret)
    if public_key is not None and public_key.strip():
        account.public_key = public_key.strip()

    if normalized_status == PAYMENT_ACCOUNT_STATUS_CONNECTED and not decrypt_sensitive_value(account.access_token_encrypted):
        token_name = "x-picpay-token" if normalized_provider == PAYMENT_PROVIDER_PICPAY else "access_token"
        raise ValueError(f"{token_name} e obrigatorio para ativar pagamentos online.")
    if (
        normalized_provider == PAYMENT_PROVIDER_PICPAY
        and normalized_status == PAYMENT_ACCOUNT_STATUS_CONNECTED
        and not decrypt_sensitive_value(account.refresh_token_encrypted)
    ):
        raise ValueError("x-seller-token e obrigatorio para ativar callback PicPay.")

    previous_connected = is_payment_account_connected(account.status)
    account.status = normalized_status
    if is_payment_account_connected(account.status):
        account.connected_at = account.connected_at or _utcnow()
        account.disconnected_at = None
    elif previous_connected:
        account.disconnected_at = _utcnow()
    if token_changed or seller_token_changed or is_new:
        account.last_sync_at = _utcnow()

    db.commit()
    db.refresh(account)

    logger.info(
        "Conta de pagamento administrada atualizada (establishment_id=%s, provider=%s, status=%s, admin=%s)",
        establishment_id,
        normalized_provider,
        account.status,
        mask_secret(admin_sub),
    )
    return account


def update_admin_payment_account_status(
    db: Session,
    *,
    establishment_id: int,
    admin_sub: str | None,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
    status: str,
) -> PaymentAccount:
    account = get_payment_account(db, establishment_id=establishment_id, provider=provider)
    if not account:
        raise ValueError("Conta de pagamento nao configurada para este estabelecimento.")

    normalized_status = normalize_payment_account_status(status)
    if normalized_status not in SUPPORTED_PAYMENT_ACCOUNT_STATUSES:
        raise ValueError("Status de conta de pagamento invalido.")
    if normalized_status == PAYMENT_ACCOUNT_STATUS_CONNECTED and not decrypt_sensitive_value(account.access_token_encrypted):
        token_name = "x-picpay-token" if account.provider == PAYMENT_PROVIDER_PICPAY else "access_token"
        raise ValueError(f"{token_name} e obrigatorio para ativar pagamentos online.")
    if (
        account.provider == PAYMENT_PROVIDER_PICPAY
        and normalized_status == PAYMENT_ACCOUNT_STATUS_CONNECTED
        and not decrypt_sensitive_value(account.refresh_token_encrypted)
    ):
        raise ValueError("x-seller-token e obrigatorio para ativar callback PicPay.")

    previous_connected = is_payment_account_connected(account.status)
    account.status = normalized_status
    account.updated_by_admin_id = admin_sub
    account.updated_at = _utcnow()
    if is_payment_account_connected(account.status):
        account.connected_at = account.connected_at or _utcnow()
        account.disconnected_at = None
    elif previous_connected:
        account.disconnected_at = _utcnow()
    if normalized_status in {
        PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
        PAYMENT_ACCOUNT_STATUS_EXPIRED,
        PAYMENT_ACCOUNT_STATUS_ERROR,
    }:
        _notify_account_event(
            db,
            establishment_id=account.establishment_id,
            title=f"Conta {_provider_label(account.provider)} requer atencao",
            body="A administracao alterou o status da conta de pagamento deste estabelecimento.",
        )
    db.commit()
    db.refresh(account)
    return account


def finalize_oauth_callback(
    db: Session,
    *,
    provider: str,
    state: str,
    code: str,
) -> PaymentAccount:
    normalized_provider = _normalize_provider(provider)
    provider_impl = get_payment_provider(normalized_provider)

    state_row = _consume_state(db, provider=normalized_provider, state=state)
    exchange = provider_impl.exchange_oauth_code(code=code, code_verifier=state_row.code_verifier)
    provider_account_id = str(
        exchange.get("provider_account_id") or exchange.get("external_user_id") or ""
    ).strip() or None

    if provider_account_id:
        existing_for_other = (
            db.query(PaymentAccount)
            .filter(
                PaymentAccount.provider == normalized_provider,
                PaymentAccount.provider_account_id == provider_account_id,
                PaymentAccount.establishment_id != state_row.establishment_id,
            )
            .first()
        )
        if existing_for_other:
            db.rollback()
            raise ValueError("Esta conta do Mercado Pago ja esta vinculada a outro estabelecimento.")

    payment_account = (
        db.query(PaymentAccount)
        .filter(
            PaymentAccount.establishment_id == state_row.establishment_id,
            PaymentAccount.provider == normalized_provider,
        )
        .first()
    )
    if not payment_account:
        payment_account = PaymentAccount(
            establishment_id=state_row.establishment_id,
            provider=normalized_provider,
            access_token_encrypted=encrypt_sensitive_value(str(exchange.get("access_token") or "")) or "",
        )
        db.add(payment_account)

    payment_account.provider_account_id = provider_account_id
    payment_account.provider_account_email = exchange.get("provider_account_email") or exchange.get("external_account_email")
    payment_account.access_token_encrypted = encrypt_sensitive_value(str(exchange.get("access_token") or "")) or ""
    payment_account.refresh_token_encrypted = encrypt_sensitive_value(exchange.get("refresh_token"))
    payment_account.public_key = str(exchange.get("public_key") or "").strip() or None
    payment_account.expires_at = exchange.get("expires_at") or exchange.get("token_expires_at")
    payment_account.status = PAYMENT_ACCOUNT_STATUS_CONNECTED
    payment_account.connected_at = _utcnow()
    payment_account.disconnected_at = None
    payment_account.last_sync_at = _utcnow()
    payment_account.updated_at = _utcnow()

    db.commit()
    db.refresh(payment_account)

    logger.info(
        "Conta de pagamento conectada (provider=%s, establishment_id=%s, provider_account_id=%s)",
        normalized_provider,
        payment_account.establishment_id,
        mask_secret(payment_account.provider_account_id),
    )

    return payment_account


def disconnect_payment_account(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> PaymentAccount | None:
    account = get_payment_account(db, establishment_id=establishment_id, provider=provider)
    if not account:
        return None

    account.status = PAYMENT_ACCOUNT_STATUS_DISCONNECTED
    account.disconnected_at = _utcnow()
    account.updated_at = _utcnow()
    _notify_account_event(
        db,
        establishment_id=account.establishment_id,
        title=f"Conta {_provider_label(account.provider)} desconectada",
        body="Pagamentos online ficaram desabilitados ate reconectar a conta.",
    )
    db.commit()
    db.refresh(account)

    logger.info(
        "Conta de pagamento desconectada (provider=%s, establishment_id=%s)",
        account.provider,
        establishment_id,
    )

    return account


def reconnect_payment_account(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> PaymentAccount:
    account = get_payment_account(db, establishment_id=establishment_id, provider=provider)
    if not account:
        raise ValueError("Conta de pagamento nao configurada para este estabelecimento.")
    if not decrypt_sensitive_value(account.access_token_encrypted):
        token_name = "x-picpay-token" if account.provider == PAYMENT_PROVIDER_PICPAY else "access_token"
        raise ValueError(f"{token_name} e obrigatorio para reconectar pagamentos online.")
    if account.provider == PAYMENT_PROVIDER_PICPAY and not decrypt_sensitive_value(account.refresh_token_encrypted):
        raise ValueError("x-seller-token e obrigatorio para reconectar PicPay.")

    account.status = PAYMENT_ACCOUNT_STATUS_CONNECTED
    account.connected_at = _utcnow()
    account.disconnected_at = None
    account.updated_at = _utcnow()
    db.commit()
    db.refresh(account)
    return account


def is_payment_integration_active(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> bool:
    return get_active_payment_account(
        db,
        establishment_id=establishment_id,
        provider=provider,
    ) is not None


def update_payment_account_settings(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
    checkout_hold_minutes: int | None = None,
    status: str | None = None,
) -> PaymentAccount:
    normalized_provider = _normalize_provider(provider)

    if checkout_hold_minutes is not None:
        if checkout_hold_minutes < 5 or checkout_hold_minutes > 60:
            raise ValueError("checkout_hold_minutes deve ficar entre 5 e 60 minutos.")

    normalized_status: str | None = None
    if status is not None:
        normalized_status = normalize_payment_account_status(status)
        if normalized_status not in SUPPORTED_PAYMENT_ACCOUNT_STATUSES:
            raise ValueError("Status de conta de pagamento invalido.")

    account = get_payment_account(
        db,
        establishment_id=establishment_id,
        provider=normalized_provider,
    )
    if not account:
        if normalized_status == PAYMENT_ACCOUNT_STATUS_CONNECTED:
            raise ValueError(f"Conecte a conta {_provider_account_label(normalized_provider)} antes de ativar os pagamentos.")
        account = PaymentAccount(
            establishment_id=establishment_id,
            provider=normalized_provider,
            access_token_encrypted="",
            status=normalized_status or PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
            checkout_hold_minutes=checkout_hold_minutes or 10,
        )
        if account.status == PAYMENT_ACCOUNT_STATUS_DISCONNECTED:
            account.disconnected_at = _utcnow()
        account.updated_at = _utcnow()
        db.add(account)
        db.commit()
        db.refresh(account)
        return account

    previous_connected = is_payment_account_connected(account.status)
    if checkout_hold_minutes is not None:
        account.checkout_hold_minutes = checkout_hold_minutes
    if normalized_status is not None:
        account.status = normalized_status
        if is_payment_account_connected(account.status):
            if not decrypt_sensitive_value(account.access_token_encrypted):
                raise ValueError(f"Conecte a conta {_provider_account_label(account.provider)} antes de ativar os pagamentos.")
            if account.provider == PAYMENT_PROVIDER_PICPAY and not decrypt_sensitive_value(account.refresh_token_encrypted):
                raise ValueError("Configure o x-seller-token PicPay antes de ativar os pagamentos.")
            account.connected_at = account.connected_at or _utcnow()
            account.disconnected_at = None
        elif previous_connected:
            account.disconnected_at = _utcnow()
        if normalized_status in {
            PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
            PAYMENT_ACCOUNT_STATUS_EXPIRED,
            PAYMENT_ACCOUNT_STATUS_ERROR,
        }:
            _notify_account_event(
                db,
                establishment_id=account.establishment_id,
                title=f"Conta {_provider_label(account.provider)} requer atencao",
                body="Revise a configuracao de pagamentos para manter o checkout online ativo.",
            )
    account.updated_at = _utcnow()

    db.commit()
    db.refresh(account)
    return account
