import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlencode, urlsplit

import requests

from app.services.payments.providers.base import PaymentProvider


logger = logging.getLogger(__name__)
LOCAL_RETURN_HOSTS = {"localhost"}


def _is_public_https_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not hostname or hostname in LOCAL_RETURN_HOSTS:
        return False
    try:
        if not ip_address(hostname).is_global:
            return False
    except ValueError:
        pass
    return True


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _safe_provider_error_code(response: requests.Response) -> str:
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return "unknown"
    if not isinstance(payload, dict):
        return "unknown"
    raw_code = str(payload.get("error") or payload.get("code") or "unknown")
    return "".join(char for char in raw_code[:64] if char.isalnum() or char in {"_", "-", "."}) or "unknown"


def _marketplace_fee_for_amount(amount: float) -> float | None:
    configured = os.getenv("MERCADOPAGO_MARKETPLACE_FEE", "").strip()
    if not configured:
        return None
    try:
        fee = Decimal(configured).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError("Taxa de marketplace do Mercado Pago invalida.") from exc
    if fee <= 0 or fee >= total:
        raise ValueError("Taxa de marketplace deve ser positiva e menor que o pagamento.")
    return float(fee)


def _is_mercadopago_checkout_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower()
    try:
        port = parsed.port
    except ValueError:
        return False
    trusted_domains = ("mercadopago.com", "mercadopago.com.br")
    trusted_host = any(hostname == domain or hostname.endswith(f".{domain}") for domain in trusted_domains)
    return (
        parsed.scheme == "https"
        and trusted_host
        and parsed.username is None
        and parsed.password is None
        and port in {None, 443}
    )


class MercadoPagoProvider(PaymentProvider):
    name = "mercadopago"

    def __init__(self) -> None:
        self.api_base = os.getenv("MERCADOPAGO_API_BASE", "https://api.mercadopago.com").rstrip("/")
        self.auth_base = os.getenv("MERCADOPAGO_AUTH_BASE", "https://auth.mercadopago.com.br").rstrip("/")
        self.client_id = os.getenv("MERCADOPAGO_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("MERCADOPAGO_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.getenv("MERCADOPAGO_REDIRECT_URI", "").strip()
        self.timeout_seconds = max(3, min(int(os.getenv("MERCADOPAGO_TIMEOUT_SECONDS", "15")), 30))
        self.is_production = os.getenv("APP_ENV", "development").strip().lower() in {"prod", "production"}
        if self.is_production:
            api = urlsplit(self.api_base)
            auth = urlsplit(self.auth_base)
            if api.scheme != "https" or api.hostname != "api.mercadopago.com":
                raise RuntimeError("MERCADOPAGO_API_BASE invalida para producao.")
            if auth.scheme != "https" or auth.hostname not in {
                "auth.mercadopago.com.br",
                "auth.mercadopago.com",
            }:
                raise RuntimeError("MERCADOPAGO_AUTH_BASE invalida para producao.")

    def _validate_oauth_config(self, *, require_secret: bool) -> None:
        missing: list[str] = []
        if not self.client_id:
            missing.append("MERCADOPAGO_CLIENT_ID")
        if require_secret and not self.client_secret:
            missing.append("MERCADOPAGO_CLIENT_SECRET")
        if not self.redirect_uri:
            missing.append("MERCADOPAGO_REDIRECT_URI")
        if missing:
            raise ValueError(
                f"Credenciais OAuth do Mercado Pago nao configuradas: {', '.join(missing)}"
            )

    def _headers(self, *, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _checkout_headers(self, *, access_token: str, idempotency_key: str) -> dict[str, str]:
        headers = self._headers(access_token=access_token)
        headers["X-Idempotency-Key"] = idempotency_key
        return headers

    def build_connect_url(self, *, state: str) -> str:
        self._validate_oauth_config(require_secret=False)

        query = urlencode(
            {
                "client_id": self.client_id,
                "response_type": "code",
                "state": state,
                "redirect_uri": self.redirect_uri,
            }
        )
        return f"{self.auth_base}/authorization?{query}"

    def exchange_oauth_code(self, *, code: str) -> dict[str, Any]:
        self._validate_oauth_config(require_secret=True)

        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        response = requests.post(
            f"{self.api_base}/oauth/token",
            data=payload,
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if response.status_code >= 300:
            logger.error(
                "Falha OAuth Mercado Pago (status=%s error=%s)",
                response.status_code,
                _safe_provider_error_code(response),
            )
            raise ValueError("Nao foi possivel autenticar com o Mercado Pago.")

        token_data = response.json()
        access_token = str(token_data.get("access_token") or "").strip()
        if not access_token:
            raise ValueError("Resposta OAuth sem access_token.")

        user_response = requests.get(
            f"{self.api_base}/users/me",
            headers=self._headers(access_token=access_token),
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if user_response.status_code >= 300:
            logger.error("Falha ao consultar usuario Mercado Pago (status=%s)", user_response.status_code)
            raise ValueError("Nao foi possivel validar a conta do Mercado Pago.")

        user_data = user_response.json()
        expires_in = token_data.get("expires_in")
        token_expires_at = None
        if isinstance(expires_in, (int, float)):
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

        return {
            "access_token": access_token,
            "refresh_token": token_data.get("refresh_token"),
            "public_key": token_data.get("public_key"),
            "token_expires_at": token_expires_at,
            "external_user_id": str(user_data.get("id") or token_data.get("user_id") or ""),
            "external_account_email": user_data.get("email"),
            "raw": {"token": token_data, "user": user_data},
        }

    def validate_access_token(self, *, access_token: str) -> dict[str, Any]:
        response = requests.get(
            f"{self.api_base}/users/me",
            headers=self._headers(access_token=access_token),
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if response.status_code >= 300:
            logger.warning("Validacao Mercado Pago falhou com status %s", response.status_code)
            return {
                "valid": False,
                "message": "Credencial recusada pelo Mercado Pago.",
                "status_code": response.status_code,
            }
        data = response.json()
        return {
            "valid": True,
            "message": "Credencial Mercado Pago validada com sucesso.",
            "external_user_id": str(data.get("id") or ""),
        }

    def create_checkout(
        self,
        *,
        access_token: str,
        idempotency_key: str,
        external_reference: str,
        title: str,
        description: str,
        amount: float,
        payer_email: str | None,
        payer_name: str | None,
        payer_phone: str | None,
        metadata: dict[str, Any],
        notification_url: str,
        return_urls: dict[str, str] | None,
        expires_at: datetime | None,
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValueError("Valor do pagamento deve ser maior que zero.")

        payload: dict[str, Any] = {
            "external_reference": external_reference,
            "items": [
                {
                    "title": title[:120],
                    "description": description[:256],
                    "quantity": 1,
                    "currency_id": "BRL",
                    "unit_price": round(float(amount), 2),
                }
            ],
            "payer": {
                "email": payer_email,
                "name": payer_name,
                "phone": {"number": payer_phone},
            },
            "metadata": metadata,
        }
        marketplace_fee = _marketplace_fee_for_amount(amount)
        if marketplace_fee is not None:
            payload["marketplace_fee"] = marketplace_fee
        if _is_public_https_url(notification_url):
            payload["notification_url"] = notification_url
        if return_urls and _is_public_https_url(return_urls.get("success")):
            back_urls = {
                key: value
                for key, value in {
                    "success": return_urls.get("success"),
                    "pending": return_urls.get("pending"),
                    "failure": return_urls.get("failure"),
                }.items()
                if _is_public_https_url(value)
            }
            if back_urls.get("success"):
                payload["back_urls"] = back_urls
                payload["auto_return"] = "approved"
        if expires_at:
            expiration_to = _as_utc(expires_at).replace(microsecond=0)
            payload["date_of_expiration"] = expiration_to.isoformat()
            payload["expires"] = True
            payload["expiration_date_from"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            payload["expiration_date_to"] = expiration_to.isoformat()

        if not payer_email:
            payload["payer"].pop("email", None)
        if not payer_name:
            payload["payer"].pop("name", None)
        if not payer_phone:
            payload["payer"].pop("phone", None)

        response = requests.post(
            f"{self.api_base}/checkout/preferences",
            headers=self._checkout_headers(access_token=access_token, idempotency_key=idempotency_key),
            json=payload,
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if response.status_code >= 300:
            logger.error("Erro Mercado Pago ao criar preferencia (status=%s)", response.status_code)
            raise ValueError("Nao foi possivel iniciar o checkout no Mercado Pago.")

        data = response.json()
        preference_id = data.get("id")
        checkout_url = data.get("init_point") or data.get("sandbox_init_point")
        if not preference_id or not checkout_url:
            raise ValueError("Resposta invalida do Mercado Pago para checkout.")
        if self.is_production and not _is_mercadopago_checkout_url(str(checkout_url)):
            raise ValueError("URL de checkout invalida recebida do Mercado Pago.")

        return {
            "preference_id": str(preference_id),
            "checkout_url": str(checkout_url),
            "raw": data,
        }

    def search_payment_by_external_reference(
        self,
        *,
        access_token: str,
        external_reference: str,
    ) -> dict[str, Any] | None:
        reference = (external_reference or "").strip()
        if not reference:
            return None

        response = requests.get(
            f"{self.api_base}/v1/payments/search",
            headers=self._headers(access_token=access_token),
            params={
                "external_reference": reference,
                "sort": "date_last_updated",
                "criteria": "desc",
                "limit": 10,
                "offset": 0,
            },
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if response.status_code >= 300:
            logger.error("Erro Mercado Pago ao buscar pagamento por referencia (status=%s)", response.status_code)
            raise ValueError("Nao foi possivel consultar o pagamento no Mercado Pago.")

        data = response.json()
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            return None

        matches = [
            item for item in results
            if isinstance(item, dict) and str(item.get("external_reference") or "").strip() == reference
        ]
        if not matches:
            return None

        approved = [item for item in matches if str(item.get("status") or "").lower() == "approved"]
        return approved[0] if approved else matches[0]

    def get_payment(self, *, access_token: str, payment_id: str) -> dict[str, Any]:
        response = requests.get(
            f"{self.api_base}/v1/payments/{payment_id}",
            headers=self._headers(access_token=access_token),
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if response.status_code >= 300:
            logger.error(
                "Erro Mercado Pago ao consultar pagamento (status=%s)",
                response.status_code,
            )
            raise ValueError("Nao foi possivel consultar o pagamento no Mercado Pago.")
        return response.json()

    def refund_payment(self, *, access_token: str, payment_id: str) -> dict[str, Any]:
        response = requests.post(
            f"{self.api_base}/v1/payments/{payment_id}/refunds",
            headers=self._headers(access_token=access_token),
            timeout=self.timeout_seconds,
            allow_redirects=False,
        )
        if response.status_code >= 300:
            logger.error("Erro Mercado Pago ao estornar pagamento (status=%s)", response.status_code)
            raise ValueError("Nao foi possivel estornar o pagamento no Mercado Pago.")
        return response.json()
