import hashlib
import hmac
import logging
import os
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.pagamento import Pagamento
from app.models.payment_webhook_event import PaymentWebhookEvent
from app.services.payments.constants import (
    PAYMENT_PROVIDER_MERCADO_PAGO,
    PAYMENT_STATUS_EXPIRED,
    PAYMENT_STATUS_PENDING,
)
from app.services.payments.payment_integration_service import get_active_payment_credentials
from app.services.payments.payment_service import apply_payment_update_from_provider, normalize_payment_status
from app.services.payments.provider_factory import get_payment_provider

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clean_str(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _body_payment_id(payload: dict) -> str | None:
    data = payload.get("data")
    if isinstance(data, dict):
        return _clean_str(data.get("id"))
    return None


def _extract_metadata(payload: dict) -> dict:
    metadata = payload.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _safe_webhook_payload(payload: dict) -> dict:
    safe: dict = {}
    for key in ("type", "action", "api_version", "date_created", "live_mode"):
        if key in payload and isinstance(payload[key], (str, int, float, bool, type(None))):
            safe[key] = payload[key]
    data_id = _body_payment_id(payload)
    if data_id:
        safe["data"] = {"id": data_id}
    return safe


def _parse_signature_header(provided_signature: str | None) -> dict[str, str]:
    if not provided_signature:
        return {}
    parts: dict[str, str] = {}
    for item in provided_signature.strip().split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[key.strip().lower()] = value.strip()
    return parts


def validate_basic_hmac_signature(
    *,
    raw_body: bytes,
    provided_signature: str | None,
    secret: str | None,
    data_id: str | None = None,
    request_id: str | None = None,
    now_timestamp: int | None = None,
) -> bool:
    del raw_body
    if not secret or not provided_signature or not data_id or not request_id:
        return False
    parts = _parse_signature_header(provided_signature)
    received = parts.get("v1", "")
    timestamp_raw = parts.get("ts", "")
    if len(received) != 64 or not timestamp_raw.isdigit():
        return False
    try:
        timestamp = int(timestamp_raw)
    except ValueError:
        return False
    max_age = max(30, min(int(os.getenv("MERCADOPAGO_WEBHOOK_MAX_AGE_SECONDS", "300")), 900))
    current = int(time.time()) if now_timestamp is None else now_timestamp
    if abs(current - timestamp) > max_age:
        return False

    normalized_data_id = data_id.lower()
    manifest = f"id:{normalized_data_id};request-id:{request_id};ts:{timestamp_raw};"
    expected = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(received, expected)


def _event_key(*, data_id: str, request_id: str, signature_header: str) -> str:
    del signature_header
    canonical = f"{data_id.lower()}:{request_id}"
    return f"signed:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _create_event(
    db: Session,
    *,
    external_event_id: str,
    external_topic: str | None,
    payload: dict,
    establishment_id: int,
    payment_id: int,
) -> tuple[PaymentWebhookEvent, bool]:
    event = PaymentWebhookEvent(
        provider=PAYMENT_PROVIDER_MERCADO_PAGO,
        establishment_id=establishment_id,
        payment_id=payment_id,
        external_event_id=external_event_id,
        external_topic=external_topic,
        signature_valid=True,
        payload=_safe_webhook_payload(payload),
        processing_status="pending",
        received_at=_utcnow(),
    )
    db.add(event)
    try:
        db.commit()
        db.refresh(event)
        return event, False
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(PaymentWebhookEvent)
            .filter(
                PaymentWebhookEvent.provider == PAYMENT_PROVIDER_MERCADO_PAGO,
                PaymentWebhookEvent.external_event_id == external_event_id,
            )
            .first()
        )
        if existing:
            if existing.processing_status == "failed":
                existing.processing_status = "pending"
                existing.error_message = None
                existing.processed_at = None
                existing.received_at = _utcnow()
                db.commit()
                db.refresh(existing)
                return existing, False
            return existing, True
        raise


def _find_payment(
    db: Session,
    *,
    provider_payment_id: str,
    external_reference: str | None,
) -> Pagamento | None:
    payment = (
        db.query(Pagamento)
        .filter(Pagamento.provider_payment_id == provider_payment_id)
        .first()
    )
    if payment:
        return payment
    if not external_reference:
        return None
    return (
        db.query(Pagamento)
        .filter(Pagamento.external_reference == external_reference)
        .first()
    )


def _metadata_int(metadata: dict, *keys: str) -> int | None:
    for key in keys:
        value = metadata.get(key)
        if value is None:
            continue
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None
    return None


