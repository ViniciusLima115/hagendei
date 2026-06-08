import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import get_frontend_url
from app.models.estabelecimento import Estabelecimento
from app.routes.deps import get_current_claims, tenant_id_from_header
from app.schemas.pagamentos import (
    MercadoPagoConnectResponse,
    PaymentAccountSettingsUpdate,
    PaymentAccountStatusResponse,
)
from app.security import TokenClaims
from app.services.payments.constants import (
    PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
    PAYMENT_PROVIDER_MERCADO_PAGO,
    PAYMENT_PROVIDER_PICPAY,
    SUPPORTED_PAYMENT_PROVIDERS,
    is_payment_account_connected,
    normalize_payment_provider,
)
from app.services.payments.crypto import mask_secret
from app.services.payments.payment_account_service import (
    STATE_TTL_MINUTES,
    disconnect_payment_account,
    finalize_oauth_callback,
    get_payment_account,
    start_connect_flow,
    update_payment_account_settings,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


def _require_tenant_claims(claims: TokenClaims) -> int:
    if claims.is_admin or claims.tenant_id is None:
        raise HTTPException(status_code=403, detail="Apenas estabelecimentos podem usar esta rota.")
    return claims.tenant_id


def _default_payment_type(establishment: Estabelecimento | None) -> str | None:
    payment_type = (getattr(establishment, "advance_payment_type", None) or "").strip().lower()
    if payment_type in {"full", "signal"}:
        return payment_type
    if bool(getattr(establishment, "pagamento_adiantado_obrigatorio", False)):
        return "full"
    return None


def _serialize_status_response(
    account,
    *,
    tenant_id: int,
    establishment: Estabelecimento | None = None,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
) -> PaymentAccountStatusResponse:
    normalized_provider = normalize_payment_provider(provider)
    payment_required_default = bool(getattr(establishment, "pagamento_adiantado_obrigatorio", False))
    advance_payment_type = _default_payment_type(establishment)
    default_provider = (
        getattr(establishment, "payment_default_provider", None)
        or PAYMENT_PROVIDER_MERCADO_PAGO
    )

    if not account:
        return PaymentAccountStatusResponse(
            connected=False,
            provider=normalized_provider,
            status=PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
            establishment_id=tenant_id,
            pix_enabled=True,
            card_enabled=True,
            payment_required_default=payment_required_default,
            advance_payment_type=advance_payment_type,
            advance_payment_amount=getattr(establishment, "advance_payment_amount", None),
            default_provider=default_provider,
        )

    provider_account_email_masked = mask_secret(account.provider_account_email, head=3, tail=7)
    provider_account_id_masked = mask_secret(account.provider_account_id)
    connected = is_payment_account_connected(account.status)
    return PaymentAccountStatusResponse(
        connected=connected,
        provider=account.provider,
        status=account.status,
        establishment_id=account.establishment_id,
        provider_account_email_masked=provider_account_email_masked,
        provider_account_id_masked=provider_account_id_masked,
        external_account_email_masked=provider_account_email_masked,
        external_user_id_masked=provider_account_id_masked,
        last_sync_at=account.last_sync_at,
        connected_at=account.connected_at,
        disconnected_at=account.disconnected_at,
        expires_at=account.expires_at,
        token_expires_at=account.expires_at,
        checkout_hold_minutes=account.checkout_hold_minutes or 10,
        pix_enabled=True,
        card_enabled=True,
        payment_required_default=payment_required_default,
        advance_payment_type=advance_payment_type,
        advance_payment_amount=getattr(establishment, "advance_payment_amount", None),
        default_provider=default_provider,
    )


def _get_tenant_establishment(db: Session, tenant_id: int) -> Estabelecimento:
    establishment = db.query(Estabelecimento).filter(Estabelecimento.id == tenant_id).first()
    if not establishment:
        raise HTTPException(status_code=404, detail="Estabelecimento nao encontrado.")
    return establishment


def _apply_payment_settings(establishment: Estabelecimento, payload: PaymentAccountSettingsUpdate) -> None:
    default_provider = normalize_payment_provider(
        payload.default_provider
        or getattr(establishment, "payment_default_provider", None)
        or PAYMENT_PROVIDER_MERCADO_PAGO
    )
    if default_provider not in SUPPORTED_PAYMENT_PROVIDERS:
        raise ValueError("Provider de pagamento nao suportado.")

    payment_required = (
        payload.payment_required_default
        if payload.payment_required_default is not None
        else bool(getattr(establishment, "pagamento_adiantado_obrigatorio", False))
    )
    payment_type = (
        payload.advance_payment_type
        or getattr(establishment, "advance_payment_type", None)
        or "full"
    )
    payment_type = payment_type.strip().lower()
    if payment_type not in {"full", "signal"}:
        raise ValueError("Tipo de pagamento invalido.")

    amount = (
        payload.advance_payment_amount
        if payload.advance_payment_amount is not None
        else getattr(establishment, "advance_payment_amount", None)
    )
    if payment_required and payment_type == "signal":
        if amount is None or float(amount) <= 0:
            raise ValueError("Informe um valor de sinal maior que zero.")

    establishment.pagamento_adiantado_obrigatorio = bool(payment_required)
    establishment.advance_payment_type = payment_type if payment_required else None
    establishment.advance_payment_amount = float(amount) if payment_required and payment_type == "signal" and amount is not None else None
    establishment.payment_default_provider = default_provider


@router.post("/mercadopago/connect", response_model=MercadoPagoConnectResponse)
def connect_mercadopago(
    claims: TokenClaims = Depends(get_current_claims),
    db: Session = Depends(get_db),
):
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


@router.get("/mercadopago/callback")
def callback_mercadopago(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    frontend_url = get_frontend_url()

    if error:
        logger.warning("Callback Mercado Pago retornou erro OAuth.")
        return RedirectResponse(
            url=f"{frontend_url}/painel/pagamentos?status=error",
            status_code=302,
        )
    if not code or not state:
        return RedirectResponse(
            url=f"{frontend_url}/painel/pagamentos?status=error",
            status_code=302,
        )

    try:
        finalize_oauth_callback(
            db,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
            state=state,
            code=code,
        )
    except ValueError as exc:
        logger.warning("Falha segura no callback Mercado Pago: %s", exc)
        return RedirectResponse(
            url=f"{frontend_url}/painel/pagamentos?status=error",
            status_code=302,
        )

    return RedirectResponse(
        url=f"{frontend_url}/painel/pagamentos?status=connected",
        status_code=302,
    )


@router.get("/mercadopago/status", response_model=PaymentAccountStatusResponse)
def status_mercadopago(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    establishment = _get_tenant_establishment(db, tenant_id)
    account = get_payment_account(
        db,
        establishment_id=tenant_id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
    )
    if not account:
        return _serialize_status_response(
            None,
            tenant_id=tenant_id,
            establishment=establishment,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        )
    return _serialize_status_response(account, tenant_id=tenant_id, establishment=establishment)


@router.post("/mercadopago/disconnect", response_model=PaymentAccountStatusResponse)
def disconnect_mercadopago(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    establishment = _get_tenant_establishment(db, tenant_id)
    account = disconnect_payment_account(
        db,
        establishment_id=tenant_id,
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
    )
    if not account:
        return _serialize_status_response(
            None,
            tenant_id=tenant_id,
            establishment=establishment,
            provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        )
    return _serialize_status_response(account, tenant_id=tenant_id, establishment=establishment)


@router.patch("/mercadopago/settings", response_model=PaymentAccountStatusResponse)
def update_mercadopago_settings(
    payload: PaymentAccountSettingsUpdate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    establishment = _get_tenant_establishment(db, tenant_id)
    try:
        _apply_payment_settings(establishment, payload)
        settings_provider = normalize_payment_provider(payload.default_provider or PAYMENT_PROVIDER_MERCADO_PAGO)
        account = update_payment_account_settings(
            db,
            establishment_id=tenant_id,
            provider=settings_provider,
            checkout_hold_minutes=payload.checkout_hold_minutes,
            status=payload.status,
        )
        db.add(establishment)
        db.commit()
        db.refresh(establishment)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_status_response(account, tenant_id=tenant_id, establishment=establishment)


@router.get("/picpay/status", response_model=PaymentAccountStatusResponse)
def status_picpay(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    establishment = _get_tenant_establishment(db, tenant_id)
    account = get_payment_account(
        db,
        establishment_id=tenant_id,
        provider=PAYMENT_PROVIDER_PICPAY,
    )
    if not account:
        return _serialize_status_response(
            None,
            tenant_id=tenant_id,
            establishment=establishment,
            provider=PAYMENT_PROVIDER_PICPAY,
        )
    return _serialize_status_response(account, tenant_id=tenant_id, establishment=establishment)


@router.post("/picpay/disconnect", response_model=PaymentAccountStatusResponse)
def disconnect_picpay(
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    establishment = _get_tenant_establishment(db, tenant_id)
    account = disconnect_payment_account(
        db,
        establishment_id=tenant_id,
        provider=PAYMENT_PROVIDER_PICPAY,
    )
    if not account:
        return _serialize_status_response(
            None,
            tenant_id=tenant_id,
            establishment=establishment,
            provider=PAYMENT_PROVIDER_PICPAY,
        )
    return _serialize_status_response(account, tenant_id=tenant_id, establishment=establishment)


@router.patch("/picpay/settings", response_model=PaymentAccountStatusResponse)
def update_picpay_settings(
    payload: PaymentAccountSettingsUpdate,
    tenant_id: int = Depends(tenant_id_from_header),
    db: Session = Depends(get_db),
):
    establishment = _get_tenant_establishment(db, tenant_id)
    try:
        _apply_payment_settings(establishment, payload)
        account = update_payment_account_settings(
            db,
            establishment_id=tenant_id,
            provider=PAYMENT_PROVIDER_PICPAY,
            checkout_hold_minutes=payload.checkout_hold_minutes,
            status=payload.status,
        )
        db.add(establishment)
        db.commit()
        db.refresh(establishment)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_status_response(account, tenant_id=tenant_id, establishment=establishment)
