import hashlib
import hmac
import logging
import os
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import is_production_env
from app.models.pagamento import Pagamento
from app.models.payment_account import PaymentAccount
from app.models.payment_webhook_event import PaymentWebhookEvent
from app.services.payments.constants import (
    PAYMENT_PROVIDER_MERCADO_PAGO,
<<<<<<< HEAD
    PAYMENT_STATUS_EXPIRED,
    PAYMENT_STATUS_PENDING,
)
from app.services.payments.payment_integration_service import get_active_payment_credentials
=======
    PAYMENT_PROVIDER_PICPAY,
    PAYMENT_STATUS_APPROVED,
    is_payment_account_connected,
)
from app.services.payments.crypto import decrypt_sensitive_value
from app.services.payments.payment_account_service import (
    get_active_payment_account,
    get_valid_access_token,
    get_valid_mercadopago_access_token,
)
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
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


<<<<<<< HEAD
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
=======
def _extract_provider_user_id(payload: dict) -> str | None:
    for key in ("user_id", "account_id", "merchant_id", "collector_id"):
        value = payload.get(key)
        if value:
            return str(value)
    collector = payload.get("collector")
    if isinstance(collector, dict) and collector.get("id"):
        return str(collector.get("id"))
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("user_id", "account_id", "merchant_id", "collector_id"):
            value = data.get(key)
            if value:
                return str(value)
        collector = data.get("collector")
        if isinstance(collector, dict) and collector.get("id"):
            return str(collector.get("id"))
    return None


def _extract_external_event_id(payload: dict, provider_payment_id: str | None, webhook_id: str | None) -> str:
    if webhook_id:
        return str(webhook_id)
    if payload.get("id"):
        return str(payload.get("id"))
    if provider_payment_id:
        return f"payment:{provider_payment_id}"
    return f"event:{hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()}"
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478


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
<<<<<<< HEAD
        signature_valid=True,
        payload=_safe_webhook_payload(payload),
=======
        signature_valid=signature_valid,
        payload=_sanitize_webhook_payload(payload),
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
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


