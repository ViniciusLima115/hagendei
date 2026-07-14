from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, Text

from app.database import Base


class PaymentAdminAuditLog(Base):
    __tablename__ = "payment_admin_audit_logs"
    __table_args__ = (
        Index("ix_payment_admin_audit_establishment_id", "establishment_id"),
        Index("ix_payment_admin_audit_payment_account_id", "payment_account_id"),
        Index("ix_payment_admin_audit_action", "action"),
        Index("ix_payment_admin_audit_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    establishment_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=False)
    payment_account_id = Column(Integer, ForeignKey("payment_accounts.id"), nullable=True)
    provider = Column(String(50), nullable=False, default="mercado_pago")
    admin_sub = Column(String(120), nullable=True)
    action = Column(String(80), nullable=False)
    status_before = Column(String(30), nullable=True)
    status_after = Column(String(30), nullable=True)
    details = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
