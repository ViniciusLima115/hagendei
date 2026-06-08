from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.database import Base
from app.services.payments.constants import (
    PAYMENT_ACCOUNT_STATUS_DISCONNECTED,
    PAYMENT_PROVIDER_MERCADO_PAGO,
)
from app.services.payments.crypto import decrypt_sensitive_value, encrypt_sensitive_value


class PaymentAccount(Base):
    __tablename__ = "payment_accounts"
    __table_args__ = (
        UniqueConstraint(
            "establishment_id",
            "provider",
            name="ux_payment_accounts_establishment_provider",
        ),
        UniqueConstraint(
            "provider",
            "provider_account_id",
            name="ux_payment_accounts_provider_account_id",
        ),
        Index("ix_payment_accounts_establishment_id", "establishment_id"),
        Index("ix_payment_accounts_provider", "provider"),
        Index("ix_payment_accounts_status", "status"),
        Index("ix_payment_accounts_provider_account_id", "provider_account_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    establishment_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=False)
    provider = Column(String(50), nullable=False, default=PAYMENT_PROVIDER_MERCADO_PAGO)
    provider_account_id = Column(String(120), nullable=True)
    provider_account_email = Column(String(255), nullable=True)
    account_name = Column(String(120), nullable=True)
    client_id_encrypted = Column(Text, nullable=True)
    client_secret_encrypted = Column(Text, nullable=True)
    access_token_encrypted = Column(Text, nullable=False)
    refresh_token_encrypted = Column(Text, nullable=True)
    public_key = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default=PAYMENT_ACCOUNT_STATUS_DISCONNECTED)
    connected_at = Column(DateTime, nullable=True)
    disconnected_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    internal_notes = Column(Text, nullable=True)
    created_by_admin_id = Column(String(120), nullable=True)
    updated_by_admin_id = Column(String(120), nullable=True)
    last_sync_at = Column(DateTime, nullable=True)
    checkout_hold_minutes = Column(Integer, nullable=False, default=10)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def external_user_id(self) -> str | None:
        return self.provider_account_id

    @external_user_id.setter
    def external_user_id(self, value: str | None) -> None:
        self.provider_account_id = value

    @property
    def external_account_email(self) -> str | None:
        return self.provider_account_email

    @external_account_email.setter
    def external_account_email(self, value: str | None) -> None:
        self.provider_account_email = value

    @property
    def token_expires_at(self) -> datetime | None:
        return self.expires_at

    @token_expires_at.setter
    def token_expires_at(self, value: datetime | None) -> None:
        self.expires_at = value

    @property
    def public_key_encrypted(self) -> str | None:
        if not self.public_key:
            return None
        return encrypt_sensitive_value(self.public_key)

    @public_key_encrypted.setter
    def public_key_encrypted(self, value: str | None) -> None:
        self.public_key = decrypt_sensitive_value(value) if value else None
