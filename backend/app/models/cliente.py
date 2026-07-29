from datetime import datetime

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from app.database import Base
from app.time_utils import utcnow_naive


class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = (
        Index("ix_clientes_email", "email"),
        UniqueConstraint(
            "estabelecimento_id",
            "telefone",
            name="ux_clientes_estabelecimento_telefone",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    telefone = Column(String(20), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    etapa_atual = Column(String(100), nullable=False, default="inicio")
    contexto = Column(JSON, nullable=True)
    data_criacao = Column(DateTime, nullable=False, default=utcnow_naive)
    estabelecimento_id = Column(Integer, ForeignKey("estabelecimentos.id"), nullable=True)
