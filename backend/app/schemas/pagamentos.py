from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.services.payments.constants import (
    PAYMENT_ACCOUNT_STATUS_CONNECTED,
    PAYMENT_PROVIDER_MERCADO_PAGO,
)


PaymentStatus = Literal[
    "not_required",
    "pending",
    "approved",
    "rejected",
    "cancelled",
    "refunded",
    "expired",
]


class MercadoPagoConnectResponse(BaseModel):
    authorization_url: str
    state_ttl_minutes: int = 15


class PaymentAccountStatusResponse(BaseModel):
    connected: bool
    provider: str
    status: str
    establishment_id: int
    provider_account_email_masked: str | None = None
    provider_account_id_masked: str | None = None
    external_account_email_masked: str | None = None
    external_user_id_masked: str | None = None
    last_sync_at: datetime | None = None
    connected_at: datetime | None = None
    disconnected_at: datetime | None = None
    expires_at: datetime | None = None
    token_expires_at: datetime | None = None
    checkout_hold_minutes: int = 10
    pix_enabled: bool = True
    card_enabled: bool = True
    payment_required_default: bool = False
    advance_payment_type: Literal["full", "signal"] | None = None
    advance_payment_amount: float | None = None
    default_provider: str = PAYMENT_PROVIDER_MERCADO_PAGO


class PaymentAccountSettingsUpdate(BaseModel):
    checkout_hold_minutes: int | None = Field(default=None, ge=5, le=60)
    status: str | None = None
    payment_required_default: bool | None = None
    advance_payment_type: Literal["full", "signal"] | None = None
    advance_payment_amount: float | None = Field(default=None, gt=0)
    default_provider: Literal["mercado_pago", "picpay"] | None = None


class AdminPaymentAccountUpsert(BaseModel):
    provider: str = PAYMENT_PROVIDER_MERCADO_PAGO
    account_name: str | None = None
    provider_account_id: str | None = None
    provider_account_email: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    public_key: str | None = None
    status: str = PAYMENT_ACCOUNT_STATUS_CONNECTED
    internal_notes: str | None = None
    checkout_hold_minutes: int = Field(default=10, ge=5, le=60)


class AdminPaymentAccountStatusUpdate(BaseModel):
    status: str


class AdminPaymentAuditLogItem(BaseModel):
    id: int
    action: str
    admin_sub: str | None = None
    status_before: str | None = None
    status_after: str | None = None
    error_message: str | None = None
    created_at: datetime


class AdminPaymentAccountResponse(BaseModel):
    id: int
    establishment_id: int
    provider: str
    account_name: str | None = None
    status: str
    provider_account_id_masked: str | None = None
    provider_account_email_masked: str | None = None
    checkout_hold_minutes: int = 10
    connected_at: datetime | None = None
    disconnected_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    last_error: str | None = None
    last_payment_status: str | None = None
    last_payment_at: datetime | None = None
    last_test_payment_status: str | None = None
    last_test_payment_at: datetime | None = None
    approved_payments_count: int = 0
    failed_payments_count: int = 0
    audit_logs: list[AdminPaymentAuditLogItem] = Field(default_factory=list)


class AdminPaymentEstablishmentResponse(BaseModel):
    id: int
    nome: str
    slug: str | None = None
    login: str | None = None
    provider: str | None = None
    payment_account_status: str = "not_configured"
    payment_account_name: str | None = None
    payment_account_id: int | None = None
    connected_at: datetime | None = None
    updated_at: datetime | None = None
    last_error: str | None = None


class AdminPaymentActionResponse(BaseModel):
    status: str
    detail: str
    establishment_id: int
    payment_account_id: int | None = None
    tested_at: datetime | None = None


class CheckoutResponse(BaseModel):
    checkout_url: str
    appointment_id: int
    payment_id: int
    expires_at: datetime | None = None


class PaymentDetailsResponse(BaseModel):
    id: int
    booking_id: int
    establishment_id: int | None = None
    provider: str
    amount: float
    status: PaymentStatus
    payment_method: str | None = None
    external_reference: str
    external_payment_id: str | None = None
    external_preference_id: str | None = None
    created_at: datetime
    updated_at: datetime
    paid_at: datetime | None = None
    expires_at: datetime | None = None


class BookingPaymentStatusResponse(BaseModel):
    booking_id: int
    booking_status: str
    payment_required: bool
    payment_status: PaymentStatus
    payment_amount: float | None = None
    payment_type: str | None = None
    payment_id: int | None = None


class AdminPaymentsListResponse(BaseModel):
    items: list[PaymentDetailsResponse]
