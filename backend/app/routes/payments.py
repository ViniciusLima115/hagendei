import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_frontend_url
from app.database import get_db
from app.models.agendamento import Agendamento
from app.models.estabelecimento import Estabelecimento
from app.models.pagamento import Pagamento
from app.models.payment_account import PaymentAccount
from app.models.payment_admin_audit_log import PaymentAdminAuditLog
from app.models.payment_webhook_event import PaymentWebhookEvent
from app.models.servico import Servico
from app.repositories import notificacao_repository as notificacao_repo
from app.routes.deps import get_current_claims, require_admin, tenant_id_from_header
from app.schemas.agendamento import AgendamentoCreate
from app.schemas.pagamentos import (
    AdminPaymentActionResponse,
    AdminPaymentAccountResponse,
    AdminPaymentAccountStatusUpdate,
    AdminPaymentAccountUpsert,
    AdminPaymentAuditLogItem,
    AdminPaymentEstablishmentResponse,
    AdminPaymentsListResponse,
    BookingPaymentStatusResponse,
    CheckoutResponse,
    MercadoPagoConnectResponse,
    PaymentAccountSettingsUpdate,
    PaymentAccountStatusResponse,
    PaymentDetailsResponse,
)
from app.security import TokenClaims
from app.services.agendamento_service import criar_agendamento
from app.services.payments.constants import (
    BOOKING_STATUS_FAILED,
    PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
    PAYMENT_ACCOUNT_STATUS_ERROR,
    PAYMENT_PROVIDER_MERCADO_PAGO,
    PAYMENT_PROVIDER_PICPAY,
    PAYMENT_STATUS_APPROVED,
    PAYMENT_STATUS_CANCELLED,
    PAYMENT_STATUS_EXPIRED,
    PAYMENT_STATUS_NOT_REQUIRED,
    PAYMENT_STATUS_REJECTED,
    normalize_payment_provider,
)
from app.services.payments.crypto import decrypt_sensitive_value, mask_secret
from app.services.payments.payment_account_service import (
    STATE_TTL_MINUTES,
    finalize_oauth_callback,
    get_payment_account,
    start_connect_flow,
    update_admin_payment_account_status,
    upsert_admin_payment_account,
    update_payment_account_settings,
    validate_mercadopago_connection,
)
from app.services.payments.payment_service import (
    apply_payment_snapshot_from_service,
    start_checkout_for_booking,
)
from app.services.payments.webhook_service import process_mercadopago_webhook, process_picpay_webhook


router = APIRouter(tags=["payments"])
logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _serialize_payment(payment: Pagamento) -> PaymentDetailsResponse:
    return PaymentDetailsResponse(
        id=payment.id,
        booking_id=payment.agendamento_id,
        establishment_id=payment.estabelecimento_id,
        provider=payment.provider,
        amount=float(payment.amount or 0),
        status=payment.status,  # type: ignore[arg-type]
        payment_method=payment.payment_method,
        external_reference=payment.external_reference,
        external_payment_id=payment.provider_payment_id,
        external_preference_id=payment.preference_id,
        created_at=payment.created_at,
        updated_at=payment.updated_at,
        paid_at=payment.paid_at,
        expires_at=payment.expires_at,
    )

def _latest_admin_payment_error(db: Session, establishment_id: int) -> str | None:
    failed_event = (
        db.query(PaymentWebhookEvent)
        .filter(
            PaymentWebhookEvent.establishment_id == establishment_id,
            PaymentWebhookEvent.processing_status == "failed",
            PaymentWebhookEvent.error_message.isnot(None),
        )
        .order_by(PaymentWebhookEvent.received_at.desc(), PaymentWebhookEvent.id.desc())
        .first()
    )
    if failed_event and failed_event.error_message:
        return failed_event.error_message

    failed_audit = (
        db.query(PaymentAdminAuditLog)
        .filter(
            PaymentAdminAuditLog.establishment_id == establishment_id,
            PaymentAdminAuditLog.error_message.isnot(None),
        )
        .order_by(PaymentAdminAuditLog.created_at.desc(), PaymentAdminAuditLog.id.desc())
        .first()
    )
    return failed_audit.error_message if failed_audit else None


