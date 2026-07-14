import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from uuid import uuid4
from urllib.parse import urlencode

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.agendamento import Agendamento
from app.models.pagamento import Pagamento
from app.models.servico import Servico
from app.repositories import notificacao_repository as notificacao_repo
from app.services.payments.constants import (
    BOOKING_STATUS_CANCELLED,
    BOOKING_STATUS_CONFIRMED,
    BOOKING_STATUS_EXPIRED,
    BOOKING_STATUS_FAILED,
    BOOKING_STATUS_PENDING_PAYMENT,
    BOOKING_STATUS_PAYMENT_REVIEW,
    PAYMENT_PROVIDER_MERCADO_PAGO,
    PAYMENT_STATUS_APPROVED,
    PAYMENT_STATUS_CANCELLED,
    PAYMENT_STATUS_CHARGED_BACK,
    PAYMENT_STATUS_EXPIRED,
    PAYMENT_STATUS_NOT_REQUIRED,
    PAYMENT_STATUS_PENDING,
    PAYMENT_STATUS_REFUNDED,
    PAYMENT_STATUS_REJECTED,
)
from app.services.payments.payment_integration_service import get_active_payment_credentials
from app.services.payments.provider_factory import get_payment_provider


logger = logging.getLogger(__name__)

PAYMENT_FINAL_STATUSES = {
    PAYMENT_STATUS_APPROVED,
    PAYMENT_STATUS_REJECTED,
    PAYMENT_STATUS_CANCELLED,
    PAYMENT_STATUS_CHARGED_BACK,
    PAYMENT_STATUS_REFUNDED,
    PAYMENT_STATUS_EXPIRED,
}
MAX_CHECKOUT_EXPIRATION_MINUTES = 5
MONEY_QUANTUM = Decimal("0.01")
PAYMENT_STATUS_TRANSITIONS = {
    PAYMENT_STATUS_PENDING: {
        PAYMENT_STATUS_PENDING,
        PAYMENT_STATUS_APPROVED,
        PAYMENT_STATUS_REJECTED,
        PAYMENT_STATUS_CANCELLED,
        PAYMENT_STATUS_REFUNDED,
        PAYMENT_STATUS_EXPIRED,
        PAYMENT_STATUS_CHARGED_BACK,
    },
    PAYMENT_STATUS_REJECTED: {PAYMENT_STATUS_REJECTED, PAYMENT_STATUS_APPROVED},
    PAYMENT_STATUS_CANCELLED: {PAYMENT_STATUS_CANCELLED, PAYMENT_STATUS_APPROVED},
    PAYMENT_STATUS_EXPIRED: {PAYMENT_STATUS_EXPIRED, PAYMENT_STATUS_APPROVED},
    PAYMENT_STATUS_APPROVED: {
        PAYMENT_STATUS_APPROVED,
        PAYMENT_STATUS_REFUNDED,
        PAYMENT_STATUS_CHARGED_BACK,
    },
    PAYMENT_STATUS_REFUNDED: {PAYMENT_STATUS_REFUNDED},
    PAYMENT_STATUS_CHARGED_BACK: {PAYMENT_STATUS_CHARGED_BACK},
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_provider(provider: str) -> str:
    normalized = (provider or "").strip().lower()
    if normalized == "mercado_pago":
        return PAYMENT_PROVIDER_MERCADO_PAGO
    return normalized


def normalize_payment_status(raw_status: str | None) -> str:
    status = (raw_status or "").strip().lower()
    if status == "approved":
        return PAYMENT_STATUS_APPROVED
    if status in {"rejected"}:
        return PAYMENT_STATUS_REJECTED
    if status == "cancelled":
        return PAYMENT_STATUS_CANCELLED
    if status == "charged_back":
        return PAYMENT_STATUS_CHARGED_BACK
    if status in {"refunded"}:
        return PAYMENT_STATUS_REFUNDED
    if status in {"expired"}:
        return PAYMENT_STATUS_EXPIRED
    return PAYMENT_STATUS_PENDING


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Valor monetario invalido.") from exc


def _fail_booking_before_checkout(db: Session, booking: Agendamento) -> None:
    booking.status = BOOKING_STATUS_FAILED
    booking.payment_status = PAYMENT_STATUS_CANCELLED
    booking.payment_hold_expires_at = None
    db.commit()


def validate_service_advance_payment_config(servico: Servico) -> tuple[bool, str | None, Decimal | None]:
    require = bool(getattr(servico, "pagamento_adiantado_obrigatorio", False))
    if not require:
        return False, None, None

    payment_type = (getattr(servico, "advance_payment_type", "") or "full").strip().lower()
    if payment_type not in {"full", "signal"}:
        raise ValueError("Tipo de pagamento adiantado invalido. Use 'full' ou 'signal'.")

    service_price = _money(servico.preco)
    if payment_type == "full":
        if service_price <= 0:
            raise ValueError("Servico com pagamento adiantado deve possuir preco maior que zero.")
        return True, payment_type, service_price

    signal_amount = getattr(servico, "advance_payment_amount", None)
    if signal_amount is None:
        raise ValueError("Informe o valor do sinal para este servico.")
    signal_value = _money(signal_amount)
    if signal_value <= 0:
        raise ValueError("O valor do sinal deve ser maior que zero.")
    if service_price > 0 and signal_value > service_price:
        raise ValueError("O valor do sinal nao pode ser maior que o preco do servico.")
    return True, payment_type, signal_value


def apply_payment_snapshot_from_service(booking: Agendamento, servico: Servico) -> None:
    required, payment_type, amount = validate_service_advance_payment_config(servico)
    booking.payment_required_snapshot = required
    booking.payment_type_snapshot = payment_type
    booking.payment_amount_snapshot = amount
    booking.pagamento_adiantado_exigido = required
    if required:
        booking.payment_status = PAYMENT_STATUS_PENDING
        booking.status = BOOKING_STATUS_PENDING_PAYMENT
    else:
        booking.payment_status = PAYMENT_STATUS_NOT_REQUIRED


def build_checkout_notification_url(external_reference: str) -> str:
    base = (
        os.getenv("BACKEND_PUBLIC_BASE_URL", "").strip()
        or os.getenv("BACKEND_URL", "").strip()
        or "http://127.0.0.1:8000"
    ).rstrip("/")
    query: dict[str, str] = {"external_reference": external_reference}
    return f"{base}/webhooks/mercadopago?{urlencode(query)}"


def build_checkout_return_urls(external_reference: str) -> dict[str, str]:
    base = (
        os.getenv("BOOKING_PUBLIC_BASE_URL", "").strip()
        or os.getenv("FRONTEND_URL", "").strip()
        or "http://localhost:3000"
    ).rstrip("/")
    query = urlencode({"external_reference": external_reference})
    return {
        "success": f"{base}/agendamento/pagamento/sucesso?{query}",
        "pending": f"{base}/agendamento/pagamento/pendente?{query}",
        "failure": f"{base}/agendamento/pagamento/falha?{query}",
    }


def _booking_conflict_filter(now: datetime):
    return or_(
        Agendamento.status.in_(["pendente", "confirmado", "reagendamento_solicitado"]),
        and_(
            Agendamento.status == BOOKING_STATUS_PENDING_PAYMENT,
            or_(
                Agendamento.payment_hold_expires_at.is_(None),
                Agendamento.payment_hold_expires_at > now,
            ),
        ),
    )


def booking_conflict_query(
    db: Session,
    *,
    establishment_id: int,
    profissional_id: int,
    start_at: datetime,
    end_at: datetime,
    exclude_booking_id: int | None = None,
):
    query = (
        db.query(Agendamento)
        .filter(
            Agendamento.estabelecimento_id == establishment_id,
            Agendamento.profissional_id == profissional_id,
            Agendamento.data_hora_inicio < end_at,
            Agendamento.data_hora_fim > start_at,
            _booking_conflict_filter(_utcnow()),
        )
    )
    if exclude_booking_id is not None:
        query = query.filter(Agendamento.id != exclude_booking_id)
    return query


def _notify_payment_event(
    db: Session,
    *,
    booking: Agendamento,
    notif_type: str,
    title: str,
    body: str | None = None,
) -> None:
    try:
        notificacao_repo.criar(
            db,
            estabelecimento_id=booking.estabelecimento_id,
            agendamento_id=booking.id,
            tipo=notif_type,
            titulo=title,
            corpo=body,
        )
    except Exception:
        logger.exception("Falha ao criar notificacao de pagamento para agendamento %s", booking.id)


def _build_external_reference(booking_id: int) -> str:
    del booking_id
    return f"pay_{uuid4().hex}"


def _json_safe_scalar(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)[:500]


def _sanitize_provider_payload(payload: dict | None) -> dict:
    source = payload if isinstance(payload, dict) else {}
    allowed = {
        "id",
        "status",
        "status_detail",
        "external_reference",
        "transaction_amount",
        "currency_id",
        "payment_method_id",
        "payment_type_id",
        "date_created",
        "date_approved",
        "date_last_updated",
        "collector_id",
        "notification_url",
        "expires_at",
        "amount",
    }
    result = {key: _json_safe_scalar(source[key]) for key in allowed if key in source}
    metadata = source.get("metadata")
    if isinstance(metadata, dict):
        metadata_keys = {
            "booking_id",
            "appointment_id",
            "agendamento_id",
            "establishment_id",
            "payment_id",
            "payment_integration_id",
            "provider",
            "environment",
            "test",
            "admin",
        }
        result["metadata"] = {
            key: _json_safe_scalar(metadata[key]) for key in metadata_keys if key in metadata
        }
    order = source.get("order")
    if isinstance(order, dict) and order.get("id") is not None:
        result["order"] = {"id": _json_safe_scalar(order["id"])}
    return result


def start_checkout_for_booking(
    db: Session,
    *,
    booking: Agendamento,
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO,
    payer_name: str | None = None,
    payer_email: str | None = None,
    payer_phone: str | None = None,
) -> Pagamento:
    normalized_provider = normalize_provider(provider)
    if not booking.payment_required_snapshot:
        raise ValueError("Este agendamento nao exige pagamento adiantado.")
    if booking.estabelecimento_id is None:
        raise ValueError("Agendamento sem estabelecimento associado.")

    locked_booking = (
        db.query(Agendamento)
        .filter(Agendamento.id == booking.id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not locked_booking:
        raise ValueError("Agendamento nao encontrado.")
    booking = locked_booking

    try:
        active_credentials = get_active_payment_credentials(
            db,
            establishment_id=booking.estabelecimento_id,
            provider=normalized_provider,
        )
    except ValueError:
        _fail_booking_before_checkout(db, booking)
        raise
    if not active_credentials:
        _fail_booking_before_checkout(db, booking)
        raise ValueError("Este estabelecimento ainda nao possui pagamento online configurado.")
    if not active_credentials.webhook_secret:
        _fail_booking_before_checkout(db, booking)
        raise ValueError("A integracao de pagamento nao possui assinatura de webhook configurada.")

    now = _utcnow()
    hold_minutes = max(1, min(int(active_credentials.checkout_hold_minutes or 10), MAX_CHECKOUT_EXPIRATION_MINUTES))
    expires_at = now + timedelta(minutes=hold_minutes)

    existing_payment = (
        db.query(Pagamento)
        .filter(Pagamento.agendamento_id == booking.id)
        .with_for_update()
        .first()
    )
    if (
        existing_payment
        and existing_payment.status == PAYMENT_STATUS_PENDING
        and existing_payment.expires_at
        and existing_payment.expires_at > now
        and existing_payment.checkout_url
    ):
        booking.status = BOOKING_STATUS_PENDING_PAYMENT
        booking.payment_status = PAYMENT_STATUS_PENDING
        booking.payment_hold_expires_at = existing_payment.expires_at
        db.commit()
        db.refresh(existing_payment)
        return existing_payment

    if existing_payment and existing_payment.status in {
        PAYMENT_STATUS_APPROVED,
        PAYMENT_STATUS_REFUNDED,
        PAYMENT_STATUS_CHARGED_BACK,
    }:
        raise ValueError("Este agendamento ja possui pagamento concluido.")

    restart_payment = False
    if existing_payment and existing_payment.status == PAYMENT_STATUS_PENDING:
        if existing_payment.expires_at and existing_payment.expires_at <= now:
            restart_payment = True
    elif existing_payment:
        restart_payment = True

    amount = _money(booking.payment_amount_snapshot)
    if amount <= 0:
        _fail_booking_before_checkout(db, booking)
        raise ValueError("Valor de pagamento invalido no snapshot do agendamento.")

    payment = existing_payment or Pagamento(
        agendamento_id=booking.id,
        estabelecimento_id=booking.estabelecimento_id,
        payment_account_id=active_credentials.payment_account_id,
        payment_integration_id=active_credentials.payment_integration_id,
        provider=normalized_provider,
        amount=amount,
        status=PAYMENT_STATUS_PENDING,
        currency="BRL",
        platform_fee_amount=Decimal("0.00"),
        expires_at=expires_at,
    )
    if existing_payment is None:
        db.add(payment)

    if restart_payment:
        payment.idempotency_key = str(uuid4())
        payment.external_reference = _build_external_reference(booking.id)
        payment.provider_payment_id = None
        payment.preference_id = None
        payment.external_merchant_order_id = None
        payment.checkout_url = None
        payment.raw_payload = None
        payment.paid_at = None

    payment.payment_account_id = active_credentials.payment_account_id
    payment.payment_integration_id = active_credentials.payment_integration_id
    payment.provider = normalized_provider
    payment.amount = amount
    payment.status = PAYMENT_STATUS_PENDING
    payment.currency = "BRL"
    payment.expires_at = expires_at
    payment.external_reference = payment.external_reference or _build_external_reference(booking.id)

    booking.status = BOOKING_STATUS_PENDING_PAYMENT
    booking.payment_status = PAYMENT_STATUS_PENDING
    booking.payment_hold_expires_at = expires_at

    db.flush()

    provider_impl = get_payment_provider(normalized_provider)
    access_token = active_credentials.access_token
    title = f"Agendamento #{booking.id}"
    description = f"Pagamento adiantado do servico {booking.servico.nome if booking.servico else ''}".strip()

    try:
        checkout = provider_impl.create_checkout(
            access_token=access_token,
            idempotency_key=payment.idempotency_key,
            external_reference=payment.external_reference,
            title=title,
            description=description,
            amount=float(amount),
            payer_email=payer_email,
            payer_name=payer_name,
            payer_phone=payer_phone,
            metadata={
                "booking_id": booking.id,
                "establishment_id": booking.estabelecimento_id,
                "payment_id": payment.id,
                "payment_integration_id": active_credentials.payment_integration_id,
                "provider": normalized_provider,
                "environment": active_credentials.environment,
            },
            notification_url=build_checkout_notification_url(payment.external_reference),
            return_urls=build_checkout_return_urls(payment.external_reference),
            expires_at=expires_at,
        )
    except Exception as exc:
        payment.status = PAYMENT_STATUS_PENDING
        payment.external_status = "checkout_creation_unknown"
        booking.payment_status = PAYMENT_STATUS_PENDING
        booking.status = BOOKING_STATUS_PENDING_PAYMENT
        db.commit()
        logger.warning(
            "Falha ao criar checkout; a mesma chave de idempotencia sera reutilizada (payment_id=%s)",
            payment.id,
        )
        raise ValueError("Nao foi possivel iniciar o checkout no momento. Tente novamente.") from exc

    payment.preference_id = checkout["preference_id"]
    payment.checkout_url = checkout["checkout_url"]
    payment.raw_payload = _sanitize_provider_payload(checkout.get("raw"))
    payment.external_status = PAYMENT_STATUS_PENDING
    booking.provider_preference_id = payment.preference_id
    booking.provider_checkout_reference = payment.external_reference

    db.commit()
    db.refresh(payment)
    return payment


def apply_payment_update_from_provider(
    db: Session,
    *,
    payment: Pagamento,
    provider_payload: dict,
) -> Pagamento:
    now = _utcnow()
    mapped_status = normalize_payment_status(provider_payload.get("status"))
    previous_status = payment.status
    allowed_transitions = PAYMENT_STATUS_TRANSITIONS.get(previous_status, {previous_status})
    if mapped_status not in allowed_transitions:
        payment.external_status = str(provider_payload.get("status") or "")[:80]
        payment.raw_payload = _sanitize_provider_payload(provider_payload)
        db.commit()
        db.refresh(payment)
        logger.warning(
            "Transicao de pagamento ignorada (payment_id=%s, from=%s, to=%s)",
            payment.id,
            previous_status,
            mapped_status,
        )
        return payment

    provider_payment_id = provider_payload.get("id")
    if provider_payment_id:
        payment.provider_payment_id = str(provider_payment_id)
    merchant_order = provider_payload.get("order", {}).get("id")
    if merchant_order:
        payment.external_merchant_order_id = str(merchant_order)
    payment.payment_method = (
        provider_payload.get("payment_method_id")
        or provider_payload.get("payment_type_id")
        or payment.payment_method
    )
    payment.external_status = str(provider_payload.get("status") or "")
    payment.raw_payload = _sanitize_provider_payload(provider_payload)
    payment.status = mapped_status

    booking = payment.agendamento
    if booking:
        booking.payment_status = mapped_status
        if mapped_status == PAYMENT_STATUS_APPROVED:
            payment.paid_at = now
            booking.payment_hold_expires_at = None
            conflicting_booking = booking_conflict_query(
                db,
                establishment_id=booking.estabelecimento_id,
                profissional_id=booking.profissional_id,
                start_at=booking.data_hora_inicio,
                end_at=booking.data_hora_fim,
                exclude_booking_id=booking.id,
            ).first()
            booking.status = BOOKING_STATUS_PAYMENT_REVIEW if conflicting_booking else BOOKING_STATUS_CONFIRMED
            if previous_status != PAYMENT_STATUS_APPROVED:
                _notify_payment_event(
                    db,
                    booking=booking,
                    notif_type="pagamento_aprovado",
                    title="Pagamento aprovado - revisar horario" if conflicting_booking else "Pagamento aprovado",
                    body=(
                        f"Pagamento do agendamento #{booking.id} foi aprovado, mas o horario possui conflito."
                        if conflicting_booking
                        else f"Pagamento do agendamento #{booking.id} foi aprovado."
                    ),
                )
        elif mapped_status == PAYMENT_STATUS_EXPIRED:
            booking.status = BOOKING_STATUS_EXPIRED
            booking.payment_hold_expires_at = None
            if previous_status != mapped_status:
                _notify_payment_event(
                    db,
                    booking=booking,
                    notif_type="pagamento_expirado",
                    title="Pagamento expirado",
                    body=f"O pagamento do agendamento #{booking.id} expirou.",
                )
        elif mapped_status in {
            PAYMENT_STATUS_REJECTED,
            PAYMENT_STATUS_CANCELLED,
            PAYMENT_STATUS_REFUNDED,
            PAYMENT_STATUS_CHARGED_BACK,
        }:
            booking.status = BOOKING_STATUS_CANCELLED
            booking.payment_hold_expires_at = None
            if previous_status != mapped_status:
                _notify_payment_event(
                    db,
                    booking=booking,
                    notif_type="pagamento_falhou",
                    title="Pagamento nao concluido",
                    body=f"O pagamento do agendamento #{booking.id} nao foi concluido.",
                )
        else:
            booking.status = BOOKING_STATUS_PENDING_PAYMENT

    db.commit()
    db.refresh(payment)
    return payment


def expire_pending_bookings_and_payments(db: Session, *, limit: int = 200) -> int:
    now = _utcnow()
    pendentes = (
        db.query(Agendamento)
        .filter(
            Agendamento.status == BOOKING_STATUS_PENDING_PAYMENT,
            Agendamento.payment_status == PAYMENT_STATUS_PENDING,
            Agendamento.payment_hold_expires_at.is_not(None),
            Agendamento.payment_hold_expires_at <= now,
        )
        .order_by(Agendamento.payment_hold_expires_at.asc())
        .limit(limit)
        .all()
    )
    if not pendentes:
        return 0

    count = 0
    for booking in pendentes:
        booking.status = BOOKING_STATUS_EXPIRED
        booking.payment_status = PAYMENT_STATUS_EXPIRED
        booking.payment_hold_expires_at = None

        payment = (
            db.query(Pagamento)
            .filter(
                Pagamento.agendamento_id == booking.id,
                Pagamento.status == PAYMENT_STATUS_PENDING,
            )
            .first()
        )
        if payment:
            payment.status = PAYMENT_STATUS_EXPIRED
            payment.external_status = PAYMENT_STATUS_EXPIRED

        _notify_payment_event(
            db,
            booking=booking,
            notif_type="pagamento_expirado",
            title="Pagamento expirado",
            body=f"O pagamento do agendamento #{booking.id} expirou e o horario foi liberado.",
        )
        count += 1

    db.commit()
    logger.info("Expiracao de pagamentos pendentes concluida: %s agendamentos expirados.", count)
    return count
