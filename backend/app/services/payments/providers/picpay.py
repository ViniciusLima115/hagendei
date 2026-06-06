import logging
import os
from datetime import datetime, timezone
from typing import Any

import requests

from app.services.payments.constants import PAYMENT_PROVIDER_PICPAY
from app.services.payments.providers.base import PaymentProvider, PaymentProviderUnavailableError


logger = logging.getLogger(__name__)


class PicPayProvider(PaymentProvider):
    name = PAYMENT_PROVIDER_PICPAY

    def __init__(self) -> None:
        self.api_base = os.getenv(
            "PICPAY_API_BASE",
            "https://appws.picpay.com/ecommerce/public",
        ).rstrip("/")
        self.timeout_seconds = int(os.getenv("PICPAY_TIMEOUT_SECONDS", "15"))

    def _manual_credentials_error(self) -> PaymentProviderUnavailableError:
        return PaymentProviderUnavailableError(
            "PicPay usa credenciais manuais por estabelecimento cadastradas pelo ADM."
        )

    def _headers(self, *, access_token: str) -> dict[str, str]:
        return {
            "x-picpay-token": access_token,
            "Content-Type": "application/json",
        }

    def _log_provider_error(self, message: str, response: requests.Response) -> None:
        logger.error(
            "%s status=%s request_id=%s",
            message,
            response.status_code,
            response.headers.get("x-request-id") or response.headers.get("x-correlation-id") or "",
        )

    def _normalize_expires_at(self, expires_at: datetime | None) -> str | None:
        if not expires_at:
            return None
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    def _split_name(self, payer_name: str | None) -> tuple[str, str]:
        cleaned = (payer_name or "").strip()
        if not cleaned:
            return "Cliente", "Barbearia"
        parts = cleaned.split()
        if len(parts) == 1:
            return parts[0][:50], "Barbearia"
        return parts[0][:50], " ".join(parts[1:])[:80]

    def _additional_info(self, metadata: dict[str, Any], *, external_reference: str, amount: float, description: str) -> dict[str, str]:
        keys = ("payment_id", "appointment_id", "booking_id", "establishment_id", "provider")
        info = {key: str(metadata[key]) for key in keys if metadata.get(key) is not None}
        info["external_reference"] = external_reference
        info["amount"] = f"{round(float(amount), 2):.2f}"
        if description:
            info["description"] = description[:120]
        return info

    def _normalize_additional_info(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not isinstance(value, list):
            return {}
        normalized: dict[str, Any] = {}
        for item in value:
            if not isinstance(item, dict):
                continue
            key = item.get("key") or item.get("name") or item.get("label")
            item_value = item.get("value")
            if key is not None and item_value is not None:
                normalized[str(key)] = item_value
        return normalized

    def _sanitize_checkout_response(self, data: dict[str, Any]) -> dict[str, Any]:
        sanitized = {
            key: data.get(key)
            for key in ("referenceId", "paymentUrl", "expiresAt", "status", "message")
            if data.get(key) is not None
        }
        qrcode = data.get("qrcode")
        if isinstance(qrcode, dict):
            sanitized["qrcode"] = {
                "content": qrcode.get("content"),
                "has_base64": bool(qrcode.get("base64")),
            }
        return sanitized

    def build_connect_url(self, *, state: str, code_challenge: str | None = None) -> str:
        raise self._manual_credentials_error()

    def exchange_oauth_code(self, *, code: str, code_verifier: str | None = None) -> dict[str, Any]:
        raise self._manual_credentials_error()

    def refresh_access_token(self, *, refresh_token: str) -> dict[str, Any]:
        raise self._manual_credentials_error()

    def validate_access_token(self, *, access_token: str) -> dict[str, Any]:
        response = requests.get(
            f"{self.api_base}/payments/__validation_probe__/status",
            headers=self._headers(access_token=access_token),
            timeout=self.timeout_seconds,
        )
        if response.status_code in {401, 403}:
            self._log_provider_error("Falha ao validar token PicPay.", response)
            raise ValueError("Token PicPay invalido.")
        return {}

    def create_checkout(
        self,
        *,
        access_token: str,
        external_reference: str,
        title: str,
        description: str,
        amount: float,
        payer_email: str | None,
        payer_name: str | None,
        payer_phone: str | None,
        metadata: dict[str, Any],
        notification_url: str,
        back_urls: dict[str, str] | None,
        expires_at: datetime | None,
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("Valor do pagamento deve ser maior que zero.")

        first_name, last_name = self._split_name(payer_name)
        buyer: dict[str, Any] = {
            "firstName": first_name,
            "lastName": last_name,
        }
        if payer_email:
            buyer["email"] = payer_email
        if payer_phone:
            buyer["phone"] = payer_phone

        payload: dict[str, Any] = {
            "referenceId": external_reference,
            "callbackUrl": notification_url,
            "returnUrl": (back_urls or {}).get("success") or (back_urls or {}).get("pending"),
            "value": round(float(amount), 2),
            "buyer": buyer,
            "additionalInfo": self._additional_info(
                metadata,
                external_reference=external_reference,
                amount=amount,
                description=description,
            ),
        }
        normalized_expires_at = self._normalize_expires_at(expires_at)
        if normalized_expires_at:
            payload["expiresAt"] = normalized_expires_at

        response = requests.post(
            f"{self.api_base}/payments",
            headers=self._headers(access_token=access_token),
            json=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 300:
            self._log_provider_error("Erro PicPay ao criar checkout.", response)
            raise ValueError("Nao foi possivel iniciar o checkout no PicPay.")

        data = response.json()
        reference_id = str(data.get("referenceId") or external_reference).strip()
        qrcode = data.get("qrcode") if isinstance(data.get("qrcode"), dict) else {}
        checkout_url = data.get("paymentUrl") or qrcode.get("content")
        if not reference_id or not checkout_url:
            raise ValueError("Resposta invalida do PicPay para checkout.")

        return {
            "preference_id": reference_id,
            "payment_id": reference_id,
            "checkout_url": str(checkout_url),
            "raw": self._sanitize_checkout_response(data),
        }

    def get_payment(self, *, access_token: str, payment_id: str) -> dict[str, Any]:
        response = requests.get(
            f"{self.api_base}/payments/{payment_id}/status",
            headers=self._headers(access_token=access_token),
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 300:
            self._log_provider_error(f"Erro PicPay ao consultar pagamento {payment_id}.", response)
            raise ValueError("Nao foi possivel consultar o pagamento no PicPay.")

        data = response.json()
        reference_id = str(data.get("referenceId") or data.get("reference_id") or payment_id).strip()
        additional_info = self._normalize_additional_info(
            data.get("additionalInfo") or data.get("additional_info")
        )
        amount = (
            data.get("value")
            or data.get("amount")
            or data.get("transaction_amount")
            or additional_info.get("amount")
        )
        normalized = dict(data)
        normalized["id"] = reference_id
        normalized["external_reference"] = reference_id
        normalized["status"] = data.get("status") or data.get("picpayStatus") or data.get("payment_status")
        if amount is not None:
            normalized["transaction_amount"] = amount
        normalized["metadata"] = additional_info
        normalized["payment_method_id"] = "picpay"
        return normalized

    def get_payment_status(
        self,
        *,
        external_payment_id: str,
        access_token: str,
        payment_integration: Any | None = None,
    ) -> dict[str, Any]:
        return self.get_payment(access_token=access_token, payment_id=external_payment_id)

    def validate_webhook(self, *, request: Any | None = None, payload: dict | None = None) -> bool:
        return False

    def process_webhook(self, *, payload: dict, payment_integration: Any | None = None) -> dict[str, Any]:
        return payload

    def refund_payment(self, *, access_token: str, payment_id: str) -> dict[str, Any]:
        response = requests.post(
            f"{self.api_base}/payments/{payment_id}/refunds",
            headers=self._headers(access_token=access_token),
            json={},
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 300:
            self._log_provider_error(f"Erro PicPay ao estornar pagamento {payment_id}.", response)
            raise ValueError("Nao foi possivel estornar o pagamento no PicPay.")
        return response.json()

    def disconnect_account(self, *, payment_integration: Any) -> dict[str, Any] | None:
        return None
