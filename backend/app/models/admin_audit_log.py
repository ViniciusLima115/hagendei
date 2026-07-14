from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String

from app.database import Base


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"
    __table_args__ = (
        Index("ix_admin_audit_logs_admin_user_id", "admin_user_id"),
        Index("ix_admin_audit_logs_establishment_id", "establishment_id"),
        Index("ix_admin_audit_logs_action", "action"),
        Index("ix_admin_audit_logs_entity", "entity_type", "entity_id"),
        Index("ix_admin_audit_logs_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    admin_user_id = Column(String(120), nullable=False)
    establishment_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True)
    action = Column(String(80), nullable=False)
    entity_type = Column(String(80), nullable=False)
    entity_id = Column(String(120), nullable=True)
    ip_address = Column(String(80), nullable=True)
    user_agent = Column(String(500), nullable=True)
    audit_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
