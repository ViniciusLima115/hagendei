import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from app.services.payments.constants import PAYMENT_PROVIDER_MERCADO_PAGO
from app.services.payments.providers.base import PaymentProvider, PaymentTokenRefreshError


logger = logging.getLogger(__name__)


def _format_mercadopago_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


class MercadoPagoProvider(PaymentProvider):
    name = PAYMENT_PROVIDER_MERCADO_PAGO

    def __init__(self) -> None:
        self.api_base = os.getenv("MERCADOPAGO_API_BASE", "https://api.mercadopago.com").rstrip("/")
        self.auth_base = os.getenv("MERCADOPAGO_AUTH_BASE", "https://auth.mercadopago.com.br").rstrip("/")
        self.client_id = os.getenv("MERCADOPAGO_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("MERCADOPAGO_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.getenv("MERCADOPAGO_REDIRECT_URI", "").strip()
        self.timeout_seconds = int(os.getenv("MERCADOPAGO_TIMEOUT_SECONDS", "15"))

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

    def _log_provider_error(self, message: str, response: requests.Response) -> None:
        error_code = ""
        error_message = ""
        try:
            data = response.json()
            if isinstance(data, dict):
                error_code = str(data.get("error") or data.get("code") or "").strip()[:120]
                error_message = str(data.get("message") or "").strip().replace("\r", " ").replace("\n", " ")[:300]
        except ValueError:
            pass
        logger.error(
            "%s status=%s request_id=%s error=%s message=%s",
            message,
            response.status_code,
            response.headers.get("x-request-id") or response.headers.get("x-correlation-id") or "",
            error_code,
            error_message,
        )

    def _response_error_code(self, response: requests.Response) -> str:
        try:
            data = response.json()
        except ValueError:
            return ""
        for key in ("error", "code", "message"):
            value = data.get(key)
            if value:
                return str(value).strip().lower()
        return ""

    def build_connect_url(self, *, state: str, code_challenge: str | None = None) -> str:
        self._validate_oauth_config(require_secret=False)

        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "platform_id": "mp",
            "state": state,
            "redirect_uri": self.redirect_uri,
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        query = urlencode(params)
        return f"{self.auth_base}/authorization?{query}"

    def exchange_oauth_code(self, *, code: str, code_verifier: str | None = None) -> dict[str, Any]:
        self._validate_oauth_config(require_secret=True)

        payload = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
        }
        if code_verifier:
            payload["code_verifier"] = code_verifier
        response = requests.post(
            f"{self.api_base}/oauth/token",
            data=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 300:
            self._log_provider_error("Falha OAuth Mercado Pago.", response)
            raise ValueError("Nao foi possivel autenticar com o Mercado Pago.")

        token_data = response.json()
        access_token = str(token_data.get("access_token") or "").strip()
        if not access_token:
            raise ValueError("Resposta OAuth sem access_token.")

        user_response = requests.get(
            f"{self.api_base}/users/me",
            headers=self._headers(access_token=access_token),
            timeout=self.timeout_seconds,
        )
        if user_response.status_code >= 300:
            self._log_provider_error("Falha ao consultar usuario Mercado Pago.", user_response)
            raise ValueError("Nao foi possivel validar a conta do Mercado Pago.")

        user_data = user_response.json()
        expires_in = token_data.get("expires_in")
        token_expires_at = None
        if isinstance(expires_in, (int, float)):
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

        provider_account_id = str(user_data.get("id") or token_data.get("user_id") or "")
        provider_account_email = user_data.get("email")

        return {
            "access_token": access_token,
            "refresh_token": token_data.get("refresh_token"),
            "public_key": token_data.get("public_key"),
            "expires_at": token_expires_at,
            "token_expires_at": token_expires_at,
            "provider_account_id": provider_account_id,
            "provider_account_email": provider_account_email,
            "external_user_id": provider_account_id,
            "external_account_email": provider_account_email,
            "raw": {"token": token_data, "user": user_data},
        }

    def refresh_access_token(self, *, refresh_token: str) -> dict[str, Any]:
        self._validate_oauth_config(require_secret=True)

        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }
        response = requests.post(
            f"{self.api_base}/oauth/token",
            data=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 300:
            self._log_provider_error("Falha ao renovar OAuth Mercado Pago.", response)
            error_code = self._response_error_code(response)
            authorization_revoked = response.status_code in {400, 401, 403} and any(
                marker in error_code
                for marker in ("invalid_grant", "invalid_refresh", "revoked", "unauthorized")
            )
            raise PaymentTokenRefreshError(
                "Nao foi possivel renovar o token do Mercado Pago.",
                authorization_revoked=authorization_revoked,
            )

        token_data = response.json()
        access_token = str(token_data.get("access_token") or "").strip()
        if not access_token:
            raise ValueError("Resposta de refresh OAuth sem access_token.")

        expires_in = token_data.get("expires_in")
        token_expires_at = None
        if isinstance(expires_in, (int, float)):
            token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))

        return {
            "access_token": access_token,
            "refresh_token": token_data.get("refresh_token"),
            "public_key": token_data.get("public_key"),
            "expires_at": token_expires_at,
            "token_expires_at": token_expires_at,
            "raw": {"token": token_data},
        }

    def validate_access_token(self, *, access_token: str) -> dict[str, Any]:
        user_response = requests.get(
            f"{self.api_base}/users/me",
            headers=self._headers(access_token=access_token),
            timeout=self.timeout_seconds,
        )
        if user_response.status_code >= 300:
            self._log_provider_error("Falha ao validar conta Mercado Pago.", user_response)
            raise ValueError("Nao foi possivel validar a conta do Mercado Pago.")

        user_data = user_response.json()
        provider_account_id = str(user_data.get("id") or "").strip() or None
        provider_account_email = user_data.get("email")
        return {
            "provider_account_id": provider_account_id,
            "provider_account_email": provider_account_email,
            "external_user_id": provider_account_id,
            "external_account_email": provider_account_email,
        }

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
            "notification_url": notification_url,
            "auto_return": "approved",
        }
        if back_urls:
            payload["back_urls"] = back_urls
        if expires_at:
            expiration = _format_mercadopago_datetime(expires_at)
            payload["date_of_expiration"] = expiration
            payload["expires"] = True
            payload["expiration_date_from"] = _format_mercadopago_datetime(datetime.now(timezone.utc))
            payload["expiration_date_to"] = expiration

        if not payer_email:
            payload["payer"].pop("email", None)
        if not payer_name:
            payload["payer"].pop("name", None)
        if not payer_phone:
            payload["payer"].pop("phone", None)

        response = requests.post(
            f"{self.api_base}/checkout/preferences",
            headers=self._headers(access_token=access_token),
            json=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 300:
            self._log_provider_error("Erro Mercado Pago ao criar preferencia.", response)
            raise ValueError("Nao foi possivel iniciar o checkout no Mercado Pago.")

        data = response.json()
        preference_id = data.get("id")
        checkout_url = data.get("init_point") or data.get("sandbox_init_point")
        if not preference_id or not checkout_url:
            raise ValueError("Resposta invalida do Mercado Pago para checkout.")

        return {
            "preference_id": str(preference_id),
            "checkout_url": str(checkout_url),
            "raw": data,
        }

    def get_payment(self, *, access_token: str, payment_id: str) -> dict[str, Any]:
        response = requests.get(
            f"{self.api_base}/v1/payments/{payment_id}",
            headers=self._headers(access_token=access_token),
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 300:
            self._log_provider_error(f"Erro Mercado Pago ao consultar pagamento {payment_id}.", response)
            raise ValueError("Nao foi possivel consultar o pagamento no Mercado Pago.")
        return response.json()

    def refund_payment(self, *, access_token: str, payment_id: str) -> dict[str, Any]:
        response = requests.post(
            f"{self.api_base}/v1/payments/{payment_id}/refunds",
            headers=self._headers(access_token=access_token),
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 300:
            self._log_provider_error(f"Erro Mercado Pago ao estornar pagamento {payment_id}.", response)
            raise ValueError("Nao foi possivel estornar o pagamento no Mercado Pago.")
        return response.json()
