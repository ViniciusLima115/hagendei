from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PaymentStatus = Literal[
    "not_required",
    "pending",
    "approved",
    "rejected",
    "cancelled",
    "refunded",
    "charged_back",
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
    environment: str | None = None
    external_account_email_masked: str | None = None
    external_user_id_masked: str | None = None
    last_sync_at: datetime | None = None
    token_expires_at: datetime | None = None
    checkout_hold_minutes: int = 10
    validation_status: str | None = None
    validation_error: str | None = None


class PaymentAccountSettingsUpdate(BaseModel):
    checkout_hold_minutes: int | None = None
    status: str | None = None


class AdminPaymentAccountUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    provider: str = Field(default="mercadopago", max_length=50)
    environment: Literal["sandbox", "production"] = "production"
    account_name: str | None = Field(default=None, max_length=120)
    client_id: str | None = Field(default=None, min_length=4, max_length=180)
    client_secret: str | None = Field(default=None, min_length=8, max_length=700)
    access_token: str | None = Field(default=None, min_length=8, max_length=700)
    public_key: str | None = Field(default=None, min_length=8, max_length=300)
    webhook_secret: str | None = Field(default=None, min_length=8, max_length=700)
    status: Literal["active", "inactive", "error", "pending_validation", "disconnected"] = "active"
    internal_notes: str | None = Field(default=None, max_length=1000)
    checkout_hold_minutes: int = Field(default=10, ge=5, le=60)

    @field_validator("account_name", "client_id", "client_secret", "access_token", "public_key", "webhook_secret", "internal_notes", mode="before")
    @classmethod
    def _blank_strings_to_none(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value


class AdminPaymentAccountStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["active", "inactive", "error", "revoked", "disconnected", "pending_validation"]
    environment: Literal["sandbox", "production"] = "production"


class AdminPaymentIntegrationResponse(BaseModel):
    provider: str
    environment: str
    status: str
    validation_status: str
    last_validated_at: datetime | None = None
    connected_at: datetime | None = None
    updated_at: datetime
    updated_by: str | None = None
    public_key_masked: str | None = None
    access_token_masked: str | None = None
    webhook_secret_masked: str | None = None
    has_client_id: bool = False
    has_client_secret: bool = False


class AdminPaymentIntegrationUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    environment: Literal["sandbox", "production"] = "production"
    public_key: str | None = Field(default=None, min_length=8, max_length=300)
    access_token: str | None = Field(default=None, min_length=8, max_length=700)
    client_id: str | None = Field(default=None, min_length=4, max_length=180)
    client_secret: str | None = Field(default=None, min_length=8, max_length=700)
    webhook_secret: str | None = Field(default=None, min_length=8, max_length=700)
    notes: str | None = Field(default=None, max_length=1000)
    status: Literal["active", "inactive", "error", "pending_validation", "disconnected"] = "active"

    @field_validator("public_key", "access_token", "client_id", "client_secret", "webhook_secret", "notes", mode="before")
    @classmethod
    def _blank_strings_to_none(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value


class AdminPaymentIntegrationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    environment: Literal["sandbox", "production"] = "production"
    public_key: str | None = Field(default=None, min_length=8, max_length=300)
    access_token: str | None = Field(default=None, min_length=8, max_length=700)
    client_id: str | None = Field(default=None, min_length=4, max_length=180)
    client_secret: str | None = Field(default=None, min_length=8, max_length=700)
    webhook_secret: str | None = Field(default=None, min_length=8, max_length=700)
    notes: str | None = Field(default=None, max_length=1000)
    status: Literal["active", "inactive", "error", "pending_validation", "disconnected"] | None = None
    clear_public_key: bool = False
    clear_client_id: bool = False
    clear_client_secret: bool = False
    clear_webhook_secret: bool = False
    clear_notes: bool = False

    @field_validator("public_key", "access_token", "client_id", "client_secret", "webhook_secret", "notes", mode="before")
    @classmethod
    def _blank_strings_to_none(cls, value):
        if value is None:
            return None
        if isinstance(value, str):
            cleaned = value.strip()
            return cleaned or None
        return value


class AdminPaymentIntegrationDisableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    environment: Literal["sandbox", "production"] = "production"
    status: Literal["inactive", "disconnected"] = "inactive"


class AdminPaymentIntegrationValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    environment: Literal["sandbox", "production"] = "production"


class AdminPaymentIntegrationValidateResponse(BaseModel):
    valid: bool
    validation_status: Literal["valid", "invalid", "error"]
    message: str
    last_validated_at: datetime | None = None


class AdminPaymentIntegrationTestCheckoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    environment: Literal["sandbox", "production"] = "sandbox"
    confirm_production: bool = False


class AdminPaymentIntegrationTestCheckoutResponse(BaseModel):
    provider: str
    environment: str
    preference_id: str
    checkout_url: str
    status: Literal["created"]


class AdminPaymentAccountResponse(BaseModel):
    id: int
    establishment_id: int
    provider: str
    environment: str = "production"
    account_name: str | None = None
    status: str
    client_id_masked: str | None = None
    client_secret_masked: str | None = None
    access_token_masked: str | None = None
    webhook_secret_masked: str | None = None
    public_key_masked: str | None = None
    internal_notes: str | None = None
    checkout_hold_minutes: int = 10
    validation_status: str = "not_validated"
    validation_error: str | None = None
    last_validated_at: datetime | None = None
    connected_at: datetime | None = None
    disconnected_at: datetime | None = None
    created_by_admin_id: str | None = None
    updated_by_admin_id: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminPaymentEstablishmentResponse(BaseModel):
    id: int
    nome: str
    slug: str | None = None
    login: str | None = None
    payment_account_status: str = "not_configured"
    payment_account_name: str | None = None
    payment_account_id: int | None = None
    payment_environment: str | None = None
    payment_validation_status: str | None = None


class CheckoutResponse(BaseModel):
    payment_id: int
    booking_id: int
    external_reference: str
    preference_id: str
    checkout_url: str
    amount: float
    payment_status: PaymentStatus
    booking_status: str
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
