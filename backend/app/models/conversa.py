from sqlalchemy import JSON, Column, Integer, String
from app.database import Base


class Conversa(Base):
    __tablename__ = "conversas"

    id = Column(Integer, primary_key=True, index=True)
    telefone = Column(String(20), unique=True, nullable=False, index=True)
    estado = Column(String(50), nullable=False, default="inicio")
    contexto = Column(JSON, nullable=True)
