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
from app.limiter import RATE_LIMIT_WEBHOOK, limiter
from app.models.agendamento import Agendamento
from app.models.estabelecimento import Estabelecimento
from app.models.pagamento import Pagamento
from app.models.payment_account import PaymentAccount
<<<<<<< HEAD
from app.models.payment_integration import PaymentIntegration
=======
from app.models.payment_admin_audit_log import PaymentAdminAuditLog
from app.models.payment_webhook_event import PaymentWebhookEvent
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
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
    AdminPaymentIntegrationDisableRequest,
    AdminPaymentIntegrationPatch,
    AdminPaymentIntegrationResponse,
    AdminPaymentIntegrationTestCheckoutRequest,
    AdminPaymentIntegrationTestCheckoutResponse,
    AdminPaymentIntegrationUpsert,
    AdminPaymentIntegrationValidateRequest,
    AdminPaymentIntegrationValidateResponse,
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
from app.services.admin_audit_service import create_admin_audit_log
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
<<<<<<< HEAD
=======
    start_connect_flow,
    update_admin_payment_account_status,
    upsert_admin_payment_account,
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
    update_payment_account_settings,
    validate_mercadopago_connection,
)
from app.services.payments.payment_integration_service import (
    create_admin_payment_integration_test_checkout,
    get_payment_integration_credentials,
    get_masked_admin_integration_credentials,
    get_payment_integration,
    get_preferred_payment_integration,
    validate_admin_payment_integration,
    update_admin_payment_integration_status,
    upsert_admin_payment_integration,
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

MAX_ADMIN_PAYMENT_PAYLOAD_BYTES = 8 * 1024
SENSITIVE_QUERY_PARAM_KEYS = {
    "access_token",
    "public_key",
    "client_secret",
    "webhook_secret",
    "credentials_encrypted",
}


def _request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _request_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _ensure_secure_admin_payment_request(request: Request, *, has_body: bool) -> None:
    for key in request.query_params.keys():
        if key.strip().lower() in SENSITIVE_QUERY_PARAM_KEYS:
            raise HTTPException(status_code=400, detail="Credenciais nao podem ser enviadas na URL.")

    if has_body:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_ADMIN_PAYMENT_PAYLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Payload de credenciais muito grande.")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Content-Length invalido.") from exc

    app_env = os.getenv("APP_ENV", "").strip().lower()
    if app_env in {"prod", "production"}:
        scheme = (request.url.scheme or "").strip().lower()
        if scheme != "https":
            raise HTTPException(status_code=400, detail="Operacao administrativa sensivel exige HTTPS em producao.")


def _audit_payment_integration_action(
    db: Session,
    *,
    request: Request,
    admin_user_id: str | None,
    establishment_id: int,
    action: str,
    integration: PaymentIntegration | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    base_metadata: dict[str, Any] = {
        "result": "success",
        "correlation_id": request.headers.get("x-request-id"),
    }
    if integration:
        base_metadata.update(
            {
                "provider": integration.provider,
                "environment": integration.environment,
                "status": integration.status,
                "validation_status": integration.validation_status,
            }
        )
    if metadata:
        base_metadata.update(metadata)

    create_admin_audit_log(
        db,
        admin_user_id=admin_user_id,
        establishment_id=establishment_id,
        action=action,
        entity_type="payment_integration",
        entity_id=integration.id if integration else None,
        ip_address=_request_ip(request),
        user_agent=_request_user_agent(request),
        metadata=base_metadata,
    )


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
        environment="production",
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


def _serialize_admin_payment_integration(integration: PaymentIntegration) -> AdminPaymentAccountResponse:
    masked = get_masked_admin_integration_credentials(integration)
    return AdminPaymentAccountResponse(
        id=integration.id,
        establishment_id=integration.establishment_id,
        provider=integration.provider,
        environment=integration.environment,
        account_name=integration.account_name,
        status=integration.status,
        client_id_masked=masked["client_id_masked"],
        client_secret_masked=masked["client_secret_masked"],
        access_token_masked=masked["access_token_masked"],
        webhook_secret_masked=masked["webhook_secret_masked"],
        public_key_masked=masked["public_key_masked"],
        internal_notes=masked["internal_notes"],
        checkout_hold_minutes=integration.checkout_hold_minutes or 10,
        validation_status=integration.validation_status,
        validation_error=integration.validation_error,
        last_validated_at=integration.last_validated_at,
        connected_at=integration.connected_at,
        disconnected_at=integration.disconnected_at,
        created_by_admin_id=integration.created_by_admin_id,
        updated_by_admin_id=integration.updated_by_admin_id,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
    )


def _serialize_admin_payment_integration_status(integration: PaymentIntegration) -> AdminPaymentIntegrationResponse:
    masked = get_masked_admin_integration_credentials(integration)
    credentials = get_payment_integration_credentials(integration)
    return AdminPaymentIntegrationResponse(
        provider=integration.provider,
        environment=integration.environment,
        status=integration.status,
        validation_status=integration.validation_status,
        last_validated_at=integration.last_validated_at,
        connected_at=integration.connected_at,
        updated_at=integration.updated_at,
        updated_by=integration.updated_by_admin_id,
        public_key_masked=masked["public_key_masked"],
        access_token_masked=masked["access_token_masked"],
        webhook_secret_masked=masked["webhook_secret_masked"],
        has_client_id=bool(credentials.get("client_id")),
        has_client_secret=bool(credentials.get("client_secret")),
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


<<<<<<< HEAD
def _get_mercadopago_integration_or_404(
    db: Session,
    *,
    establishment_id: int,
    environment: str,
) -> PaymentIntegration:
    try:
        integration = get_payment_integration(
            db,
            establishment_id=establishment_id,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            environment=environment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not integration:
        raise HTTPException(status_code=404, detail="Integracao Mercado Pago nao configurada.")
    return integration
=======
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
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478


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
    integrations = (
        db.query(PaymentIntegration)
        .filter(PaymentIntegration.provider == PAYMENT_PROVIDER_MERCADO_PAGO)
        .all()
    )
    accounts = (
        db.query(PaymentAccount)
        .filter(PaymentAccount.provider == PAYMENT_PROVIDER_MERCADO_PAGO)
        .all()
    )

    integrations_by_establishment: dict[int, PaymentIntegration] = {}
    for integration in integrations:
        current = integrations_by_establishment.get(integration.establishment_id)
        if (
            current is None
            or (integration.status == "active" and current.status != "active")
            or (
                integration.status == current.status
                and integration.environment == "production"
                and current.environment != "production"
            )
        ):
            integrations_by_establishment[integration.establishment_id] = integration

    accounts_by_establishment = {account.establishment_id: account for account in accounts}
    items: list[AdminPaymentEstablishmentResponse] = []
    for establishment in establishments:
<<<<<<< HEAD
        integration = integrations_by_establishment.get(establishment.id)
        account = accounts_by_establishment.get(establishment.id)
=======
        account = _get_admin_primary_payment_account(db, establishment.id)
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
        items.append(
            AdminPaymentEstablishmentResponse(
                id=establishment.id,
                nome=establishment.nome,
                slug=establishment.slug,
                login=establishment.login,
<<<<<<< HEAD
                payment_account_status=(
                    integration.status if integration else account.status if account else "not_configured"
                ),
                payment_account_name=(
                    integration.account_name if integration else account.account_name if account else None
                ),
                payment_account_id=integration.id if integration else account.id if account else None,
                payment_environment=integration.environment if integration else None,
                payment_validation_status=integration.validation_status if integration else None,
=======
                provider=account.provider if account else None,
                payment_account_status=account.status if account else "not_configured",
                payment_account_name=account.account_name if account else None,
                payment_account_id=account.id if account else None,
                connected_at=account.connected_at if account else None,
                updated_at=account.updated_at if account else None,
                last_error=_latest_admin_payment_error(db, establishment.id),
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
            )
        )
    return items


@router.get(
    "/admin/establishments/{establishment_id}/payment-integrations",
    response_model=list[AdminPaymentIntegrationResponse],
)
def admin_list_establishment_payment_integrations(
    establishment_id: int,
<<<<<<< HEAD
    request: Request,
=======
    provider: str = Query(default=PAYMENT_PROVIDER_MERCADO_PAGO),
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
    _claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=False)
    _get_establishment_or_404(db, establishment_id)
<<<<<<< HEAD
    integrations = (
        db.query(PaymentIntegration)
        .filter(PaymentIntegration.establishment_id == establishment_id)
        .order_by(PaymentIntegration.provider.asc(), PaymentIntegration.environment.asc())
        .all()
    )
    return [_serialize_admin_payment_integration_status(item) for item in integrations]


@router.post(
    "/admin/establishments/{establishment_id}/payment-integrations/mercado-pago",
    response_model=AdminPaymentIntegrationResponse,
)
def admin_create_establishment_mercadopago_integration(
    establishment_id: int,
    request: Request,
    payload: AdminPaymentIntegrationUpsert,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=True)
    _get_establishment_or_404(db, establishment_id)
    existing = get_payment_integration(
        db,
        establishment_id=establishment_id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        environment=payload.environment,
    )
    try:
        integration = upsert_admin_payment_integration(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            environment=payload.environment,
            public_key=payload.public_key,
            access_token=payload.access_token,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            webhook_secret=payload.webhook_secret,
            internal_notes=payload.notes,
            status=payload.status,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit_payment_integration_action(
        db,
        request=request,
        admin_user_id=claims.sub,
        establishment_id=establishment_id,
        action="payment_credentials_updated" if existing else "payment_credentials_created",
        integration=integration,
    )
    return _serialize_admin_payment_integration_status(integration)


@router.put(
    "/admin/establishments/{establishment_id}/payment-integrations/mercado-pago",
    response_model=AdminPaymentIntegrationResponse,
)
def admin_put_establishment_mercadopago_integration(
    establishment_id: int,
    request: Request,
    payload: AdminPaymentIntegrationUpsert,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    return admin_create_establishment_mercadopago_integration(
        establishment_id=establishment_id,
        request=request,
        payload=payload,
        claims=claims,
        db=db,
    )


@router.patch(
    "/admin/establishments/{establishment_id}/payment-integrations/mercado-pago",
    response_model=AdminPaymentIntegrationResponse,
)
def admin_patch_establishment_mercadopago_integration(
    establishment_id: int,
    request: Request,
    payload: AdminPaymentIntegrationPatch,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=True)
    _get_establishment_or_404(db, establishment_id)
    existing = get_payment_integration(
        db,
        establishment_id=establishment_id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        environment=payload.environment,
    )
    clear_fields: set[str] = set()
    if payload.clear_public_key:
        clear_fields.add("public_key")
    if payload.clear_client_id:
        clear_fields.add("client_id")
    if payload.clear_client_secret:
        clear_fields.add("client_secret")
    if payload.clear_webhook_secret:
        clear_fields.add("webhook_secret")
    if payload.clear_notes:
        clear_fields.add("notes")

    try:
        integration = upsert_admin_payment_integration(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            environment=payload.environment,
            public_key=payload.public_key,
            access_token=payload.access_token,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            webhook_secret=payload.webhook_secret,
            internal_notes=payload.notes,
            status=payload.status or (existing.status if existing else "active"),
            clear_fields=clear_fields,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit_payment_integration_action(
        db,
        request=request,
        admin_user_id=claims.sub,
        establishment_id=establishment_id,
        action="payment_credentials_updated" if existing else "payment_credentials_created",
        integration=integration,
        metadata={"cleared_fields_count": len(clear_fields)},
    )
    return _serialize_admin_payment_integration_status(integration)


@router.post(
    "/admin/establishments/{establishment_id}/payment-integrations/mercado-pago/disable",
    response_model=AdminPaymentIntegrationResponse,
)
def admin_disable_establishment_mercadopago_integration(
    establishment_id: int,
    request: Request,
    payload: AdminPaymentIntegrationDisableRequest,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=True)
    _get_establishment_or_404(db, establishment_id)
    try:
        integration = update_admin_payment_integration_status(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            environment=payload.environment,
            status=payload.status,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit_payment_integration_action(
        db,
        request=request,
        admin_user_id=claims.sub,
        establishment_id=establishment_id,
        action="payment_credentials_disabled",
        integration=integration,
    )
    return _serialize_admin_payment_integration_status(integration)


@router.post(
    "/admin/establishments/{establishment_id}/payment-integrations/mercado-pago/validate",
    response_model=AdminPaymentIntegrationValidateResponse,
)
def admin_validate_establishment_mercadopago_integration(
    establishment_id: int,
    request: Request,
    payload: AdminPaymentIntegrationValidateRequest,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=True)
    _get_establishment_or_404(db, establishment_id)
    integration = _get_mercadopago_integration_or_404(
        db,
        establishment_id=establishment_id,
        environment=payload.environment,
    )
    try:
        valid, validation_status, message, validated_at = validate_admin_payment_integration(
            db,
            integration=integration,
            admin_sub=claims.sub,
        )
    except ValueError as exc:
        db.rollback()
        _audit_payment_integration_action(
            db,
            request=request,
            admin_user_id=claims.sub,
            establishment_id=establishment_id,
            action="payment_credentials_validation_failed",
            integration=integration,
            metadata={"reason": str(exc)[:160]},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit_payment_integration_action(
        db,
        request=request,
        admin_user_id=claims.sub,
        establishment_id=establishment_id,
        action="payment_credentials_validated" if valid else "payment_credentials_validation_failed",
        integration=integration,
        metadata={"valid": valid},
    )
    return AdminPaymentIntegrationValidateResponse(
        valid=valid,
        validation_status=validation_status,  # type: ignore[arg-type]
        message=message,
        last_validated_at=validated_at,
    )


@router.post(
    "/admin/establishments/{establishment_id}/payment-integrations/mercado-pago/test-checkout",
    response_model=AdminPaymentIntegrationTestCheckoutResponse,
)
def admin_test_checkout_establishment_mercadopago_integration(
    establishment_id: int,
    request: Request,
    payload: AdminPaymentIntegrationTestCheckoutRequest,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=True)
    _get_establishment_or_404(db, establishment_id)
    integration = _get_mercadopago_integration_or_404(
        db,
        establishment_id=establishment_id,
        environment=payload.environment,
    )
    try:
        checkout = create_admin_payment_integration_test_checkout(
            db,
            integration=integration,
            admin_sub=claims.sub,
            confirm_production=payload.confirm_production,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _audit_payment_integration_action(
        db,
        request=request,
        admin_user_id=claims.sub,
        establishment_id=establishment_id,
        action="payment_checkout_test_created",
        integration=integration,
        metadata={"checkout_status": "created"},
    )
    return AdminPaymentIntegrationTestCheckoutResponse(
        provider=integration.provider,
        environment=integration.environment,
        preference_id=checkout["preference_id"],
        checkout_url=checkout["checkout_url"],
        status="created",
    )


@router.get("/admin/establishments/{establishment_id}/payment-account", response_model=AdminPaymentAccountResponse)
def admin_get_establishment_payment_account(
    establishment_id: int,
    request: Request,
    environment: str | None = Query(default=None),
    _claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=False)
    _get_establishment_or_404(db, establishment_id)
    try:
        integration = (
            get_payment_integration(
                db,
                establishment_id=establishment_id,
                provider=PAYMENT_PROVIDER_MERCADO_PAGO,
                environment=environment or "production",
            )
            if environment
            else get_preferred_payment_integration(
                db,
                establishment_id=establishment_id,
                provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if integration:
        return _serialize_admin_payment_integration(integration)

    account = get_payment_account(db, establishment_id=establishment_id, provider=PAYMENT_PROVIDER_MERCADO_PAGO)
=======
    account = _get_admin_payment_account(db, establishment_id=establishment_id, provider=provider)
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
    if not account:
        raise HTTPException(status_code=404, detail="Conta de pagamento nao configurada.")
    return _serialize_admin_payment_account(db, account)


@router.post("/admin/establishments/{establishment_id}/payment-account", response_model=AdminPaymentAccountResponse)
def admin_create_establishment_payment_account(
    establishment_id: int,
    request: Request,
    payload: AdminPaymentAccountUpsert,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=True)
    _get_establishment_or_404(db, establishment_id)
<<<<<<< HEAD
    existing = get_payment_integration(
        db,
        establishment_id=establishment_id,
        provider=payload.provider,
        environment=payload.environment,
    )
=======
    previous = get_payment_account(db, establishment_id=establishment_id, provider=payload.provider)
    status_before = previous.status if previous else None
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
    try:
        integration = upsert_admin_payment_integration(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=payload.provider,
            environment=payload.environment,
            account_name=payload.account_name,
            provider_account_id=payload.provider_account_id,
            provider_account_email=payload.provider_account_email,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            public_key=payload.public_key,
            webhook_secret=payload.webhook_secret,
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
<<<<<<< HEAD
    _audit_payment_integration_action(
        db,
        request=request,
        admin_user_id=claims.sub,
        establishment_id=establishment_id,
        action="payment_credentials_updated" if existing else "payment_credentials_created",
        integration=integration,
    )
    return _serialize_admin_payment_integration(integration)
=======
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
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478


@router.patch("/admin/establishments/{establishment_id}/payment-account", response_model=AdminPaymentAccountResponse)
def admin_update_establishment_payment_account(
    establishment_id: int,
    request: Request,
    payload: AdminPaymentAccountUpsert,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=True)
    _get_establishment_or_404(db, establishment_id)
<<<<<<< HEAD
    existing = get_payment_integration(
        db,
        establishment_id=establishment_id,
        provider=payload.provider,
        environment=payload.environment,
    )
=======
    previous = get_payment_account(db, establishment_id=establishment_id, provider=payload.provider)
    status_before = previous.status if previous else None
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
    try:
        integration = upsert_admin_payment_integration(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=payload.provider,
            environment=payload.environment,
            account_name=payload.account_name,
            provider_account_id=payload.provider_account_id,
            provider_account_email=payload.provider_account_email,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            access_token=payload.access_token,
            refresh_token=payload.refresh_token,
            public_key=payload.public_key,
            webhook_secret=payload.webhook_secret,
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
<<<<<<< HEAD
    _audit_payment_integration_action(
        db,
        request=request,
        admin_user_id=claims.sub,
        establishment_id=establishment_id,
        action="payment_credentials_updated" if existing else "payment_credentials_created",
        integration=integration,
    )
    return _serialize_admin_payment_integration(integration)
=======
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
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478


@router.patch("/admin/establishments/{establishment_id}/payment-account/status", response_model=AdminPaymentAccountResponse)
def admin_update_establishment_payment_account_status(
    establishment_id: int,
    request: Request,
    payload: AdminPaymentAccountStatusUpdate,
    provider: str = Query(default=PAYMENT_PROVIDER_MERCADO_PAGO),
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=True)
    _get_establishment_or_404(db, establishment_id)
    normalized_provider = normalize_payment_provider(provider)
    previous = get_payment_account(db, establishment_id=establishment_id, provider=normalized_provider)
    status_before = previous.status if previous else None
    try:
        integration = update_admin_payment_integration_status(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
<<<<<<< HEAD
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            environment=payload.environment,
=======
            provider=normalized_provider,
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
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
<<<<<<< HEAD
    _audit_payment_integration_action(
        db,
        request=request,
        admin_user_id=claims.sub,
        establishment_id=establishment_id,
        action="payment_credentials_disabled" if integration.status in {"inactive", "disconnected"} else "payment_credentials_updated",
        integration=integration,
    )
    return _serialize_admin_payment_integration(integration)
=======
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
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478


@router.delete("/admin/establishments/{establishment_id}/payment-account", status_code=204)
def admin_remove_establishment_payment_account(
    establishment_id: int,
<<<<<<< HEAD
    request: Request,
=======
    provider: str = Query(default=PAYMENT_PROVIDER_MERCADO_PAGO),
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=False)
    _get_establishment_or_404(db, establishment_id)
    normalized_provider = normalize_payment_provider(provider)
    previous = get_payment_account(db, establishment_id=establishment_id, provider=normalized_provider)
    status_before = previous.status if previous else None
    try:
<<<<<<< HEAD
        integration = update_admin_payment_integration_status(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            environment="production",
            status="disconnected",
=======
        account = update_admin_payment_account_status(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=normalized_provider,
            status=PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
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
<<<<<<< HEAD
    _audit_payment_integration_action(
        db,
        request=request,
        admin_user_id=claims.sub,
        establishment_id=establishment_id,
        action="payment_credentials_disabled",
        integration=integration,
=======
    _record_admin_payment_audit(
        db,
        establishment_id=establishment_id,
        admin_sub=claims.sub,
        action="deactivate",
        account=account,
        status_before=status_before,
        status_after=account.status,
        details={"provider": account.provider},
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
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
@limiter.limit(RATE_LIMIT_WEBHOOK)
async def webhook_mercadopago(
    request: Request,
    topic: str | None = Query(default=None),
    webhook_id: str | None = Query(default=None, alias="id"),
    provider_payment_id: str | None = Query(default=None, alias="data.id"),
<<<<<<< HEAD
    external_reference: str | None = Query(default=None),
    payment_id: int | None = Query(default=None),
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if token is not None:
        raise HTTPException(status_code=400, detail="Webhook token via query param nao e permitido.")
    if payment_id is not None:
        raise HTTPException(status_code=400, detail="Use external_reference ou data.id para localizar o pagamento.")

    content_length = request.headers.get("content-length", "")
    if content_length.isdigit() and int(content_length) > 65536:
        raise HTTPException(status_code=413, detail="Payload de webhook excede o limite permitido.")
=======
    db: Session = Depends(get_db),
):
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
    raw_body = await request.body()
    if len(raw_body) > 65536:
        raise HTTPException(status_code=413, detail="Payload de webhook excede o limite permitido.")
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

<<<<<<< HEAD
    signature_header = request.headers.get("x-signature")
    request_id_header = request.headers.get("x-request-id")
=======
    signature_header = request.headers.get("x-signature") or request.headers.get("x-hub-signature")
    signature_secret = os.getenv("MERCADOPAGO_WEBHOOK_SECRET", "").strip() or None
    request_id = request.headers.get("x-request-id")
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478

    try:
        result = process_mercadopago_webhook(
            db,
            payload=payload,
            raw_body=raw_body,
            provider_payment_id_query=provider_payment_id,
            external_reference_query=external_reference,
            webhook_id=webhook_id,
            topic=topic,
            signature_header=signature_header,
<<<<<<< HEAD
            request_id_header=request_id_header,
        )
        if result.get("reason") == "assinatura_invalida":
            raise HTTPException(status_code=401, detail="Assinatura de webhook invalida.")
        if result.get("status") == "failed" and result.get("reason") in {
            "sem_payment_id",
            "payment_id_query_divergente",
        }:
            raise HTTPException(status_code=400, detail="Webhook invalido.")
        if result.get("reason") == "provider_indisponivel":
            raise HTTPException(status_code=503, detail="Provider temporariamente indisponivel.")
=======
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
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
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
