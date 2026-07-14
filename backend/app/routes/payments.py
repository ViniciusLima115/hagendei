import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import RATE_LIMIT_WEBHOOK, limiter
from app.models.agendamento import Agendamento
from app.models.estabelecimento import Estabelecimento
from app.models.pagamento import Pagamento
from app.models.payment_account import PaymentAccount
from app.models.payment_integration import PaymentIntegration
from app.models.servico import Servico
from app.routes.deps import require_admin, tenant_id_from_header
from app.schemas.agendamento import AgendamentoCreate
from app.schemas.pagamentos import (
    AdminPaymentAccountResponse,
    AdminPaymentAccountStatusUpdate,
    AdminPaymentAccountUpsert,
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
    PaymentAccountSettingsUpdate,
    PaymentAccountStatusResponse,
    PaymentDetailsResponse,
)
from app.services.agendamento_service import criar_agendamento
from app.services.admin_audit_service import create_admin_audit_log
from app.services.payments.constants import (
    PAYMENT_PROVIDER_MERCADO_PAGO,
    PAYMENT_STATUS_NOT_REQUIRED,
)
from app.services.payments.crypto import mask_secret
from app.services.payments.payment_account_service import (
    get_masked_admin_credentials,
    get_payment_account,
    update_payment_account_settings,
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
from app.services.payments.webhook_service import process_mercadopago_webhook


router = APIRouter(tags=["payments"])

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


def _serialize_admin_payment_account(account: PaymentAccount) -> AdminPaymentAccountResponse:
    masked = get_masked_admin_credentials(account)
    return AdminPaymentAccountResponse(
        id=account.id,
        establishment_id=account.establishment_id,
        provider=account.provider,
        environment="production",
        account_name=account.account_name,
        status=account.status,
        client_id_masked=masked["client_id_masked"],
        client_secret_masked=masked["client_secret_masked"],
        access_token_masked=masked["access_token_masked"],
        public_key_masked=masked["public_key_masked"],
        internal_notes=account.internal_notes,
        checkout_hold_minutes=account.checkout_hold_minutes or 10,
        created_by_admin_id=account.created_by_admin_id,
        updated_by_admin_id=account.updated_by_admin_id,
        created_at=account.created_at,
        updated_at=account.updated_at,
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
        payment_id=payment.id,
        booking_id=payment.agendamento_id,
        external_reference=payment.external_reference,
        preference_id=payment.preference_id or "",
        checkout_url=payment.checkout_url or "",
        amount=float(payment.amount or 0),
        payment_status=payment.status,  # type: ignore[arg-type]
        booking_status=booking.status,
        expires_at=payment.expires_at,
    )


def _get_establishment_or_404(db: Session, establishment_id: int) -> Estabelecimento:
    establishment = db.query(Estabelecimento).filter(Estabelecimento.id == establishment_id).first()
    if not establishment:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")
    return establishment


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
        integration = integrations_by_establishment.get(establishment.id)
        account = accounts_by_establishment.get(establishment.id)
        items.append(
            AdminPaymentEstablishmentResponse(
                id=establishment.id,
                nome=establishment.nome,
                slug=establishment.slug,
                login=establishment.login,
                payment_account_status=(
                    integration.status if integration else account.status if account else "not_configured"
                ),
                payment_account_name=(
                    integration.account_name if integration else account.account_name if account else None
                ),
                payment_account_id=integration.id if integration else account.id if account else None,
                payment_environment=integration.environment if integration else None,
                payment_validation_status=integration.validation_status if integration else None,
            )
        )
    return items


@router.get(
    "/admin/establishments/{establishment_id}/payment-integrations",
    response_model=list[AdminPaymentIntegrationResponse],
)
def admin_list_establishment_payment_integrations(
    establishment_id: int,
    request: Request,
    _claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=False)
    _get_establishment_or_404(db, establishment_id)
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
    if not account:
        raise HTTPException(status_code=404, detail="Conta de pagamento nao configurada.")
    return _serialize_admin_payment_account(account)


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
    existing = get_payment_integration(
        db,
        establishment_id=establishment_id,
        provider=payload.provider,
        environment=payload.environment,
    )
    try:
        integration = upsert_admin_payment_integration(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=payload.provider,
            environment=payload.environment,
            account_name=payload.account_name,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            access_token=payload.access_token,
            public_key=payload.public_key,
            webhook_secret=payload.webhook_secret,
            status=payload.status,
            internal_notes=payload.internal_notes,
            checkout_hold_minutes=payload.checkout_hold_minutes,
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
    return _serialize_admin_payment_integration(integration)


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
    existing = get_payment_integration(
        db,
        establishment_id=establishment_id,
        provider=payload.provider,
        environment=payload.environment,
    )
    try:
        integration = upsert_admin_payment_integration(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=payload.provider,
            environment=payload.environment,
            account_name=payload.account_name,
            client_id=payload.client_id,
            client_secret=payload.client_secret,
            access_token=payload.access_token,
            public_key=payload.public_key,
            webhook_secret=payload.webhook_secret,
            status=payload.status,
            internal_notes=payload.internal_notes,
            checkout_hold_minutes=payload.checkout_hold_minutes,
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
    return _serialize_admin_payment_integration(integration)


@router.patch("/admin/establishments/{establishment_id}/payment-account/status", response_model=AdminPaymentAccountResponse)
def admin_update_establishment_payment_account_status(
    establishment_id: int,
    request: Request,
    payload: AdminPaymentAccountStatusUpdate,
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
        action="payment_credentials_disabled" if integration.status in {"inactive", "disconnected"} else "payment_credentials_updated",
        integration=integration,
    )
    return _serialize_admin_payment_integration(integration)


@router.delete("/admin/establishments/{establishment_id}/payment-account", status_code=204)
def admin_remove_establishment_payment_account(
    establishment_id: int,
    request: Request,
    claims=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_secure_admin_payment_request(request, has_body=False)
    _get_establishment_or_404(db, establishment_id)
    try:
        integration = update_admin_payment_integration_status(
            db,
            establishment_id=establishment_id,
            admin_sub=claims.sub,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            environment="production",
            status="disconnected",
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    _audit_payment_integration_action(
        db,
        request=request,
        admin_user_id=claims.sub,
        establishment_id=establishment_id,
        action="payment_credentials_disabled",
        integration=integration,
    )
    return None


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

    try:
        apply_payment_snapshot_from_service(booking, servico)
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
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            payer_name=booking.cliente_nome,
            payer_email=booking.cliente_email,
            payer_phone=booking.cliente_telefone,
        )
    except ValueError as exc:
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
            apply_payment_snapshot_from_service(booking, servico)
            db.commit()
            db.refresh(booking)

    if not booking.payment_required_snapshot:
        raise HTTPException(status_code=400, detail="Este agendamento nao exige pagamento adiantado.")

    try:
        payment = start_checkout_for_booking(
            db,
            booking=booking,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
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

    payment = db.query(Pagamento).filter(Pagamento.agendamento_id == booking.id).first()
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
    raw_body = await request.body()
    if len(raw_body) > 65536:
        raise HTTPException(status_code=413, detail="Payload de webhook excede o limite permitido.")
    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    signature_header = request.headers.get("x-signature")
    request_id_header = request.headers.get("x-request-id")

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
