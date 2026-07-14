from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.database import Base
from app.time_utils import utcnow_naive


class PaymentIntegration(Base):
    __tablename__ = "payment_integrations"
    __table_args__ = (
        UniqueConstraint(
            "establishment_id",
            "provider",
            "environment",
            name="ux_payment_integrations_establishment_provider_environment",
        ),
        UniqueConstraint(
            "provider",
            "environment",
            "credentials_fingerprint",
            name="ux_payment_integrations_provider_environment_fingerprint",
        ),
        Index("ix_payment_integrations_establishment_id", "establishment_id"),
        Index("ix_payment_integrations_provider", "provider"),
        Index("ix_payment_integrations_environment", "environment"),
        Index("ix_payment_integrations_status", "status"),
        Index("ix_payment_integrations_validation_status", "validation_status"),
    )

    id = Column(Integer, primary_key=True, index=True)
    establishment_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=False)
    provider = Column(String(50), nullable=False, default="mercadopago")
    environment = Column(String(20), nullable=False, default="production")
    status = Column(String(30), nullable=False, default="pending_validation")

    credentials_encrypted = Column(Text, nullable=False)
    credentials_fingerprint = Column(String(64), nullable=True)
    public_metadata_encrypted = Column(Text, nullable=True)

    account_name = Column(String(120), nullable=True)
    internal_notes = Column(Text, nullable=True)
    checkout_hold_minutes = Column(Integer, nullable=False, default=10)

    last_validated_at = Column(DateTime, nullable=True)
    validation_status = Column(String(30), nullable=False, default="not_validated")
    validation_error = Column(Text, nullable=True)

    created_by_admin_id = Column(String(120), nullable=True)
    updated_by_admin_id = Column(String(120), nullable=True)
    connected_at = Column(DateTime, nullable=True)
    disconnected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow_naive)
    updated_at = Column(DateTime, nullable=False, default=utcnow_naive, onupdate=utcnow_naive)
