from sqlalchemy import Column, ForeignKey, Integer, String
from app.database import Base


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    telefone = Column(String(20), unique=True, nullable=False)
    barbearia_id = Column(Integer, ForeignKey("barbearias.id"), nullable=True)