def _money_cents(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _extract_provider_amount(provider_payload: dict) -> Decimal | None:
    for key in ("transaction_amount", "total_paid_amount"):
        amount = _money_cents(provider_payload.get(key))
        if amount is not None:
            return amount
    details = provider_payload.get("transaction_details")
    if isinstance(details, dict):
        return _money_cents(details.get("total_paid_amount"))
    return None


def _validate_provider_payload_for_payment(
    payment: Pagamento,
    provider_payload: dict,
    *,
    expected_account_id: str | None = None,
) -> tuple[bool, str | None]:
    metadata = _extract_metadata(provider_payload)
    provider_status = normalize_payment_status(provider_payload.get("status"))

    external_reference = _clean_str(provider_payload.get("external_reference"))
    if external_reference and external_reference != payment.external_reference:
        return False, "external_reference_divergente"

    provider_payment_id = _clean_str(provider_payload.get("id"))
    if not provider_payment_id:
        return False, "provider_payment_id_ausente"
    if payment.provider_payment_id and provider_payment_id != payment.provider_payment_id:
        return False, "provider_payment_id_divergente"

    metadata_payment_id = _metadata_int(metadata, "payment_id")
    if metadata_payment_id is not None and metadata_payment_id != payment.id:
        return False, "payment_id_divergente"
    metadata_booking_id = _metadata_int(metadata, "booking_id", "appointment_id", "agendamento_id")
    if metadata_booking_id is not None and metadata_booking_id != payment.agendamento_id:
        return False, "appointment_id_divergente"
    metadata_establishment_id = _metadata_int(metadata, "establishment_id")
    if metadata_establishment_id is not None and metadata_establishment_id != payment.estabelecimento_id:
        return False, "establishment_id_divergente"

    reference_matches = bool(external_reference == payment.external_reference)
    metadata_matches = bool(
        (metadata_payment_id is not None and metadata_payment_id == payment.id)
        or (metadata_booking_id is not None and metadata_booking_id == payment.agendamento_id)
    )
    if not reference_matches and not metadata_matches:
        return False, "referencia_pagamento_nao_confirmada"

    currency = _clean_str(provider_payload.get("currency_id"))
    if provider_status == "approved" and not currency:
        return False, "moeda_pagamento_ausente"
    if currency and currency.upper() != str(payment.currency or "BRL").upper():
        return False, "moeda_pagamento_divergente"

    collector_id = _clean_str(provider_payload.get("collector_id"))
    collector = provider_payload.get("collector")
    if not collector_id and isinstance(collector, dict):
        collector_id = _clean_str(collector.get("id"))
    if expected_account_id:
        if not collector_id:
            return False, "conta_recebedora_ausente"
        if collector_id != expected_account_id:
            return False, "conta_recebedora_divergente"

    if provider_status == "approved":
        expected_amount = _money_cents(payment.amount)
        provider_amount = _extract_provider_amount(provider_payload)
        if expected_amount is None or provider_amount is None:
            return False, "valor_pagamento_ausente"
        if provider_amount != expected_amount:
            return False, "valor_pagamento_divergente"
    return True, None


def _safe_fail_event(db: Session, event: PaymentWebhookEvent, reason: str) -> dict:
    event.processing_status = "rejected"
    event.error_message = reason.replace("_", " ")[:240]
    event.processed_at = _utcnow()
    db.commit()
    return {"status": "failed", "reason": reason, "event_id": event.external_event_id}


def _retryable_fail_event(db: Session, event: PaymentWebhookEvent, reason: str) -> dict:
    event_id = event.id
    external_event_id = event.external_event_id
    db.rollback()
    persisted = db.query(PaymentWebhookEvent).filter(PaymentWebhookEvent.id == event_id).first()
    if persisted:
        persisted.processing_status = "failed"
        persisted.error_message = reason.replace("_", " ")[:240]
        persisted.processed_at = _utcnow()
        db.commit()
        event_key = persisted.external_event_id
    else:
        event_key = external_event_id
    return {"status": "failed", "reason": reason, "event_id": event_key}


def sync_payment_status_from_provider(db: Session, *, payment: Pagamento) -> tuple[Pagamento, bool]:
    active_credentials = get_active_payment_credentials(
        db,
        establishment_id=payment.estabelecimento_id or 0,
        provider=payment.provider,
    )
    if not active_credentials:
        raise ValueError("Conta de pagamento inativa.")

    provider_impl = get_payment_provider(payment.provider)
    provider_payload: dict | None = None
    if payment.provider_payment_id:
        provider_payload = provider_impl.get_payment(
            access_token=active_credentials.access_token,
            payment_id=str(payment.provider_payment_id),
        )
    elif payment.external_reference:
        provider_payload = provider_impl.search_payment_by_external_reference(
            access_token=active_credentials.access_token,
            external_reference=payment.external_reference,
        )
    if not provider_payload:
        return payment, False

    valid, reason = _validate_provider_payload_for_payment(
        payment,
        provider_payload,
        expected_account_id=active_credentials.external_account_id,
    )
    if not valid:
        raise ValueError(reason or "pagamento_invalido")
    return apply_payment_update_from_provider(db, payment=payment, provider_payload=provider_payload), True


def sync_pending_payment_statuses(
    db: Session,
    *,
    establishment_id: int | None = None,
    booking_ids: list[int] | None = None,
    limit: int = 20,
) -> int:
    query = db.query(Pagamento).filter(
        Pagamento.provider == PAYMENT_PROVIDER_MERCADO_PAGO,
        Pagamento.status.in_([PAYMENT_STATUS_PENDING, PAYMENT_STATUS_EXPIRED]),
        Pagamento.external_reference.is_not(None),
    )
    if establishment_id is not None:
        query = query.filter(Pagamento.estabelecimento_id == establishment_id)
    if booking_ids:
        query = query.filter(Pagamento.agendamento_id.in_(booking_ids))

    synced = 0
    for payment in query.order_by(Pagamento.id.desc()).limit(limit).all():
        try:
            _, changed = sync_payment_status_from_provider(db, payment=payment)
            synced += int(changed)
        except Exception:
            logger.warning("Falha ao sincronizar pagamento com provider (payment_id=%s)", payment.id)
            db.rollback()
    return synced


def process_mercadopago_webhook(
    db: Session,
    *,
    payload: dict,
    raw_body: bytes,
    provider_payment_id_query: str | None,
    external_reference_query: str | None,
    webhook_id: str | None,
    topic: str | None,
    signature_header: str | None,
    request_id_header: str | None,
) -> dict:
    del webhook_id
    body_payment_id = _body_payment_id(payload)
    query_payment_id = _clean_str(provider_payment_id_query)
    if body_payment_id and query_payment_id and body_payment_id != query_payment_id:
        return {"status": "failed", "reason": "payment_id_query_divergente"}
    provider_payment_id = query_payment_id or body_payment_id
    request_id = _clean_str(request_id_header)
    if not provider_payment_id:
        return {"status": "failed", "reason": "sem_payment_id"}

    event_type = (_clean_str(topic) or _clean_str(payload.get("type")) or "").lower()
    action = (_clean_str(payload.get("action")) or "").lower()
    if event_type != "payment" and not action.startswith("payment."):
        return {"status": "ignored", "reason": "tipo_evento_nao_suportado"}

    payment = _find_payment(
        db,
        provider_payment_id=provider_payment_id,
        external_reference=_clean_str(external_reference_query),
    )
    if not payment:
        return {"status": "ignored", "reason": "pagamento_nao_mapeado"}

    credentials = get_active_payment_credentials(
        db,
        establishment_id=payment.estabelecimento_id or 0,
        provider=payment.provider,
    )
    if not credentials:
        return {"status": "failed", "reason": "conta_pagamento_inativa"}

    valid_signature = validate_basic_hmac_signature(
        raw_body=raw_body,
        provided_signature=signature_header,
        secret=credentials.webhook_secret,
        data_id=provider_payment_id,
        request_id=request_id,
    )
    if not valid_signature:
        return {"status": "failed", "reason": "assinatura_invalida"}

    event_id = _event_key(
        data_id=provider_payment_id,
        request_id=request_id or "",
        signature_header=signature_header or "",
    )
    event, duplicate = _create_event(
        db,
        external_event_id=event_id,
        external_topic=event_type or action,
        payload=payload,
        establishment_id=payment.estabelecimento_id or 0,
        payment_id=payment.id,
    )
    if duplicate:
        return {"status": "ignored", "reason": "evento_duplicado", "event_id": event.external_event_id}

    try:
        provider_payload = get_payment_provider(payment.provider).get_payment(
            access_token=credentials.access_token,
            payment_id=provider_payment_id,
        )
    except Exception:
        logger.warning("Falha temporaria ao consultar provider para evento de pagamento.")
        return _retryable_fail_event(db, event, "provider_indisponivel")
    valid_payload, reason = _validate_provider_payload_for_payment(
        payment,
        provider_payload,
        expected_account_id=credentials.external_account_id,
    )
    if not valid_payload:
        return _safe_fail_event(db, event, reason or "pagamento_invalido")

    updated = apply_payment_update_from_provider(db, payment=payment, provider_payload=provider_payload)
    event.processing_status = "processed"
    event.processed_at = _utcnow()
    db.commit()
    return {
        "status": "ok",
        "event_id": event.external_event_id,
        "payment_id": updated.id,
        "payment_status": updated.status,
        "booking_id": updated.agendamento_id,
        "booking_status": updated.agendamento.status if updated.agendamento else None,
    }