<<<<<<< HEAD
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
=======
def _parse_signature_header(signature_header: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for item in signature_header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[key.strip().lower()] = value.strip()
    return parts


def _validate_legacy_body_hmac(
    *,
    raw_body: bytes,
    provided_signature: str,
    secret: str,
) -> bool:
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    received = provided_signature.strip()
    if received.startswith("sha256="):
        received = received.split("=", 1)[1]
    if "v1=" in received:
        parts = _parse_signature_header(received)
        received = parts.get("v1", "")
    return hmac.compare_digest(received, expected)
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478


def validate_mercadopago_signature(
    *,
    raw_body: bytes,
    provided_signature: str | None,
    secret: str | None,
    request_id: str | None,
    data_id: str | None,
) -> bool | None:
    if not secret:
        return None
    if not provided_signature:
        return False

    parts = _parse_signature_header(provided_signature)
    timestamp = parts.get("ts")
    received = parts.get("v1")
    if timestamp and received and request_id:
        manifest_parts: list[str] = []
        if data_id:
            manifest_parts.append(f"id:{data_id}")
        manifest_parts.append(f"request-id:{request_id}")
        manifest_parts.append(f"ts:{timestamp}")
        manifest = ";".join(manifest_parts) + ";"
        expected = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(received, expected)

    if is_production_env():
        return False
    return _validate_legacy_body_hmac(
        raw_body=raw_body,
        provided_signature=provided_signature,
        secret=secret,
    )


def _sanitize_webhook_payload(payload: dict) -> dict:
    data = payload.get("data")
    sanitized: dict = {}
    for key in (
        "id",
        "type",
        "action",
        "topic",
        "live_mode",
        "user_id",
        "account_id",
        "merchant_id",
        "collector_id",
        "referenceId",
        "reference_id",
        "authorizationId",
        "authorization_id",
    ):
        if key in payload:
            sanitized[key] = payload.get(key)
    if isinstance(data, dict):
        sanitized["data"] = {
            key: data.get(key)
            for key in ("id", "type", "user_id", "account_id", "merchant_id", "collector_id")
            if key in data
        }
    return sanitized


def _sanitize_provider_payload(payload: dict) -> dict:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None
    order = payload.get("order") if isinstance(payload.get("order"), dict) else None
    return {
        key: value
        for key, value in {
            "id": payload.get("id"),
            "status": payload.get("status"),
            "external_reference": payload.get("external_reference"),
            "transaction_amount": payload.get("transaction_amount"),
            "total_paid_amount": payload.get("total_paid_amount"),
            "amount": payload.get("amount") or payload.get("value"),
            "payment_method_id": payload.get("payment_method_id"),
            "payment_type_id": payload.get("payment_type_id"),
            "collector_id": payload.get("collector_id"),
            "authorizationId": payload.get("authorizationId") or payload.get("authorization_id"),
            "metadata": metadata,
            "order": {"id": order.get("id")} if order and order.get("id") else None,
        }.items()
        if value is not None
    }


def _extract_metadata(payload: dict) -> dict:
    metadata = payload.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _metadata_value(metadata: dict, *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


def _matches_int(value: str | None, expected: int | None) -> bool:
    if expected is None:
        return False
    if value is None:
        return False
    try:
        return int(str(value)) == int(expected)
    except (TypeError, ValueError):
        return str(value).strip() == str(expected)


def _extract_provider_amount(payload: dict) -> float | None:
    candidates = [
        payload.get("transaction_amount"),
        payload.get("total_paid_amount"),
        payload.get("amount"),
        payload.get("value"),
        payload.get("amount_paid"),
    ]
    transaction_details = payload.get("transaction_details")
    if isinstance(transaction_details, dict):
        candidates.extend([
            transaction_details.get("total_paid_amount"),
            transaction_details.get("net_received_amount"),
        ])
    for value in candidates:
        if value is None or value == "":
            continue
        try:
            return round(float(value), 2)
        except (TypeError, ValueError):
            continue
    return None


def _validate_provider_payload_for_payment(
    *,
    payment: Pagamento,
    account: PaymentAccount,
    provider_payment_id: str | None,
    provider_payload: dict,
) -> str | None:
    if payment.estabelecimento_id != account.establishment_id:
        return "conta_estabelecimento_divergente"

    payload_payment_id = provider_payload.get("id")
    if provider_payment_id and payload_payment_id and str(provider_payment_id) != str(payload_payment_id):
        return "provider_payment_id_divergente"

    provider_account_id = _extract_provider_user_id(provider_payload)
    if provider_account_id and account.provider_account_id and str(provider_account_id) != str(account.provider_account_id):
        return "conta_provider_divergente"

    external_reference = str(provider_payload.get("external_reference") or "").strip()
    if external_reference and payment.external_reference and external_reference != payment.external_reference:
        return "external_reference_divergente"

    metadata = _extract_metadata(provider_payload)
    metadata_payment_id = _metadata_value(metadata, "payment_id")
    metadata_appointment_id = _metadata_value(metadata, "appointment_id", "booking_id")
    metadata_establishment_id = _metadata_value(metadata, "establishment_id", "tenant_id")

    if metadata_payment_id and not _matches_int(metadata_payment_id, payment.id):
        return "metadata_payment_id_divergente"
    if metadata_appointment_id and not _matches_int(metadata_appointment_id, payment.agendamento_id):
        return "metadata_appointment_id_divergente"
    if metadata_establishment_id and not _matches_int(metadata_establishment_id, payment.estabelecimento_id):
        return "metadata_establishment_id_divergente"

    mapped_status = normalize_payment_status(provider_payload.get("status"))
    if mapped_status != PAYMENT_STATUS_APPROVED:
        return None

    if not external_reference:
        return "external_reference_ausente"
    if payment.provider != PAYMENT_PROVIDER_PICPAY:
        if not metadata:
            return "metadata_ausente"
        if not metadata_payment_id:
            return "metadata_payment_id_ausente"
        if not metadata_appointment_id:
            return "metadata_appointment_id_ausente"
        if not metadata_establishment_id:
            return "metadata_establishment_id_ausente"

    provider_amount = _extract_provider_amount(provider_payload)
    if provider_amount is None:
        return "valor_ausente"
    expected_amount = round(float(payment.amount or 0), 2)
    if abs(provider_amount - expected_amount) > 0.01:
        return "valor_divergente"
    return None


def _get_active_account_from_payload(db: Session, payload: dict) -> PaymentAccount | None:
    provider_account_id = _extract_provider_user_id(payload)
    if not provider_account_id:
        return None
    account = (
        db.query(PaymentAccount)
        .filter(
            PaymentAccount.provider == PAYMENT_PROVIDER_MERCADO_PAGO,
            PaymentAccount.provider_account_id == provider_account_id,
        )
        .first()
    )
    if not account or not is_payment_account_connected(account.status):
        return None
    return account


def _extract_picpay_reference_id(payload: dict, reference_id_query: str | None = None) -> str | None:
    if reference_id_query:
        return str(reference_id_query)
    for key in ("referenceId", "reference_id", "external_reference"):
        value = payload.get(key)
        if value:
            return str(value)
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("referenceId", "reference_id", "external_reference"):
            value = data.get(key)
            if value:
                return str(value)
    return None


def _extract_picpay_authorization_id(payload: dict) -> str | None:
    for key in ("authorizationId", "authorization_id"):
        value = payload.get(key)
        if value:
            return str(value)
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("authorizationId", "authorization_id"):
            value = data.get(key)
            if value:
                return str(value)
    return None


def _extract_picpay_external_event_id(payload: dict, reference_id: str | None) -> str:
    authorization_id = _extract_picpay_authorization_id(payload)
    if authorization_id:
        return f"authorization:{authorization_id}"
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    if reference_id:
        return f"reference:{reference_id}:{payload_hash}"
    return f"event:{payload_hash}"


def _normalize_seller_token_header(value: str | None) -> str:
    cleaned = (value or "").strip()
    if cleaned.lower().startswith("bearer "):
        return cleaned.split(" ", 1)[1].strip()
    return cleaned


def _validate_picpay_seller_token(*, account: PaymentAccount, seller_token_header: str | None) -> bool:
    expected = decrypt_sensitive_value(account.refresh_token_encrypted)
    received = _normalize_seller_token_header(seller_token_header)
    if not expected or not received:
        return False
    return hmac.compare_digest(str(expected), received)


def process_picpay_webhook(
    db: Session,
    *,
    payload: dict,
    reference_id_query: str | None = None,
    seller_token_header: str | None,
) -> dict:
    reference_id = _extract_picpay_reference_id(payload, reference_id_query)
    authorization_id = _extract_picpay_authorization_id(payload)
    external_event_id = _extract_picpay_external_event_id(payload, reference_id)

    initial_event, is_duplicate = _create_event(
        db,
        provider=PAYMENT_PROVIDER_PICPAY,
        external_event_id=external_event_id,
        external_topic="callback",
        payload=payload,
        signature_valid=None,
    )
    if is_duplicate:
        return {"status": "ignored", "reason": "evento_duplicado", "event_id": initial_event.external_event_id}

    if not reference_id:
        initial_event.processing_status = "failed"
        initial_event.error_message = "Webhook PicPay sem referenceId."
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "failed", "reason": "sem_reference_id", "event_id": initial_event.external_event_id}

    payment = (
        db.query(Pagamento)
        .filter(
            Pagamento.provider == PAYMENT_PROVIDER_PICPAY,
            (
                (Pagamento.provider_payment_id == str(reference_id))
                | (Pagamento.preference_id == str(reference_id))
                | (Pagamento.external_reference == str(reference_id))
            ),
        )
        .first()
    )
    if payment is None:
        initial_event.processing_status = "ignored"
        initial_event.error_message = "Pagamento PicPay nao mapeado."
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "ignored", "reason": "pagamento_nao_mapeado", "event_id": initial_event.external_event_id}

    initial_event.payment_id = payment.id
    initial_event.establishment_id = payment.estabelecimento_id
    db.commit()

    account = get_active_payment_account(
        db,
        establishment_id=payment.estabelecimento_id or 0,
        provider=PAYMENT_PROVIDER_PICPAY,
    )
    if not account:
        initial_event.processing_status = "failed"
        initial_event.error_message = "Conta PicPay ativa nao encontrada."
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "failed", "reason": "conta_pagamento_inativa", "event_id": initial_event.external_event_id}

    signature_valid = _validate_picpay_seller_token(account=account, seller_token_header=seller_token_header)
    initial_event.signature_valid = signature_valid
    if not signature_valid:
        initial_event.processing_status = "failed"
        initial_event.error_message = "x-seller-token invalido."
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "forbidden", "reason": "assinatura_invalida", "event_id": initial_event.external_event_id}

    provider_impl = get_payment_provider(PAYMENT_PROVIDER_PICPAY)
    access_token = get_valid_access_token(db, account)
    provider_payload = provider_impl.get_payment(
        access_token=access_token,
        payment_id=str(reference_id),
    )
    if authorization_id and not provider_payload.get("authorizationId"):
        provider_payload["authorizationId"] = authorization_id

    validation_reason = _validate_provider_payload_for_payment(
        payment=payment,
        account=account,
        provider_payment_id=str(reference_id),
        provider_payload=provider_payload,
    )
    if validation_reason:
        initial_event.processing_status = "failed"
        initial_event.error_message = validation_reason
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "failed", "reason": validation_reason, "event_id": initial_event.external_event_id}

    updated_payment = apply_payment_update_from_provider(
        db,
        payment=payment,
        provider_payload=_sanitize_provider_payload(provider_payload),
    )

    initial_event.processing_status = "processed"
    initial_event.processed_at = _utcnow()
    db.commit()

    return {
        "status": "ok",
        "event_id": initial_event.external_event_id,
        "payment_id": updated_payment.id,
        "payment_status": updated_payment.status,
        "booking_id": updated_payment.agendamento_id,
        "booking_status": updated_payment.agendamento.status if updated_payment.agendamento else None,
    }


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
<<<<<<< HEAD
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
=======
    signature_secret: str | None,
    request_id: str | None = None,
) -> dict:
    provider_payment_id = _extract_provider_payment_id(payload, provider_payment_id_query)
    external_event_id = _extract_external_event_id(payload, provider_payment_id, webhook_id)
    signature_valid = validate_mercadopago_signature(
        raw_body=raw_body,
        provided_signature=signature_header,
        secret=signature_secret,
        request_id=request_id,
        data_id=provider_payment_id_query or provider_payment_id,
    )
    if signature_valid is None and is_production_env():
        signature_valid = False
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478

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