def _payment_counts(db: Session, establishment_id: int) -> tuple[int, int]:
    approved = (
        db.query(func.count(Pagamento.id))
        .filter(
            Pagamento.estabelecimento_id == establishment_id,
            Pagamento.status == PAYMENT_STATUS_APPROVED,
        )
        .scalar()
        or 0
    )
    failed = (
        db.query(func.count(Pagamento.id))
        .filter(
            Pagamento.estabelecimento_id == establishment_id,
            Pagamento.status.in_([PAYMENT_STATUS_REJECTED, PAYMENT_STATUS_CANCELLED, PAYMENT_STATUS_EXPIRED]),
        )
        .scalar()
        or 0
    )
    return int(approved), int(failed)


def _provider_label(provider: str | None) -> str:
    normalized = normalize_payment_provider(provider)
    if normalized == PAYMENT_PROVIDER_PICPAY:
        return "PicPay"
    return "Mercado Pago"


def _get_admin_payment_account(
    db: Session,
    *,
    establishment_id: int,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> PaymentAccount | None:
    normalized_provider = normalize_payment_provider(provider)
    return get_payment_account(
        db,
        establishment_id=establishment_id,
        provider=normalized_provider,
    )


def _get_admin_primary_payment_account(db: Session, establishment_id: int) -> PaymentAccount | None:
    accounts = (
        db.query(PaymentAccount)
        .filter(PaymentAccount.establishment_id == establishment_id)
        .all()
    )
    if not accounts:
        return None
    provider_priority = {PAYMENT_PROVIDER_MERCADO_PAGO: 0, PAYMENT_PROVIDER_PICPAY: 1}
    status_priority = {"connected": 0, "error": 1, "expired": 2, "disconnected": 3}
    return sorted(
        accounts,
        key=lambda account: (
            status_priority.get(account.status, 9),
            provider_priority.get(account.provider, 9),
            account.id,
        ),
    )[0]


def _latest_payment(db: Session, establishment_id: int) -> Pagamento | None:
    return (
        db.query(Pagamento)
        .filter(Pagamento.estabelecimento_id == establishment_id)
        .order_by(Pagamento.created_at.desc(), Pagamento.id.desc())
        .first()
    )


def _latest_test_audit(db: Session, establishment_id: int) -> PaymentAdminAuditLog | None:
    return (
        db.query(PaymentAdminAuditLog)
        .filter(
            PaymentAdminAuditLog.establishment_id == establishment_id,
            PaymentAdminAuditLog.action == "test_checkout",
        )
        .order_by(PaymentAdminAuditLog.created_at.desc(), PaymentAdminAuditLog.id.desc())
        .first()
    )


def _audit_items(db: Session, establishment_id: int, *, limit: int = 8) -> list[AdminPaymentAuditLogItem]:
    rows = (
        db.query(PaymentAdminAuditLog)
        .filter(PaymentAdminAuditLog.establishment_id == establishment_id)
        .order_by(PaymentAdminAuditLog.created_at.desc(), PaymentAdminAuditLog.id.desc())
        .limit(limit)
        .all()
    )
    return [
        AdminPaymentAuditLogItem(
            id=row.id,
            action=row.action,
            admin_sub=mask_secret(row.admin_sub),
            status_before=row.status_before,
            status_after=row.status_after,
            error_message=row.error_message,
            created_at=row.created_at,
        )
        for row in rows
    ]


def _record_admin_payment_audit(
    db: Session,
    *,
    establishment_id: int,
    admin_sub: str | None,
    action: str,
    account: PaymentAccount | None = None,
    status_before: str | None = None,
    status_after: str | None = None,
    details: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    sanitized_details = details or {}
    for forbidden in ("access_token", "refresh_token", "client_secret", "client_id"):
        sanitized_details.pop(forbidden, None)
    db.add(
        PaymentAdminAuditLog(
            establishment_id=establishment_id,
            payment_account_id=account.id if account else None,
            provider=account.provider if account else PAYMENT_PROVIDER_MERCADO_PAGO,
            admin_sub=admin_sub,
            action=action,
            status_before=status_before,
            status_after=status_after,
            details=sanitized_details or None,
            error_message=error_message,
        )
    )
    db.commit()


def _notify_reconnect_request(db: Session, *, establishment_id: int, provider: str = PAYMENT_PROVIDER_MERCADO_PAGO) -> None:
    provider_name = _provider_label(provider)
    try:
        notificacao_repo.criar(
            db,
            estabelecimento_id=establishment_id,
            tipo="conta_pagamento_desconectada",
            titulo=f"Reconecte o {provider_name}",
            corpo=f"A administracao solicitou uma nova conexao da sua conta {provider_name}.",
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Falha ao notificar solicitacao de reconexao de pagamento.")


def _serialize_admin_payment_account(db: Session, account: PaymentAccount) -> AdminPaymentAccountResponse:
    approved_count, failed_count = _payment_counts(db, account.establishment_id)
    latest_payment = _latest_payment(db, account.establishment_id)
    latest_test = _latest_test_audit(db, account.establishment_id)
    latest_test_details = latest_test.details if latest_test and isinstance(latest_test.details, dict) else {}
    return AdminPaymentAccountResponse(
        id=account.id,
        establishment_id=account.establishment_id,
        provider=account.provider,
        account_name=account.account_name,
        status=account.status,
        provider_account_id_masked=mask_secret(account.provider_account_id),
        provider_account_email_masked=mask_secret(account.provider_account_email, head=3, tail=7),
        checkout_hold_minutes=account.checkout_hold_minutes or 10,
        connected_at=account.connected_at,
        disconnected_at=account.disconnected_at,
        expires_at=account.expires_at,
        created_at=account.created_at,
        updated_at=account.updated_at,
        last_error=_latest_admin_payment_error(db, account.establishment_id),
        last_payment_status=latest_payment.status if latest_payment else None,
        last_payment_at=latest_payment.created_at if latest_payment else None,
        last_test_payment_status=latest_test_details.get("result") if latest_test else None,
        last_test_payment_at=latest_test.created_at if latest_test else None,
        approved_payments_count=approved_count,
        failed_payments_count=failed_count,
        audit_logs=_audit_items(db, account.establishment_id),
    )


def _serialize_checkout(payment: Pagamento) -> CheckoutResponse:
    booking = payment.agendamento
    if not booking:
        raise HTTPException(status_code=500, detail="Pagamento sem agendamento associado.")
    return CheckoutResponse(
        checkout_url=payment.checkout_url or "",
        appointment_id=payment.agendamento_id,
        payment_id=payment.id,
        expires_at=payment.expires_at,
    )


def _get_establishment_or_404(db: Session, establishment_id: int) -> Estabelecimento:
    establishment = db.query(Estabelecimento).filter(Estabelecimento.id == establishment_id).first()
    if not establishment:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")
    return establishment


def _require_tenant_claims(claims: TokenClaims) -> int:
    if claims.is_admin or claims.tenant_id is None:
        raise HTTPException(status_code=403, detail="Apenas estabelecimentos podem conectar Mercado Pago.")
    return claims.tenant_id


def _payment_panel_redirect(status_value: str) -> RedirectResponse:
    frontend_url = get_frontend_url()
    return RedirectResponse(
        url=f"{frontend_url}/painel/pagamentos?status={status_value}",
        status_code=302,
    )


@router.get("/payments/checkout-return/{status_value}")
def checkout_return_redirect(
    status_value: str,
    external_reference: str = Query(...),
    slug: str | None = Query(default=None),
):
    frontend_paths = {
        "success": "/agendamento/pagamento/sucesso",
        "pending": "/agendamento/pagamento/pendente",
        "failure": "/agendamento/pagamento/falha",
    }
    frontend_path = frontend_paths.get(status_value)
    if not frontend_path:
        raise HTTPException(status_code=404, detail="Retorno de pagamento invalido.")
    query_params = {"external_reference": external_reference}
    if slug:
        query_params["slug"] = slug
    query = urlencode(query_params)
    return RedirectResponse(url=f"{get_frontend_url()}{frontend_path}?{query}", status_code=302)


def _build_mercadopago_connect_response(
    db: Session,
    *,
    claims: TokenClaims,
) -> MercadoPagoConnectResponse:
    tenant_id = _require_tenant_claims(claims)
    try:
        authorization_url = start_connect_flow(
            db,
            establishment_id=tenant_id,
            user_sub=claims.sub,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return MercadoPagoConnectResponse(
        authorization_url=authorization_url,
        state_ttl_minutes=STATE_TTL_MINUTES,
    )


@router.post("/payments/mercadopago/connect", response_model=MercadoPagoConnectResponse)
def connect_mercadopago_oauth(
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    return _build_mercadopago_connect_response(db, claims=claims)


@router.get("/payments/mercadopago/connect")
def connect_mercadopago_oauth_redirect(
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
    response = _build_mercadopago_connect_response(db, claims=claims)
    return RedirectResponse(url=response.authorization_url, status_code=302)


@router.get("/payments/mercadopago/callback")
def callback_mercadopago_oauth(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if error:
        logger.warning("Callback Mercado Pago retornou erro OAuth.")
        return _payment_panel_redirect("error")
    if not code or not state:
        return _payment_panel_redirect("error")

    try:
        finalize_oauth_callback(
            db,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            state=state,
            code=code,
        )
    except ValueError as exc:
        logger.warning("Falha segura no callback Mercado Pago: %s", exc)
        return _payment_panel_redirect("error")

    return _payment_panel_redirect("connected")


@router.get("/admin/establishments", response_model=list[AdminPaymentEstablishmentResponse])
def admin_list_establishments_payment_status(
    _claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    establishments = (
        db.query(Estabelecimento)
        .order_by(Estabelecimento.criado_em.desc(), Estabelecimento.id.desc())
        .all()
    )
    items: list[AdminPaymentEstablishmentResponse] = []
    for establishment in establishments:
        account = _get_admin_primary_payment_account(db, establishment.id)
        items.append(
            AdminPaymentEstablishmentResponse(
                id=establishment.id,
                nome=establishment.nome,
                slug=establishment.slug,
                login=establishment.login,
                provider=account.provider if account else None,
                payment_account_status=account.status if account else "not_configured",
                payment_account_name=account.account_name if account else None,
                payment_account_id=account.id if account else None,
                connected_at=account.connected_at if account else None,
                updated_at=account.updated_at if account else None,
                last_error=_latest_admin_payment_error(db, establishment.id),
            )
        )
    return items


@router.get("/admin/establishments/{establishment_id}/payment-account", response_model=AdminPaymentAccountResponse)
def admin_get_establishment_payment_account(
    establishment_id: int,
    provider: str = Query(default=PAYMENT_PROVIDER_MERCADO_PAGO),
    _claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    account = _get_admin_payment_account(db, establishment_id=establishment_id, provider=provider)
    if not account:
        raise HTTPException(status_code=404, detail="Conta de pagamento nao configurada.")
    return _serialize_admin_payment_account(db, account)


@router.post("/admin/establishments/{establishment_id}/payment-account", response_model=AdminPaymentAccountResponse)
def admin_create_establishment_payment_account(
    establishment_id: int,
    payload: AdminPaymentAccountUpsert,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    previous = get_payment_account(db, establishment_id=establishment_id, provider=payload.provider)
    status_before = previous.status if previous else None
    try:
        account = upsert_admin_payment_account(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=payload.provider,
            account_name=payload.account_name,
            provider_account_id=payload.provider_account_id,
            provider_account_email=payload.provider_account_email,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            public_key=payload.public_key,
            status=payload.status,
            internal_notes=payload.internal_notes,
            checkout_hold_minutes=payload.checkout_hold_minutes,
        )
    except ValueError as exc:
        db.rollback()
        _record_admin_payment_audit(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            action="upsert_payment_account_failed",
            account=previous,
            status_before=status_before,
            status_after=None,
            details={"provider": payload.provider, "status": payload.status},
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _record_admin_payment_audit(
        db,
        establishment_id=establishment_id,
        admin_sub=claims.sub,
        action="upsert_payment_account",
        account=account,
        status_before=status_before,
        status_after=account.status,
        details={
            "provider": account.provider,
            "checkout_hold_minutes": account.checkout_hold_minutes,
            "manual_admin_update": True,
        },
    )
    return _serialize_admin_payment_account(db, account)


@router.patch("/admin/establishments/{establishment_id}/payment-account", response_model=AdminPaymentAccountResponse)
def admin_update_establishment_payment_account(
    establishment_id: int,
    payload: AdminPaymentAccountUpsert,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    previous = get_payment_account(db, establishment_id=establishment_id, provider=payload.provider)
    status_before = previous.status if previous else None
    try:
        account = upsert_admin_payment_account(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=payload.provider,
            account_name=payload.account_name,
            provider_account_id=payload.provider_account_id,
            provider_account_email=payload.provider_account_email,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            public_key=payload.public_key,
            status=payload.status,
            internal_notes=payload.internal_notes,
            checkout_hold_minutes=payload.checkout_hold_minutes,
        )
    except ValueError as exc:
        db.rollback()
        _record_admin_payment_audit(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            action="upsert_payment_account_failed",
            account=previous,
            status_before=status_before,
            status_after=None,
            details={"provider": payload.provider, "status": payload.status},
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _record_admin_payment_audit(
        db,
        establishment_id=establishment_id,
        admin_sub=claims.sub,
        action="upsert_payment_account",
        account=account,
        status_before=status_before,
        status_after=account.status,
        details={
            "provider": account.provider,
            "checkout_hold_minutes": account.checkout_hold_minutes,
            "manual_admin_update": True,
        },
    )
    return _serialize_admin_payment_account(db, account)


@router.patch("/admin/establishments/{establishment_id}/payment-account/status", response_model=AdminPaymentAccountResponse)
def admin_update_establishment_payment_account_status(
    establishment_id: int,
    payload: AdminPaymentAccountStatusUpdate,
    provider: str = Query(default=PAYMENT_PROVIDER_MERCADO_PAGO),
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    normalized_provider = normalize_payment_provider(provider)
    previous = get_payment_account(db, establishment_id=establishment_id, provider=normalized_provider)
    status_before = previous.status if previous else None
    try:
        account = update_admin_payment_account_status(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=normalized_provider,
            status=payload.status,
        )
    except ValueError as exc:
        db.rollback()
        _record_admin_payment_audit(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            action="status_update_failed",
            account=previous,
            status_before=status_before,
            status_after=payload.status,
            details={"provider": normalized_provider},
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _record_admin_payment_audit(
        db,
        establishment_id=establishment_id,
        admin_sub=claims.sub,
        action="status_update",
        account=account,
        status_before=status_before,
        status_after=account.status,
        details={"provider": account.provider},
    )
    return _serialize_admin_payment_account(db, account)


@router.delete("/admin/establishments/{establishment_id}/payment-account", status_code=204)
def admin_remove_establishment_payment_account(
    establishment_id: int,
    provider: str = Query(default=PAYMENT_PROVIDER_MERCADO_PAGO),
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    normalized_provider = normalize_payment_provider(provider)
    previous = get_payment_account(db, establishment_id=establishment_id, provider=normalized_provider)
    status_before = previous.status if previous else None
    try:
        account = update_admin_payment_account_status(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=normalized_provider,
            status=PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
        )
    except ValueError as exc:
        db.rollback()
        _record_admin_payment_audit(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            action="deactivate_failed",
            account=previous,
            status_before=status_before,
            status_after=PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
            details={"provider": normalized_provider},
            error_message=str(exc),
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _record_admin_payment_audit(
        db,
        establishment_id=establishment_id,
        admin_sub=claims.sub,
        action="deactivate",
        account=account,
        status_before=status_before,
        status_after=account.status,
        details={"provider": account.provider},
    )
    return None


@router.post(
    "/admin/establishments/{establishment_id}/payment-account/deactivate",
    response_model=AdminPaymentAccountResponse,
)
def admin_deactivate_establishment_payment_account(
    establishment_id: int,
    provider: str = Query(default=PAYMENT_PROVIDER_MERCADO_PAGO),
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    normalized_provider = normalize_payment_provider(provider)
    previous = get_payment_account(db, establishment_id=establishment_id, provider=normalized_provider)
    status_before = previous.status if previous else None
    try:
        account = update_admin_payment_account_status(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=normalized_provider,
            status=PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
        )
    except ValueError as exc:
        db.rollback()
        _record_admin_payment_audit(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            action="deactivate_failed",
            account=previous,
            status_before=status_before,
            status_after=PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
            details={"provider": normalized_provider},
            error_message=str(exc),
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _record_admin_payment_audit(
        db,
        establishment_id=establishment_id,
        admin_sub=claims.sub,
        action="deactivate",
        account=account,
        status_before=status_before,
        status_after=account.status,
        details={"provider": account.provider},
    )
    return _serialize_admin_payment_account(db, account)


@router.post(
    "/admin/establishments/{establishment_id}/payment-account/request-reconnect",
    response_model=AdminPaymentAccountResponse,
)
def admin_request_payment_account_reconnect(
    establishment_id: int,
    provider: str = Query(default=PAYMENT_PROVIDER_MERCADO_PAGO),
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    normalized_provider = normalize_payment_provider(provider)
    previous = get_payment_account(db, establishment_id=establishment_id, provider=normalized_provider)
    status_before = previous.status if previous else None
    try:
        account = update_admin_payment_account_status(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=normalized_provider,
            status=PAYMENT_ACCOUNT_STATUS_ERROR,
        )
        _notify_reconnect_request(db, establishment_id=establishment_id, provider=normalized_provider)
    except ValueError as exc:
        db.rollback()
        _record_admin_payment_audit(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            action="request_reconnect_failed",
            account=previous,
            status_before=status_before,
            status_after=PAYMENT_ACCOUNT_STATUS_ERROR,
            details={"provider": normalized_provider},
            error_message=str(exc),
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    _record_admin_payment_audit(
        db,
        establishment_id=establishment_id,
        admin_sub=claims.sub,
        action="request_reconnect",
        account=account,
        status_before=status_before,
        status_after=account.status,
        details={"provider": account.provider},
    )
    return _serialize_admin_payment_account(db, account)


def _admin_test_checkout_allowed() -> bool:
    app_env = os.getenv("APP_ENV", "").strip().lower()
    if app_env not in {"prod", "production"}:
        return True
    return os.getenv("MERCADOPAGO_TEST_CHECKOUT_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


@router.post(
    "/admin/establishments/{establishment_id}/payment-account/test-checkout",
    response_model=AdminPaymentActionResponse,
)
def admin_test_payment_checkout(
    establishment_id: int,
    provider: str = Query(default=PAYMENT_PROVIDER_MERCADO_PAGO),
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_establishment_or_404(db, establishment_id)
    normalized_provider = normalize_payment_provider(provider)
    provider_name = _provider_label(normalized_provider)
    account = get_payment_account(
        db,
        establishment_id=establishment_id,
        provider=normalized_provider,
    )
    if not account:
        _record_admin_payment_audit(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            action="test_checkout",
            details={"result": "failed", "reason": "account_not_configured"},
            error_message=f"Conta {provider_name} nao configurada.",
        )
        raise HTTPException(status_code=404, detail=f"Conta {provider_name} nao configurada.")

    if account.status != "connected":
        _record_admin_payment_audit(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            action="test_checkout",
            account=account,
            status_before=account.status,
            status_after=account.status,
            details={"result": "failed", "reason": "account_not_connected"},
            error_message=f"Conta {provider_name} nao conectada.",
        )
        raise HTTPException(status_code=400, detail=f"Conta {provider_name} nao conectada.")

    if not _admin_test_checkout_allowed():
        _record_admin_payment_audit(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            action="test_checkout",
            account=account,
            status_before=account.status,
            status_after=account.status,
            details={"result": "blocked", "reason": "production_without_test_flag"},
            error_message="Teste de checkout bloqueado em producao.",
        )
        raise HTTPException(status_code=400, detail="Teste de checkout permitido apenas em sandbox/teste.")

    validation_status_before = account.status
    if normalized_provider == PAYMENT_PROVIDER_MERCADO_PAGO:
        try:
            account = validate_mercadopago_connection(db, establishment_id=establishment_id)
        except ValueError as exc:
            db.rollback()
            if account:
                db.refresh(account)
            _record_admin_payment_audit(
                db,
                establishment_id=establishment_id,
                admin_sub=claims.sub,
                action="test_checkout",
                account=account,
                status_before=validation_status_before,
                status_after=account.status if account else None,
                details={"result": "failed", "reason": "connection_validation_failed"},
                error_message=str(exc),
            )
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif normalized_provider == PAYMENT_PROVIDER_PICPAY:
        if not decrypt_sensitive_value(account.access_token_encrypted):
            raise HTTPException(status_code=400, detail="x-picpay-token nao configurado.")
        if not decrypt_sensitive_value(account.refresh_token_encrypted):
            raise HTTPException(status_code=400, detail="x-seller-token PicPay nao configurado.")
        account.last_sync_at = _utcnow()
        account.updated_at = _utcnow()
        db.commit()
        db.refresh(account)
    else:
        raise HTTPException(status_code=400, detail="Provider de pagamento nao suportado.")

    tested_at = _utcnow()
    _record_admin_payment_audit(
        db,
        establishment_id=establishment_id,
        admin_sub=claims.sub,
        action="test_checkout",
        account=account,
        status_before=account.status,
        status_after=account.status,
        details={"result": "ready", "sandbox": True},
    )
    return AdminPaymentActionResponse(
        status="ready",
        detail=f"Checkout {provider_name} validado em modo sandbox/teste.",
        establishment_id=establishment_id,
        payment_account_id=account.id,
        tested_at=tested_at,
    )


@router.post("/bookings")
def create_booking_with_optional_checkout(
    payload: AgendamentoCreate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        created = criar_agendamento(db, payload, tenant_id=tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    booking = db.query(Agendamento).filter(Agendamento.id == created["id"]).first()
    if not booking:
        raise HTTPException(status_code=500, detail="Falha ao localizar agendamento criado.")
    servico = db.query(Servico).filter(Servico.id == booking.servico_id).first()
    if not servico:
        raise HTTPException(status_code=500, detail="Servico do agendamento nao encontrado.")

    establishment = _get_establishment_or_404(db, tenant_id)

    try:
        apply_payment_snapshot_from_service(booking, servico, establishment)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.commit()
    db.refresh(booking)

    if not booking.payment_required_snapshot:
        return {
            "booking_id": booking.id,
            "booking_status": booking.status,
            "payment_required": False,
            "payment_status": PAYMENT_STATUS_NOT_REQUIRED,
        }

    try:
        payment = start_checkout_for_booking(
            db,
            booking=booking,
            payer_name=booking.cliente_nome,
            payer_email=booking.cliente_email,
            payer_phone=booking.cliente_telefone,
        )
    except ValueError as exc:
        booking.status = BOOKING_STATUS_FAILED
        booking.payment_status = PAYMENT_STATUS_REJECTED
        booking.payment_hold_expires_at = None
        db.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "booking_id": booking.id,
        "booking_status": booking.status,
        "payment_required": True,
        "checkout": _serialize_checkout(payment).model_dump(),
    }


@router.post("/bookings/{booking_id}/checkout", response_model=CheckoutResponse)
def create_or_reuse_booking_checkout(
    booking_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    booking = (
        db.query(Agendamento)
        .filter(
            Agendamento.id == booking_id,
            Agendamento.estabelecimento_id == tenant_id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento nao encontrado.")

    if not booking.payment_required_snapshot:
        servico = db.query(Servico).filter(Servico.id == booking.servico_id).first()
        if servico:
            establishment = _get_establishment_or_404(db, tenant_id)
            apply_payment_snapshot_from_service(booking, servico, establishment)
            db.commit()
            db.refresh(booking)

    if not booking.payment_required_snapshot:
        raise HTTPException(status_code=400, detail="Este agendamento nao exige pagamento adiantado.")

    try:
        payment = start_checkout_for_booking(
            db,
            booking=booking,
            payer_name=booking.cliente_nome,
            payer_email=booking.cliente_email,
            payer_phone=booking.cliente_telefone,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_checkout(payment)


@router.get("/payments/{payment_id}", response_model=PaymentDetailsResponse)
def get_payment_by_id(
    payment_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    payment = (
        db.query(Pagamento)
        .filter(
            Pagamento.id == payment_id,
            Pagamento.estabelecimento_id == tenant_id,
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento nao encontrado.")
    return _serialize_payment(payment)


@router.get("/bookings/{booking_id}/payment-status", response_model=BookingPaymentStatusResponse)
def get_booking_payment_status(
    booking_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    booking = (
        db.query(Agendamento)
        .filter(
            Agendamento.id == booking_id,
            Agendamento.estabelecimento_id == tenant_id,
        )
        .first()
    )
    if not booking:
        raise HTTPException(status_code=404, detail="Agendamento nao encontrado.")

    payment = (
        db.query(Pagamento)
        .filter(
            Pagamento.agendamento_id == booking.id,
            Pagamento.estabelecimento_id == tenant_id,
        )
        .first()
    )
    return BookingPaymentStatusResponse(
        booking_id=booking.id,
        booking_status=booking.status,
        payment_required=bool(booking.payment_required_snapshot),
        payment_status=booking.payment_status,  # type: ignore[arg-type]
        payment_amount=booking.payment_amount_snapshot,
        payment_type=booking.payment_type_snapshot,
        payment_id=payment.id if payment else None,
    )


@router.post("/webhooks/mercadopago")
async def webhook_mercadopago(
    request: Request,
    topic: str | None = Query(default=None),
    webhook_id: str | None = Query(default=None, alias="id"),
    provider_payment_id: str | None = Query(default=None, alias="data.id"),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    signature_header = request.headers.get("x-signature") or request.headers.get("x-hub-signature")
    signature_secret = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "").strip() or None
    request_id = request.headers.get("x-request-id")

    try:
        result = process_mercadopago_webhook(
            db,
            payload=payload,
            raw_body=raw_body,
            provider_payment_id_query=provider_payment_id,
            webhook_id=webhook_id,
            topic=topic,
            signature_header=signature_header,
            signature_secret=signature_secret,
            request_id=request_id,
        )
        if result.get("status") == "forbidden":
            raise HTTPException(status_code=403, detail="Webhook Mercado Pago invalido.")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/webhooks/picpay")
async def webhook_picpay(
    request: Request,
    reference_id: str | None = Query(default=None, alias="referenceId"),
    db: Session = Depends(get_db),
):
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    seller_token_header = request.headers.get("authorization") or request.headers.get("x-seller-token")

    try:
        result = process_picpay_webhook(
            db,
            payload=payload,
            reference_id_query=reference_id,
            seller_token_header=seller_token_header,
        )
        if result.get("status") == "forbidden":
            raise HTTPException(status_code=403, detail="Webhook PicPay invalido.")
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/admin/payments", response_model=AdminPaymentsListResponse)
def admin_list_payments(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    payments = (
        db.query(Pagamento)
        .filter(Pagamento.estabelecimento_id == tenant_id)
        .order_by(Pagamento.created_at.desc())
        .limit(200)
        .all()
    )
    return AdminPaymentsListResponse(items=[_serialize_payment(item) for item in payments])


@router.get("/admin/payments/{payment_id}", response_model=PaymentDetailsResponse)
def admin_get_payment(
    payment_id: int,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    payment = (
        db.query(Pagamento)
        .filter(
            Pagamento.id == payment_id,
            Pagamento.estabelecimento_id == tenant_id,
        )
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Pagamento nao encontrado.")
    return _serialize_payment(payment)


@router.get("/admin/payment-account", response_model=PaymentAccountStatusResponse)
def admin_get_payment_account(
    _claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status_code=400,
        detail="Use /admin/establishments/{id}/payment-account para consultar a conta de pagamento.",
    )


@router.patch("/admin/payment-account/settings", response_model=PaymentAccountStatusResponse)
def admin_update_payment_account_settings(
    payload: PaymentAccountSettingsUpdate,
    _claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    raise HTTPException(
        status_code=400,
        detail="Use /admin/establishments/{id}/payment-account para alterar a conta de pagamento.",
    )
