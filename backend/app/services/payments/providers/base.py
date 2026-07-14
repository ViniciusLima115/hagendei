from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class PaymentProviderError(ValueError):
    pass


class PaymentProviderUnavailableError(PaymentProviderError):
    pass


class PaymentTokenRefreshError(PaymentProviderError):
    def __init__(self, message: str, *, authorization_revoked: bool = False) -> None:
        super().__init__(message)
        self.authorization_revoked = authorization_revoked


class PaymentProvider(ABC):
    name: str

    def ensure_available(self) -> None:
        return None

    @abstractmethod
    def build_connect_url(self, *, state: str, code_challenge: str | None = None) -> str:
        raise NotImplementedError

    @abstractmethod
    def exchange_oauth_code(self, *, code: str, code_verifier: str | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def refresh_access_token(self, *, refresh_token: str) -> dict[str, Any]:
        raise NotImplementedError

    def validate_access_token(self, *, access_token: str) -> dict[str, Any]:
        return {}

    def get_payment_status(
        self,
        *,
        external_payment_id: str,
        access_token: str,
        payment_integration: Any | None = None,
    ) -> dict[str, Any]:
        return self.get_payment(access_token=access_token, payment_id=external_payment_id)

    def validate_webhook(self, *, request: Any | None = None, payload: dict | None = None) -> bool:
        raise NotImplementedError

    def process_webhook(self, *, payload: dict, payment_integration: Any | None = None) -> dict[str, Any]:
        raise NotImplementedError

    def disconnect_account(self, *, payment_integration: Any) -> dict[str, Any] | None:
        return None

    @abstractmethod
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
<<<<<<< HEAD
        return_urls: dict[str, str] | None,
=======
        back_urls: dict[str, str] | None,
>>>>>>> 58bfd5f7b3e3f2e381d1812d30878ea29463a478
        expires_at: datetime | None,
        marketplace_fee: float | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_payment(self, *, access_token: str, payment_id: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def search_payment_by_external_reference(
        self,
        *,
        access_token: str,
        idempotency_key: str,
        external_reference: str,
    ) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    def refund_payment(self, *, access_token: str, payment_id: str) -> dict[str, Any]:
        raise NotImplementedError