<<<<<<< HEAD
    credentials = get_active_payment_credentials(
=======
    if signature_valid is False:
        initial_event.processing_status = "failed"
        initial_event.error_message = "Assinatura invalida."
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "forbidden", "reason": "assinatura_invalida", "event_id": initial_event.external_event_id}

    payment = None
    provider_payload: dict | None = None
    account: PaymentAccount | None = None
    if provider_payment_id:
        payment = (
            db.query(Pagamento)
            .filter(
                Pagamento.provider == PAYMENT_PROVIDER_MERCADO_PAGO,
                Pagamento.provider_payment_id == str(provider_payment_id),
            )
            .first()
        )

    if payment is None and isinstance(payload.get("external_reference"), str):
        payment = (
            db.query(Pagamento)
            .filter(
                Pagamento.provider == PAYMENT_PROVIDER_MERCADO_PAGO,
                Pagamento.external_reference == payload["external_reference"],
            )
            .first()
        )

    if payment is None and provider_payment_id:
        account = _get_active_account_from_payload(db, payload)
        if account:
            provider_impl = get_payment_provider(account.provider)
            access_token = get_valid_access_token(db, account)
            provider_payload = provider_impl.get_payment(
                access_token=access_token,
                payment_id=str(provider_payment_id),
            )
            external_reference = str(provider_payload.get("external_reference") or "").strip()
            if external_reference:
                payment = (
                    db.query(Pagamento)
                    .filter(
                        Pagamento.external_reference == external_reference,
                        Pagamento.estabelecimento_id == account.establishment_id,
                        Pagamento.provider == account.provider,
                    )
                    .first()
                )

    if payment is None:
        initial_event.processing_status = "ignored"
        initial_event.error_message = "Pagamento nao mapeado."
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "ignored", "reason": "pagamento_nao_mapeado", "event_id": initial_event.external_event_id}

    initial_event.payment_id = payment.id
    initial_event.establishment_id = payment.estabelecimento_id
    db.commit()

    account = account or get_active_payment_account(
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
        db,
        establishment_id=payment.estabelecimento_id or 0,
        provider=payment.provider,
    )
    if not credentials:
        return {"status": "failed", "reason": "conta_pagamento_inativa"}

<<<<<<< HEAD
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
=======
    if not provider_payment_id and payment.provider_payment_id:
        provider_payment_id = payment.provider_payment_id
    if not provider_payment_id:
        initial_event.processing_status = "failed"
        initial_event.error_message = "Webhook sem payment_id."
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "failed", "reason": "sem_payment_id", "event_id": initial_event.external_event_id}

    if provider_payload is None:
        provider_impl = get_payment_provider(payment.provider)
        access_token = (
            get_valid_mercadopago_access_token(db, establishment_id=payment.estabelecimento_id or 0)
            if payment.provider == PAYMENT_PROVIDER_MERCADO_PAGO
            else get_valid_access_token(db, account)
        )
        provider_payload = provider_impl.get_payment(
            access_token=access_token,
            payment_id=str(provider_payment_id),
        )

    validation_reason = _validate_provider_payload_for_payment(
        payment=payment,
        account=account,
        provider_payment_id=str(provider_payment_id) if provider_payment_id else None,
        provider_payload=provider_payload,
    )
    if validation_reason:
        initial_event.processing_status = "failed"
        initial_event.error_message = validation_reason
        initial_event.processed_at = _utcnow()
        db.commit()
        return {"status": "failed", "reason": validation_reason, "event_id": initial_event.external_event_id}

    updated_payment = apply_payment_update_from_provider(
        db,
        payment=payment,
        provider_payload=_sanitize_provider_payload(provider_payload),
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
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
