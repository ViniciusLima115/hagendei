from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def build_connect_url(self, *, state: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def exchange_oauth_code(self, *, code: str) -> dict[str, Any]:
        raise NotImplementedError

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
        return_urls: dict[str, str] | None,
        expires_at: datetime | None,
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
