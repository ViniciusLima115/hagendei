from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Index, Integer, String, UniqueConstraint
from app.database import Base


class Conversa(Base):
    __tablename__ = "conversas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "telefone", name="ux_conversas_tenant_telefone"),
        Index("ix_conversas_tenant_ativa", "tenant_id", "ativa"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, nullable=True, index=True)
    telefone = Column(String(20), nullable=False, index=True)
    estado = Column(String(50), nullable=False, default="inicio")
    contexto = Column(JSON, nullable=True)
    ativa = Column(Boolean, nullable=False, default=True, index=True)
    criado_em = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    atualizado_em = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )
